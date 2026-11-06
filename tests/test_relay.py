"""Real Cookie/CSRF chains and persisted state, no injected administrator bypass."""
import asyncio
import hashlib
from contextlib import asynccontextmanager
from unittest.mock import patch

import httpx
import pytest

import main
from apps.base.models import DownloadAttempt, FileCodes, PairingRequest, RelayDevice, RelayUpload
from apps.relay import config
from apps.relay.auth import _pair_limits
from apps.relay.cleanup import sweep
from apps.relay.files import download_response
from apps.relay.uploads import final_path, temp_dir


def sha(data):
    return hashlib.sha256(data).hexdigest()


async def headers(client):
    session = (await client.get('/api/relay/session')).json()
    return {'Origin': 'http://test', 'X-Relay-CSRF': session['csrf']}


async def pair(client, code='007'):
    return await client.post('/api/relay/pair', json={'passcode': code}, headers=await headers(client))


@asynccontextmanager
async def browser():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
        yield client


async def upload(client, data=b'hello', name='中文照片.txt', chunked=False):
    h = await headers(client)
    result = await client.post('/api/relay/uploads', json={'name': name, 'size': len(data), 'sha256': sha(data),
                                                         'chunked': chunked}, headers=h)
    assert result.status_code == 200, result.text
    session = result.json()
    chunk_size = session['chunk_size']
    for index in range(max(1, (len(data) + chunk_size - 1) // chunk_size)):
        block = data[index*chunk_size:(index+1)*chunk_size]
        response = await client.put(f"/api/relay/uploads/{session['id']}/chunks/{index}", content=block,
                                    headers={**h, 'X-Chunk-SHA256': sha(block)})
        assert response.status_code == 200, response.text
    response = await client.post(f"/api/relay/uploads/{session['id']}/complete", headers=h)
    assert response.status_code == 200, response.text
    return response.json()['file'], session


@pytest.fixture(autouse=True)
def clear_limits():
    _pair_limits.clear()


async def test_pair_approval_isolation_and_idempotence(initialized_client):
    a = initialized_client
    assert (await pair(a)).json()['paired']
    async with browser() as b, browser() as c, browser() as d:
        assert (await pair(b)).json()['paired']
        pending = (await pair(c)).json()
        assert pending['status'] == 'pending'
        assert (await c.get('/api/relay/files')).status_code == 401
        assert (await pair(d, '7')).json()['paired']
        file, session = await upload(a)
        assert len((await b.get('/api/relay/files')).json()['files']) == 1
        assert (await d.get(f"/api/relay/files/{file['id']}/download")).status_code == 404
        assert (await d.get(f"/api/relay/uploads/{session['id']}")).status_code == 404
        h = await headers(a)
        url = '/api/relay/pairing/requests/' + pending['request_id']
        results = await asyncio.gather(*(a.post(url, json={'approve': True}, headers=h) for _ in range(2)))
        assert [r.json()['status'] for r in results] == ['approved', 'approved']
        joined = await c.post('/api/relay/pairing/status', headers=await headers(c))
        assert joined.json()['paired']
        assert await RelayDevice.filter(group_id=(await RelayDevice.get(id=joined.json()['device_id'])).group_id).count() == 3
        assert len((await c.get('/api/relay/files')).json()['files']) == 1
        denied = await d.post(url, json={'approve': True}, headers=await headers(d))
        assert denied.status_code == 404


async def test_pairing_reject_timeout_and_pending_cannot_upload(initialized_client):
    a = initialized_client
    await pair(a)
    async with browser() as b, browser() as c:
        await pair(b)
        p = (await pair(c)).json()
        forbidden = await c.post('/api/relay/uploads', json={'name': 'x', 'size': 0, 'sha256': sha(b'')}, headers=await headers(c))
        assert forbidden.status_code == 401
        await a.post('/api/relay/pairing/requests/' + p['request_id'], json={'approve': False}, headers=await headers(a))
        assert (await c.post('/api/relay/pairing/status', headers=await headers(c))).json()['status'] == 'rejected'
        p = (await pair(c)).json()
        await PairingRequest.filter(id=p['request_id']).update(expires=config.now()-1)
        assert (await c.post('/api/relay/pairing/status', headers=await headers(c))).json()['status'] == 'expired'


@pytest.mark.parametrize('value', ['', '12345', '１', 'a12', 7, '00\n'])
async def test_invalid_passcodes(initialized_client, value):
    assert (await pair(initialized_client, value)).status_code == 422


async def test_csrf_origins_and_admin_not_device(initialized_client):
    a = initialized_client
    assert (await a.post('/api/relay/pair', json={'passcode': '7'})).status_code == 403
    h = await headers(a)
    assert (await a.post('/api/relay/pair', json={'passcode': '7'}, headers={**h, 'Origin': 'https://evil.test'})).status_code == 403
    assert (await a.get('/api/relay/files', headers={'Authorization': 'Bearer administrator'})).status_code == 401
    await pair(a)
    assert (await a.delete('/api/relay/files/1')).status_code == 403
    for name in ('relay_device', 'relay_csrf'):
        assert name in a.cookies
    r = await a.get('/api/relay/session')
    assert 'no-store' in r.headers['cache-control']


async def test_repair_migrates_only_owned_valid_files_preserving_times(initialized_client):
    a = initialized_client
    await pair(a)
    first, _ = await upload(a, b'one')
    async with browser() as b:
        await pair(b)
        other, _ = await upload(b, b'two')
        # Start a retry window, then repair; only the uploader's file follows.
        assert (await a.get(f"/api/relay/files/{first['id']}/download")).content == b'one'
        before = await FileCodes.get(id=first['id'])
        old_cookie = a.cookies['relay_device']
        result = await pair(a, '001')
        assert result.json()['paired']
        assert old_cookie != a.cookies['relay_device']
        own = (await a.get('/api/relay/files')).json()['files']
        assert [f['id'] for f in own] == [first['id']]
        assert own[0]['expires'] == before.relay_expires
        assert own[0]['published'] == before.published
        assert [f['id'] for f in (await b.get('/api/relay/files')).json()['files']] == [other['id']]
        assert (await b.get(f"/api/relay/files/{first['id']}/download")).status_code == 404
        async with browser() as old:
            old.cookies['relay_device'] = old_cookie
            assert (await old.get('/api/relay/files')).status_code == 401


async def test_pending_repair_does_not_move_files_or_old_uploads(initialized_client):
    a = initialized_client
    await pair(a, '1')
    file, _ = await upload(a)
    async with browser() as b, browser() as c:
        await pair(b, '2')
        await pair(c, '2')
        p = (await pair(a, '2')).json()
        group_before = (await FileCodes.get(id=file['id'])).relay_group_id
        assert (await FileCodes.get(id=file['id'])).relay_group_id == group_before
        await b.post('/api/relay/pairing/requests/' + p['request_id'], json={'approve': True}, headers=await headers(b))
        assert (await a.post('/api/relay/pairing/status', headers=await headers(a))).json()['paired']
        assert (await FileCodes.get(id=file['id'])).relay_group_id != group_before


@pytest.mark.parametrize('data,chunked', [(b'', False), (b'abc', False), (b'x'*(config.CHUNK_SIZE+17), True)])
async def test_upload_integrity_idempotence_and_zero(initialized_client, data, chunked):
    a = initialized_client
    await pair(a)
    file, session = await upload(a, data, chunked=chunked)
    assert file['size'] == len(data) and file['sha256'] == sha(data)
    assert final_path(session['id']).read_bytes() == data
    h = await headers(a)
    responses = await asyncio.gather(*(a.post(f"/api/relay/uploads/{session['id']}/complete", headers=h) for _ in range(3)))
    assert all(r.json()['file']['id'] == file['id'] for r in responses)
    assert await FileCodes.all().count() == 1


async def test_bad_chunk_missing_hash_and_quota(initialized_client):
    a = initialized_client
    await pair(a)
    h = await headers(a)
    request = {'name': 'a.txt', 'size': 3, 'sha256': sha(b'abc')}
    session = (await a.post('/api/relay/uploads', json=request, headers=h)).json()
    url = f"/api/relay/uploads/{session['id']}"
    assert (await a.post(url+'/complete', headers=h)).status_code == 422
    assert (await a.put(url+'/chunks/0', content=b'abcd', headers={**h, 'X-Chunk-SHA256': sha(b'abcd')})).status_code == 422
    assert (await a.put(url+'/chunks/0', content=b'abc', headers={**h, 'X-Chunk-SHA256': sha(b'bad')})).status_code == 422
    assert (await a.put(url+'/chunks/-1', content=b'abc', headers=h)).status_code == 422
    assert (await a.put(url+'/content', content=b'abc', headers={**h, 'X-Chunk-SHA256': sha(b'abc')})).status_code == 200
    (temp_dir(session['id'])/'0').write_bytes(b'bad')
    assert (await a.post(url+'/complete', headers=h)).status_code == 422
    from core.settings import settings
    with patch.dict(settings.user_config, {'storage_limit': 3}):
        assert (await a.post('/api/relay/uploads', json={**request, 'name': 'b'}, headers=h)).status_code == 507
    assert await FileCodes.all().count() == 0
    assert (await a.post('/api/relay/uploads', json={**request, 'size': config.MAX_FILE+1}, headers=h)).status_code == 413


async def test_full_hash_disambiguates_middle_content(initialized_client):
    a = initialized_client
    await pair(a)
    h = await headers(a)
    first = b'x'*1024+b'a'+b'x'*1024
    second = b'x'*1024+b'b'+b'x'*1024
    ids = []
    for data in (first, second):
        r = await a.post('/api/relay/uploads', json={'name': 'same.bin', 'size': len(data), 'sha256': sha(data)}, headers=h)
        ids.append(r.json()['id'])
    assert ids[0] != ids[1]


async def test_download_countdown_range_head_and_prefetch(initialized_client):
    a = initialized_client
    await pair(a)
    file, _ = await upload(a, b'abcdef')
    url = f"/api/relay/files/{file['id']}/download"
    assert (await a.head(url)).status_code == 200
    r = await a.get(url, headers={'Range': 'bytes=1-3'})
    assert r.status_code == 206 and r.content == b'bcd'
    await a.get(url, headers={'Sec-Purpose': 'prefetch'})
    assert (await FileCodes.get(id=file['id'])).first_sent is None
    with patch.object(config, 'now', return_value=file['published']+100):
        assert (await a.get(url)).content == b'abcdef'
    first = await FileCodes.get(id=file['id'])
    assert first.relay_expires == file['published']+700
    await a.get(url)
    assert (await FileCodes.get(id=file['id'])).relay_expires == first.relay_expires
    with patch.object(config, 'now', return_value=first.relay_expires+1):
        assert (await a.get(url)).status_code == 404
        assert not (await a.get('/api/relay/files')).json()['files']


async def test_delete_lease_and_retryable_failure(initialized_client):
    a = initialized_client
    await pair(a)
    file, session = await upload(a)
    stamp = config.now()
    attempt = await DownloadAttempt.create(id='lease', file_id=file['id'], group_id=1,
                                          lease_until=stamp+90, protect_until=stamp+100)
    assert (await a.delete(f"/api/relay/files/{file['id']}", headers=await headers(a))).status_code == 200
    assert (await a.get(f"/api/relay/files/{file['id']}/download")).status_code == 404
    await sweep()
    assert final_path(session['id']).exists()
    await DownloadAttempt.filter(id=attempt.id).update(lease_until=stamp-1)
    with patch('pathlib.Path.unlink', side_effect=OSError('disk failure')):
        await sweep()
    row = await FileCodes.get(id=file['id'])
    assert row.delete_state == 'pending' and row.cleanup_error
    await sweep()
    assert not await FileCodes.filter(id=file['id']).exists()
    assert not final_path(session['id']).exists()


async def test_disconnect_and_slow_send_heartbeat(initialized_client):
    a = initialized_client
    await pair(a)
    file, _ = await upload(a, b'x'*300000)
    response = await download_response(file['id'])
    disconnected = asyncio.Event()
    sent = asyncio.Event()
    async def receive():
        await disconnected.wait()
        return {'type': 'http.disconnect'}
    async def send(message):
        if message['type'] == 'http.response.body' and message.get('more_body'):
            sent.set()
            await asyncio.Event().wait()
    with patch.object(config, 'LEASE_HEARTBEAT', .01):
        task = asyncio.create_task(response({}, receive, send))
        await sent.wait()
        initial = (await DownloadAttempt.get(id=response.attempt.id)).lease_until
        await asyncio.sleep(.04)
        assert (await DownloadAttempt.get(id=response.attempt.id)).lease_until > initial
        disconnected.set()
        await task
    assert (await FileCodes.get(id=file['id'])).first_sent is None
    assert (await DownloadAttempt.get(id=response.attempt.id)).state == 'ended'


@pytest.mark.parametrize('path', ['/share/file','/share/select','/share/download','/chunk/upload', '/presign', '/api/presign/confirm','/mcp'])
async def test_old_routes_closed(initialized_client, path):
    for method in ('GET', 'POST'):
        r = await initialized_client.request(method, path, headers={'Accept': 'text/html'})
        assert r.status_code == 410 and 'text/html' not in r.headers['content-type']


async def test_missing_api_never_spa(initialized_client):
    r = await initialized_client.get('/api/relay/missing', headers={'Accept': 'text/html'})
    assert r.status_code == 404 and 'application/json' in r.headers['content-type']


async def test_pair_rate_limit_does_not_throttle_lists(initialized_client):
    a = initialized_client
    await pair(a)
    for _ in range(9):
        assert (await pair(a)).status_code == 200
    assert (await pair(a)).status_code == 429
    for _ in range(12):
        assert (await a.get('/api/relay/files')).status_code == 200


async def test_repair_invalidates_unfinished_upload_and_stale_tab(initialized_client):
    a = initialized_client
    await pair(a)
    original = (await a.get('/api/relay/session')).json()
    h = await headers(a)
    item = (await a.post('/api/relay/uploads', json={'name': 'old', 'size': 1, 'sha256': sha(b'x')}, headers=h)).json()
    await a.put(f"/api/relay/uploads/{item['id']}/content", content=b'x', headers={**h, 'X-Chunk-SHA256': sha(b'x')})
    await pair(a, '2')
    new_headers = await headers(a)
    assert (await a.get('/api/relay/files', headers={'X-Relay-Session': original['session_id']})).status_code == 409
    assert (await a.post(f"/api/relay/uploads/{item['id']}/complete", headers=new_headers)).status_code == 404
    assert await FileCodes.all().count() == 0
    assert (await RelayUpload.get(id=item['id'])).state == 'cancelled'
    await sweep()
    assert not temp_dir(item['id']).exists()


async def test_admin_deletion_and_download_obey_relay_rules(initialized_client):
    from tests.test_api_contract import _login
    a = initialized_client
    await pair(a)
    file, session = await upload(a)
    token = await _login(a)
    h = {'Authorization': 'Bearer '+token}
    r = await a.get('/admin/file/download', params={'id': file['id']}, headers=h)
    assert r.content == b'hello'
    assert (await FileCodes.get(id=file['id'])).first_sent is not None
    r = await a.patch('/admin/file/update', json={'id': file['id'], 'expired_at': '2099-01-01T00:00:00'}, headers=h)
    assert r.status_code == 404
    r = await a.patch('/admin/file/policy-action', json={'id': file['id'], 'action': 'make_permanent'}, headers=h)
    assert r.status_code == 404
    dashboard = (await a.get('/admin/dashboard', headers=h)).json()['detail']
    assert dashboard['storage_limit'] == config.MAX_STORAGE
    assert dashboard['occupied_bytes'] == file['size']
    r = await a.request('DELETE', '/admin/file/delete', json={'id': file['id']}, headers=h)
    assert r.status_code == 200
    assert (await FileCodes.get(id=file['id'])).delete_state == 'pending'
    await sweep()
    assert not final_path(session['id']).exists()


async def test_disk_shortage_preserves_existing_files(initialized_client):
    from types import SimpleNamespace
    a = initialized_client
    await pair(a)
    existing, _ = await upload(a)
    with patch('apps.relay.uploads.shutil.disk_usage', return_value=SimpleNamespace(free=1)):
        result = await a.post('/api/relay/uploads', json={'name': 'new', 'size': 1, 'sha256': sha(b'x')}, headers=await headers(a))
    assert result.status_code == 507
    assert await FileCodes.filter(id=existing['id']).exists()


async def test_corrupt_full_hash_rejected_and_cancel_cleanup_retries(initialized_client):
    a = initialized_client
    await pair(a)
    h = await headers(a)
    item = (await a.post('/api/relay/uploads', json={'name': 'wrong', 'size': 3, 'sha256': sha(b'bad')}, headers=h)).json()
    await a.put(f"/api/relay/uploads/{item['id']}/content", content=b'abc', headers={**h, 'X-Chunk-SHA256': sha(b'abc')})
    assert (await a.post(f"/api/relay/uploads/{item['id']}/complete", headers=h)).status_code == 422
    await a.delete(f"/api/relay/uploads/{item['id']}", headers=h)
    with patch('apps.relay.cleanup.clear_chunks', side_effect=OSError('disk failed')):
        await sweep()
    assert (await RelayUpload.get(id=item['id'])).state == 'cancelled'
    await sweep()
    assert (await RelayUpload.get(id=item['id'])).state == 'cleaned'


async def test_retry_after_lost_complete_response_reuses_published_result(initialized_client):
    a = initialized_client
    await pair(a)
    file, original = await upload(a, b'once', 'once.txt')
    r = await a.post('/api/relay/uploads', json={'name': 'once.txt', 'size': 4, 'sha256': sha(b'once')}, headers=await headers(a))
    assert r.json()['state'] == 'completed'
    assert r.json()['id'] == original['id']
    assert r.json()['file']['id'] == file['id']
    assert await FileCodes.all().count() == 1
    await a.delete(f"/api/relay/files/{file['id']}", headers=await headers(a))
    r = await a.post('/api/relay/uploads', json={'name': 'once.txt', 'size': 4, 'sha256': sha(b'once')}, headers=await headers(a))
    assert r.json()['id'] != original['id']
