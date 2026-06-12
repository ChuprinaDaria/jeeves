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


@pytest.mark.django_db
class TestSkills:
    """Markdown skills: attach/detach via the canvas server + prompt injection."""

    @pytest.fixture
    def client_obj(self):
        from Jeeves.clients.models import Client
        return Client.objects.create(
            user='test', description='test', api_key='rag_test_key_skill',
            tag='skill-client')

    def _make_skill(self, slug, allowed=None):
        from Jeeves.tools.models import Skill
        return Skill.objects.create(
            name=slug, slug=slug, description='d',
            content=f'## {slug}\nBe great at {slug}.',
            allowed_targets=allowed or [])

    def test_attach_and_list(self, client_obj):
        from mcp_servers.canvas.server import attach_skill_sync, list_skills_sync
        self._make_skill('test-marketing')
        result = attach_skill_sync(client_obj.pk, 'test-marketing', 'manager')
        assert result['attached'] is True
        listed = {s['skill']: s for s in list_skills_sync(client_obj.pk)['skills']}
        assert listed['test-marketing']['attached_to'] == ['manager']

    def test_attach_respects_allowed_targets(self, client_obj):
        from mcp_servers.canvas.server import attach_skill_sync
        self._make_skill('test-leads-only', allowed=['leads'])
        assert 'error' in attach_skill_sync(client_obj.pk, 'test-leads-only', 'assistant')
        assert attach_skill_sync(client_obj.pk, 'test-leads-only', 'leads')['attached']

    def test_detach(self, client_obj):
        from mcp_servers.canvas.server import attach_skill_sync, detach_skill_sync
        self._make_skill('test-sales')
        attach_skill_sync(client_obj.pk, 'test-sales', 'manager')
        assert detach_skill_sync(client_obj.pk, 'test-sales', 'manager')['detached']
        assert 'error' in detach_skill_sync(client_obj.pk, 'test-sales', 'manager')

    def test_seeded_standard_skills_exist(self, db):
        from Jeeves.tools.models import Skill
        slugs = set(Skill.objects.values_list('slug', flat=True))
        assert {'marketing-pro', 'sales-pro', 'lead-qualifier'} <= slugs

    def test_skill_injected_into_prompt_for_scope(self, client_obj):
        from unittest.mock import MagicMock

        from asgiref.sync import async_to_sync

        from mcp_servers.canvas.server import attach_skill_sync
        from Jeeves.agents.orchestrator import AgentOrchestrator

        self._make_skill('test-style')
        attach_skill_sync(client_obj.pk, 'test-style', 'manager')

        config = MagicMock()
        config.language = 'en'
        config.temperature = 0.7
        config.max_tokens = 1024
        config.consultant_prompt = ''
        config.consultant_description = ''
        orch = AgentOrchestrator(client_obj, config)

        async def _load(orch):
            await orch._build_scope_filter()
            await orch._load_deployment_context()
            await orch._load_scope_skills()

        # consultant scope (telegram) sees the skill
        orch._scope = 'manager'
        async_to_sync(_load)(orch)
        prompt = orch._build_system_prompt('telegram')
        assert 'Be great at test-style' in prompt
        assert '## Skill: test-style' in prompt

        # assistant scope does not (skill attached to manager only)
        orch._scope = 'assistant'
        async_to_sync(_load)(orch)
        config.assistant_prompt = ''
        config.assistant_description = ''
        prompt = orch._build_system_prompt('sandbox')
        assert 'Be great at test-style' not in prompt


@pytest.mark.django_db
class TestCustomIntegration:
    """Jeeves creates a per-client custom REST integration."""

    @pytest.fixture
    def client_obj(self):
        from Jeeves.clients.models import Client
        return Client.objects.create(
            user='test', description='t', api_key='rag_test_key_ci', tag='ci-client')

    def _endpoints(self):
        return [{
            'name': 'create_contact', 'description': 'Add a contact', 'method': 'POST',
            'path': '/v1/contacts',
            'params': [{'name': 'email', 'type': 'string', 'location': 'body', 'required': True}],
        }]

    def test_create_no_auth_connects(self, client_obj):
        from mcp_servers.canvas.server import create_http_integration_sync
        from Jeeves.tools.models import ToolCard, ToolConnection

        res = create_http_integration_sync(
            client_obj.pk, 'Acme CRM', 'https://api.acme.com', self._endpoints(),
            targets=['assistant'])
        assert res['status'] == 'connected'
        card = ToolCard.objects.get(slug=res['integration'])
        assert card.transport_type == 'http_rest'
        assert card.owner_client_id == client_obj.pk  # private to this client
        assert card.tools_schema[0]['request']['body'] == ['email']
        conn = ToolConnection.objects.get(client=client_obj, tool_card=card, target='assistant')
        assert conn.enabled and conn.status == 'connected'

    def test_create_with_api_key_stores_encrypted(self, client_obj):
        from mcp_servers.canvas.server import create_http_integration_sync
        from Jeeves.tools.models import ToolConnection

        res = create_http_integration_sync(
            client_obj.pk, 'Acme', 'https://api.acme.com', self._endpoints(),
            auth={'type': 'bearer', 'credential_key': 'token'},
            api_key='secret-xyz', targets=['assistant'])
        conn = ToolConnection.objects.get(tool_card__slug=res['integration'])
        assert conn.credentials['token'] == 'secret-xyz'
        assert conn.status == 'connected'

    def test_rejects_non_https_base_url(self, client_obj):
        from mcp_servers.canvas.server import create_http_integration_sync
        res = create_http_integration_sync(
            client_obj.pk, 'X', 'http://api.acme.com', self._endpoints())
        assert 'error' in res

    def test_rejects_private_base_url(self, client_obj):
        from mcp_servers.canvas.server import create_http_integration_sync
        res = create_http_integration_sync(
            client_obj.pk, 'X', 'https://10.0.0.1', self._endpoints())
        assert 'error' in res

    def test_requires_endpoints(self, client_obj):
        from mcp_servers.canvas.server import create_http_integration_sync
        res = create_http_integration_sync(
            client_obj.pk, 'X', 'https://api.acme.com', [])
        assert 'error' in res
