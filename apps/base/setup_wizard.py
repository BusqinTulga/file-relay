"""Minimal first-run setup and public metadata for FileRelay."""
import html
from urllib.parse import parse_qs
from fastapi import Request
from fastapi.responses import HTMLResponse
from apps.relay.policy import policy, validate_limits
from core.settings import settings
from core.version import APP_VERSION


def build_public_config():
    return {key: getattr(settings, key) for key in
            ("name", "description", "notify_title", "notify_content", "show_admin_addr")} | policy()


def build_public_meta():
    return {"version": APP_VERSION}


def parse_setup_options(data):
    values = {key: data[key] for key in ("upload_size", "storage_limit", "open_upload") if key in data}
    validate_limits(values)
    return values


def build_setup_page(error="", form=None):
    form = form or {}
    name = html.escape(str(form.get("site_name") or "FileRelay／文件接力"), quote=True)
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>初始化 FileRelay</title>
<style>body{{font:16px system-ui;background:#f4f4f5;color:#18181b;margin:0;padding:24px}}
main{{max-width:440px;margin:8vh auto;background:white;padding:32px;border-radius:20px}}
label{{display:block;margin:20px 0}}input,button{{box-sizing:border-box;width:100%;padding:12px;margin-top:8px;border:1px solid #ddd;border-radius:8px}}
button{{background:#18181b;color:white;cursor:pointer}}p{{line-height:1.7}}.error{{color:#b91c1c}}</style>
<main><h1>初始化 FileRelay</h1><p>设置管理员密码后即可开始文件接力。</p>
<p class="error" role="alert">{html.escape(str(error))}</p><form method="post" action="/setup">
<label>站点名称<input name="site_name" maxlength="80" value="{name}" required></label>
<label>管理员密码<input name="admin_password" type="password" minlength="8" maxlength="255" autocomplete="new-password" required></label>
<label>确认密码<input name="confirm_password" type="password" minlength="8" maxlength="255" autocomplete="new-password" required></label>
<p>默认单文件上限 1 GB，全站 500 GB，可在后台调低。文件最多保留 24 小时，首次完整下载后保留 10 分钟。</p>
<button>完成初始化</button></form></main></html>'''


def build_setup_success_page():
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>初始化完成</title><h1>初始化完成</h1><p><a href="/">开始文件接力</a> · <a href="/#/admin">进入管理后台</a></p></html>'


def setup_response(content, status_code=200):
    return HTMLResponse(content, status_code=status_code, headers={"Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})


def is_setup_path(path):
    return path.rstrip('/') == '/setup'


def wants_html_response(request: Request):
    return request.method in {'GET', 'HEAD'} and any(
        value in request.headers.get('accept', '*/*') for value in ('text/html', '*/*'))


async def read_setup_payload(request: Request):
    if 'application/json' in request.headers.get('content-type', ''):
        data = await request.json()
        return data if isinstance(data, dict) else {}
    return {key: values[-1] for key, values in parse_qs((await request.body()).decode()).items()}
