"""Public-facing pages and routes: setup wizard, theme assets, index,
robots.txt, and the public config endpoints."""
import html
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from apps.base.config import initialize_system, is_runtime_initialized
from apps.base.setup_wizard import (
    SETUP_TEXT,
    build_public_config,
    build_public_meta,
    build_setup_page,
    build_setup_success_page,
    parse_setup_options,
    read_setup_payload,
    setup_locale,
    setup_response,
)
from core.error_i18n import localize_error, preferred_locale
from core.response import APIResponse
from core.settings import BASE_DIR, settings
from core.version import APP_VERSION

router = APIRouter()


@router.get("/setup", include_in_schema=False)
@router.get("/setup/", include_in_schema=False)
async def setup_page(request: Request):
    if is_runtime_initialized():
        return RedirectResponse(url="/", status_code=303)
    return setup_response(build_setup_page(locale=setup_locale(request)))


@router.post("/setup", include_in_schema=False)
@router.post("/setup/", include_in_schema=False)
async def setup_submit(request: Request):
    if is_runtime_initialized():
        return RedirectResponse(url="/", status_code=303)

    data = await read_setup_payload(request)
    locale = setup_locale(request, data.get("lang"))
    admin_password = str(data.get("admin_password") or "")
    confirm_password = str(data.get("confirm_password") or "")
    site_name = str(data.get("site_name") or "")

    if admin_password != confirm_password:
        return setup_response(build_setup_page(SETUP_TEXT[locale]["mismatch"], data, locale=locale), 400)

    try:
        setup_options = parse_setup_options(data)
        await initialize_system(
            admin_password=admin_password,
            site_name=site_name,
            setup_options=setup_options,
        )
    except ValueError as exc:
        detail = localize_error(str(exc), locale, 400)
        return setup_response(build_setup_page(detail, data, locale=locale), 400)

    if "application/json" in request.headers.get("accept", ""):
        return APIResponse(detail={"ok": True, "admin": "/admin/dashboard"})
    return setup_response(build_setup_success_page(locale))

def resolve_theme_root():
    return (BASE_DIR / "themes" / "2024").resolve()


def resolve_theme_file(*parts: str):
    theme_root = resolve_theme_root()
    file_path = theme_root.joinpath(*parts).resolve()
    # 防止通过 /assets/../ 读取主题目录外的文件。
    try:
        file_path.relative_to(theme_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="资源不存在")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="资源不存在")
    return file_path


# Vite 产物带内容指纹（如 index-BX2s1QqP.js），内容变化时文件名必然变化，
# 可以安全地长缓存；public/ 下的未哈希资源原地升级时名字不变，只给短缓存，
# 过期后靠 FileResponse 自带的 ETag/Last-Modified 走 304。
_HASHED_ASSET_RE = re.compile(
    r"-[A-Za-z0-9_-]{8,}\.(?:js|mjs|css|map|woff2?|ttf|otf|eot|svg|png|jpe?g|gif|webp|avif|ico)$",
    re.IGNORECASE,
)
_IMMUTABLE_ASSET_CACHE = "public, max-age=31536000, immutable"
_DEFAULT_ASSET_CACHE = "public, max-age=86400"


def _asset_cache_control(asset_path: str) -> str:
    if _HASHED_ASSET_RE.search(asset_path):
        return _IMMUTABLE_ASSET_CACHE
    return _DEFAULT_ASSET_CACHE


@lru_cache(maxsize=8)
def _render_index_html(
    template_path: str,
    inode: int,
    mtime_ns: int,
    size: int,
    title: str,
    description: str,
    keywords: str,
    opacity: str,
    background: str,
) -> str:
    """Render index.html once per (theme file version, site config) pair.

    The stat fields keep the cache honest when a theme is replaced in place;
    config values are part of the key so admin edits are visible immediately
    without any cross-module invalidation hook.
    """
    return (
        Path(template_path)
        .read_text(encoding="utf-8")
        .replace("{{title}}", html.escape(title))
        .replace("{{description}}", html.escape(description))
        .replace("{{keywords}}", html.escape(keywords))
        .replace("{{opacity}}", html.escape(opacity))
        .replace("{{background}}", html.escape(background))
    )


@router.get("/assets/{asset_path:path}", include_in_schema=False)
async def theme_asset(asset_path: str):
    return FileResponse(
        resolve_theme_file("assets", asset_path),
        headers={"Cache-Control": _asset_cache_control(asset_path)},
    )


async def not_found_handler(request, exc=None):
    """区分"浏览器导航到未知路径"与"API 处理器抛出的 404"。

    Starlette 的 status-code handler 优先于 HTTPException 类 handler，
    直接注册 index 会让全应用所有 HTTPException(404) 变成 200 HTML 页
    （负路径测试抓到的存量 bug）。浏览器（Accept 含 text/html）仍拿到
    主题首页做 SPA 兜底；API 客户端拿到 JSON 404。
    """
    locale = preferred_locale(request) if request is not None else "zh-CN"
    original_detail = getattr(exc, "detail", "")
    detail = original_detail if locale != "zh-CN" and isinstance(original_detail, str) else "资源不存在"
    message = "Not Found" if locale == "zh-CN" else localize_error("资源不存在", locale, 404)
    json_404 = JSONResponse(
        status_code=404,
        content={"code": 404, "message": message, "detail": localize_error(detail, locale, 404)},
        headers={"Vary": "Accept-Language"},
    )
    if request is not None and not request.url.path.startswith(("/api/", "/admin/", "/share", "/chunk", "/presign", "/mcp")) and request.method in {"GET", "HEAD"} and "text/html" in (
        request.headers.get("accept", "")
    ):
        try:
            return await index(request, exc)
        except HTTPException:
            return json_404
    return json_404


@router.get("/")
async def index(request=None, exc=None):
    # Site config is admin input (and during the setup window anyone can claim it);
    # always escape before injecting into the theme template to prevent stored XSS
    # (mirrors the setup page).
    template_path = resolve_theme_file("index.html")
    try:
        stat_result = template_path.stat()
    except OSError:
        # resolve_theme_file 与 stat 之间文件被删除/替换时仍按 404 处理，
        # 不能退回缓存内容。
        raise HTTPException(status_code=404, detail="资源不存在")
    content = _render_index_html(
        str(template_path),
        stat_result.st_ino,
        stat_result.st_mtime_ns,
        stat_result.st_size,
        str(settings.name),
        str(settings.description),
        "",
        "0.9",
        "",
    )
    return HTMLResponse(
        content=content,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )

@router.get("/robots.txt")
async def robots():
    return HTMLResponse(content="User-agent: *\nDisallow: /", media_type="text/plain")


@router.post("/")
async def get_config():
    return APIResponse(detail=build_public_config())


@router.get("/api/v1/config")
async def get_public_config():
    return APIResponse(
        detail={
            "config": build_public_config(),
            "meta": build_public_meta(),
        }
    )


@router.get("/health")
async def health_check():
    return APIResponse(
        detail={
            "status": "ok",
            "version": APP_VERSION,
            "storage": "local",
            "theme": "themes/2024",
        }
    )
