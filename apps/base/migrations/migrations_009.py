"""FileRelay v1 schema. Fresh installs run all migrations; never rebuild on startup."""
from tortoise import connections


async def migrate():
    conn = connections.get("default")
    # Also safe to retry if a process stopped between ALTER statements.
    columns = {row["name"] for row in await conn.execute_query_dict("PRAGMA table_info(filecodes)")}
    additions = {
        "relay_group_id": "INT", "uploader_device_id": "VARCHAR(36)",
        "published": "REAL", "relay_expires": "REAL", "first_sent": "REAL",
        "delete_state": "VARCHAR(16) NOT NULL DEFAULT 'active'",
        "cleanup_error": "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in additions.items():
        if name not in columns:
            await conn.execute_script(f'ALTER TABLE filecodes ADD COLUMN "{name}" {definition};')
    await conn.execute_script("""
    CREATE INDEX IF NOT EXISTS idx_relay_file_group ON filecodes(relay_group_id);
    CREATE INDEX IF NOT EXISTS idx_relay_file_device ON filecodes(uploader_device_id);
    CREATE INDEX IF NOT EXISTS idx_relay_file_expiry ON filecodes(relay_expires);
    CREATE TABLE IF NOT EXISTS relaygroup (
      id INTEGER PRIMARY KEY AUTOINCREMENT, passcode VARCHAR(4) NOT NULL UNIQUE, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS relaydevice (id VARCHAR(36) PRIMARY KEY, group_id INT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_relay_device_group ON relaydevice(group_id);
    CREATE TABLE IF NOT EXISTS relaysession (
      token_hash VARCHAR(64) PRIMARY KEY, device_id VARCHAR(36) NOT NULL,
      csrf VARCHAR(64) NOT NULL, valid INT NOT NULL DEFAULT 1);
    CREATE INDEX IF NOT EXISTS idx_relay_session_device ON relaysession(device_id);
    CREATE TABLE IF NOT EXISTS pairingrequest (
      id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) NOT NULL UNIQUE, group_id INT NOT NULL,
      original_session VARCHAR(64), status VARCHAR(16) NOT NULL DEFAULT 'pending',
      expires REAL NOT NULL, confirmed_by VARCHAR(36), handled REAL);
    CREATE INDEX IF NOT EXISTS idx_pairing_group ON pairingrequest(group_id);
    CREATE INDEX IF NOT EXISTS idx_pairing_expiry ON pairingrequest(expires);
    CREATE TABLE IF NOT EXISTS relayupload (
      id VARCHAR(36) PRIMARY KEY, group_id INT NOT NULL, device_id VARCHAR(36) NOT NULL,
      session_hash VARCHAR(64) NOT NULL, name VARCHAR(255) NOT NULL, size BIGINT NOT NULL,
      sha256 VARCHAR(64) NOT NULL, chunk_size INT NOT NULL, state VARCHAR(16) NOT NULL DEFAULT 'uploading',
      expires REAL NOT NULL, file_id INT, error TEXT NOT NULL DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_relay_upload_group ON relayupload(group_id);
    CREATE INDEX IF NOT EXISTS idx_relay_upload_device ON relayupload(device_id);
    CREATE INDEX IF NOT EXISTS idx_relay_upload_state ON relayupload(state);
    CREATE INDEX IF NOT EXISTS idx_relay_upload_expiry ON relayupload(expires);
    CREATE TABLE IF NOT EXISTS relaychunk (
      id INTEGER PRIMARY KEY AUTOINCREMENT, upload_id VARCHAR(36) NOT NULL,
      "index" INT NOT NULL, size INT NOT NULL, sha256 VARCHAR(64) NOT NULL,
      UNIQUE(upload_id, "index"));
    CREATE TABLE IF NOT EXISTS downloadattempt (
      id VARCHAR(36) PRIMARY KEY, file_id INT NOT NULL, group_id INT NOT NULL,
      state VARCHAR(16) NOT NULL DEFAULT 'active', lease_until REAL NOT NULL,
      protect_until REAL NOT NULL, completed REAL);
    CREATE INDEX IF NOT EXISTS idx_download_file ON downloadattempt(file_id);
    CREATE INDEX IF NOT EXISTS idx_download_lease ON downloadattempt(lease_until);
    """)
