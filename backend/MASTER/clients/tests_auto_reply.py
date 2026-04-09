from datetime import datetime
from unittest.mock import patch
from django.test import TestCase
from MASTER.clients.models import Client
from MASTER.clients.models_auto_reply import ChannelAutoReply
from MASTER.clients.auto_reply import should_consultant_respond


class ShouldConsultantRespondTest(TestCase):
    def setUp(self):
        from MASTER.accounts.models import User
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client_obj = Client.objects.create(user=self.user, tag='test')

    # --- Web/sandbox always responds ---
    def test_web_channel_always_responds(self):
        self.assertTrue(should_consultant_respond(self.client_obj, 'web', 'any'))

    def test_sandbox_channel_always_responds(self):
        self.assertTrue(should_consultant_respond(self.client_obj, 'sandbox', 'any'))

    # --- No config = respond to all ---
    def test_no_config_responds(self):
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Master switch ---
    def test_disabled_does_not_respond(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=False,
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    def test_enabled_always_responds(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='always',
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Schedule ---
    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_within_window_responds(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 30, tzinfo=ZoneInfo('UTC'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_outside_window_does_not_respond(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 20, 0, tzinfo=ZoneInfo('UTC'))  # Monday 20:00
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_day_disabled_does_not_respond(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 0, tzinfo=ZoneInfo('UTC'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': False}],
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_day_missing_does_not_respond(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 0, tzinfo=ZoneInfo('UTC'))  # Monday=0
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 2, 'start': '09:00', 'end': '18:00', 'enabled': True}],  # Wednesday only
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Contact filtering ---
    def test_all_except_blocks_listed_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all_except', contact_list=['48571079588'],
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    def test_all_except_allows_unlisted_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all_except', contact_list=['48571079588'],
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48999888777'))

    def test_only_allows_listed_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='only', contact_list=['48571079588'],
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    def test_only_blocks_unlisted_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='only', contact_list=['48571079588'],
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48999888777'))

    def test_contact_plus_prefix_normalized(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all_except', contact_list=['48571079588'],
        )
        self.assertFalse(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '+48571079588'))

    def test_contact_mode_all_ignores_list(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all', contact_list=['48571079588'],
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Timezone ---
    @patch('MASTER.clients.auto_reply.datetime')
    def test_timezone_conversion(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 7, 6, 12, 0, tzinfo=ZoneInfo('Europe/Warsaw'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='Europe/Warsaw',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_invalid_timezone_falls_back_to_utc(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 0, tzinfo=ZoneInfo('UTC'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='Invalid/Zone',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertTrue(should_consultant_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))
