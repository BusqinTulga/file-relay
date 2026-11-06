"""Setup wizard: form parsing rules and the two admin-facing HTML pages.

Pure presentation/logic — no router here; routes live in apps.base.pages.
"""
import html
from urllib.parse import parse_qs

from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse

from core.settings import DEFAULT_CONFIG, settings
from core.version import APP_VERSION


FILE_SIZE_UNITS = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}
SAVE_TIME_UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
EXPIRE_STYLE_OPTIONS = [
    ("day", "按天"),
    ("hour", "按小时"),
    ("minute", "按分钟"),
    ("forever", "永久"),
    ("count", "按取件次数"),
]


def normalize_public_flag(value) -> int:
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "on", "yes"})
    return int(bool(value))


def build_public_config() -> dict:
    return {
        "name": settings.name,
        "description": settings.description,
        "explain": settings.page_explain,
        "upload_size": settings.upload_size,
        "allowed_file_types": settings.allowed_file_types,
        "expire_style": settings.expire_style,
        "enable_chunk": settings.enable_chunk,
        "open_upload": settings.open_upload,
        "notify_title": settings.notify_title,
        "notify_content": settings.notify_content,
        "show_admin_address": normalize_public_flag(settings.show_admin_addr),
        "max_save_seconds": settings.max_save_seconds,
    }


def build_public_meta() -> dict:
    return {
        "version": APP_VERSION,
        "api": {
            "legacy_config": "/",
            "public_config": "/api/v1/config",
            "health": "/health",
        },
        "features": {
            "chunk_upload": bool(settings.enable_chunk),
            "guest_upload": bool(settings.open_upload),
            "admin_address_visible": bool(normalize_public_flag(settings.show_admin_addr)),
            "expiration_modes": settings.expire_style,
        },
        "limits": {
            "upload_size": settings.upload_size,
            "allowed_file_types": settings.allowed_file_types,
            "max_save_seconds": settings.max_save_seconds,
            "upload_window_minutes": settings.upload_minute,
            "upload_window_count": settings.upload_count,
        },
    }





def get_form_value(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key, default)
    if isinstance(value, list):
        value = value[-1] if value else default
    return str(value if value is not None else default)


def get_form_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return []


def normalize_bool_field(data: dict, key: str, default: bool) -> bool:
    if key not in data:
        return default
    return get_form_value(data, key).lower() in {"1", "true", "on", "yes"}


def parse_int_field(
    data: dict[str, Any],
    key: str,
    default: int,
    label: str,
    min_value: int = 0,
    max_value: int | None = None,
) -> int:
    raw_value = get_form_value(data, key, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError:
        raise ValueError(f"{label} 必须是整数")
    if value < min_value:
        raise ValueError(f"{label} 不能小于 {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{label} 不能大于 {max_value}")
    return value


def parse_allowed_file_types(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or ["*"]


def parse_setup_options(data: dict) -> dict:
    upload_size_unit = get_form_value(data, "upload_size_unit", "MB").upper()
    if upload_size_unit not in FILE_SIZE_UNITS:
        raise ValueError("文件大小单位不正确")
    upload_size_value = parse_int_field(
        data, "upload_size_value", 10, "文件大小限制", min_value=1
    )

    save_time_unit = get_form_value(data, "save_time_unit", "day")
    if save_time_unit not in SAVE_TIME_UNITS:
        raise ValueError("最长保存时间单位不正确")
    save_time_value = parse_int_field(
        data, "save_time_value", 0, "最长保存时间", min_value=0
    )

    expire_styles = get_form_list(data, "expire_style")
    valid_expire_styles = {style for style, _label in EXPIRE_STYLE_OPTIONS}
    expire_styles = [style for style in expire_styles if style in valid_expire_styles]
    if not expire_styles:
        raise ValueError("至少需要选择一种过期方式")

    code_generate_type = get_form_value(
        data, "code_generate_type", DEFAULT_CONFIG["code_generate_type"]
    )
    if code_generate_type not in {"number", "secret"}:
        raise ValueError("提取码类型不正确")

    return {
        "allowed_file_types": parse_allowed_file_types(
            get_form_value(data, "allowed_file_types", "*")
        ),
        "code_generate_type": code_generate_type,
        "enable_chunk": int(normalize_bool_field(data, "enable_chunk", False)),
        "error_count": parse_int_field(
            data, "error_count", DEFAULT_CONFIG["error_count"], "取件错误次数限制", 1
        ),
        "error_minute": parse_int_field(
            data, "error_minute", DEFAULT_CONFIG["error_minute"], "取件错误检测窗口", 1
        ),
        "login_count": parse_int_field(
            data, "login_count", DEFAULT_CONFIG["login_count"], "登录失败次数限制", 1
        ),
        "login_minute": parse_int_field(
            data, "login_minute", DEFAULT_CONFIG["login_minute"], "登录失败检测窗口", 1
        ),
        "expire_style": expire_styles,
        "max_save_seconds": save_time_value * SAVE_TIME_UNITS[save_time_unit],
        "open_upload": int(normalize_bool_field(data, "open_upload", True)),
        "upload_count": parse_int_field(
            data, "upload_count", DEFAULT_CONFIG["upload_count"], "上传次数限制", 1
        ),
        "upload_minute": parse_int_field(
            data, "upload_minute", DEFAULT_CONFIG["upload_minute"], "上传检测窗口", 1
        ),
        "upload_size": upload_size_value * FILE_SIZE_UNITS[upload_size_unit],
    }

def build_expire_style_inputs(selected_styles: list[str]) -> str:
    inputs = []
    selected = set(selected_styles)
    for style, label in EXPIRE_STYLE_OPTIONS:
        checked = " checked" if style in selected else ""
        inputs.append(
            f'<label class="check"><input type="checkbox" name="expire_style" value="{style}"{checked}> {label}</label>'
        )
    return "\n        ".join(inputs)

def build_setup_page(error: str = "", form: dict | None = None) -> str:
    form = form or {}
    message = html.escape(error)
    name = html.escape(get_form_value(form, "site_name", "FileRelay／文件接力"), quote=True)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>初始化 FileRelay</title>
<style>body{{font:16px system-ui;background:#f7f8fc;color:#26334d;margin:0;padding:6vh 20px}}
main{{max-width:460px;margin:auto;background:white;border:1px solid #e2e8f0;border-radius:20px;padding:32px}}
h1{{font-size:24px}}p{{line-height:1.7;color:#64748b}}label{{display:block;margin-top:20px}}
input,button{{box-sizing:border-box;width:100%;padding:13px;border:1px solid #cbd5e1;border-radius:10px;margin-top:8px;font:inherit}}
button{{background:#6366f1;color:white;margin-top:28px;border:0}}.error{{color:#dc2626}}</style></head>
<body><main><h1>FileRelay／文件接力</h1><p>首次使用，请设置独立的管理员密码。设备配对在首页完成。</p>
<p class="error" role="alert">{message}</p><form action="/setup" method="post">
<label for="site_name">站点名称</label><input id="site_name" name="site_name" maxlength="80" value="{name}">
<label for="admin_password">管理员密码（至少 8 位）</label><input id="admin_password" name="admin_password" type="password" minlength="8" required autocomplete="new-password">
<label for="confirm_password">再次输入密码</label><input id="confirm_password" name="confirm_password" type="password" minlength="8" required autocomplete="new-password">
<p>单文件上限 1 GB，全站容量 500 GB。文件最多保留 24 小时，首次完整发送后保留 10 分钟供重试。</p>
<button type="submit">完成初始化</button></form></main></body></html>'''


def build_setup_success_page() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="2;url=/#/admin">
  <title>初始化完成</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f8fb;
      color: #172033;
    }
    main {
      width: min(100%, 420px);
      padding: 28px;
      border: 1px solid #d9e1ec;
      border-radius: 8px;
      background: #fff;
      text-align: center;
      box-shadow: 0 18px 50px rgba(23, 32, 51, .08);
    }
    h1 { margin: 0 0 10px; font-size: 24px; letter-spacing: 0; }
    p { margin: 0 0 22px; color: #60708a; line-height: 1.65; }
    a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 0 18px;
      border-radius: 6px;
      background: #2563eb;
      color: white;
      text-decoration: none;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <main>
    <h1>初始化完成</h1>
    <p>管理员密码已设置，请使用刚才的密码登录后台。</p>
    <a href="/">开始文件接力</a>
  </main>
</body>
</html>"""

def setup_response(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=content,
        status_code=status_code,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


def is_setup_path(path: str) -> bool:
    return path.rstrip("/") == "/setup"


def wants_html_response(request: Request) -> bool:
    if request.method not in {"GET", "HEAD"}:
        return False
    accept = request.headers.get("accept", "")
    return not accept or "text/html" in accept or "*/*" in accept


async def read_setup_payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}

    body = (await request.body()).decode("utf-8")
    return {
        key: values if len(values) > 1 else values[-1]
        for key, values in parse_qs(body).items()
    }
