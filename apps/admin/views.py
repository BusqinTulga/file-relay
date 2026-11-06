"""FileRelay administration: overview, files and settings."""
import asyncio
import shutil
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from tortoise.functions import Sum
from apps.admin.dependencies import admin_required, get_admin_session, get_config_service, get_file_service
from apps.admin.schemas import LoginData, IDData, IDsData
from apps.admin.services import FileService
from apps.admin.config_service import ConfigService
from apps.base.auth import create_token, get_admin_session_expire_seconds, verify_token
from apps.base.models import FileCodes, KeyValue
from apps.base.utils import ip_limit
from apps.relay import config
from apps.relay.policy import policy
from apps.relay.auth import state_lock
from apps.relay.uploads import used_capacity
from core.logger import logger
from core.response import APIResponse
from core.settings import settings, data_root
from core.utils import verify_password, password_needs_rehash, hash_password

admin_api = APIRouter(prefix="/admin", dependencies=[Depends(admin_required)])


@admin_api.post("/login")
async def login(data: LoginData, ip: str = Depends(ip_limit["login"])):
    # 登录失败计入 IP 频率限制，超过 login_count/login_minute 后暂时锁定
    if not verify_password(data.password, settings.admin_token):
        ip_limit["login"].add_ip(ip)
        raise HTTPException(status_code=401, detail="密码错误")

    # 透明重哈希：存量 sha256/明文口令在登录成功（已证明持有口令）时升级为 scrypt
    if password_needs_rehash(settings.admin_token):
        try:
            record = await KeyValue.filter(key="settings").first()
            if record:
                stored = dict(record.value or {})
                stored["admin_token"] = hash_password(data.password)
                record.value = stored
                await record.save()
                settings.admin_token = stored["admin_token"]
                logger.info("管理员口令已升级为 scrypt 哈希")
        except Exception:
            logger.warning("口令哈希升级失败，保持旧格式", exc_info=True)

    expires_in = get_admin_session_expire_seconds()
    token = create_token({"is_admin": True}, expires_in=expires_in)
    return APIResponse(
        detail={
            "id": "admin",
            "username": "admin",
            "token": token,
            "token_type": "Bearer",
            "expires_at": verify_token(token)["exp"],
            "expires_in": expires_in,
        }
    )


@admin_api.get("/verify")
async def verify_admin(session: dict = Depends(get_admin_session)):
    return APIResponse(detail=session)


@admin_api.post("/logout")
async def logout_admin():
    return APIResponse(detail={"ok": True})



@admin_api.get("/dashboard")
async def dashboard():
    stamp = config.now()
    async with state_lock:
        occupied = await used_capacity()
        sums = await FileCodes.all().annotate(total=Sum("size")).values("total")
        published = (sums[0]["total"] or 0) if sums else 0
        active = await FileCodes.filter(delete_state="active", relay_expires__gt=stamp).count()
        total = await FileCodes.all().count()
        effective = policy()
    disk = await asyncio.to_thread(shutil.disk_usage, data_root)
    started = await KeyValue.get_or_none(key="sys_start")
    return APIResponse(detail={**effective, "active_files": active, "pending_files": total-active,
        "published_bytes": published, "reserved_bytes": max(0, occupied-published),
        "occupied_bytes": occupied, "available_bytes": max(0, effective["storage_limit"]-occupied),
        "disk_free_bytes": disk.free, "sys_start": started.value if started else None,
        "file_ttl": config.FILE_TTL, "retry_window": config.RETRY_WINDOW})


@admin_api.get("/file/list")
async def file_list(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                    keyword: str = Query("", max_length=255), status: str = "all",
                    service: FileService = Depends(get_file_service)):
    return APIResponse(detail=await service.list_files(page, size, keyword, status))


@admin_api.get("/file/detail")
async def file_detail(id: int, service: FileService = Depends(get_file_service)):
    return APIResponse(detail=await service.get_file_detail(id))


@admin_api.delete("/file/delete")
async def file_delete(data: IDData, service: FileService = Depends(get_file_service)):
    return APIResponse(detail=await service.delete_file(data.id))


@admin_api.post("/file/batch-delete")
async def file_batch_delete(data: IDsData, service: FileService = Depends(get_file_service)):
    deleted, failed = [], []
    for file_id in dict.fromkeys(data.ids):
        try:
            await service.delete_file(file_id)
            deleted.append(file_id)
        except HTTPException as exc:
            failed.append({"id": file_id, "reason": exc.detail})
    return APIResponse(detail={"deleted": deleted, "failed": failed})


@admin_api.head("/file/download", include_in_schema=False)
@admin_api.get("/file/download")
async def file_download(id: int, request: Request, service: FileService = Depends(get_file_service)):
    return await service.download_file(id, request)


@admin_api.get("/config/get")
async def get_config(service: ConfigService = Depends(get_config_service)):
    return APIResponse(detail=service.get_config())


@admin_api.patch("/config/update")
async def update_config(data: dict, service: ConfigService = Depends(get_config_service),
                        files: FileService = Depends(get_file_service)):
    await service.update_config(data)
    await files.record_admin_activity("config.update")
    return APIResponse()
