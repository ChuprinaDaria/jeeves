"""Tests for the canvas MCP server logic (Jeeves edits his own canvas)."""
import pytest

from mcp_servers.canvas.server import (
    add_connection_sync,
    list_connections_sync,
    remove_connection_sync,
)
from Jeeves.tools.models import ToolCard, ToolConnection


@pytest.fixture
def client_obj(db):
    from Jeeves.clients.models import Client
    return Client.objects.create(
        user='test', description='test', api_key='rag_test_key_canvas',
        tag='canvas-client')


def _make_card(slug, auth_type='none', is_system=False):
    return ToolCard.objects.create(
        name=slug, slug=slug, tagline='t', description='d', icon='i',
        color='#000000', category='ai', transport_type='builtin',
        auth_type=auth_type, is_system=is_system)


@pytest.mark.django_db
class TestCanvasServer:
    def test_add_connection_no_auth_connects_immediately(self, client_obj):
        _make_card('beta-tool')
        result = add_connection_sync(client_obj.pk, 'beta-tool', ['assistant', 'manager'])
        assert 'error' not in result
        assert {r['status'] for r in result['results']} == {'connected'}
        conns = ToolConnection.objects.filter(client=client_obj, tool_card__slug='beta-tool')
        assert {c.target for c in conns} == {'assistant', 'manager'}
        assert all(c.enabled and c.status == 'connected' for c in conns)

    def test_add_connection_with_auth_stays_pending(self, client_obj):
        _make_card('gamma-tool', auth_type='api_key')
        result = add_connection_sync(client_obj.pk, 'gamma-tool', ['manager'])
        assert result.get('needs_credentials') is True
        conn = ToolConnection.objects.get(client=client_obj, tool_card__slug='gamma-tool')
        assert conn.status == 'pending' and conn.enabled

    def test_add_inherits_existing_credentials(self, client_obj):
        card = _make_card('delta-tool', auth_type='api_key')
        ToolConnection.objects.create(
            client=client_obj, tool_card=card, target='assistant',
            status='connected', enabled=True)
        result = add_connection_sync(client_obj.pk, 'delta-tool', ['manager'])
        assert 'needs_credentials' not in result
        assert result['results'][0]['status'] == 'connected'

    def test_add_validates_targets(self, client_obj):
        _make_card('eps-tool')
        assert 'error' in add_connection_sync(client_obj.pk, 'eps-tool', ['nope'])
        assert 'error' in add_connection_sync(client_obj.pk, 'eps-tool', [])
        assert 'error' in add_connection_sync(client_obj.pk, 'missing-tool', ['assistant'])

    def test_remove_detaches_but_keeps_credentials(self, client_obj):
        _make_card('zeta-tool')
        add_connection_sync(client_obj.pk, 'zeta-tool', ['manager'])
        result = remove_connection_sync(client_obj.pk, 'zeta-tool', 'manager')
        assert result['detached'] is True
        conn = ToolConnection.objects.get(client=client_obj, tool_card__slug='zeta-tool')
        assert conn.enabled is False and conn.status == 'connected'

    def test_remove_protects_system_tools(self, client_obj):
        card = _make_card('sys-tool', is_system=True)
        ToolConnection.objects.create(
            client=client_obj, tool_card=card, target='assistant',
            status='connected', enabled=True)
        assert 'error' in remove_connection_sync(client_obj.pk, 'sys-tool', 'assistant')

    def test_list_connections(self, client_obj):
        _make_card('lst-tool')
        add_connection_sync(client_obj.pk, 'lst-tool', ['leads'])
        result = list_connections_sync(client_obj.pk)
        pairs = {(c['tool'], c['target']) for c in result['connections']}
        assert ('lst-tool', 'leads') in pairs
