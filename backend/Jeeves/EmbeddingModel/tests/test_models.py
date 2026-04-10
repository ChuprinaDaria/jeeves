import pytest
from django.db import connection

from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider


@pytest.mark.django_db
class TestApiKeyEncryption:
    def test_llm_api_key_encrypted_at_rest(self):
        row = LLMProvider.objects.create(
            name='Test LLM',
            provider_type='openai',
            model_name='gpt-4o-mini',
            api_key='sk-proj-secret-123',
        )
        with connection.cursor() as cur:
            cur.execute(
                'SELECT api_key FROM "EmbeddingModel_llmprovider" WHERE id=%s',
                [row.pk],
            )
            (raw,) = cur.fetchone()
        assert raw is not None
        assert 'sk-proj-secret-123' not in raw

    def test_llm_api_key_decrypted_on_read(self):
        LLMProvider.objects.create(
            name='Test LLM 2',
            provider_type='openai',
            model_name='gpt-4o-mini',
            api_key='sk-plain-roundtrip',
        )
        reloaded = LLMProvider.objects.get(name='Test LLM 2')
        assert reloaded.api_key == 'sk-plain-roundtrip'

    def test_embedding_api_key_encrypted_at_rest(self):
        row = EmbeddingModel.objects.create(
            name='Test Embed',
            provider='openai',
            model_name='text-embedding-3-small',
            dimensions=1536,
            api_key='sk-embed-secret',
        )
        with connection.cursor() as cur:
            cur.execute(
                'SELECT api_key FROM "EmbeddingModel_embeddingmodel" WHERE id=%s',
                [row.pk],
            )
            (raw,) = cur.fetchone()
        assert raw is not None
        assert 'sk-embed-secret' not in raw

    def test_llm_save_clears_api_key_via_empty_string(self):
        row = LLMProvider.objects.create(
            name='Clearable',
            provider_type='openai',
            model_name='gpt-4o-mini',
            api_key='sk-old',
        )
        row.api_key = ''
        row.save()
        reloaded = LLMProvider.objects.get(pk=row.pk)
        assert reloaded.api_key in ('', None)
