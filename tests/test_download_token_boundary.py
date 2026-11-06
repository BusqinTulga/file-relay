"""Legacy per-file tokens cannot open relay files or revive public downloads."""
import pytest
from core.utils import get_select_token

@pytest.mark.parametrize('key',['0'*64,'密钥'*32,'',None])
async def test_legacy_keys_never_open_download(initialized_client,key):
    response=await initialized_client.get('/share/download',params={'key':key or '', 'code':'007'})
    assert response.status_code==410

async def test_old_signed_keys_are_also_closed(initialized_client):
    for offset in (0,1):
        token=await get_select_token('007',offset=offset)
        assert (await initialized_client.get('/share/download',params={'key':token,'code':'007'})).status_code==410
