import pytest
from Jeeves.concierge_platform.models import PlatformDefaults
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider


@pytest.mark.django_db
class TestPlatformDefaults:
    def test_singleton_get_creates_if_missing(self):
        assert PlatformDefaults.objects.count() == 0
        defaults = PlatformDefaults.get()
        assert defaults.pk == 1
        assert PlatformDefaults.objects.count() == 1

    def test_singleton_get_returns_existing(self):
        PlatformDefaults.objects.create(pk=1)
        defaults = PlatformDefaults.get()
        assert defaults.pk == 1
        assert PlatformDefaults.objects.count() == 1

    def test_save_always_pk_1(self):
        d = PlatformDefaults()
        d.save()
        assert d.pk == 1
        d2 = PlatformDefaults()
        d2.save()
        assert d2.pk == 1
        assert PlatformDefaults.objects.count() == 1


@pytest.mark.django_db
class TestPlatformDefaultsGetters:
    def test_get_default_llm_returns_active_default(self):
        LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            is_default=True, is_active=True,
        )
        LLMProvider.objects.create(
            name='B', provider_type='openai', model_name='gpt-4o',
            is_default=False, is_active=True,
        )
        result = PlatformDefaults.get_default_llm_provider()
        assert result is not None
        assert result.name == 'A'

    def test_get_default_llm_returns_none_when_no_default(self):
        LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            is_default=False, is_active=True,
        )
        assert PlatformDefaults.get_default_llm_provider() is None

    def test_get_default_llm_skips_inactive(self):
        LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            is_default=True, is_active=False,
        )
        assert PlatformDefaults.get_default_llm_provider() is None

    def test_get_default_embedding_returns_active_default(self):
        EmbeddingModel.objects.create(
            name='E', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536, is_default=True, is_active=True,
        )
        result = PlatformDefaults.get_default_embedding_model()
        assert result is not None
        assert result.name == 'E'

    def test_get_default_embedding_skips_inactive(self):
        EmbeddingModel.objects.create(
            name='E', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536, is_default=True, is_active=False,
        )
        assert PlatformDefaults.get_default_embedding_model() is None
