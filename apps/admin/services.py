"""Small administrator view over the same Relay lifecycle."""
from fastapi import HTTPException
from tortoise.expressions import Q, RawSQL
from apps.base.models import FileCodes, KeyValue
from apps.relay import config
from apps.relay.files import mark_delete, download_response
from apps.relay.uploads import view_file


def file_status(file, stamp=None):
    stamp = config.now() if stamp is None else stamp
    if file.delete_state != "active":
        return "cleanup_failed" if file.cleanup_error else "pending"
    if file.relay_expires <= stamp:
        return "expired"
    return "retry" if file.first_sent is not None else "waiting"


async def admin_file(file):
    return {**view_file(file), "status": file_status(file), "cleanup_error": file.cleanup_error}


class FileService:
    async def list_files(self, page=1, size=20, keyword="", status="all"):
        query = FileCodes.all()
        if keyword:
            query = query.annotate(display_name=RawSQL('"prefix" || "suffix"')).filter(display_name__icontains=keyword)
        stamp = config.now()
        filters = {
            "waiting": Q(delete_state="active", relay_expires__gt=stamp, first_sent__isnull=True),
            "retry": Q(delete_state="active", relay_expires__gt=stamp, first_sent__not_isnull=True),
            "expired": Q(delete_state="active", relay_expires__lte=stamp),
            "pending": ~Q(delete_state="active") & Q(cleanup_error=""),
            "cleanup_failed": ~Q(delete_state="active") & ~Q(cleanup_error=""),
        }
        if status != "all":
            if status not in filters:
                raise HTTPException(422, "文件状态无效")
            query = query.filter(filters[status])
        total = await query.count()
        rows = await query.order_by("-published", "-id").offset((page-1)*size).limit(size)
        return {"files": [await admin_file(row) for row in rows], "total": total}

    async def get_file_detail(self, file_id):
        file = await FileCodes.get_or_none(id=file_id)
        if not file:
            raise HTTPException(404, "文件不存在")
        return await admin_file(file)

    async def delete_file(self, file_id):
        await mark_delete(file_id)
        await self.record_admin_activity("file.delete", file_id)
        return {"id": file_id, "state": "pending"}

    async def download_file(self, file_id, request):
        return await download_response(file_id, request)

    async def record_admin_activity(self, action, target=None):
        # Bounded history, never store passwords, session credentials or config values.
        from apps.relay.auth import state_lock
        async with state_lock:
            row = await KeyValue.get_or_none(key="admin_activities")
            history = row.value if row and isinstance(row.value, list) else []
            history.append({"action": action, "target": target, "time": config.now()})
            await KeyValue.update_or_create(key="admin_activities", defaults={"value": history[-100:]})
