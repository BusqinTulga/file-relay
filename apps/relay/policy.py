"""One source of effective upload policy; all sizes are integer bytes."""
from fastapi import HTTPException
from core.settings import settings
from apps.relay import config


def format_size(size):
    unit, decimals = ("GB", 9) if size >= 1_000_000_000 else ("MB", 6)
    whole, remainder = divmod(size, 10 ** decimals)
    value = f"{whole}.{remainder:0{decimals}d}".rstrip("0").rstrip(".")
    return f"{value} {unit}"


def policy():
    return {"upload_size": settings.upload_size, "storage_limit": settings.storage_limit,
            "open_upload": settings.open_upload}


def validate_limits(values):
    for key, upper in (("upload_size", config.MAX_FILE), ("storage_limit", config.MAX_STORAGE)):
        if key in values and (type(values[key]) is not int or not 1 <= values[key] <= upper):
            label = "单文件上限" if key == "upload_size" else "全站容量"
            raise ValueError(f"{label}必须大于 0 且不能超过 {format_size(upper)}")
    for key in ("open_upload", "show_admin_addr"):
        if key in values and (type(values[key]) is not int or values[key] not in (0, 1)):
            raise ValueError(f"{key} 必须是 0 或 1")


def check_upload(size):
    if size > settings.upload_size:
        raise HTTPException(413, f"文件大小超过单文件上限（{format_size(settings.upload_size)}）")
    if not settings.open_upload:
        raise HTTPException(403, "上传已暂停，请稍后重试")
