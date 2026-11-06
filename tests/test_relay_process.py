"""Real uvicorn lifespan + on-disk migrations + restart + socket disconnect.

Run without sandbox network restrictions. Every subprocess uses tmp_path.
"""
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager

import httpx


@contextmanager
def running(root, log):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = {**os.environ, 'FILERELAY_DATA_ROOT': str(root), 'APP_ENV': 'development'}
    with log.open('ab') as output:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1',
                                    '--port', str(port), '--no-access-log'], env=env, stdout=output, stderr=output)
        url = f'http://127.0.0.1:{port}'
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise AssertionError(log.read_text())
                try:
                    if httpx.get(url+'/setup', timeout=.5).status_code in (200, 303):
                        break
                except httpx.RequestError:
                    pass
                time.sleep(.1)
            else:
                raise AssertionError('uvicorn did not start: '+log.read_text())
            yield url, port
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_real_startup_restart_backup_and_disconnect(tmp_path):
    root = tmp_path/'data'
    log = tmp_path/'server.log'
    payload = b'stream-payload'*2_000_000  # exceeds socket buffers, then close before response ends
    digest = hashlib.sha256(payload).hexdigest()
    with running(root, log) as (url, port), httpx.Client(base_url=url, timeout=30) as c:
        r = c.post('/setup', json={'admin_password': 'Test-Process-12345', 'confirm_password': 'Test-Process-12345',
                                  'site_name': 'FileRelay'}, headers={'Accept': 'application/json'})
        assert r.status_code == 200, r.text
        bootstrap = c.get('/api/relay/session').json()
        h = {'Origin': url, 'X-Relay-CSRF': bootstrap['csrf']}
        r = c.post('/api/relay/pair', json={'passcode': '001'}, headers=h)
        assert r.status_code == 200, r.text
        identity = c.get('/api/relay/session').json()
        h['X-Relay-CSRF'] = identity['csrf']
        upload = c.post('/api/relay/uploads', json={'name': '进程.bin', 'size': len(payload), 'sha256': digest,
                                                   'chunked': False}, headers=h).json()
        r = c.put('/api/relay/uploads/'+upload['id']+'/content', content=payload, headers={**h, 'X-Chunk-SHA256': digest})
        assert r.status_code == 200, r.text
        r = c.post('/api/relay/uploads/'+upload['id']+'/complete', headers=h)
        assert r.status_code == 200, r.text
        file = r.json()['file']
        cookies = dict(c.cookies)
        # Use TCP directly: ASGI in-process clients buffer the whole response and cannot prove disconnect behavior.
        with socket.create_connection(('127.0.0.1', port), timeout=5) as stream:
            request = f"GET /api/relay/files/{file['id']}/download HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nCookie: relay_device={cookies['relay_device']}\r\nConnection: close\r\n\r\n"
            stream.sendall(request.encode())
            received = stream.recv(4096)
            assert b'200 OK' in received
        time.sleep(.3)
        assert c.get('/api/relay/files/'+str(file['id'])).json()['first_sent'] is None
    assert (root/'filecodebox.db').exists()
    with running(root, log) as (url, _), httpx.Client(base_url=url, cookies=cookies, timeout=30) as c:
        restored = c.get('/api/relay/session').json()
        assert restored['paired'] and restored['device_id'] == identity['device_id']
        r = c.get('/api/relay/files/'+str(file['id'])+'/download')
        assert r.content == payload
        sent = c.get('/api/relay/files/'+str(file['id'])).json()
        assert sent['first_sent'] and sent['expires'] < file['expires']
    backup = tmp_path/'backup'
    shutil.copytree(root, backup)  # quiesced database and matching blobs
    with running(backup, log) as (url, _), httpx.Client(base_url=url, cookies=cookies) as c:
        assert c.get('/api/relay/session').json()['paired']
        restored = c.get('/api/relay/files/'+str(file['id'])).json()
        assert restored['expires'] == sent['expires'] and restored['sha256'] == digest
        assert c.get('/').status_code == 200
    import sqlite3
    with sqlite3.connect(backup/'filecodebox.db') as db:
        assert db.execute('SELECT COUNT(*) FROM migrates').fetchone()[0] == 9

    # Persist a pending deletion plus an abandoned lease, then exercise actual startup cleanup.
    with sqlite3.connect(backup/'filecodebox.db') as db:
        db.execute("UPDATE filecodes SET delete_state='pending' WHERE id=?", (file['id'],))
        db.execute("INSERT INTO downloadattempt(id,file_id,group_id,state,lease_until,protect_until) "
                   "VALUES('crashed',?,1,'active',0,0)", (file['id'],))
    with running(backup, log) as (url, _), httpx.Client(base_url=url, cookies=cookies) as c:
        assert c.get('/api/relay/files/'+str(file['id'])+'/download').status_code == 404
        for _ in range(50):
            with sqlite3.connect(backup/'filecodebox.db') as db:
                if db.execute('SELECT COUNT(*) FROM filecodes WHERE id=?', (file['id'],)).fetchone()[0] == 0:
                    break
            time.sleep(.1)
        else:
            raise AssertionError('pending deletion not recovered at startup')
        assert not (backup/'relay/files'/upload['id']).exists()
