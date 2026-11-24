"""Remove retired notification settings from the persisted application config."""
import json
from tortoise.transactions import in_transaction


async def migrate():
    async with in_transaction() as tx:
        rows = await tx.execute_query_dict("SELECT value FROM keyvalue WHERE key='settings'")
        if not rows or rows[0]["value"] is None:
            return

        config = json.loads(rows[0]["value"])
        if config is None:
            return
        if not isinstance(config, dict):
            raise RuntimeError("设置配置格式无效，无法移除旧通知字段")

        if "notify_title" in config or "notify_content" in config:
            config.pop("notify_title", None)
            config.pop("notify_content", None)
            await tx.execute_query(
                "UPDATE keyvalue SET value=? WHERE key='settings'",
                [json.dumps(config, ensure_ascii=False)],
            )
