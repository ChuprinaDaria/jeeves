from unittest.mock import patch

import pytest
import requests

from Jeeves.concierge_platform import provider_test_client as ptc


class _Resp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


class TestLLMDispatch:
    def test_openai_success(self):
        fake = _Resp(200, {'data': [{'id': f'm{i}'} for i in range(47)]})
        with patch('Jeeves.concierge_platform.provider_test_client.requests.get', return_value=fake) as mock_get:
            result = ptc.test_llm_provider('openai', 'sk-good')
        assert result.outcome == 'success'
        assert result.metadata.get('models_count') == 47
        mock_get.assert_called_once()
        assert 'openai.com' in mock_get.call_args[0][0]

    def test_openai_invalid_key(self):
        fake = _Resp(401, {})
        with patch('Jeeves.concierge_platform.provider_test_client.requests.get', return_value=fake):
            result = ptc.test_llm_provider('openai', 'sk-bad')
        assert result.outcome == 'invalid_key'

    def test_openai_timeout(self):
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.get',
            side_effect=requests.Timeout('boom'),
        ):
            result = ptc.test_llm_provider('openai', 'sk-bad')
        assert result.outcome == 'network_error'
        assert 'timeout' in result.message.lower() or 'boom' in result.message.lower()

    def test_anthropic_success(self):
        fake = _Resp(200, {'data': [{'id': 'claude-4'}]})
        with patch('Jeeves.concierge_platform.provider_test_client.requests.get', return_value=fake) as mock_get:
            result = ptc.test_llm_provider('anthropic', 'sk-ant-good')
        assert result.outcome == 'success'
        assert 'anthropic.com' in mock_get.call_args[0][0]

    def test_anthropic_invalid_key(self):
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.get',
            return_value=_Resp(403, {}),
        ):
            result = ptc.test_llm_provider('anthropic', 'sk-ant-bad')
        assert result.outcome == 'invalid_key'

    def test_cohere_success(self):
        fake = _Resp(200, {'models': [{'name': 'command-r'}]})
        with patch('Jeeves.concierge_platform.provider_test_client.requests.get', return_value=fake):
            result = ptc.test_llm_provider('cohere', 'co-good')
        assert result.outcome == 'success'

    def test_kimi_success(self):
        fake = _Resp(200, {'data': [{'id': 'moonshot-v1'}]})
        with patch('Jeeves.concierge_platform.provider_test_client.requests.get', return_value=fake) as mock_get:
            result = ptc.test_llm_provider('kimi', 'ms-good')
        assert result.outcome == 'success'
        assert 'moonshot' in mock_get.call_args[0][0]

    def test_ollama_success(self):
        fake = _Resp(200, {'models': [{'name': 'qwen2.5:7b'}]})
        with patch('Jeeves.concierge_platform.provider_test_client.requests.get', return_value=fake) as mock_get:
            result = ptc.test_llm_provider(
                'ollama_main', '', api_endpoint='http://localhost:11434',
            )
        assert result.outcome == 'success'
        assert '/api/tags' in mock_get.call_args[0][0]

    def test_ollama_connection_refused(self):
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.get',
            side_effect=requests.ConnectionError('refused'),
        ):
            result = ptc.test_llm_provider(
                'ollama_main', '', api_endpoint='http://localhost:11434',
            )
        assert result.outcome == 'network_error'

    def test_unsupported_provider(self):
        result = ptc.test_llm_provider('unknown_xyz', 'any')
        assert result.outcome == 'network_error'
        assert 'unsupported' in result.message.lower()


class TestEmbeddingDispatch:
    def test_openai_embedding_success(self):
        fake = _Resp(200, {'data': [{'embedding': [0.1] * 1536}]})
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.post',
            return_value=fake,
        ):
            result = ptc.test_embedding_model(
                'openai', 'sk-good', 'text-embedding-3-small', dimensions=1536,
            )
        assert result.outcome == 'success'

    def test_openai_embedding_dimension_mismatch_is_warning(self):
        fake = _Resp(200, {'data': [{'embedding': [0.1] * 1024}]})
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.post',
            return_value=fake,
        ):
            result = ptc.test_embedding_model(
                'openai', 'sk-good', 'text-embedding-3-small', dimensions=1536,
            )
        assert result.outcome == 'success'
        assert 'dimension' in result.message.lower()

    def test_openai_embedding_invalid_key(self):
        fake = _Resp(401, {})
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.post',
            return_value=fake,
        ):
            result = ptc.test_embedding_model(
                'openai', 'sk-bad', 'text-embedding-3-small', dimensions=1536,
            )
        assert result.outcome == 'invalid_key'

    def test_cohere_embedding_success(self):
        fake = _Resp(200, {'embeddings': [[0.1] * 1024]})
        with patch(
            'Jeeves.concierge_platform.provider_test_client.requests.post',
            return_value=fake,
        ):
            result = ptc.test_embedding_model(
                'cohere', 'co-good', 'embed-multilingual-v3.0', dimensions=1024,
            )
        assert result.outcome == 'success'

    def test_anthropic_embedding_unsupported(self):
        result = ptc.test_embedding_model(
            'anthropic', 'sk-ant', 'claude-embed', dimensions=1024,
        )
        assert result.outcome == 'network_error'
        assert 'anthropic' in result.message.lower()
