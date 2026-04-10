import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import Roles, User
from Jeeves.concierge_platform.models import PlatformDefaults
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider


def _owner():
    user = User.objects.create_user(
        username='o@t.com', email='o@t.com', password='x',
        first_name='o', last_name='w', role=Roles.OWNER,
        is_staff=True, is_superuser=True,
    )
    c = APIClient()
    c.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}",
    )
    return c


URL = '/api/owner/settings/defaults/'


@pytest.mark.django_db
class TestPlatformDefaultsAPI:
    def test_requires_owner(self):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_get_returns_singleton_with_derived_defaults(self):
        LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            is_default=True, is_active=True,
        )
        EmbeddingModel.objects.create(
            name='E', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536, is_default=True, is_active=True,
        )
        c = _owner()
        resp = c.get(URL)
        assert resp.status_code == 200
        assert resp.data['default_llm']['name'] == 'A'
        assert resp.data['default_embedding']['name'] == 'E'

    def test_get_returns_null_defaults_when_none(self):
        c = _owner()
        resp = c.get(URL)
        assert resp.status_code == 200
        assert resp.data['default_llm'] is None
        assert resp.data['default_embedding'] is None

    def test_put_updates_tunables(self):
        c = _owner()
        resp = c.put(
            URL,
            {
                'default_temperature': 0.5,
                'default_max_tokens': 8192,
                'default_similarity_threshold': 0.75,
                'default_max_context_chunks': 6,
                'default_top_k': 8,
                'supported_languages': ['en', 'uk'],
                'default_language': 'en',
                'language_detection_method': 'llm',
                'default_greeting': 'Hello.',
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content
        obj = PlatformDefaults.get()
        assert obj.default_temperature == 0.5
        assert obj.default_max_tokens == 8192

    def test_put_ignores_default_llm_field(self):
        c = _owner()
        resp = c.put(
            URL,
            {
                'default_temperature': 0.7,
                'default_max_tokens': 4096,
                'default_similarity_threshold': 0.7,
                'default_max_context_chunks': 5,
                'default_top_k': 10,
                'supported_languages': ['en'],
                'default_language': 'en',
                'language_detection_method': 'llm',
                'default_greeting': 'Hi',
                'default_llm': {'id': 99, 'name': 'nope', 'is_default': True},
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content

    def test_put_validates_temperature_range(self):
        c = _owner()
        resp = c.put(
            URL,
            {
                'default_temperature': 10.0,
                'default_max_tokens': 4096,
                'default_similarity_threshold': 0.7,
                'default_max_context_chunks': 5,
                'default_top_k': 10,
                'supported_languages': ['en'],
                'default_language': 'en',
                'language_detection_method': 'llm',
                'default_greeting': 'Hi',
            },
            format='json',
        )
        assert resp.status_code == 400
        assert 'default_temperature' in resp.data

    def test_put_validates_language_in_supported(self):
        c = _owner()
        resp = c.put(
            URL,
            {
                'default_temperature': 0.7,
                'default_max_tokens': 4096,
                'default_similarity_threshold': 0.7,
                'default_max_context_chunks': 5,
                'default_top_k': 10,
                'supported_languages': ['en', 'uk'],
                'default_language': 'zz',
                'language_detection_method': 'llm',
                'default_greeting': 'Hi',
            },
            format='json',
        )
        assert resp.status_code == 400
        assert 'default_language' in resp.data
