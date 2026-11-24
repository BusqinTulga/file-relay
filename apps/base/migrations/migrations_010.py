"""Remove retired FileCodeBox schema; preserve all Relay identities and deadlines.

A consistent SQLite backup is made before any mutation. Legacy blob references
are archived alongside it, never unlinked by a schema migration.
"""
import asyncio
import json
import os
import sqlite3
from pathlib import Path
from tortoise import connections
from tortoise.transactions import in_transaction
from core.settings import DEFAULT_CONFIG, data_root
from core.logger import logger

FILE_COLUMNS = ('id', 'prefix', 'suffix', 'size', 'file_hash', 'upload_id',
                'relay_group_id', 'uploader_device_id', 'published', 'relay_expires',
                'first_sent', 'delete_state', 'cleanup_error')
RETIRED_TABLES = ('uploadchunk', 'presignuploadsession', 'storagereservation')
RETIRED_KEYS = ('admin_file_view_presets', 'admin_file_metadata')


def backup_database(source):
    directory = data_root / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / 'before-schema-010.db'
    if destination.exists():
        # Never overwrite the first pre-upgrade backup on a retry.
        with sqlite3.connect(destination) as saved:
            if saved.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('迁移前备份无效，请检查 backups/before-schema-010.db')
        return
    temporary = destination.with_suffix('.tmp')
    with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as src, sqlite3.connect(temporary) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('迁移前数据库备份校验失败')
        catalog = {}
        tables = {row[0] for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('filecodes', *RETIRED_TABLES):
            if table in tables:
                src.row_factory = sqlite3.Row
                where = ' WHERE relay_group_id IS NULL' if table == 'filecodes' else ''
                catalog[table] = [dict(row) for row in src.execute(f'SELECT * FROM {table}{where}')]
        # Catalog keeps old physical paths traceable without importing them into Relay.
        catalog_path = directory / 'retired-assets-010.json'
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))
        os.chmod(catalog_path, 0o600)
    os.chmod(temporary, 0o600)
    os.replace(temporary, destination)


def normalize_config(raw):
    result = {key: value for key, value in raw.items() if key in DEFAULT_CONFIG}
    for key, upper in (('upload_size', 1_000_000_000), ('storage_limit', 500_000_000_000)):
        value = result.get(key, upper)
        if key == 'storage_limit' and value == 0:
            value = upper
        if type(value) is not int or value <= 0:
            logger.warning('配置 %s 无效，使用保守默认值', key)
            value = 10_000_000 if key == 'upload_size' else upper
        if value > upper:
            logger.warning('配置 %s 超出产品边界，收敛至 %s 字节', key, upper)
        result[key] = min(value, upper)
    return result


async def migrate():
    conn = connections.get('default')
    # Use the actual connection's file, not a hard-coded application path. In-memory
    # fixture databases have no disk backup; real upgrades always have one.
    databases = await conn.execute_query_dict('PRAGMA database_list')
    source = next((row['file'] for row in databases if row['name'] == 'main'), '')
    if source:
        await asyncio.to_thread(backup_database, Path(source))
    async with in_transaction() as tx:
        columns = {row['name'] for row in await tx.execute_query_dict('PRAGMA table_info(filecodes)')}
        if 'code' in columns:
            sequences = await tx.execute_query_dict("SELECT seq FROM sqlite_sequence WHERE name='filecodes'")
            high_water = sequences[0]['seq'] if sequences else 0
            await tx.execute_query('''CREATE TABLE filecodes_relay (
                id INTEGER PRIMARY KEY AUTOINCREMENT, prefix VARCHAR(255) NOT NULL DEFAULT '',
                suffix VARCHAR(255) NOT NULL DEFAULT '', size BIGINT NOT NULL DEFAULT 0,
                file_hash VARCHAR(64), upload_id VARCHAR(36), relay_group_id INT,
                uploader_device_id VARCHAR(36), published REAL, relay_expires REAL, first_sent REAL,
                delete_state VARCHAR(16) NOT NULL DEFAULT 'active', cleanup_error TEXT NOT NULL DEFAULT '')''')
            names = ','.join(FILE_COLUMNS)
            await tx.execute_query(f'INSERT INTO filecodes_relay ({names}) SELECT {names} FROM filecodes WHERE relay_group_id IS NOT NULL')
            await tx.execute_query('DROP TABLE filecodes')
            await tx.execute_query('ALTER TABLE filecodes_relay RENAME TO filecodes')
            # Never reuse IDs of already-cleaned Relay files: completed sessions
            # and download attempts may still refer to those historical IDs.
            await tx.execute_query("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='filecodes'", [high_water])
        for table in RETIRED_TABLES:
            await tx.execute_query(f'DROP TABLE IF EXISTS {table}')
        for name, column in (('group', 'relay_group_id'), ('device', 'uploader_device_id'), ('expiry', 'relay_expires')):
            await tx.execute_query(f'CREATE INDEX IF NOT EXISTS idx_relay_file_{name} ON filecodes({column})')
        rows = await tx.execute_query_dict("SELECT value FROM keyvalue WHERE key='settings'")
        if rows:
            value = rows[0]['value']
            raw = json.loads(value) if value is not None else None
            normalized = normalize_config({} if raw is None else raw)
            await tx.execute_query("UPDATE keyvalue SET value=? WHERE key='settings'", [json.dumps(normalized)])
        for key in RETIRED_KEYS:
            await tx.execute_query('DELETE FROM keyvalue WHERE key=?', [key])
        # Nonessential cached counters/views are retired; preserve auth, startup and
        # bounded operator activity. The migrates table owns the upgrade version.
        await tx.execute_query("DELETE FROM keyvalue WHERE key NOT IN ('settings','sys_start','admin_activities')")
        if await tx.execute_query_dict('PRAGMA foreign_key_check'):
            raise RuntimeError('数据库迁移外键校验失败')
        checked = await tx.execute_query_dict('PRAGMA integrity_check')
        if any(row['integrity_check'] != 'ok' for row in checked):
            raise RuntimeError('数据库迁移完整性校验失败')
