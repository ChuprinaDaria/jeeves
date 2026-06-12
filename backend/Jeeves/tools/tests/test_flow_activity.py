"""Tests for the live canvas activity endpoint (FlowActivityView)."""
import pytest
from django.utils import timezone

from Jeeves.agents.models import AgentConfig, AgentLog, AgentSession


@pytest.fixture
def client_obj(db):
    from Jeeves.clients.models import Client
    return Client.objects.create(
        user='test', description='test', api_key='rag_test_key_act',
        tag='activity-client')


def _log_tool_call(client_obj, tool_name='search', channel='web', call_type='rag'):
    config, _ = AgentConfig.objects.get_or_create(client=client_obj)
    session = AgentSession.objects.create(agent_config=config, channel=channel)
    return AgentLog.objects.create(
        session=session, call_type=call_type, tool_name=tool_name, status='ok')


@pytest.mark.django_db
class TestFlowActivity:
    URL = '/api/tools/flow/activity/'

    def _get(self, api_client, client_obj, **params):
        return api_client.get(self.URL, params, HTTP_X_CLIENT_TOKEN=client_obj.tag)

    def test_requires_client(self, client):
        res = client.get(self.URL)
        assert res.status_code == 401

    def test_recent_event_mapped_to_edge(self, client, client_obj):
        _log_tool_call(client_obj)
        res = self._get(client, client_obj)
        assert res.status_code == 200
        events = res.json()['events']
        assert len(events) == 1
        assert events[0]['slug'] == 'rag'  # seeded system card, auto-connected
        assert events[0]['target'] == 'manager'  # 'web' channel → manager scope

    def test_sandbox_channel_maps_to_assistant(self, client, client_obj):
        _log_tool_call(client_obj, channel='sandbox')
        res = self._get(client, client_obj)
        assert res.json()['events'][0]['target'] == 'assistant'

    def test_aggregates_count_week_usage(self, client, client_obj):
        for _ in range(3):
            _log_tool_call(client_obj)
        # `since` in the future — no live events, aggregates still counted
        future = (timezone.now() + timezone.timedelta(minutes=1)).isoformat()
        res = self._get(client, client_obj, since=future)
        body = res.json()
        assert body['events'] == []
        agg = {(a['slug'], a['target']): a['count'] for a in body['aggregates']}
        assert agg[('rag', 'manager')] == 3

    def test_other_clients_activity_invisible(self, client, client_obj):
        from Jeeves.clients.models import Client
        other = Client.objects.create(
            user='other', description='d', api_key='rag_test_key_other',
            tag='other-client')
        _log_tool_call(other)
        res = self._get(client, client_obj)
        assert res.json()['events'] == []
