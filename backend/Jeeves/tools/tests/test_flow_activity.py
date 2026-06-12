"""Tests for the live canvas activity endpoint (FlowActivityView)."""
import pytest
from django.core.cache import cache
from django.utils import timezone

from Jeeves.agents.models import AgentConfig, AgentLog, AgentSession


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


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

    def test_owner_telegram_maps_to_assistant(self, client, client_obj):
        # owner_telegram is an OWNER channel → assistant scope (was wrongly
        # 'manager' before channel routing was centralized).
        _log_tool_call(client_obj, channel='owner_telegram')
        res = self._get(client, client_obj)
        assert res.json()['events'][0]['target'] == 'assistant'

    def test_aggregates_cached_between_polls(self, client, client_obj):
        from django.core.cache import cache as _cache
        _log_tool_call(client_obj)
        future = (timezone.now() + timezone.timedelta(minutes=1)).isoformat()
        self._get(client, client_obj, since=future)
        assert _cache.get(f'flow-activity-agg:{client_obj.id}') is not None
        # A new log doesn't change the cached aggregate until TTL expires.
        _log_tool_call(client_obj)
        res = self._get(client, client_obj, since=future)
        agg = {(a['slug'], a['target']): a['count'] for a in res.json()['aggregates']}
        assert agg[('rag', 'manager')] == 1  # still cached, not 2


@pytest.mark.django_db
class TestSkillsAPI:
    LIST = '/api/tools/skills/'

    def test_list_and_attach_detach(self, client, client_obj):
        res = client.get(self.LIST, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        skills = {s['skill'] for s in res.json()['skills']}
        assert 'marketing-pro' in skills  # seeded

        res = client.post('/api/tools/skills/marketing-pro/attach/',
                          {'target': 'manager'}, content_type='application/json',
                          HTTP_X_CLIENT_TOKEN=client_obj.tag)
        assert res.status_code == 200 and res.json()['attached']

        res = client.get(self.LIST, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        by_slug = {s['skill']: s for s in res.json()['skills']}
        assert by_slug['marketing-pro']['attached_to'] == ['manager']

        res = client.post('/api/tools/skills/marketing-pro/detach/',
                          {'target': 'manager'}, content_type='application/json',
                          HTTP_X_CLIENT_TOKEN=client_obj.tag)
        assert res.json()['detached']

    def test_invalid_target_rejected(self, client, client_obj):
        res = client.post('/api/tools/skills/marketing-pro/attach/',
                          {'target': 'nope'}, content_type='application/json',
                          HTTP_X_CLIENT_TOKEN=client_obj.tag)
        assert res.status_code == 400


@pytest.mark.django_db
class TestCatalogTenancy:
    """Custom (owner_client) cards are visible only to their owner."""

    CATALOG = '/api/tools/catalog/'

    def _custom_card(self, owner):
        from Jeeves.tools.models import ToolCard
        return ToolCard.objects.create(
            name='Acme CRM', slug=f'ci-{owner.pk}-acme', tagline='t',
            description='d', icon='puzzle', color='#000000', category='custom',
            transport_type='http_rest', auth_type='none', owner_client=owner)

    def test_owner_sees_own_custom_card(self, client, client_obj):
        self._custom_card(client_obj)
        res = client.get(self.CATALOG, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        slugs = {t['slug']: t for t in res.json()}
        assert f'ci-{client_obj.pk}-acme' in slugs
        assert slugs[f'ci-{client_obj.pk}-acme']['is_custom'] is True

    def test_other_tenant_does_not_see_custom_card(self, client, client_obj):
        from Jeeves.clients.models import Client
        other = Client.objects.create(
            user='o', description='d', api_key='rag_test_key_cat2', tag='other-cat')
        self._custom_card(other)  # belongs to `other`
        res = client.get(self.CATALOG, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        slugs = {t['slug'] for t in res.json()}
        assert f'ci-{other.pk}-acme' not in slugs
