"""The former ordinary upload proxy is closed after relay uploads are connected."""
import pytest
from tests.test_api_contract import _login

@pytest.mark.parametrize('prefix',['/presign','/api/presign'])
@pytest.mark.parametrize('suffix',['/upload/init','/upload/proxy/old','/upload/status/old',
    '/upload/confirm/old','/upload/cancel/old'])
async def test_presign_protocol_closed(initialized_client,prefix,suffix):
    token=await _login(initialized_client)
    for h in ({},{'Authorization':f'Bearer {token}'}):
        response=await initialized_client.post(prefix+suffix,json={},headers=h)
        assert response.status_code==410
