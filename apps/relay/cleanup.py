"""Persistent, retryable deletion. No unlink before admission closes and leases end."""
import asyncio

from apps.base.models import DownloadAttempt, FileCodes, PairingRequest, RelayUpload
from apps.relay import config
from apps.relay.auth import state_lock
from apps.relay.uploads import clear_chunks, final_path, upload_lock
from core.logger import logger


async def sweep():
    stamp = config.now()
    async with state_lock:
        await FileCodes.filter(relay_group_id__not_isnull=True, delete_state="active",
                               relay_expires__lte=stamp).update(delete_state="pending")
        await DownloadAttempt.filter(state="active", lease_until__lte=stamp).update(state="abandoned")
        await PairingRequest.filter(status__in=["pending", "approved"], expires__lte=stamp).update(status="expired")
    # Queries are bounded so one pass never monopolizes the worker.
    rows = await FileCodes.filter(relay_group_id__not_isnull=True, delete_state="pending").limit(100)
    for file in rows:
        async with state_lock:
            if await DownloadAttempt.filter(file_id=file.id, state="active", lease_until__gt=config.now(),
                                            protect_until__gt=config.now()).exists():
                continue
            await FileCodes.filter(id=file.id, delete_state="pending").update(delete_state="deleting")
        try:
            # Relay files are always owned local blobs, never NAS references.
            await asyncio.to_thread(final_path(file.upload_id).unlink, missing_ok=True)
            await FileCodes.filter(id=file.id, delete_state="deleting").delete()
        except OSError as exc:
            await FileCodes.filter(id=file.id).update(delete_state="pending", cleanup_error=str(exc)[:500])
    # A process crash can leave 'deleting'; no new downloads can enter it.
    await FileCodes.filter(relay_group_id__not_isnull=True, delete_state="deleting").update(delete_state="pending")
    expired = await RelayUpload.exclude(state="cleaned").filter(expires__lte=stamp).limit(100)
    cancelled = await RelayUpload.filter(state="cancelled").limit(100)
    completed = await RelayUpload.filter(state="completed").exclude(error="").limit(100)
    for item in {u.id: u for u in [*expired, *cancelled, *completed]}.values():
        async with upload_lock(item.id):
            upload = await RelayUpload.get(id=item.id)
            try:
                await clear_chunks(upload)
                if upload.file_id is None:
                    await asyncio.to_thread(final_path(upload.id).unlink, missing_ok=True)
                await RelayUpload.filter(id=upload.id).update(
                    state="completed" if upload.state == "completed" and upload.expires > stamp else "cleaned", error="")
            except OSError as exc:
                await RelayUpload.filter(id=upload.id).update(error=str(exc)[:500])
    # Keep idempotent outcomes for the upload TTL, not an unbounded history.
    await RelayUpload.filter(state="cleaned", expires__lt=stamp - config.UPLOAD_TTL).delete()
    await DownloadAttempt.exclude(state="active").filter(lease_until__lt=stamp - config.FILE_TTL).delete()
    await PairingRequest.filter(expires__lt=stamp - config.FILE_TTL).delete()


async def cleanup_loop():
    while True:
        try:
            await sweep()
        except Exception:
            logger.exception("FileRelay 清理失败，将在下一轮重试")
        await asyncio.sleep(config.SCAN_INTERVAL)
