#!/usr/bin/env python3
"""Disposable local image + volume smoke test. Never uses a configured NAS/Compose volume."""
import hashlib
import json
import subprocess
import sys
import time
import uuid

import httpx


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def verify(image):
    suffix = uuid.uuid4().hex[:12]
    volume, name = 'filerelay-test-'+suffix, 'filerelay-test-'+suffix
    docker('volume', 'create', volume)

    def start():
        docker('run', '-d', '--name', name, '-p', '127.0.0.1::12345', '-e', 'APP_ENV=development',
               '-v', volume+':/app/data', image)
        mapping = json.loads(docker('inspect', name))[0]['NetworkSettings']['Ports']['12345/tcp'][0]
        url = 'http://127.0.0.1:'+mapping['HostPort']
        for _ in range(120):
            try:
                if httpx.get(url+'/setup', timeout=1).status_code in (200, 303):
                    return url
            except httpx.RequestError:
                pass
            time.sleep(.25)
        raise AssertionError(docker('logs', name))

    try:
        url = start()
        with httpx.Client(base_url=url, timeout=30) as client:
            r = client.post('/setup', json={'admin_password': 'Container-Test-12345',
                'confirm_password': 'Container-Test-12345', 'site_name': 'FileRelay'}, headers={'Accept': 'application/json'})
            assert r.status_code == 200, r.text
            session = client.get('/api/relay/session').json()
            h = {'Origin': url, 'X-Relay-CSRF': session['csrf']}
            assert client.post('/api/relay/pair', json={'passcode': '007'}, headers=h).json()['paired']
            session = client.get('/api/relay/session').json()
            h['X-Relay-CSRF'] = session['csrf']
            content = b'FileRelay local image verification'
            sha = hashlib.sha256(content).hexdigest()
            upload = client.post('/api/relay/uploads', json={'name': 'image-check.txt', 'size': len(content),
                                                            'sha256': sha, 'chunked': False}, headers=h).json()
            r = client.put('/api/relay/uploads/'+upload['id']+'/content', content=content,
                           headers={**h, 'X-Chunk-SHA256': sha})
            assert r.status_code == 200, r.text
            r = client.post('/api/relay/uploads/'+upload['id']+'/complete', headers=h)
            assert r.status_code == 200, r.text
            file = r.json()['file']
            login = client.post('/admin/login', json={'password': 'Container-Test-12345'})
            auth = {'Authorization': 'Bearer ' + login.json()['detail']['token']}
            saved = client.patch('/admin/config/update', json={'upload_size': 10_000_000}, headers=auth)
            assert saved.status_code == 200, saved.text
            assert client.get('/api/v1/config').json()['detail']['config']['upload_size'] == 10_000_000
            denied = client.post('/api/relay/uploads', json={'name': 'oversize.bin', 'size': 10_000_001,
                'sha256': sha, 'chunked': True}, headers=h)
            assert denied.status_code == 413, denied.text
            assert client.get('/admin/local/lists', headers=auth).status_code == 404
            assert client.get(f"/api/relay/files/{file['id']}/download").content == content
            before = client.get(f"/api/relay/files/{file['id']}").json()
            cookies = dict(client.cookies)
            assert client.get('/').status_code == 200
            assert client.get('/share/download').status_code == 410
        docker('exec', name, 'sh', '-c', 'test -f /app/themes/2024/index.html && test -f /app/apps/relay/auth.py')
        docker('exec', name, 'python', '-c', """import sqlite3
from pathlib import Path
with sqlite3.connect('/app/data/filecodebox.db') as db:
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not {'uploadchunk', 'presignuploadsession', 'storagereservation'} & tables
    columns = {row[1] for row in db.execute('PRAGMA table_info(filecodes)')}
    assert not {'code', 'text', 'expired_at', 'expired_count', 'file_path'} & columns
assert Path('/app/data/backups/before-schema-010.db').is_file()
""")
        docker('rm', '-f', name)
        url = start()
        with httpx.Client(base_url=url, cookies=cookies) as client:
            restored = client.get('/api/relay/session').json()
            assert restored['device_id'] == session['device_id']
            assert client.get('/api/v1/config').json()['detail']['config']['upload_size'] == 10_000_000
            after = client.get(f"/api/relay/files/{file['id']}").json()
            assert after['expires'] == before['expires'] and after['sha256'] == sha
            assert client.get(f"/api/relay/files/{file['id']}/download").content == content
        print('PASS: local frontend/backend, setup, Cookie auth, upload/SHA256, native download, retired routes, volume/container recreation, persisted deadline and configured upload limit')
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)


if __name__ == '__main__':
    verify(sys.argv[1] if len(sys.argv) > 1 else 'file-relay:verification')
