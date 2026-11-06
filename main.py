# @Time    : 2023/8/9 23:23
# @Author  : Lan
# @File    : main.py
# @Software: PyCharm
import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
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
from apps.base.pages import not_found_handler, router as pages_router
from apps.base.setup_wizard import build_setup_page, is_setup_path, setup_response, wants_html_response
from apps.base.tasks import (
    clean_expired_presign_sessions,
    clean_incomplete_uploads,
    delete_expire_files,
)
from apps.relay.auth import router as relay_auth
from apps.relay.uploads import router as relay_uploads
from apps.relay.files import router as relay_files
from apps.relay.cleanup import cleanup_loop
from core.database import db_startup_lock, init_db
from core.errors import StorageError
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
    task = asyncio.create_task(delete_expire_files())
    chunk_cleanup_task = asyncio.create_task(clean_incomplete_uploads())
    presign_cleanup_task = asyncio.create_task(clean_expired_presign_sessions())
    logger.info("应用初始化完成")

    try:
        yield
    finally:
        relay_cleanup_task.cancel()
        task.cancel()
        chunk_cleanup_task.cancel()
        presign_cleanup_task.cancel()
        await asyncio.gather(
            relay_cleanup_task,
            task,
            chunk_cleanup_task,
            presign_cleanup_task,
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


@app.exception_handler(StorageError)
async def storage_error_handler(request, exc: StorageError):
    # Render StorageError exactly like FastAPI renders HTTPException so the
    # framework-free storage layer keeps identical client-visible responses.
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.middleware("http")
async def refresh_settings_middleware(request, call_next):
    await refresh_settings()
    path = request.url.path
    if any(path == prefix or path.startswith(prefix + "/") for prefix in (
        "/share", "/chunk", "/presign", "/api/presign", "/mcp"
    )):
        return JSONResponse(status_code=410, content={"detail": "旧公开接口已关闭，请使用 FileRelay 配对首页"})
    if not is_runtime_initialized() and not is_setup_path(request.url.path):
        if wants_html_response(request):
            return setup_response(build_setup_page())
        return JSONResponse(
            status_code=428,
            content={
                "code": 428,
                "message": "系统未初始化，请先完成初始化",
                "msg": "系统未初始化，请先完成初始化",
                "detail": {"setup": "/setup"},
            },
        )
    response = await call_next(request)
    if path.startswith("/api/relay"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie"
    return response

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
