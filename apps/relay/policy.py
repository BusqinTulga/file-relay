"""One source of effective upload policy; all sizes are integer bytes."""
from fastapi import HTTPException
from core.settings import settings
from apps.relay import config


def policy():
    return {"upload_size": settings.upload_size, "storage_limit": settings.storage_limit,
            "open_upload": settings.open_upload}


def validate_limits(values):
    for key, upper in (("upload_size", config.MAX_FILE), ("storage_limit", config.MAX_STORAGE)):
        if key in values and (type(values[key]) is not int or not 1 <= values[key] <= upper):
            raise ValueError(f"{key} 必须是 1 至 {upper} 之间的整数字节数")
    for key in ("open_upload", "show_admin_addr"):
        if key in values and (type(values[key]) is not int or values[key] not in (0, 1)):
            raise ValueError(f"{key} 必须是 0 或 1")


def check_upload(size):
    if size > settings.upload_size:
        raise HTTPException(413, f"单文件上限为 {settings.upload_size} 字节（{settings.upload_size / 1_000_000:g} MB）")
    if not settings.open_upload:
        raise HTTPException(403, "上传已暂停，请稍后重试")
