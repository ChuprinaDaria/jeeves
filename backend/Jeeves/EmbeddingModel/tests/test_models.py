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


@pytest.mark.django_db
class TestIsDefaultMutualExclusion:
    def _mk_llm(self, name, is_default=False, is_active=True):
        return LLMProvider.objects.create(
            name=name,
            provider_type='openai',
            model_name='gpt-4o-mini',
            is_default=is_default,
            is_active=is_active,
        )

    def _mk_embed(self, name, is_default=False, is_active=True):
        return EmbeddingModel.objects.create(
            name=name,
            provider='openai',
            model_name='text-embedding-3-small',
            dimensions=1536,
            is_default=is_default,
            is_active=is_active,
        )

    def test_setting_default_unsets_others_llm(self):
        a = self._mk_llm('A', is_default=True)
        b = self._mk_llm('B', is_default=True)
        a.refresh_from_db()
        b.refresh_from_db()
        assert b.is_default is True
        assert a.is_default is False

    def test_setting_default_unsets_only_same_type(self):
        llm = self._mk_llm('LLM-default', is_default=True)
        embed = self._mk_embed('Embed-default', is_default=True)
        llm.refresh_from_db()
        embed.refresh_from_db()
        assert llm.is_default is True
        assert embed.is_default is True

    def test_delete_default_promotes_next_active(self):
        a = self._mk_llm('A', is_default=True)
        b = self._mk_llm('B')
        c = self._mk_llm('C')
        a.delete()
        b.refresh_from_db()
        c.refresh_from_db()
        assert b.is_default is True
        assert c.is_default is False

    def test_delete_default_with_no_other_active_leaves_no_default(self):
        a = self._mk_llm('A', is_default=True)
        b = self._mk_llm('B', is_active=False)
        a.delete()
        b.refresh_from_db()
        assert b.is_default is False
