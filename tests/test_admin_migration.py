"""Real pre-cleanup SQLite schema upgraded in place, with credentials and blobs."""
import importlib
import json
import sqlite3
import pytest
import httpx
from tortoise import Tortoise
import main
from core.database import execute_migrations
from core.settings import DEFAULT_CONFIG
from apps.base.config import refresh_settings
from apps.base.models import RelayUpload, DownloadAttempt, FileCodes, KeyValue
from apps.relay.uploads import ROOT, final_path, temp_dir
from tests.helpers import MEMORY_DB_CONFIG, close_db
from tests.test_relay import pair, headers, sha
from tests.conftest import TEST_ADMIN_PASSWORD
from core.utils import hash_password


@pytest.fixture
async def old_database(tmp_path, monkeypatch):
    migration = importlib.import_module('apps.base.migrations.migrations_010')
    monkeypatch.setattr(migration, 'data_root', tmp_path)
    config = {**MEMORY_DB_CONFIG, 'connections': {'default': {'engine': 'tortoise.backends.sqlite',
        'credentials': {'file_path': str(tmp_path/'upgrade.db'), 'journal_mode': 'WAL'}}}}
    if Tortoise._inited:
        await close_db()
    await Tortoise.init(config=config)
    conn = Tortoise.get_connection('default')
    await conn.execute_query('CREATE TABLE migrates (id INTEGER PRIMARY KEY, migration_file TEXT UNIQUE)')
    for number in range(1, 10):
        await importlib.import_module(f'apps.base.migrations.migrations_{number:03d}').migrate()
        await conn.execute_query('INSERT INTO migrates(migration_file) VALUES(?)', [f'migrations_{number:03d}.py'])
    settings = {**DEFAULT_CONFIG, 'admin_token':hash_password(TEST_ADMIN_PASSWORD), 'jwt_secret':'s'*48,
        'upload_size':10_485_760, 'storage_limit':0, 's3_secret_access_key':'retired-secret', 'themes_select':'themes/2024'}
    await KeyValue.create(key='settings', value=settings)
    await KeyValue.create(key='admin_file_view_presets', value={'presets': ['old']})
    await KeyValue.create(key='admin_file_metadata', value={'1': {'note':'old'}})
    await KeyValue.create(key='sys_start', value=123)
    await KeyValue.create(key='admin_activities', value=[{'action':'config.update'}])
    await refresh_settings(force=True)
    from core.settings import settings
    settings.storage_limit = 500_000_000_000  # prior runtime enforced the fixed Relay bound
    try:
        yield conn, tmp_path, migration
    finally:
        await close_db()


async def test_upgrade_preserves_ids_credentials_inflight_leases_deadlines_and_data(old_database):
    conn, root, migration = old_database
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as c:
        identity = (await pair(c)).json()
        h = await headers(c)
        started = await c.post('/api/relay/uploads', headers=h,
            json={'name':'inflight.bin','size':3,'sha256':sha(b'abc'),'chunked':False})
        assert started.status_code == 200, started.text
        pending = started.json()
        assert (await c.put(f"/api/relay/uploads/{pending['id']}/content", content=b'abc',
            headers={**h,'X-Chunk-SHA256':sha(b'abc')})).status_code == 200
        # Seed published legacy-layout rows with real Relay payloads and fixed timestamps.
        ROOT.mkdir(parents=True, exist_ok=True)
        for file_id, upload_id, state, error in ((42,'published','active',''), (43,'cleanup','pending','disk failure')):
            path = final_path(upload_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'old-content')
            await conn.execute_query('''INSERT INTO filecodes
                (id,code,prefix,suffix,size,file_hash,upload_id,relay_group_id,uploader_device_id,published,relay_expires,first_sent,delete_state,cleanup_error)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                [file_id,'internal-'+str(file_id),'old','.txt',11,sha(b'old-content'),upload_id,1,identity['device_id'],100,9_999_999_999,200,state,error])
        await DownloadAttempt.create(id='old-lease',file_id=42,group_id=1,lease_until=9_999_999_999,protect_until=9_999_999_999)
        # A NAS reference is retained in the backup catalog, with its original untouched.
        nas = root/'nas-original.txt'
        nas.write_bytes(b'NAS')
        await conn.execute_query("INSERT INTO filecodes(code,prefix,file_path,uuid_file_name,size) VALUES('legacy','NAS',?,?,3)", [str(nas.parent),nas.name])
        await conn.execute_query("UPDATE sqlite_sequence SET seq=1000 WHERE name='filecodes'")
        before_upload = await RelayUpload.get(id=pending['id'])
        await execute_migrations()
        await refresh_settings(force=True)
        columns = {row['name'] for row in await conn.execute_query_dict('PRAGMA table_info(filecodes)')}
        assert columns == set(migration.FILE_COLUMNS)
        tables = {row['name'] for row in await conn.execute_query_dict("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not set(migration.RETIRED_TABLES) & tables
        config = (await KeyValue.get(key='settings')).value
        assert config['upload_size'] == 10_485_760 and config['storage_limit'] == 500_000_000_000
        assert 's3_secret_access_key' not in config and 'themes_select' not in config
        assert not await KeyValue.filter(key__in=migration.RETIRED_KEYS).exists()
        assert await KeyValue.filter(key='admin_activities').exists()
        restored = (await c.get('/api/relay/session')).json()
        assert restored['device_id'] == identity['device_id'] and restored['session_id'] == identity['session_id']
        from tests.test_api_contract import _login
        token = await _login(c)
        listing = await c.get('/admin/file/list', params={'keyword':'old.txt'}, headers={'Authorization':'Bearer '+token})
        assert listing.json()['detail']['total'] == 2
        file = await FileCodes.get(id=42)
        assert (file.published,file.relay_expires,file.first_sent) == (100,9_999_999_999,200)
        failed = await FileCodes.get(id=43)
        assert failed.delete_state == 'pending' and failed.cleanup_error == 'disk failure'
        assert (await DownloadAttempt.get(id='old-lease')).state == 'active'
        after_upload = await RelayUpload.get(id=pending['id'])
        assert after_upload.size == before_upload.size and after_upload.expires == before_upload.expires
        assert (temp_dir(pending['id'])/'0').read_bytes() == b'abc'
        assert (await c.get('/api/relay/files/42/download')).content == b'old-content'
        result = await c.post(f"/api/relay/uploads/{pending['id']}/complete", headers=h)
        assert result.status_code == 200, result.text
        assert result.json()['file']['id'] > 1000
        assert nas.read_bytes() == b'NAS'
        backup = root/'backups/before-schema-010.db'
        with sqlite3.connect(backup) as saved:
            assert 'code' in {row[1] for row in saved.execute('PRAGMA table_info(filecodes)')}
            assert saved.execute('SELECT COUNT(*) FROM filecodes').fetchone()[0] == 3
        catalog = json.loads((root/'backups/retired-assets-010.json').read_text())
        assert catalog['filecodes'][0]['uuid_file_name'] == nas.name
        # Direct retry covers crash after migration commit but before runner registration.
        await migration.migrate()
        await execute_migrations()
        assert await FileCodes.all().count() == 3
        assert (await KeyValue.get(key='settings')).value['upload_size'] == 10_485_760
        assert (await c.get('/api/relay/session')).json()['session_id'] == identity['session_id']


async def test_failed_upgrade_rolls_back_schema_and_can_restore_backup(old_database):
    conn, root, migration = old_database
    await conn.execute_query("CREATE TRIGGER fail_update BEFORE UPDATE ON keyvalue BEGIN SELECT RAISE(ABORT, 'upgrade interrupted'); END")
    with pytest.raises(Exception, match='upgrade interrupted'):
        await execute_migrations()
    assert 'code' in {row['name'] for row in await conn.execute_query_dict('PRAGMA table_info(filecodes)')}
    assert await conn.execute_query_dict("SELECT name FROM sqlite_master WHERE name='presignuploadsession'")
    assert not await conn.execute_query_dict("SELECT * FROM migrates WHERE migration_file='migrations_010.py'")
    assert (await KeyValue.get(key='settings')).value['s3_secret_access_key'] == 'retired-secret'
    with sqlite3.connect(root/'backups/before-schema-010.db') as backup:
        assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    await conn.execute_query('DROP TRIGGER fail_update')
    await execute_migrations()
    assert 'code' not in {row['name'] for row in await conn.execute_query_dict('PRAGMA table_info(filecodes)')}


async def test_backup_failure_blocks_all_mutations(old_database, monkeypatch):
    conn, root, migration = old_database
    def fail(_):
        raise OSError('backup disk full')
    monkeypatch.setattr(migration, 'backup_database', fail)
    with pytest.raises(OSError, match='backup disk full'):
        await execute_migrations()
    assert 'code' in {row['name'] for row in await conn.execute_query_dict('PRAGMA table_info(filecodes)')}
    assert await KeyValue.filter(key='admin_file_view_presets').exists()
