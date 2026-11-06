import asyncio
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response
from tortoise.transactions import in_transaction
from tortoise.expressions import F

from apps.base.models import DownloadAttempt, FileCodes
from apps.relay import config
from apps.relay.auth import csrf, device_session, state_lock
from apps.relay.uploads import assert_current, final_path, view_file

router = APIRouter(prefix="/api/relay")


async def available_file(file_id, group_id=None):
    query = FileCodes.filter(id=file_id, delete_state="active", relay_expires__gt=config.now())
    query = query.filter(relay_group_id=group_id) if group_id is not None else query.filter(relay_group_id__not_isnull=True)
    file = await query.first()
    if not file:
        raise HTTPException(404, "文件不存在或已到期")
    return file


@router.get("/files")
async def list_files(auth=Depends(device_session)):
    session, device = auth
    async with state_lock:
        await assert_current(session, device)
        rows = await FileCodes.filter(relay_group_id=device.group_id, delete_state="active",
                                      relay_expires__gt=config.now()).order_by("-published")
    return {"session_id": session.token_hash, "files": [view_file(f) for f in rows]}


@router.get("/files/{file_id}")
async def metadata(file_id: int, auth=Depends(device_session)):
    _, device = auth
    return view_file(await available_file(file_id, device.group_id))


async def mark_delete(file_id):
    async with state_lock:
        await FileCodes.filter(id=file_id).update(delete_state="pending")


@router.delete("/files/{file_id}", dependencies=[Depends(csrf)])
async def delete_file(file_id: int, auth=Depends(device_session)):
    session, device = auth
    async with state_lock:
        await assert_current(session, device)
        file = await available_file(file_id, device.group_id)
        await FileCodes.filter(id=file.id).update(delete_state="pending")
    return {"deleted": True}


class LeasedDownload(Response):
    """Count completion only after ASGI accepts the final body, never in a generator finally.

    A separate heartbeat keeps a backpressured send alive, bounded by protect_until.
    Disconnect cancels sending. A completed full response means server transmission,
    not browser persistence. Ranges, HEAD and prefetch never start the retry window.
    """
    def __init__(self, file, attempt, start, end, eligible, head=False, ranged=False):
        self.file, self.attempt = file, attempt
        self.start, self.end, self.eligible, self.head = start, end, eligible, head
        length = max(0, end - start + 1)
        headers = {"Content-Length": str(length), "Cache-Control": "no-store", "Accept-Ranges": "bytes",
                   "X-Content-Type-Options": "nosniff",
                   "Content-Disposition": "attachment; filename*=UTF-8''" + quote(file.prefix + file.suffix, safe="")}
        if ranged:
            headers["Content-Range"] = f"bytes {start}-{end}/{file.size}"
        super().__init__(b"", status_code=206 if ranged else 200, media_type="application/octet-stream", headers=headers)

    async def __call__(self, scope, receive, send):
        successful = False

        async def transmit():
            await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
            if not self.head:
                async with aiofiles.open(final_path(self.file.upload_id), "rb") as source:
                    await source.seek(self.start)
                    remaining = max(0, self.end - self.start + 1)
                    while remaining:
                        block = await source.read(min(256 * 1024, remaining))
                        if not block:
                            raise OSError("下载源文件意外截断")
                        await send({"type": "http.response.body", "body": block, "more_body": True})
                        remaining -= len(block)
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        async def disconnected():
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return

        async def heartbeat():
            while True:
                await asyncio.sleep(config.LEASE_HEARTBEAT)
                if config.now() >= self.attempt.protect_until:
                    raise TimeoutError("下载超过最长保护时间")
                await DownloadAttempt.filter(id=self.attempt.id, state="active").update(
                    lease_until=min(config.now() + config.LEASE_TTL, self.attempt.protect_until))

        sender = asyncio.create_task(transmit())
        listener = asyncio.create_task(disconnected())
        renewer = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait({sender, listener, renewer}, return_when=asyncio.FIRST_COMPLETED)
            if sender in done and not sender.cancelled() and sender.exception() is None and listener not in done:
                successful = not self.head and self.eligible
            if sender in done:
                sender.result()
        finally:
            for task in (sender, listener, renewer):
                task.cancel()
            await asyncio.gather(sender, listener, renewer, return_exceptions=True)
            # Always settle the persisted lease, including disconnect and read/send failure.
            async with state_lock, in_transaction():
                stamp = config.now()
                await DownloadAttempt.filter(id=self.attempt.id).update(
                    state="completed" if successful else "ended", completed=stamp if successful else None,
                    lease_until=stamp)
                if successful:
                    file = await FileCodes.get_or_none(id=self.file.id)
                    if file:
                        await FileCodes.filter(id=file.id).update(used_count=F("used_count") + 1)
                    if file and file.first_sent is None:
                        expiry = min(file.relay_expires, stamp + config.RETRY_WINDOW)
                        await FileCodes.filter(id=file.id, first_sent__isnull=True).update(
                            first_sent=stamp, relay_expires=expiry,
                            expired_at=datetime.fromtimestamp(expiry, timezone.utc))


async def download_response(file_id, request=None, auth=None):
    async with state_lock:
        if auth:
            await assert_current(*auth)
        file = await available_file(file_id, auth[1].group_id if auth else None)
        if not final_path(file.upload_id).is_file():
            raise HTTPException(404, "文件实体不存在")
        start, end = 0, file.size - 1
        ranged = bool(request and request.headers.get("range"))
        if ranged:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", request.headers["range"])
            if not match or file.size == 0 or not any(match.groups()):
                raise HTTPException(416, "Range 不可用", headers={"Content-Range": f"bytes */{file.size}"})
            left, right = match.groups()
            if left:
                start, end = int(left), min(int(right), end) if right else end
            else:
                start = max(0, file.size - int(right))
            if start > end or start < 0:
                raise HTTPException(416, "Range 不可用", headers={"Content-Range": f"bytes */{file.size}"})
        head = bool(request and request.method == "HEAD")
        purpose = " ".join(request.headers.get(k, "") for k in ("purpose", "sec-purpose", "x-purpose")) if request else ""
        eligible = not ranged and "prefetch" not in purpose.lower() and "preview" not in purpose.lower()
        stamp = config.now()
        attempt = await DownloadAttempt.create(id=str(uuid.uuid4()), file_id=file.id, group_id=file.relay_group_id,
            lease_until=stamp + config.LEASE_TTL, protect_until=stamp + config.MAX_DOWNLOAD_SECONDS)
        return LeasedDownload(file, attempt, start, end, eligible, head, ranged)


@router.api_route("/files/{file_id}/download", methods=["GET", "HEAD"])
async def download(file_id: int, request: Request, auth=Depends(device_session)):
    return await download_response(file_id, request, auth)
