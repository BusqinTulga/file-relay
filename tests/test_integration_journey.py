"""Retired public protocols cannot be revived by administrator authentication."""
import pytest
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


async def test_fresh_install_exposes_setup_in_json_api_response(client):
    for path in ('/api/v1/config', '/api/relay/session', '/admin/verify'):
        response = await client.get(path)
        assert response.status_code == 428
        assert response.json()['detail']['setup'] == '/setup'
    assert '初始化 FileRelay' in (await client.get('/')).text
