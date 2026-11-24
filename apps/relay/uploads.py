"""Bounded, resumable local uploads. Disk operations stay outside SQL transactions."""
import asyncio
import hashlib
import math
import os
import shutil
import uuid
from contextlib import asynccontextmanager

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from tortoise.expressions import Subquery
from tortoise.functions import Sum
from tortoise.transactions import in_transaction

from apps.base.models import FileCodes, RelayChunk, RelayDevice, RelaySession, RelayUpload
from apps.relay import config
from apps.relay.auth import csrf, device_session, state_lock
from core.settings import data_root, settings
from apps.relay.policy import check_upload

router = APIRouter(prefix="/api/relay")
ROOT = data_root / "relay"
# Ref-counted locks are discarded after waiters finish.
_locks: dict[str, tuple[asyncio.Lock, int]] = {}


@asynccontextmanager
async def upload_lock(upload_id):
    lock, count = _locks.get(upload_id, (asyncio.Lock(), 0))
    _locks[upload_id] = (lock, count + 1)
    try:
        async with lock:
            yield
    finally:
        _, count = _locks[upload_id]
        if count == 1:
            del _locks[upload_id]
        else:
            _locks[upload_id] = (lock, count - 1)


def upload_in_use(upload_id):
    return upload_id in _locks


def temp_dir(upload_id):
    return ROOT / "uploads" / upload_id


def final_path(upload_id):
    return ROOT / "files" / upload_id


def view_file(file):
    return {"id": file.id, "name": file.prefix + file.suffix, "size": file.size,
            "sha256": file.file_hash, "published": file.published, "expires": file.relay_expires,
            "first_sent": file.first_sent}


async def assert_current(session, device):
    current = await RelayDevice.get_or_none(id=device.id, group_id=device.group_id)
    if not current or not await RelaySession.filter(token_hash=session.token_hash, valid=True).exists():
        raise HTTPException(401, "设备凭证已改变，请刷新页面")


async def owned_upload(upload_id, auth):
    session, device = auth
    await assert_current(session, device)
    upload = await RelayUpload.get_or_none(id=upload_id, group_id=device.group_id, device_id=device.id,
                                           session_hash=session.token_hash)
    if not upload:
        raise HTTPException(404, "上传不存在")
    if upload.state != "completed" and upload.expires <= config.now():
        raise HTTPException(410, "上传已过期，请重新选择文件")
    return upload


async def upload_view(upload):
    result = {"id": upload.id, "state": upload.state, "chunk_size": upload.chunk_size,
              "chunks": await RelayChunk.filter(upload_id=upload.id).order_by("index").values_list("index", flat=True),
              "error": upload.error}
    if upload.file_id:
        file = await FileCodes.get_or_none(id=upload.file_id)
        result["file"] = view_file(file) if file else None
    return result


class UploadInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    chunked: bool = True


async def used_capacity():
    published = await FileCodes.all().annotate(total=Sum("size")).values("total")
    pending = await RelayUpload.exclude(state__in=["completed", "cleaned"]).annotate(total=Sum("size")).values("total")
    # Completed sessions can retain duplicate chunks after a failed disk cleanup.
    completed = Subquery(RelayUpload.filter(state="completed").values("id"))
    residual = await RelayChunk.filter(upload_id__in=completed).annotate(total=Sum("size")).values("total")
    return sum((rows[0]["total"] or 0) if rows else 0 for rows in (published, pending, residual))


@router.post("/uploads", dependencies=[Depends(csrf)])
async def start_upload(data: UploadInput, auth=Depends(device_session)):
    if any(ord(c) < 32 for c in data.name) or "/" in data.name or "\\" in data.name or data.name in {".", ".."}:
        raise HTTPException(422, "文件名无效")
    session, device = auth
    async with state_lock:
        await assert_current(session, device)
        if data.size > config.MAX_FILE:
            check_upload(data.size)
        existing = await RelayUpload.filter(
            group_id=device.group_id, device_id=device.id, session_hash=session.token_hash,
            name=data.name, size=data.size, sha256=data.sha256,
            state__in=["uploading", "merging", "completed"], expires__gt=config.now()).order_by("-expires").first()
        if existing and existing.state == "completed":
            if not await FileCodes.filter(id=existing.file_id, relay_group_id=device.group_id,
                    delete_state="active", relay_expires__gt=config.now()).exists():
                existing = None
        if existing and existing.state == "completed":
            return await upload_view(existing)
        if existing:
            await enforce_policy(existing)
            return await upload_view(existing)
        check_upload(data.size)
        if await used_capacity() + data.size > settings.storage_limit:
            raise HTTPException(507, "全站容量不足，请等待到期清理")
        ROOT.mkdir(parents=True, exist_ok=True)
        # Account for all outstanding promises as well as merge duplication.
        outstanding = await RelayUpload.exclude(state__in=["completed", "cleaned"]).annotate(
            total=Sum("size")).values("total")
        promised = (outstanding[0]["total"] or 0) if outstanding else 0
        free = (await asyncio.to_thread(shutil.disk_usage, ROOT)).free
        if free < 2 * (data.size + promised) + 16 * 1024 * 1024:
            raise HTTPException(507, "磁盘可用空间不足")
        upload = await RelayUpload.create(id=str(uuid.uuid4()), group_id=device.group_id, device_id=device.id,
            session_hash=session.token_hash, name=data.name, size=data.size, sha256=data.sha256,
            chunk_size=config.CHUNK_SIZE if data.chunked and data.size > 0 else max(data.size, 1),
            expires=config.now() + config.UPLOAD_TTL)
        return await upload_view(upload)


@router.get("/uploads/{upload_id}")
async def get_upload(upload_id: str, auth=Depends(device_session)):
    return await upload_view(await owned_upload(upload_id, auth))


async def enforce_policy(upload):
    try:
        check_upload(upload.size)
    except HTTPException as exc:
        if exc.status_code == 413:
            await RelayUpload.filter(id=upload.id).exclude(state__in=["completed", "cleaned"]).update(
                state="cancelled", error=exc.detail)
        raise


async def write_chunk(upload_id, index, request, auth):
    async with upload_lock(upload_id):
        upload = await owned_upload(upload_id, auth)
        if upload.state != "uploading":
            raise HTTPException(409, "上传状态不允许写入")
        await enforce_policy(upload)
        count = max(1, math.ceil(upload.size / upload.chunk_size))
        if index < 0 or index >= count:
            raise HTTPException(422, "分片索引无效")
        expected = min(upload.chunk_size, upload.size - index * upload.chunk_size)
        declared_hash = request.headers.get("x-chunk-sha256", "")
        if len(declared_hash) != 64:
            raise HTTPException(422, "缺少分片 SHA256")
        directory = temp_dir(upload.id)
        directory.mkdir(parents=True, exist_ok=True)
        partial = directory / f"{index}.part"
        target = directory / str(index)
        hasher, length = hashlib.sha256(), 0
        try:
            async with aiofiles.open(partial, "wb") as output:
                stream = aiter(request.stream())
                while True:
                    try:
                        async with asyncio.timeout(config.UPLOAD_IDLE_TIMEOUT):
                            block = await anext(stream, None)
                    except TimeoutError as exc:
                        raise HTTPException(408, "上传等待数据超时，请重试") from exc
                    if block is None:
                        break
                    length += len(block)
                    if length > expected:
                        raise HTTPException(422, "分片长度超出声明")
                    hasher.update(block)
                    await output.write(block)
                await output.flush()
            if length != expected or hasher.hexdigest() != declared_hash:
                raise HTTPException(422, "分片长度或 SHA256 不匹配")
            async with state_lock:
                upload = await owned_upload(upload_id, auth)
                if upload.state != "uploading":
                    raise HTTPException(409, "上传已取消")
                await enforce_policy(upload)
                os.replace(partial, target)
                await RelayChunk.update_or_create(upload_id=upload.id, index=index,
                    defaults={"size": length, "sha256": hasher.hexdigest()})
            return {"index": index, "size": length}
        except BaseException as exc:
            partial.unlink(missing_ok=True)
            await RelayUpload.filter(id=upload_id, state="uploading").update(error=str(exc)[:500])
            raise


@router.put("/uploads/{upload_id}/chunks/{index}", dependencies=[Depends(csrf)])
async def put_chunk(upload_id: str, index: int, request: Request, auth=Depends(device_session)):
    return await write_chunk(upload_id, index, request, auth)


@router.put("/uploads/{upload_id}/content", dependencies=[Depends(csrf)])
async def put_content(upload_id: str, request: Request, auth=Depends(device_session)):
    upload = await owned_upload(upload_id, auth)
    if upload.size > upload.chunk_size:
        raise HTTPException(422, "此会话需要分片上传")
    return await write_chunk(upload_id, 0, request, auth)


class UploadIntegrityError(ValueError):
    def __init__(self, message: str, index: int | None = None):
        super().__init__(message)
        self.index = index


def merge_and_verify(upload, chunks):
    directory = temp_dir(upload.id)
    directory.mkdir(parents=True, exist_ok=True)
    merged = directory / "merged.part"
    total, hasher = 0, hashlib.sha256()
    with merged.open("wb") as output:
        for chunk in chunks:
            part_hash, part_size = hashlib.sha256(), 0
            expected = min(upload.chunk_size, upload.size - chunk.index * upload.chunk_size)
            try:
                source = (directory / str(chunk.index)).open("rb")
            except FileNotFoundError as exc:
                raise UploadIntegrityError("分片实体丢失，请重传", chunk.index) from exc
            with source:
                while block := source.read(1024 * 1024):
                    total += len(block)
                    part_size += len(block)
                    if part_size > expected:
                        raise UploadIntegrityError("分片实体损坏，请重传", chunk.index)
                    hasher.update(block)
                    part_hash.update(block)
                    output.write(block)
            if part_size != expected or part_hash.hexdigest() != chunk.sha256:
                raise UploadIntegrityError("分片实体损坏，请重传", chunk.index)
        output.flush()
        os.fsync(output.fileno())
    if total != upload.size or hasher.hexdigest() != upload.sha256:
        raise UploadIntegrityError("文件总长度或完整 SHA256 不匹配，请重传")
    final_path(upload.id).parent.mkdir(parents=True, exist_ok=True)
    os.replace(merged, final_path(upload.id))


async def clear_chunks(upload):
    directory = temp_dir(upload.id)
    if directory.exists():
        await asyncio.to_thread(shutil.rmtree, directory)
    await RelayChunk.filter(upload_id=upload.id).delete()


@router.post("/uploads/{upload_id}/complete", dependencies=[Depends(csrf)])
async def complete(upload_id: str, auth=Depends(device_session)):
    async with upload_lock(upload_id):
        upload = await owned_upload(upload_id, auth)
        if upload.state == "completed":
            return await upload_view(upload)
        if upload.state not in {"uploading", "merging"}:
            raise HTTPException(409, "上传已取消或过期")
        chunks = await RelayChunk.filter(upload_id=upload.id).order_by("index")
        await enforce_policy(upload)
        count = max(1, math.ceil(upload.size / upload.chunk_size))
        if [c.index for c in chunks] != list(range(count)):
            raise HTTPException(422, "分片不完整")
        changed = await RelayUpload.filter(id=upload.id, state__in=["uploading", "merging"]).update(state="merging")
        if not changed:
            raise HTTPException(409, "上传状态已改变")
        try:
            await asyncio.to_thread(merge_and_verify, upload, chunks)
            async with state_lock:
                current = await owned_upload(upload_id, auth)
                if current.state != "merging":
                    raise HTTPException(409, "上传已取消")
                await enforce_policy(current)
                async with in_transaction():
                    stamp = config.now()
                    file = await FileCodes.create(prefix=upload.name, size=upload.size,
                        file_hash=upload.sha256, upload_id=upload.id,
                        relay_group_id=upload.group_id, uploader_device_id=upload.device_id,
                        published=stamp, relay_expires=stamp + config.FILE_TTL)
                    await RelayUpload.filter(id=upload.id).update(state="completed", file_id=file.id, error="")
        except Exception as exc:
            if isinstance(exc, UploadIntegrityError):
                recorded = RelayChunk.filter(upload_id=upload.id)
                if exc.index is not None:
                    recorded = recorded.filter(index=exc.index)
                await recorded.delete()
            await RelayUpload.filter(id=upload.id, state="merging").update(state="uploading", error=str(exc)[:500])
            if isinstance(exc, HTTPException):
                raise
            if isinstance(exc, UploadIntegrityError):
                raise HTTPException(422, str(exc)) from exc
            raise HTTPException(422, "文件校验或发布失败，可重试上传") from exc
        upload = await RelayUpload.get(id=upload.id)
        try:
            await clear_chunks(upload)
        except OSError as exc:
            await RelayUpload.filter(id=upload.id).update(error=str(exc)[:500])
        return await upload_view(upload)


@router.delete("/uploads/{upload_id}", dependencies=[Depends(csrf)])
async def cancel_upload(upload_id: str, auth=Depends(device_session)):
    async with upload_lock(upload_id), state_lock:
        upload = await owned_upload(upload_id, auth)
        if upload.state == "completed":
            raise HTTPException(409, "文件已发布，请从列表删除")
        await RelayUpload.filter(id=upload.id).update(state="cancelled")
    return {"state": "cancelled"}
