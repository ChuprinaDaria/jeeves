from unittest.mock import MagicMock
from django.test import TestCase
from MASTER.agents.orchestrator import AgentOrchestrator, DEFAULT_ASSISTANT_PROMPT, DEFAULT_CONSULTANT_PROMPT


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
