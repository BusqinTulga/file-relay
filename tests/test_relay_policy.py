"""Exercise real admin writes and every Relay upload stage, not patched constants."""
import asyncio
import pytest
from apps.base.models import FileCodes, RelayUpload
from apps.relay.uploads import temp_dir, final_path, used_capacity
from apps.relay.cleanup import sweep
from tests.test_api_contract import _login
from tests.test_relay import pair, upload, headers, sha


async def admin(client):
    return {'Authorization': 'Bearer ' + await _login(client)}


async def configure(client, values, auth):
    result = await client.patch('/admin/config/update', json=values, headers=auth)
    assert result.status_code == 200, result.text


async def start(client, size, name='test', chunked=True, digest=None):
    return await client.post('/api/relay/uploads', headers=await headers(client),
        json={'name': name, 'size': size, 'sha256': digest or sha(b'x' * min(size, 100)), 'chunked': chunked})


@pytest.mark.parametrize('chunked', [False, True])
async def test_ten_mb_actual_boundary_and_no_reservation_for_oversize(initialized_client, chunked):
    c = initialized_client
    auth = await admin(c)
    limit = 10_000_000
    await configure(c, {'upload_size': limit}, auth)
    await pair(c)
    public = (await c.get('/api/v1/config')).json()['detail']['config']
    settings = (await c.get('/admin/config/get', headers=auth)).json()['detail']
    overview = (await c.get('/admin/dashboard', headers=auth)).json()['detail']
    assert public['upload_size'] == settings['upload_size'] == overview['upload_size'] == limit
    for size in (limit-1, limit):
        result = await start(c, size, name=str(size), chunked=chunked)
        assert result.status_code == 200
    before = await used_capacity()
    result = await start(c, limit+1, chunked=chunked)
    assert result.status_code == 413 and str(limit) in result.json()['detail']
    assert await used_capacity() == before
    assert await RelayUpload.all().count() == 2
    assert (await start(c, 2**100)).status_code == 413
    file, _ = await upload(c, b'x'*limit, name='exact.bin', chunked=chunked)
    assert file['size'] == limit
    assert len((await c.get(f"/api/relay/files/{file['id']}/download")).content) == limit


@pytest.mark.parametrize('value', [0, -1, True, '10', 1.5, 1_000_000_001])
async def test_invalid_limits_do_not_mutate_config(initialized_client, value):
    c = initialized_client
    auth = await admin(c)
    before = (await c.get('/admin/config/get', headers=auth)).json()
    result = await c.patch('/admin/config/update', json={'upload_size': value}, headers=auth)
    assert result.status_code == 422
    assert (await c.get('/admin/config/get', headers=auth)).json() == before


async def test_reduction_cancels_unfinished_but_preserves_published_and_idempotence(initialized_client):
    c = initialized_client
    auth = await admin(c)
    await pair(c)
    file, complete = await upload(c, b'published')
    pending = (await start(c, 9, name='unfinished')).json()
    await configure(c, {'upload_size': 3}, auth)
    assert (await c.get(f"/api/relay/files/{file['id']}/download")).content == b'published'
    h = await headers(c)
    assert (await c.post(f"/api/relay/uploads/{complete['id']}/complete", headers=h)).status_code == 200
    assert (await c.post(f"/api/relay/uploads/{pending['id']}/complete", headers=h)).status_code == 413
    assert (await RelayUpload.get(id=pending['id'])).state == 'cancelled'
    await sweep()
    assert (await RelayUpload.get(id=pending['id'])).state == 'cleaned'
    assert not temp_dir(pending['id']).exists()
    await configure(c, {'upload_size': 9}, auth)
    assert (await start(c, 9, name='retry')).status_code == 200


async def test_pause_blocks_old_writes_and_publish_and_can_resume(initialized_client):
    c = initialized_client
    auth = await admin(c)
    await pair(c)
    pending = (await start(c, 3, digest=sha(b'abc'), chunked=False)).json()
    url = '/api/relay/uploads/' + pending['id']
    h = {**await headers(c), 'X-Chunk-SHA256': sha(b'abc')}
    await configure(c, {'open_upload': 0}, auth)
    assert (await start(c, 0)).status_code == 403
    assert (await c.put(url+'/content', content=b'abc', headers=h)).status_code == 403
    assert (await c.post(url+'/complete', headers=h)).status_code == 403
    assert (await c.get(url)).status_code == 200
    await configure(c, {'open_upload': 1}, auth)
    assert (await c.put(url+'/content', content=b'abc', headers=h)).status_code == 200
    assert (await c.post(url+'/complete', headers=h)).status_code == 200
    assert (await RelayUpload.get(id=pending['id'])).state == 'completed'


@pytest.mark.parametrize('change,status,cancelled', [({'upload_size': 1}, 413, True), ({'open_upload': 0}, 403, False)])
async def test_policy_changes_during_merge_are_checked_before_publish(initialized_client, monkeypatch, change, status, cancelled):
    from apps.relay import uploads
    c = initialized_client
    auth = await admin(c)
    await pair(c)
    pending = (await start(c, 3, digest=sha(b'abc'), chunked=False)).json()
    url = '/api/relay/uploads/'+pending['id']
    h = {**await headers(c), 'X-Chunk-SHA256': sha(b'abc')}
    assert (await c.put(url+'/content', content=b'abc', headers=h)).status_code == 200
    # Pause after physical merge, change the persisted policy, then let publication proceed.
    entered, release = asyncio.Event(), asyncio.Event()
    original = uploads.asyncio.to_thread
    async def pause_merge(func, *args, **kwargs):
        result = await original(func, *args, **kwargs)
        if func is uploads.merge_and_verify:
            entered.set()
            await release.wait()
        return result
    monkeypatch.setattr(uploads.asyncio, 'to_thread', pause_merge)
    task = asyncio.create_task(c.post(url+'/complete', headers=h))
    await asyncio.wait_for(entered.wait(), 3)
    await configure(c, change, auth)
    release.set()
    result = await task
    assert result.status_code == status, result.text
    assert not await FileCodes.all().count()
    row = await RelayUpload.get(id=pending['id'])
    assert row.state == ('cancelled' if cancelled else 'uploading')
    if cancelled:
        await sweep()
        assert not final_path(pending['id']).exists()


async def test_capacity_reduction_preserves_existing_reservation_and_atomic_new_admission(initialized_client):
    c = initialized_client
    auth = await admin(c)
    await pair(c)
    pending = (await start(c, 3, digest=sha(b'abc'), chunked=False)).json()
    await configure(c, {'storage_limit': 1}, auth)
    assert (await start(c, 1, name='new')).status_code == 507
    url = '/api/relay/uploads/'+pending['id']
    h = {**await headers(c), 'X-Chunk-SHA256': sha(b'abc')}
    await c.put(url+'/content', content=b'abc', headers=h)
    assert (await c.post(url+'/complete', headers=h)).status_code == 200
    assert await used_capacity() == 3
    await configure(c, {'storage_limit': 5}, auth)
    results = await asyncio.gather(start(c, 2, name='one'), start(c, 2, name='two'))
    assert sorted(r.status_code for r in results) == [200, 507]
    assert await used_capacity() == 5


async def test_admin_only_retained_api_and_exact_partial_settings(initialized_client):
    c = initialized_client
    auth = await admin(c)
    await configure(c, {'upload_size': 10_485_760}, auth)
    results = await asyncio.gather(c.patch('/admin/config/update', json={'description': 'new'}, headers=auth),
                                  c.patch('/admin/config/update', json={'notify_title': 'notice'}, headers=auth))
    assert all(r.status_code == 200 for r in results)
    stored = (await c.get('/admin/config/get', headers=auth)).json()['detail']
    assert stored['upload_size'] == 10_485_760 and stored['description'] == 'new' and stored['notify_title'] == 'notice'
    assert not {'jwt_secret', 's3_secret_access_key', 'trusted_proxies', 'server_port'} & stored.keys()
    for key in ('s3_bucket_name', 'expire_style', 'themes_select', 'server_port'):
        assert (await c.patch('/admin/config/update', json={key: 'x'}, headers=auth)).status_code == 422
    for path in ('local/lists', 'local/share', 'local/delete', 'file/policy-action', 'file/update',
                 'file/metadata', 'file/view-presets', 'file/preview', 'activities'):
        result = await c.post('/admin/'+path, json={}, headers={**auth, 'Accept': 'text/html'})
        assert result.status_code == 404 and 'application/json' in result.headers['content-type']


async def test_file_list_relay_statuses_and_batch_partial_failure(initialized_client):
    c = initialized_client
    auth = await admin(c)
    await pair(c)
    file, _ = await upload(c, b'abc', name='findme.txt')
    listing = (await c.get('/admin/file/list', params={'keyword':'findme', 'status':'waiting'}, headers=auth)).json()['detail']
    assert listing['total'] == 1 and listing['files'][0]['id'] == file['id']
    assert not {'code', 'relay_group_id', 'session_hash', 'text'} & listing['files'][0].keys()
    await c.get(f"/api/relay/files/{file['id']}/download")
    assert (await c.get('/admin/file/list', params={'status':'retry'}, headers=auth)).json()['detail']['total'] == 1
    result = await c.post('/admin/file/batch-delete', json={'ids':[file['id'], 999999]}, headers=auth)
    assert result.json()['detail']['deleted'] == [file['id']]
    assert result.json()['detail']['failed'][0]['id'] == 999999
    assert (await c.get('/admin/file/list', params={'status':'pending'}, headers=auth)).json()['detail']['total'] == 1


async def test_password_change_revokes_old_admin_but_not_device(initialized_client):
    c = initialized_client
    auth = await admin(c)
    await pair(c)
    await configure(c, {'admin_token': 'Replacement-Password-123'}, auth)
    assert (await c.get('/admin/verify', headers=auth)).status_code == 401
    assert (await c.get('/api/relay/session')).json()['paired']
    assert (await c.post('/admin/login', json={'password':'Replacement-Password-123'})).status_code == 200


async def test_download_is_attachment_for_html_and_unicode_filename(initialized_client):
    from urllib.parse import unquote
    c = initialized_client
    await pair(c)
    payload = b'<script>alert(1)</script>'
    file, _ = await upload(c, payload, name='报告.html')
    result = await c.get(f"/api/relay/files/{file['id']}/download")
    assert result.content == payload
    assert result.headers['content-disposition'].startswith('attachment;')
    assert '报告.html' in unquote(result.headers['content-disposition'])
    assert result.headers['content-type'] == 'application/octet-stream'
