"""Minimal first-run setup and public metadata for FileRelay."""
import html
from urllib.parse import parse_qs
from fastapi import Request
from fastapi.responses import HTMLResponse
from apps.relay.policy import format_size, policy, validate_limits
from core.error_i18n import preferred_locale
from core.settings import DEFAULT_CONFIG, settings
from core.version import APP_VERSION


FAVICON_PATH = "/assets/logo_small.png"
SETUP_LANGUAGES = {"zh-CN": "中文", "en-US": "English", "ja-JP": "日本語"}
SETUP_TEXT = {
    "zh-CN": {
        "title": "初始化文件快传",
        "intro": "设置管理员密码后即可使用文件快传。",
        "site": "站点名称",
        "name": DEFAULT_CONFIG["name"],
        "password": "管理员密码",
        "confirm": "确认密码",
        "limits": "当前单文件上限 {file}，全站 {site}，可在后台调整。文件最多保留 24 小时，首次完整下载后保留 10 分钟。",
        "submit": "完成初始化",
        "complete": "初始化完成",
        "home": "开始使用文件快传",
        "admin": "进入管理后台",
        "mismatch": "两次输入的管理员密码不一致",
    },
    "en-US": {
        "title": "Set up FileRelay",
        "intro": "Set an administrator password to start transferring files.",
        "site": "Site name",
        "name": "FileRelay",
        "password": "Administrator password",
        "confirm": "Confirm password",
        "limits": (
            "The current limits are {file} per file and {site} in total. You can change them in the admin console. "
            "Files are kept for up to 24 hours, with 10 minutes to retry after the first complete download."
        ),
        "submit": "Complete setup",
        "complete": "Setup complete",
        "home": "Start transferring files",
        "admin": "Open the admin console",
        "mismatch": "The administrator passwords do not match.",
    },
    "ja-JP": {
        "title": "FileRelay の初期設定",
        "intro": "管理者パスワードを設定すると、ファイルの転送を開始できます。",
        "site": "サイト名",
        "name": "FileRelay／ファイルリレー",
        "password": "管理者パスワード",
        "confirm": "パスワードを確認",
        "limits": (
            "現在の上限は1ファイルあたり {file}、サイト全体で {site} です。管理画面で変更できます。"
            "ファイルは最長24時間、初回のダウンロード完了後は10分間保持されます。"
        ),
        "submit": "初期設定を完了",
        "complete": "初期設定が完了しました",
        "home": "ファイルの転送を開始",
        "admin": "管理画面を開く",
        "mismatch": "管理者パスワードが一致しません。",
    },
}


def setup_locale(request: Request, submitted=None):
    if isinstance(submitted, str) and submitted in SETUP_LANGUAGES:
        return submitted
    return preferred_locale(request)


def build_public_config():
    return {key: getattr(settings, key) for key in
            ("name", "description", "show_admin_addr")} | policy()


def build_public_meta():
    return {"version": APP_VERSION}


def parse_setup_options(data):
    values = {key: data[key] for key in ("upload_size", "storage_limit", "open_upload") if key in data}
    validate_limits(values)
    return values


def build_setup_page(error="", form=None, *, locale="zh-CN"):
    form = form or {}
    text = SETUP_TEXT[locale]
    name = html.escape(str(form.get("site_name") or ""), quote=True)
    limits = text["limits"].format(file=format_size(settings.upload_size), site=format_size(settings.storage_limit))
    languages = " · ".join(
        f'<a href="/setup?lang={code}" lang="{code}"{" aria-current=true" if code == locale else ""}>{label}</a>'
        for code, label in SETUP_LANGUAGES.items()
    )
    return f'''<!doctype html><html lang="{locale}"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{text["title"]}</title>
<link rel="icon" type="image/png" href="{FAVICON_PATH}">
<style>body{{font:16px system-ui;background:#f4f4f5;color:#18181b;margin:0;padding:24px}}
main{{max-width:440px;margin:8vh auto;background:white;padding:32px;border-radius:20px}}
.setup-field{{margin:20px 0}}input,button{{box-sizing:border-box;width:100%;padding:12px;margin-top:8px;border:1px solid #ddd;border-radius:8px}}
button{{background:#18181b;color:white;cursor:pointer}}p{{line-height:1.7}}.error{{color:#b91c1c}}
nav{{text-align:right;font-size:.875rem}}nav a{{color:#52525b}}nav a[aria-current]{{font-weight:bold}}</style>
<main><nav>{languages}</nav><h1>{text["title"]}</h1><p>{text["intro"]}</p>
<p class="error" role="alert">{html.escape(str(error))}</p><form method="post" action="/setup" novalidate>
<input type="hidden" name="lang" value="{locale}">
<div class="setup-field">
<span id="setup-site-name">{text["site"]}</span>
<input name="site_name" aria-labelledby="setup-site-name" maxlength="80" value="{name}" placeholder="{text["name"]}">
</div>
<div class="setup-field">
<span id="setup-password">{text["password"]}</span>
<input name="admin_password" aria-labelledby="setup-password" type="password" minlength="8" maxlength="255" autocomplete="new-password" required>
</div>
<div class="setup-field">
<span id="setup-confirm">{text["confirm"]}</span>
<input name="confirm_password" aria-labelledby="setup-confirm" type="password" minlength="8" maxlength="255" autocomplete="new-password" required>
</div>
<p>{limits}</p><button>{text["submit"]}</button></form></main></html>'''


def build_setup_success_page(locale="zh-CN"):
    text = SETUP_TEXT[locale]
    return f'''<!doctype html><html lang="{locale}"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{text["complete"]}</title>
<link rel="icon" type="image/png" href="{FAVICON_PATH}">
<h1>{text["complete"]}</h1><p><a href="/?lang={locale}">{text["home"]}</a> ·
<a href="/admin/dashboard?lang={locale}">{text["admin"]}</a></p></html>'''


def setup_response(content, status_code=200):
    return HTMLResponse(content, status_code=status_code, headers={"Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        )})


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
