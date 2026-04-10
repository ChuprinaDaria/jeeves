import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import Roles, User
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider, ModelPair


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


URL = '/api/owner/ai-providers/pairs/'


@pytest.mark.django_db
class TestModelPairAPI:
    def setup_method(self):
        self.llm = LLMProvider.objects.create(
            name='L', provider_type='openai', model_name='gpt-4o-mini',
        )
        self.em = EmbeddingModel.objects.create(
            name='E', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536,
        )

    def test_requires_auth(self):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_create(self):
        c = _owner()
        resp = c.post(
            URL,
            {
                'llm_provider_id': self.llm.pk,
                'embedding_model_id': self.em.pk,
                'external_guid': 'pair-guid-1',
                'is_active': True,
            },
            format='json',
        )
        assert resp.status_code == 201, resp.content
        assert resp.data['llm_provider']['id'] == self.llm.pk
        assert resp.data['embedding_model']['id'] == self.em.pk

    def test_list_returns_nested(self):
        ModelPair.objects.create(
            llm_provider=self.llm, embedding_model=self.em,
            external_guid='g2',
        )
        c = _owner()
        resp = c.get(URL)
        assert resp.status_code == 200
        rows = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        assert len(rows) == 1
        assert rows[0]['llm_provider']['name'] == 'L'

    def test_delete(self):
        p = ModelPair.objects.create(
            llm_provider=self.llm, embedding_model=self.em,
            external_guid='g3',
        )
        c = _owner()
        resp = c.delete(f'{URL}{p.pk}/')
        assert resp.status_code == 204
