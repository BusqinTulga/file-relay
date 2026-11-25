"""Retired public protocols cannot be revived by administrator authentication."""
from pathlib import Path

import pytest
from apps.base import pages
from tests.test_api_contract import _login

@pytest.mark.parametrize('path', ['/share/text','/share/file','/share/select','/share/metadata',
    '/share/download','/chunk/upload/init','/chunk/upload/chunk/x/0',
    '/chunk/upload/complete/x','/chunk/upload/status/x'])
async def test_retired_protocols_are_closed(initialized_client,path):
    token=await _login(initialized_client)
    for authorization in ({},{'Authorization':f'Bearer {token}'}):
        for method in ('GET','POST','PUT','DELETE','HEAD'):
            response=await initialized_client.request(method,path,headers=authorization)
            assert response.status_code==410

async def test_admin_still_requires_own_token(initialized_client):
    assert (await initialized_client.get('/admin/file/list')).status_code==401


async def test_fresh_install_exposes_setup_in_json_api_response(client, monkeypatch):
    for path in ('/api/v1/config', '/api/relay/session', '/admin/verify'):
        response = await client.get(path)
        assert response.status_code == 428
        assert response.json()['detail']['setup'] == '/setup'
    setup_page = await client.get('/')
    assert '初始化文件快传' in setup_page.text
    assert 'FileRelay／文件快传' in setup_page.text
    assert 'rel="icon" type="image/png" href="/assets/logo_small.png"' in setup_page.text
    assert "img-src 'self'" in setup_page.headers['content-security-policy']

    public_dir = Path(__file__).resolve().parents[1] / 'frontend' / 'public'
    monkeypatch.setattr(pages, 'resolve_theme_root', lambda: public_dir)
    icon = await client.get('/assets/logo_small.png', headers={'Accept': 'image/png'})
    assert icon.status_code == 200
    assert icon.headers['content-type'] == 'image/png'
    assert icon.content == (public_dir / 'assets/logo_small.png').read_bytes()


async def test_setup_language_survives_validation_and_success(client):
    response = await client.get('/', headers={'Accept-Language': 'ja-JP,en-US;q=0.9'})
    assert '<html lang="ja-JP">' in response.text
    response = await client.get('/setup?lang=en-US', headers={'Accept-Language': 'ja-JP'})
    assert '<title>Set up FileRelay</title>' in response.text

    form = {'lang': 'en-US', 'admin_password': 'Setup-Test-123', 'confirm_password': 'different'}
    response = await client.post('/setup', data=form)
    assert response.status_code == 400
    assert 'The administrator passwords do not match.' in response.text

    form['confirm_password'] = form['admin_password']
    response = await client.post('/setup', data=form)
    assert response.status_code == 200
    assert '<title>Setup complete</title>' in response.text
    assert 'href="/?lang=en-US"' in response.text
    assert 'rel="icon" type="image/png" href="/assets/logo_small.png"' in response.text


async def test_setup_preserves_admin_password_whitespace(client):
    password = '  Setup-Test-123  '
    response = await client.post('/setup', data={'admin_password': password, 'confirm_password': password})
    assert response.status_code == 200

    response = await client.post('/admin/login', json={'password': password})
    assert response.status_code == 200
    assert response.json()['detail']['token']


@pytest.mark.parametrize('locale,limit_error,password_error', [
    ('zh-CN', '单文件上限必须大于 0 且不能超过 5 GB', '密码错误'),
    ('en-US', 'The single-file limit must be greater than 0 and no greater than 5 GB.', 'Incorrect password.'),
    ('ja-JP', '1ファイルの上限は0より大きく、5 GB 以下にしてください。', 'パスワードが正しくありません。'),
])
async def test_api_localizes_errors_for_selected_language(initialized_client, locale, limit_error, password_error):
    token = await _login(initialized_client)
    response = await initialized_client.patch(
        '/admin/config/update',
        json={'upload_size': 6_000_000_000},
        headers={'Authorization': f'Bearer {token}', 'Accept-Language': locale},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == limit_error

    response = await initialized_client.post(
        '/admin/login', json={'password': 'incorrect'}, headers={'Accept-Language': locale},
    )
    assert response.status_code == 401
    assert response.json()['detail'] == password_error
