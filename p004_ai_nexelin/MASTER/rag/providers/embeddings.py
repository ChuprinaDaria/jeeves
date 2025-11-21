import requests
from typing import List, Dict, Any, Union
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider:
    def embed(self, texts: Union[str, List[str]]) -> Dict[str, Any]:
        raise NotImplementedError
    
    def get_dimensions(self) -> int:
        raise NotImplementedError


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key)
        # Dimensions mapping for OpenAI embedding models
        self._dimensions_map = {
            'text-embedding-3-small': 1536,
            'text-embedding-3-large': 3072,
            'text-embedding-ada-002': 1536,
            'text-embedding-3': 1536,  # Default for v3
        }
    
    def embed(self, texts: Union[str, List[str]]) -> Dict[str, Any]:
        if isinstance(texts, str):
            texts = [texts]
        
        response = self.client.embeddings.create(
            model=self.model_name,
            input=texts
        )
        
        vectors = [item.embedding for item in response.data]
        # OpenAI python SDK: usage usually present
        total_tokens = response.usage.total_tokens
        actual_dimensions = len(vectors[0]) if vectors else self.get_dimensions()
        
        return {
            'vectors': vectors,
            'token_count': total_tokens,
            'dimensions': actual_dimensions
        }
    
    def get_dimensions(self) -> int:
        # Повертаємо dimensions на основі назви моделі
        for model_key, dims in self._dimensions_map.items():
            if model_key in self.model_name.lower():
                return dims
        # За замовчуванням для нових моделей використовуємо фактичну розмірність
        # Але для безпеки повертаємо 1536
        return 1536


class BGEEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_endpoint: str, model_name: str = 'bge-large'):
        self.api_endpoint = api_endpoint.rstrip('/')
        self.model_name = model_name
    
    def embed(self, texts: Union[str, List[str]]) -> Dict[str, Any]:
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            response = requests.post(
                f"{self.api_endpoint}/embed",
                json={
                    'texts': texts,
                    'model': self.model_name
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'vectors': data['embeddings'],
                'token_count': data.get('token_count', sum(len(t.split()) for t in texts)),
                'dimensions': len(data['embeddings'][0]) if data['embeddings'] else 1536
            }
        except Exception as e:
            raise Exception(f"BGE embedding failed: {str(e)}")
    
    def get_dimensions(self) -> int:
        return 1536


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_endpoint: str = None, model_name: str = 'bge-m3'):
        from django.conf import settings
        self.api_endpoint = (api_endpoint or getattr(settings, 'OLLAMA_ENDPOINT', 'http://localhost:11434')).rstrip('/')
        self.model_name = model_name
    
    def embed(self, texts: Union[str, List[str]]) -> Dict[str, Any]:
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            vectors = []
            for text in texts:
                response = requests.post(
                    f"{self.api_endpoint}/api/embeddings",
                    json={
                        'model': self.model_name,
                        'prompt': text
                    },
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                vectors.append(data['embedding'])
            
            return {
                'vectors': vectors,
                'token_count': sum(len(t.split()) for t in texts),
                'dimensions': len(vectors[0]) if vectors else (1024 if 'bge-m3' in self.model_name.lower() else 768)
            }
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise Exception(f"Ollama embedding failed: {str(e)}")
    
    def get_dimensions(self) -> int:
        if 'bge-m3' in self.model_name.lower():
            return 1024
        else:
            return 768


class AnthropicEmbeddingProvider(BaseEmbeddingProvider):
    """
    Anthropic Embedding Provider
    
    Примітка: Anthropic поки що не має публічних embedding моделей.
    Цей провайдер створено для майбутньої підтримки, коли Anthropic випустить embedding API.
    """
    def __init__(self, api_key: str, model_name: str = 'claude-embedding'):
        self.api_key = api_key
        self.model_name = model_name
        self.api_endpoint = "https://api.anthropic.com/v1"
    
    def embed(self, texts: Union[str, List[str]]) -> Dict[str, Any]:
        """
        Створює embeddings через Anthropic API.
        
        Примітка: Це заглушка. Коли Anthropic випустить embedding API,
        тут буде реалізовано справжній запит до API.
        """
        if isinstance(texts, str):
            texts = [texts]
        
        # Поки що викидаємо помилку, оскільки Anthropic не має embedding API
        raise NotImplementedError(
            "Anthropic поки що не має публічних embedding моделей. "
            "Використовуйте OpenAI або інші провайдери для embeddings."
        )
    
    def get_dimensions(self) -> int:
        # За замовчуванням, коли Anthropic випустить embeddings, вони можуть бути 1024 або 1536
        # Оновіть це значення коли з'явиться офіційна інформація
        return 1024


