import pytest
from django.core.cache import cache
from Jeeves.concierge_platform.models import FeatureFlag


@pytest.fixture
def client_obj(db):
    from Jeeves.clients.models import Client
    return Client.objects.create(
        user='test', description='test', api_key='rag_test_key_001',
        tag='test-client')


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestFeatureFlag:
    def test_unknown_flag_returns_false(self, client_obj):
        assert FeatureFlag.is_enabled('nonexistent', client_obj) is False

    def test_rollout_off(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='off')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is False

    def test_rollout_all(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='all')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True

    def test_rollout_selected_not_in_list(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='selected')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is False

    def test_rollout_selected_in_list(self, client_obj):
        flag = FeatureFlag.objects.create(key='test_flag', rollout='selected')
        flag.enabled_clients.add(client_obj)
        cache.clear()
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True

    def test_result_is_cached(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='all')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True
        FeatureFlag.objects.all().delete()
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True

    def test_cache_invalidated_on_save(self, client_obj):
        flag = FeatureFlag.objects.create(key='test_flag', rollout='all')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True
        flag.rollout = 'off'
        flag.save()
        assert FeatureFlag.is_enabled('test_flag', client_obj) is False

    def test_default_on_flag_without_row(self, client_obj):
        FeatureFlag.objects.filter(key='mcp_real_agent').delete()
        cache.clear()
        assert FeatureFlag.is_enabled('mcp_real_agent', client_obj) is True

    def test_default_on_flag_explicit_opt_out(self, client_obj):
        FeatureFlag.objects.update_or_create(
            key='mcp_real_agent', defaults={'rollout': 'off'})
        cache.clear()
        assert FeatureFlag.is_enabled('mcp_real_agent', client_obj) is False
