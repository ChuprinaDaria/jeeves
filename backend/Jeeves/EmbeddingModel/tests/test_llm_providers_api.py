from unittest.mock import patch

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import Roles, User
from Jeeves.EmbeddingModel.models import LLMProvider


def _owner():
    user = User.objects.create_user(
        username='owner@test.com', email='owner@test.com', password='x',
        first_name='o', last_name='w', role=Roles.OWNER,
        is_staff=True, is_superuser=True,
    )
    c = APIClient()
    c.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}",
    )
    return c


@pytest.mark.django_db
class TestLLMProviderAPI:
    url = '/api/owner/ai-providers/llm/'

    def test_requires_auth(self):
        resp = APIClient().get(self.url)
        assert resp.status_code in (401, 403)

    def test_client_role_forbidden(self):
        user = User.objects.create_user(
            username='c@x.com', email='c@x.com', password='x',
            first_name='c', last_name='l', role=Roles.CLIENT,
        )
        c = APIClient()
        c.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}",
        )
        resp = c.get(self.url)
        assert resp.status_code == 403

    def test_list_empty(self):
        c = _owner()
        resp = c.get(self.url)
        assert resp.status_code == 200
        assert resp.data == [] or resp.data.get('results') == []

    def test_create_minimal(self):
        c = _owner()
        payload = {
            'name': 'GPT-4o Mini',
            'provider_type': 'openai',
            'model_name': 'gpt-4o-mini',
            'api_key': 'sk-proj-realkey',
            'max_tokens': 4096,
            'temperature': 0.7,
            'cost_per_1k_input_tokens': '0.00015',
            'cost_per_1k_output_tokens': '0.0006',
            'is_active': True,
            'is_default': True,
        }
        resp = c.post(self.url, payload, format='json')
        assert resp.status_code == 201, resp.content
        assert resp.data['api_key_masked'] == '****lkey'
        assert resp.data['api_key_set'] is True
        assert LLMProvider.objects.filter(name='GPT-4o Mini').exists()

    def test_detail_masks_api_key(self):
        LLMProvider.objects.create(
            name='X', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-abc1234',
        )
        c = _owner()
        row = LLMProvider.objects.get(name='X')
        resp = c.get(f'{self.url}{row.pk}/')
        assert resp.status_code == 200
        assert resp.data['api_key_set'] is True
        assert resp.data['api_key_masked'].endswith('1234')

    def test_update_without_api_key_keeps_existing(self):
        row = LLMProvider.objects.create(
            name='Keep', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-old-keep',
        )
        c = _owner()
        resp = c.put(
            f'{self.url}{row.pk}/',
            {
                'name': 'Keep',
                'provider_type': 'openai',
                'model_name': 'gpt-4o-mini',
                'temperature': 0.5,
                'max_tokens': 4096,
                'cost_per_1k_input_tokens': '0',
                'cost_per_1k_output_tokens': '0',
                'is_active': True,
                'is_default': False,
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content
        reloaded = LLMProvider.objects.get(pk=row.pk)
        assert reloaded.api_key == 'sk-old-keep'
        assert reloaded.temperature == 0.5

    def test_update_with_api_key_replaces(self):
        row = LLMProvider.objects.create(
            name='Replace', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-old',
        )
        c = _owner()
        resp = c.put(
            f'{self.url}{row.pk}/',
            {
                'name': 'Replace',
                'provider_type': 'openai',
                'model_name': 'gpt-4o-mini',
                'api_key': 'sk-new',
                'temperature': 0.7,
                'max_tokens': 4096,
                'cost_per_1k_input_tokens': '0',
                'cost_per_1k_output_tokens': '0',
                'is_active': True,
                'is_default': False,
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content
        assert LLMProvider.objects.get(pk=row.pk).api_key == 'sk-new'

    def test_update_with_empty_string_clears(self):
        row = LLMProvider.objects.create(
            name='Clear', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-old',
        )
        c = _owner()
        resp = c.put(
            f'{self.url}{row.pk}/',
            {
                'name': 'Clear',
                'provider_type': 'openai',
                'model_name': 'gpt-4o-mini',
                'api_key': '',
                'temperature': 0.7,
                'max_tokens': 4096,
                'cost_per_1k_input_tokens': '0',
                'cost_per_1k_output_tokens': '0',
                'is_active': True,
                'is_default': False,
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content
        reloaded = LLMProvider.objects.get(pk=row.pk)
        assert not reloaded.api_key

    def test_delete(self):
        row = LLMProvider.objects.create(
            name='Del', provider_type='openai', model_name='gpt-4o-mini',
        )
        c = _owner()
        resp = c.delete(f'{self.url}{row.pk}/')
        assert resp.status_code == 204
        assert not LLMProvider.objects.filter(pk=row.pk).exists()

    def test_setting_default_unsets_others_over_api(self):
        a = LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            is_default=True,
        )
        b = LLMProvider.objects.create(
            name='B', provider_type='openai', model_name='gpt-4o',
        )
        c = _owner()
        resp = c.put(
            f'{self.url}{b.pk}/',
            {
                'name': 'B',
                'provider_type': 'openai',
                'model_name': 'gpt-4o',
                'temperature': 0.7,
                'max_tokens': 4096,
                'cost_per_1k_input_tokens': '0',
                'cost_per_1k_output_tokens': '0',
                'is_active': True,
                'is_default': True,
            },
            format='json',
        )
        assert resp.status_code == 200, resp.content
        a.refresh_from_db()
        b.refresh_from_db()
        assert b.is_default is True
        assert a.is_default is False


@pytest.mark.django_db
class TestLLMProviderTestAction:
    url = '/api/owner/ai-providers/llm/'

    def test_test_action_success(self):
        row = LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-stored',
        )
        c = _owner()
        with patch(
            'Jeeves.concierge_platform.provider_test_client.test_llm_provider'
        ) as mock:
            from Jeeves.concierge_platform.provider_test_client import TestResult
            mock.return_value = TestResult(
                outcome='success', message='ok', metadata={'models_count': 42},
            )
            resp = c.post(f'{self.url}{row.pk}/test/', {}, format='json')
        assert resp.status_code == 200
        assert resp.data['outcome'] == 'success'
        assert resp.data['metadata']['models_count'] == 42
        assert mock.call_args.kwargs['api_key'] == 'sk-stored'

    def test_test_action_override_key(self):
        row = LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-stored',
        )
        c = _owner()
        with patch(
            'Jeeves.concierge_platform.provider_test_client.test_llm_provider'
        ) as mock:
            from Jeeves.concierge_platform.provider_test_client import TestResult
            mock.return_value = TestResult(outcome='invalid_key', message='bad')
            resp = c.post(
                f'{self.url}{row.pk}/test/',
                {'api_key': 'sk-override'},
                format='json',
            )
        assert resp.status_code == 200
        assert mock.call_args.kwargs['api_key'] == 'sk-override'

    def test_test_unsaved(self):
        c = _owner()
        with patch(
            'Jeeves.concierge_platform.provider_test_client.test_llm_provider'
        ) as mock:
            from Jeeves.concierge_platform.provider_test_client import TestResult
            mock.return_value = TestResult(outcome='success')
            resp = c.post(
                f'{self.url}test-unsaved/',
                {
                    'provider_type': 'openai',
                    'api_key': 'sk-new',
                    'model_name': 'gpt-4o',
                },
                format='json',
            )
        assert resp.status_code == 200
        assert mock.call_args.kwargs['provider_type'] == 'openai'
        assert mock.call_args.kwargs['api_key'] == 'sk-new'

    def test_test_action_does_not_mutate_state(self):
        row = LLMProvider.objects.create(
            name='A', provider_type='openai', model_name='gpt-4o-mini',
            api_key='sk-stored',
        )
        c = _owner()
        with patch(
            'Jeeves.concierge_platform.provider_test_client.test_llm_provider'
        ) as mock:
            from Jeeves.concierge_platform.provider_test_client import TestResult
            mock.return_value = TestResult(outcome='invalid_key')
            c.post(
                f'{self.url}{row.pk}/test/',
                {'api_key': 'sk-override'},
                format='json',
            )
        reloaded = LLMProvider.objects.get(pk=row.pk)
        assert reloaded.api_key == 'sk-stored'
        assert reloaded.is_active is True
