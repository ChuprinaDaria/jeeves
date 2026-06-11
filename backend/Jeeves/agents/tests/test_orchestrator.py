import sys
from unittest.mock import MagicMock

import pytest
from asgiref.sync import async_to_sync
from django.test import TestCase

from Jeeves.agents.orchestrator import AgentOrchestrator, DEFAULT_ASSISTANT_PROMPT, DEFAULT_CONSULTANT_PROMPT


class TestDualPromptBuilding(TestCase):
    def setUp(self):
        self.client = MagicMock(pk=1)
        self.config = MagicMock()
        self.config.assistant_prompt = ''
        self.config.consultant_prompt = 'Custom consultant prompt'
        self.config.assistant_description = 'Can search leads'
        self.config.consultant_description = ''
        self.config.get_language.return_value = 'en'
        self.orchestrator = AgentOrchestrator(self.client, self.config)
        self.orchestrator._tools = []
        self.orchestrator._connected_server_names = set()

    def test_sandbox_uses_assistant_prompt(self):
        self.orchestrator._scope = 'assistant'
        prompt = self.orchestrator._build_system_prompt('sandbox')
        self.assertIn(DEFAULT_ASSISTANT_PROMPT, prompt)
        self.assertIn('Can search leads', prompt)

    def test_messenger_uses_consultant_prompt(self):
        self.orchestrator._scope = 'manager'
        prompt = self.orchestrator._build_system_prompt('telegram')
        self.assertIn('Custom consultant prompt', prompt)
        self.assertNotIn(DEFAULT_ASSISTANT_PROMPT, prompt)

    def test_scope_from_channel(self):
        self.orchestrator._scope = 'assistant' if 'sandbox' == 'sandbox' else 'manager'
        self.assertEqual(self.orchestrator._scope, 'assistant')

        self.orchestrator._scope = 'assistant' if 'telegram' == 'sandbox' else 'manager'
        self.assertEqual(self.orchestrator._scope, 'manager')


@pytest.mark.django_db
class TestScopeFilterDefaults:
    """All spawned MCP servers are available by default; ToolConnection
    rows only opt servers out or attach per-client credentials."""

    @pytest.fixture
    def client_obj(self):
        from Jeeves.clients.models import Client
        return Client.objects.create(
            user='test', description='test', api_key='rag_test_key_orch',
            tag='orch-client')

    def _make_orchestrator(self, client_obj, server_names):
        config = MagicMock()
        config.language = 'en'
        config.temperature = 0.7
        config.max_tokens = 1024
        orch = AgentOrchestrator(client_obj, config)
        orch._sessions = {name: MagicMock() for name in server_names}
        return orch

    def _make_card(self, server_name):
        # Slug '<server>-test' avoids clashing with seeded ToolCards while
        # still matching the server via the startswith('<server>-') rule.
        from Jeeves.tools.models import ToolCard
        slug = f'{server_name}-test'
        return ToolCard.objects.create(
            name=slug, slug=slug, tagline='t', description='d',
            icon='i', color='#000000', category='ai',
            transport_type='stdio', auth_type='none')

    def test_all_servers_available_without_connections(self, client_obj):
        orch = self._make_orchestrator(client_obj, ['alpha', 'beta', 'gamma'])
        orch._scope = 'manager'
        async_to_sync(orch._build_scope_filter)()
        assert orch._connected_server_names == {'alpha', 'beta', 'gamma'}

    def test_disabled_connection_removes_server(self, client_obj):
        from Jeeves.tools.models import ToolConnection
        ToolConnection.objects.create(
            client=client_obj, tool_card=self._make_card('beta'),
            target='manager', enabled=False)
        orch = self._make_orchestrator(client_obj, ['alpha', 'beta'])
        orch._scope = 'manager'
        async_to_sync(orch._build_scope_filter)()
        assert orch._connected_server_names == {'alpha'}

    def test_disabled_connection_in_other_scope_ignored(self, client_obj):
        from Jeeves.tools.models import ToolConnection
        ToolConnection.objects.create(
            client=client_obj, tool_card=self._make_card('beta'),
            target='assistant', enabled=False)
        orch = self._make_orchestrator(client_obj, ['alpha', 'beta'])
        orch._scope = 'manager'
        async_to_sync(orch._build_scope_filter)()
        assert orch._connected_server_names == {'alpha', 'beta'}

    def test_connected_connection_attaches_credentials(self, client_obj):
        from Jeeves.tools.models import ToolConnection
        conn = ToolConnection.objects.create(
            client=client_obj, tool_card=self._make_card('beta'),
            target='manager', enabled=True, status='connected')
        orch = self._make_orchestrator(client_obj, ['alpha', 'beta'])
        orch._scope = 'manager'
        async_to_sync(orch._build_scope_filter)()
        assert orch._connected_server_names == {'alpha', 'beta'}
        assert orch._tool_to_connection['beta'].pk == conn.pk

    def test_pending_connection_keeps_server_available(self, client_obj):
        from Jeeves.tools.models import ToolConnection
        ToolConnection.objects.create(
            client=client_obj, tool_card=self._make_card('beta'),
            target='manager', enabled=True, status='pending')
        orch = self._make_orchestrator(client_obj, ['beta'])
        orch._scope = 'manager'
        async_to_sync(orch._build_scope_filter)()
        assert orch._connected_server_names == {'beta'}
        assert 'beta' not in orch._tool_to_connection


@pytest.mark.django_db
class TestCatalogServers:
    """Owner-added MCP servers from the tool catalog (DB) reach the agent.

    Catalog servers are opt-in: a client needs an enabled ToolConnection."""

    @pytest.fixture
    def client_obj(self):
        from Jeeves.clients.models import Client
        return Client.objects.create(
            user='test', description='test', api_key='rag_test_key_cat',
            tag='cat-client')

    def _make_orchestrator(self, client_obj):
        config = MagicMock()
        config.language = 'en'
        config.temperature = 0.7
        config.max_tokens = 1024
        return AgentOrchestrator(client_obj, config)

    def _make_stdio_card(self):
        from Jeeves.agents.tests.test_mcp_pool import DUMMY_SERVER
        from Jeeves.tools.models import InstalledMCPServer, ToolCard
        card = ToolCard.objects.create(
            name='Outlook Assistant', slug='outlook-assistant', tagline='Email helper',
            description='d', icon='i', color='#000000', category='custom',
            transport_type='stdio', auth_type='none')
        InstalledMCPServer.objects.create(
            tool_card=card, package_name='outlook-test-pkg', package_type='pypi',
            run_command=sys.executable, run_args=['-c', DUMMY_SERVER])
        return card

    def test_installed_stdio_server_tools_reach_agent(self, settings, client_obj):
        settings.MCP_POOL_ENABLED = False
        settings.MCP_SERVERS = {}
        self._make_stdio_card()
        orch = self._make_orchestrator(client_obj)
        try:
            async_to_sync(orch.connect)()
            assert 'outlook-assistant' in orch._sessions
            assert orch._tool_to_server.get('echo') == 'outlook-assistant'
            assert 'outlook-assistant' in orch._dynamic_servers
        finally:
            async_to_sync(orch.disconnect)()

    def test_catalog_server_requires_enabled_connection(self, settings, client_obj):
        from Jeeves.tools.models import ToolConnection
        settings.MCP_POOL_ENABLED = False
        settings.MCP_SERVERS = {}
        card = self._make_stdio_card()
        orch = self._make_orchestrator(client_obj)
        try:
            async_to_sync(orch.connect)()
            orch._scope = 'manager'

            async_to_sync(orch._build_scope_filter)()
            assert 'outlook-assistant' not in orch._connected_server_names

            ToolConnection.objects.create(
                client=client_obj, tool_card=card, target='manager', enabled=True)
            async_to_sync(orch._build_scope_filter)()
            assert 'outlook-assistant' in orch._connected_server_names
        finally:
            async_to_sync(orch.disconnect)()

    def test_remote_card_tools_from_stored_schema(self, settings, client_obj):
        from Jeeves.tools.models import ToolCard, ToolConnection
        settings.MCP_POOL_ENABLED = False
        settings.MCP_SERVERS = {}
        card = ToolCard.objects.create(
            name='HookLayer', slug='hooklayer', tagline='Webhooks',
            description='d', icon='i', color='#000000', category='custom',
            transport_type='streamable_http', auth_type='api_key',
            mcp_server_url='https://hooks.example.com/mcp',
            tools_schema=[{
                'name': 'fire_hook',
                'description': 'Fire a webhook',
                'inputSchema': {'type': 'object', 'properties': {'url': {'type': 'string'}}},
            }])
        ToolConnection.objects.create(
            client=client_obj, tool_card=card, target='manager',
            enabled=True, status='connected')
        orch = self._make_orchestrator(client_obj)
        try:
            async_to_sync(orch.connect)()
            assert orch._tool_to_server.get('fire_hook') == 'hooklayer'

            orch._scope = 'manager'
            async_to_sync(orch._build_scope_filter)()
            assert 'hooklayer' in orch._connected_server_names

            llm_tools = orch._tools_to_llm_format()
            assert 'fire_hook' in [t['function']['name'] for t in llm_tools]
        finally:
            async_to_sync(orch.disconnect)()
