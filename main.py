# @Time    : 2023/8/9 23:23
# @Author  : Lan
# @File    : main.py
# @Software: PyCharm
import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from tortoise import Tortoise
from tortoise.contrib.fastapi import tortoise_exception_handlers

from apps.admin.views import admin_api
from apps.base.config import (
    ensure_security_settings,
    ensure_settings_row,
    is_runtime_initialized,
    refresh_settings,
)
from apps.base.models import KeyValue
from apps.base.pages import (
    index as render_index,
    not_found_handler,
    router as pages_router,
)
from apps.base.setup_wizard import build_setup_page, is_setup_path, setup_response, wants_html_response
from apps.relay.auth import router as relay_auth
from apps.relay.uploads import router as relay_uploads
from apps.relay.files import router as relay_files
from apps.relay.cleanup import cleanup_loop
from core.database import db_startup_lock, init_db
from core.logger import get_log_level_name, is_access_log_enabled, logger
from core.settings import settings
from core.version import APP_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.server_workers != 1 or int(os.getenv("WORKERS", "1")) != 1:
        raise RuntimeError("FileRelay requires one worker")
    logger.info("正在初始化应用...")
    # 初始化数据库
    await init_db()

    # 加载配置（多进程下串行化启动写操作）
    async with db_startup_lock():
        await load_config()
    # 启动后台任务
    relay_cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info("应用初始化完成")

    try:
        yield
    finally:
        relay_cleanup_task.cancel()
        await asyncio.gather(
            relay_cleanup_task,
            return_exceptions=True,
        )
        await Tortoise.close_connections()
        logger.info("应用已关闭")


async def load_config():
    await ensure_settings_row()
    await KeyValue.update_or_create(
        key="sys_start", defaults={"value": int(time.time() * 1000)}
    )
    # refresh_settings already syncs every rate limiter (error/metadata/upload/login)
    # via _sync_ip_limits; do not hand-sync a subset here — that once drifted by
    # missing the metadata limiter.
    await refresh_settings(force=True)
    await ensure_security_settings()

    # Rate limiters keep per-process state (apps.base.dependencies.IPRateLimit).
    # With multiple workers each process counts independently, so the effective
    # threshold scales with the worker count and resets on restart.
    if settings.server_workers > 1:
        logger.warning(
            "server_workers=%s：进程内限流在多 worker 下各自独立，阈值将按 worker 数放大；"
            "如需完整限流请使用单 worker（默认）或改造为共享存储限流",
            settings.server_workers,
        )


# Tortoise 的 ORM 异常映射（DoesNotExist → 404、IntegrityError → 422）。
# 只注册处理器；连接初始化统一由 lifespan 里的 init_db() 负责，
# 避免 register_tortoise 合并 lifespan 造成的双重初始化。
app = FastAPI(
    lifespan=lifespan,
    version=APP_VERSION,
    exception_handlers=tortoise_exception_handlers(),
)

# Direct browser visits to these Vue routes need the SPA shell. The dashboard
# path is also a JSON API endpoint, so only HTML navigations are intercepted.
FRONTEND_HISTORY_PATHS = frozenset({
    "/send",
    "/login",
    "/admin",
    "/admin/dashboard",
    "/admin/files",
    "/admin/local",
    "/admin/mcp",
    "/admin/settings",
})


class RequestMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await refresh_settings()
        request = Request(scope)
        path = request.url.path
        is_history_path = path.rstrip("/") in FRONTEND_HISTORY_PATHS
        is_frontend_navigation = (
            request.method == "GET"
            and is_history_path
            and "text/html" in request.headers.get("accept", "")
        )
        if any(path == prefix or path.startswith(prefix + "/") for prefix in (
            "/share", "/chunk", "/presign", "/api/presign", "/mcp"
        )):
            response = JSONResponse(status_code=410, content={"detail": "旧公开接口已关闭，请使用 FileRelay 配对首页"})
            await response(scope, receive, send)
            return
        if not is_runtime_initialized() and not is_setup_path(path):
            if is_frontend_navigation or (
                not path.startswith(("/api/", "/admin/")) and wants_html_response(request)
            ):
                response = setup_response(build_setup_page())
            else:
                response = JSONResponse(
                    status_code=428,
                    headers={"Cache-Control": "no-store"},
                    content={
                        "code": 428,
                        "message": "系统未初始化，请先完成初始化",
                        "msg": "系统未初始化，请先完成初始化",
                        "detail": {"setup": "/setup"},
                    },
                )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if is_history_path:
                    headers.add_vary_header("Accept")
                if path.startswith("/api/relay"):
                    headers["Cache-Control"] = "no-store"
                    headers.add_vary_header("Cookie")
            await send(message)

        if is_frontend_navigation:
            try:
                response = await render_index(request)
            except HTTPException as exc:
                response = await http_exception_handler(request, exc)
            await response(scope, receive, send_with_headers)
            return

        # Pass body events directly to the server so the download response can
        # distinguish a completed send from a handoff to a middleware buffer.
        use_response_headers = is_history_path or path.startswith("/api/relay")
        await self.app(scope, receive, send_with_headers if use_response_headers else send)


app.add_middleware(RequestMiddleware)

# Old anonymous protocols are intentionally not registered.
app.include_router(relay_auth)
app.include_router(relay_uploads)
app.include_router(relay_files)
app.include_router(admin_api)
app.include_router(pages_router)

# 404 时返回主题首页（index 兼任 exception handler 与 GET / 路由）
app.add_exception_handler(404, not_found_handler)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        workers=settings.server_workers,
        log_level=get_log_level_name(),
        access_log=is_access_log_enabled(),
    )
