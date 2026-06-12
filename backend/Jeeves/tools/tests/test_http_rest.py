"""Custom REST integration: SSRF guard, request building, executor."""
from types import SimpleNamespace

import pytest

from Jeeves.tools.http_rest import (
    _build_request, assert_safe_url, call_http_rest, RestError,
)


def _card(base_url='https://api.example.com', auth=None, tools=None):
    return SimpleNamespace(
        transport_type='http_rest',
        mcp_server_url=base_url,
        auth_config={'base_url': base_url, 'auth': auth or {}},
        tools_schema=tools or [],
    )


class TestSSRFGuard:
    def test_blocks_non_https(self):
        with pytest.raises(RestError):
            assert_safe_url('http://api.example.com/')

    def test_blocks_loopback(self):
        with pytest.raises(RestError):
            assert_safe_url('https://127.0.0.1/')

    def test_blocks_private_range(self):
        with pytest.raises(RestError):
            assert_safe_url('https://10.0.0.5/')

    def test_blocks_cloud_metadata(self):
        with pytest.raises(RestError):
            assert_safe_url('https://169.254.169.254/latest/meta-data/')

    def test_allows_public_https(self):
        assert_safe_url('https://api.github.com/')  # resolves to a public IP


class TestBuildRequest:
    def test_path_query_body_and_bearer_auth(self):
        card = _card(auth={'type': 'bearer', 'credential_key': 'token'})
        entry = {
            'name': 'update_contact',
            'request': {'method': 'POST', 'path': '/v1/contacts/{id}',
                        'query': ['notify'], 'body': ['email']},
        }
        method, url, headers, body = _build_request(
            card, entry,
            {'id': 42, 'notify': 'true', 'email': 'a@b.com'},
            {'token': 'secret'})
        assert method == 'POST'
        assert url == 'https://api.example.com/v1/contacts/42?notify=true'
        assert headers['Authorization'] == 'Bearer secret'
        assert body == {'email': 'a@b.com'}

    def test_query_auth_in_url(self):
        card = _card(auth={'type': 'query', 'param': 'key', 'credential_key': 'api_key'})
        entry = {'name': 'list', 'request': {'method': 'GET', 'path': '/items'}}
        _, url, _, _ = _build_request(card, entry, {}, {'api_key': 'abc'})
        assert url == 'https://api.example.com/items?key=abc'

    def test_custom_header_auth(self):
        card = _card(auth={'type': 'header', 'header': 'X-Api-Key',
                           'prefix': '', 'credential_key': 'api_key'})
        entry = {'name': 'x', 'request': {'method': 'GET', 'path': '/'}}
        _, _, headers, _ = _build_request(card, entry, {}, {'api_key': 'k'})
        assert headers['X-Api-Key'] == 'k'


@pytest.mark.asyncio
async def test_call_http_rest_unknown_endpoint():
    card = _card(tools=[{'name': 'known'}])
    result = await call_http_rest(card, None, 'unknown', {})
    assert 'error' in result


@pytest.mark.asyncio
async def test_call_http_rest_blocks_private_target():
    card = _card(base_url='https://127.0.0.1',
                 tools=[{'name': 'ping', 'request': {'method': 'GET', 'path': '/'}}])
    result = await call_http_rest(card, None, 'ping', {})
    assert 'private/internal' in result or 'Only https' in result
