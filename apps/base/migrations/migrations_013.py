"""Rename the previous default site name in existing installations."""
import json

from tortoise.transactions import in_transaction


async def migrate():
    async with in_transaction() as tx:
        rows = await tx.execute_query_dict("SELECT value FROM keyvalue WHERE key='settings'")
        if not rows or rows[0]["value"] is None:
            return

        config = json.loads(rows[0]["value"])
        if isinstance(config, dict) and config.get("name") in ("FileRelay／文件接力", "FileRelay・文件接力"):
            config["name"] = "FileRelay／文件快传"
            await tx.execute_query(
                "UPDATE keyvalue SET value=? WHERE key='settings'",
                [json.dumps(config, ensure_ascii=False)],
            )
