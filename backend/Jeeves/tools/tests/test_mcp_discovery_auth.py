"""Discovery passes the API key as a Bearer header (remote-first path)."""
from unittest.mock import patch

from Jeeves.tools.mcp_discovery import _auth_headers, discover_or_parse, DiscoveryResult


def test_auth_headers():
    assert _auth_headers('k') == {'Authorization': 'Bearer k'}
    assert _auth_headers('') == {}
    assert _auth_headers(None) == {}


def test_discover_or_parse_forwards_api_key_to_live():
    captured = {}

    def fake_live(url, api_key=None):
        captured['url'] = url
        captured['api_key'] = api_key
        return DiscoveryResult(server_name='s', tools=[{'name': 'x'}], transport='sse')

    with patch('Jeeves.tools.mcp_discovery._is_html', return_value=False), \
         patch('Jeeves.tools.mcp_discovery._discover_live', side_effect=fake_live):
        result = discover_or_parse('https://srv.example.com/sse', api_key='secret')

    assert captured == {'url': 'https://srv.example.com/sse', 'api_key': 'secret'}
    assert result.tools == [{'name': 'x'}]
