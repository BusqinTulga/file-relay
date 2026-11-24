"""Keep the old default for existing settings that inherit the file limit."""
import json

from tortoise.transactions import in_transaction

PREVIOUS_DEFAULT = 1_000_000_000


async def migrate():
    async with in_transaction() as tx:
        rows = await tx.execute_query_dict("SELECT value FROM keyvalue WHERE key='settings'")
        if not rows:
            return

        value = rows[0]["value"]
        config = json.loads(value) if value is not None else None
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise RuntimeError("设置配置格式无效，无法保留原有单文件上限")

        if "upload_size" not in config:
            config["upload_size"] = PREVIOUS_DEFAULT
            await tx.execute_query(
                "UPDATE keyvalue SET value=? WHERE key='settings'",
                [json.dumps(config, ensure_ascii=False)],
            )
