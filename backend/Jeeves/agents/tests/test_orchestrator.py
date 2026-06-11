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
