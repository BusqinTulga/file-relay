"""Validated, partial administrator configuration writes."""
from fastapi import HTTPException
from apps.base.models import KeyValue
from apps.base.config import refresh_settings
from apps.relay.auth import state_lock
from apps.relay.policy import validate_limits
from core.security import generate_jwt_secret
from core.settings import settings, data_root, ADMIN_SESSION_EXPIRE_MIN, ADMIN_SESSION_EXPIRE_MAX
from core.utils import hash_password

EDITABLE = {"name", "description", "notify_title", "notify_content", "admin_token",
            "admin_session_expire", "show_admin_addr", "open_upload", "upload_size", "storage_limit"}


class ConfigService:
    def get_config(self):
        result = {key: getattr(settings, key) for key in EDITABLE}
        result["admin_token"] = ""
        result["data_root"] = str(data_root)
        return result

    async def update_config(self, data):
        if set(data) - EDITABLE:
            raise HTTPException(422, "不支持的设置项：" + ", ".join(sorted(set(data) - EDITABLE)))
        try:
            validate_limits(data)
            if "admin_session_expire" in data:
                value = data["admin_session_expire"]
                if type(value) is not int or not ADMIN_SESSION_EXPIRE_MIN <= value <= ADMIN_SESSION_EXPIRE_MAX or value % ADMIN_SESSION_EXPIRE_MIN:
                    raise ValueError("登录有效期必须为 1 至 365 个整天")
            for key in ("name", "description", "notify_title", "notify_content", "admin_token"):
                if key in data and (not isinstance(data[key], str) or len(data[key]) > (5000 if key == "notify_content" else 255)):
                    raise ValueError(f"{key} 格式或长度错误")
            if "name" in data and not data["name"].strip():
                raise ValueError("站点名称不能为空")
            if data.get("admin_token") and len(data["admin_token"]) < 8:
                raise ValueError("管理员密码至少需要 8 位")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        update = dict(data)
        password = update.pop("admin_token", "")
        if password:
            update["admin_token"] = hash_password(password)
            update["jwt_secret"] = generate_jwt_secret()
        # Shared with final publication. Read inside the lock so concurrent partial
        # edits cannot overwrite each other or race an upload's final policy check.
        async with state_lock:
            row = await KeyValue.get(key="settings")
            current = {**dict(settings.items()), **(row.value or {})}
            current.update(update)
            row.value = current
            await row.save()
            await refresh_settings(force=True)
