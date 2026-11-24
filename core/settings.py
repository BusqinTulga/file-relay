from typing import Any
# @Time    : 2023/8/15 09:51
# @Author  : Lan
# @File    : settings.py
# @Software: PyCharm
from pathlib import Path
import os

ADMIN_SESSION_EXPIRE_DEFAULT = 30 * 24 * 60 * 60
ADMIN_SESSION_EXPIRE_MIN = 24 * 60 * 60
ADMIN_SESSION_EXPIRE_MAX = 365 * 24 * 60 * 60

BASE_DIR = Path(__file__).resolve().parent.parent
data_root = Path(os.environ.get("FILERELAY_DATA_ROOT", str(BASE_DIR / "data"))).expanduser().resolve()

if not data_root.exists():
    data_root.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG: dict[str, Any] = {
    "name": "FileRelay／文件接力",
    "description": "在你的设备之间，轻松传递文件",
    "admin_token": "", "jwt_secret": "",
    "admin_session_expire": ADMIN_SESSION_EXPIRE_DEFAULT,
    "open_upload": 1, "upload_size": 5_000_000_000,
    "storage_limit": 500_000_000_000, "show_admin_addr": 0,
    "login_count": 5, "login_minute": 15,
    "server_workers": 1, "server_host": "0.0.0.0", "server_port": 12345,
    "trusted_proxies": [],
}


class Settings:
    def __init__(self, defaults=None):
        self.default_config = defaults or {}
        self.user_config = {}

    def __getattr__(self, attr):
        if attr in self.user_config:
            return self.user_config[attr]
        if attr in self.default_config:
            return self.default_config[attr]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{attr}'"
        )

    def __setattr__(self, key, value):
        if key in ["default_config", "user_config"]:
            super().__setattr__(key, value)
        else:
            self.user_config[key] = value

    def unknown_keys(self, config: dict) -> list[str]:
        """Keys in `config` that DEFAULT_CONFIG does not define.

        Unknown keys silently fall through __getattr__ and crash later at the
        usage site; callers (refresh_settings) surface them at load time.
        """
        return sorted(k for k in config if k not in self.default_config)

    def items(self):
        return {**self.default_config, **self.user_config}.items()


settings = Settings(DEFAULT_CONFIG)
