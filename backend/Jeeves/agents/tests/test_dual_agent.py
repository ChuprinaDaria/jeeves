from django.test import TestCase
from Jeeves.agents.models import AgentConfig, AgentSession


class TestAgentConfigDualPrompt(TestCase):
    def test_fields_exist(self):
        config = AgentConfig()
        self.assertEqual(config.assistant_prompt, '')
        self.assertEqual(config.consultant_prompt, '')
        self.assertEqual(config.assistant_description, '')
        self.assertEqual(config.consultant_description, '')

    def test_sandbox_channel_choice(self):
        channels = dict(AgentSession.CHANNEL_CHOICES)
        self.assertIn('sandbox', channels)
