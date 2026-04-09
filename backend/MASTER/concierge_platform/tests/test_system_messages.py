import pytest
from django.core.cache import cache
from MASTER.concierge_platform.models import SystemMessage


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestSystemMessage:
    def test_get_existing_key(self):
        SystemMessage.objects.create(
            key='chat.timeout',
            translations={'en': 'Session timed out', 'de': 'Sitzung abgelaufen'})
        assert SystemMessage.get('chat.timeout', 'en') == 'Session timed out'
        assert SystemMessage.get('chat.timeout', 'de') == 'Sitzung abgelaufen'

    def test_get_fallback_to_english(self):
        SystemMessage.objects.create(
            key='chat.timeout',
            translations={'en': 'Session timed out'})
        assert SystemMessage.get('chat.timeout', 'fr') == 'Session timed out'

    def test_get_missing_key_returns_empty(self):
        assert SystemMessage.get('nonexistent', 'en') == ''

    def test_result_is_cached(self):
        SystemMessage.objects.create(key='test', translations={'en': 'hello'})
        assert SystemMessage.get('test', 'en') == 'hello'
        SystemMessage.objects.all().delete()
        assert SystemMessage.get('test', 'en') == 'hello'
