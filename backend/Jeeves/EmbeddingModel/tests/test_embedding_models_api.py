from unittest.mock import patch

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import Roles, User
from Jeeves.EmbeddingModel.models import EmbeddingModel


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


URL = '/api/owner/ai-providers/embeddings/'


@pytest.mark.django_db
class TestEmbeddingModelAPI:
    def test_list_requires_auth(self):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_create_minimal(self):
        c = _owner()
        payload = {
            'name': 'text-embedding-3-small',
            'provider': 'openai',
            'model_name': 'text-embedding-3-small',
            'dimensions': 1536,
            'api_key': 'sk-em-real',
            'is_active': True,
            'is_default': True,
            'cost_per_1k_tokens': '0',
        }
        resp = c.post(URL, payload, format='json')
        assert resp.status_code == 201, resp.content
        assert resp.data['api_key_set'] is True
        assert resp.data['api_key_masked'].endswith('real')

    def test_detail_masks_api_key(self):
        row = EmbeddingModel.objects.create(
            name='E', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536, api_key='sk-e-1234',
        )
        c = _owner()
        resp = c.get(f'{URL}{row.pk}/')
        assert resp.status_code == 200
        assert resp.data['api_key_set'] is True
        assert resp.data['api_key_masked'].endswith('1234')

    def test_update_without_api_key_keeps_existing(self):
        row = EmbeddingModel.objects.create(
            name='E2', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536, api_key='sk-old',
        )
        c = _owner()
        resp = c.put(
            f'{URL}{row.pk}/',
            {
                'name': 'E2',
                'provider': 'openai',
                'model_name': 'text-embedding-3-small',
                'dimensions': 1536,
                'is_active': True,
                'is_default': False,
                'cost_per_1k_tokens': '0',
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content
        assert EmbeddingModel.objects.get(pk=row.pk).api_key == 'sk-old'

    def test_dimensions_too_large_rejected(self):
        c = _owner()
        resp = c.post(
            URL,
            {
                'name': 'Big',
                'provider': 'openai',
                'model_name': 'big-embed',
                'dimensions': 3000,
                'is_active': True,
                'is_default': False,
                'cost_per_1k_tokens': '0',
            },
            format='json',
        )
        assert resp.status_code == 400
        assert 'dimensions' in resp.data

    def test_dimensions_zero_rejected(self):
        c = _owner()
        resp = c.post(
            URL,
            {
                'name': 'Zero',
                'provider': 'openai',
                'model_name': 'z',
                'dimensions': 0,
                'is_active': True,
                'is_default': False,
                'cost_per_1k_tokens': '0',
            },
            format='json',
        )
        assert resp.status_code == 400
        assert 'dimensions' in resp.data

    def test_test_action_success(self):
        row = EmbeddingModel.objects.create(
            name='E3', provider='openai', model_name='text-embedding-3-small',
            dimensions=1536, api_key='sk-stored',
        )
        c = _owner()
        with patch(
            'Jeeves.concierge_platform.provider_test_client.test_embedding_model'
        ) as mock:
            from Jeeves.concierge_platform.provider_test_client import TestResult
            mock.return_value = TestResult(outcome='success', message='ok')
            resp = c.post(f'{URL}{row.pk}/test/', {}, format='json')
        assert resp.status_code == 200
        assert resp.data['outcome'] == 'success'
        assert mock.call_args.kwargs['api_key'] == 'sk-stored'

    def test_test_unsaved(self):
        c = _owner()
        with patch(
            'Jeeves.concierge_platform.provider_test_client.test_embedding_model'
        ) as mock:
            from Jeeves.concierge_platform.provider_test_client import TestResult
            mock.return_value = TestResult(outcome='success')
            resp = c.post(
                f'{URL}test-unsaved/',
                {
                    'provider': 'openai',
                    'api_key': 'sk-new',
                    'model_name': 'text-embedding-3-small',
                    'dimensions': 1536,
                },
                format='json',
            )
        assert resp.status_code == 200
        assert mock.call_args.kwargs['provider'] == 'openai'

    def test_delete(self):
        row = EmbeddingModel.objects.create(
            name='D', provider='openai', model_name='m', dimensions=1536,
        )
        c = _owner()
        resp = c.delete(f'{URL}{row.pk}/')
        assert resp.status_code == 204
