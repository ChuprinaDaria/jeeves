"""Integration triggers: webhook ingress, schedule dispatch, MCP tools."""
import json
from unittest.mock import patch

import pytest
from django.utils import timezone

from Jeeves.tools.models import IntegrationTrigger


@pytest.fixture
def client_obj(db):
    from Jeeves.clients.models import Client
    return Client.objects.create(
        user='t', description='d', api_key='rag_test_key_trig', tag='trig-client')


@pytest.mark.django_db
class TestTriggerMCPTools:
    def test_create_webhook_returns_url(self, client_obj):
        from mcp_servers.canvas.server import create_trigger_sync
        res = create_trigger_sync(
            client_obj.pk, 'New order', 'webhook', 'Notify me about the order')
        assert res['kind'] == 'webhook'
        assert res['webhook_url'].startswith('/api/tools/triggers/webhook/')
        t = IntegrationTrigger.objects.get(pk=res['id'])
        assert t.token and t.client_id == client_obj.pk

    def test_create_schedule_sets_next_run(self, client_obj):
        from mcp_servers.canvas.server import create_trigger_sync
        res = create_trigger_sync(
            client_obj.pk, 'Hourly poll', 'schedule', 'Poll the API',
            interval_seconds=30)  # below floor → clamped to 60
        t = IntegrationTrigger.objects.get(pk=res['id'])
        assert t.interval_seconds == 60
        assert t.next_run_at is not None

    def test_create_validates(self, client_obj):
        from mcp_servers.canvas.server import create_trigger_sync
        assert 'error' in create_trigger_sync(client_obj.pk, '', 'webhook', 'x')
        assert 'error' in create_trigger_sync(client_obj.pk, 'n', 'bad', 'x')
        assert 'error' in create_trigger_sync(client_obj.pk, 'n', 'webhook', '')

    def test_list_and_remove(self, client_obj):
        from mcp_servers.canvas.server import (
            create_trigger_sync, list_triggers_sync, remove_trigger_sync)
        res = create_trigger_sync(client_obj.pk, 'X', 'webhook', 'do x')
        listed = list_triggers_sync(client_obj.pk)['triggers']
        assert any(t['id'] == res['id'] for t in listed)
        assert remove_trigger_sync(client_obj.pk, res['id'])['removed']
        assert 'error' in remove_trigger_sync(client_obj.pk, res['id'])


@pytest.mark.django_db
class TestWebhookEndpoint:
    def _trigger(self, client_obj, secret=None):
        return IntegrationTrigger.objects.create(
            client=client_obj, name='wh', kind='webhook',
            instruction='handle it', token='tok123',
            secret={'header': 'X-Webhook-Secret', 'value': secret} if secret else {})

    @patch('Jeeves.tools.triggers.run_trigger.delay')
    def test_fires_and_enqueues(self, mock_delay, client, client_obj):
        self._trigger(client_obj)
        res = client.post('/api/tools/triggers/webhook/tok123/',
                          json.dumps({'order': 7}), content_type='application/json')
        assert res.status_code == 202
        assert mock_delay.called
        assert mock_delay.call_args.args[1] == {'order': 7}

    @patch('Jeeves.tools.triggers.run_trigger.delay')
    def test_unknown_token_404(self, mock_delay, client, client_obj):
        res = client.post('/api/tools/triggers/webhook/nope/', '{}',
                          content_type='application/json')
        assert res.status_code == 404
        assert not mock_delay.called

    @patch('Jeeves.tools.triggers.run_trigger.delay')
    def test_secret_required(self, mock_delay, client, client_obj):
        self._trigger(client_obj, secret='s3cr3t')
        # missing/wrong secret → 401
        res = client.post('/api/tools/triggers/webhook/tok123/', '{}',
                          content_type='application/json')
        assert res.status_code == 401
        # correct secret → 202
        res = client.post('/api/tools/triggers/webhook/tok123/', '{}',
                          content_type='application/json',
                          HTTP_X_WEBHOOK_SECRET='s3cr3t')
        assert res.status_code == 202


@pytest.mark.django_db
class TestScheduleDispatch:
    @patch('Jeeves.tools.triggers.run_trigger.delay')
    def test_dispatch_due_only(self, mock_delay, client_obj):
        from Jeeves.tools.triggers import dispatch_due_triggers
        past = timezone.now() - timezone.timedelta(seconds=10)
        future = timezone.now() + timezone.timedelta(hours=1)
        due = IntegrationTrigger.objects.create(
            client=client_obj, name='due', kind='schedule', instruction='go',
            interval_seconds=60, next_run_at=past)
        IntegrationTrigger.objects.create(
            client=client_obj, name='later', kind='schedule', instruction='go',
            interval_seconds=60, next_run_at=future)
        result = dispatch_due_triggers()
        assert result['dispatched'] == 1
        assert mock_delay.call_args.args[0] == due.pk
        due.refresh_from_db()
        assert due.next_run_at > past  # advanced

    @patch('Jeeves.agents.dispatch.generate_response_dual', return_value='done')
    def test_run_trigger_sync(self, mock_gen, client_obj):
        from Jeeves.tools.triggers import run_trigger_sync
        t = IntegrationTrigger.objects.create(
            client=client_obj, name='t', kind='webhook', instruction='Summarize',
            token='x', target='assistant')
        res = run_trigger_sync(t.pk, {'a': 1})
        assert res['ok'] is True
        kwargs = mock_gen.call_args.kwargs
        assert kwargs['channel'] == 'sandbox'  # assistant target → owner channel
        assert 'Summarize' in kwargs['message'] and '"a": 1' in kwargs['message']
        t.refresh_from_db()
        assert t.fire_count == 1
