"""MCP remains closed even with a valid administrator token."""
import pytest
from tests.test_api_contract import _login

@pytest.mark.parametrize('method',['initialize','tools/list','tools/call'])
async def test_mcp_closed(initialized_client,method):
    token=await _login(initialized_client)
    for headers in ({},{'Authorization':f'Bearer {token}'},{'Origin':'https://evil.test'}):
        r=await initialized_client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':method},headers=headers)
        assert r.status_code==410
