import requests
from typing import List, Dict, Any
from openai import OpenAI


class BaseLLMProvider:
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class OpenAILLMProvider(BaseLLMProvider):
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key)
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2000)
        
        # Modern OpenAI models use max_completion_tokens instead of max_tokens
        # Some models don't support temperature parameter (only default=1 allowed):
        # - o1/o3 reasoning models (o1, o1-preview, o1-mini, o3, o3-mini)
        # - gpt-5.1 models (gpt-5.1-chat-latest, etc.)
        model_name = self.model_name or ""
        model_lower = model_name.lower()
        no_temperature_models = ("o1", "o3", "gpt-5.1")
        is_reasoning_model = model_lower.startswith(no_temperature_models)

        params: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            # Use max_completion_tokens for all modern OpenAI models
            "max_completion_tokens": max_tokens,
        }

        # Only add temperature for non-reasoning models
        if not is_reasoning_model:
            params["temperature"] = temperature

        response = self.client.chat.completions.create(**params)
        
        return {
            'content': response.choices[0].message.content,
            'model': response.model,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }


class QwenLocalProvider(BaseLLMProvider):
    def __init__(self, api_endpoint: str, model_name: str = 'qwen2.5'):
        self.api_endpoint = api_endpoint.rstrip('/')
        self.model_name = model_name
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2000)
        
        try:
            response = requests.post(
                f"{self.api_endpoint}/chat",
                json={
                    'model': self.model_name,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'content': data.get('response', data.get('content', '')),
                'model': self.model_name,
                'usage': data.get('usage', {})
            }
        except Exception as e:
            raise Exception(f"Qwen generation failed: {str(e)}")


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(self, api_endpoint: str, model_name: str = 'llama3', server_type: str | None = None):
        self.api_endpoint = api_endpoint.rstrip('/')
        self.model_name = model_name
        # server_type: 'main' | 'light' | None — використовується для fallback логіки
        self.server_type = server_type or ''
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        temperature = kwargs.get('temperature', 0.7)
        timeout = kwargs.get('timeout', 180)
        
        try:
            prompt = self._messages_to_prompt(messages)
            
            response = requests.post(
                f"{self.api_endpoint}/api/generate",
                json={
                    'model': self.model_name,
                    'prompt': prompt,
                    'temperature': temperature,
                    'stream': False
                },
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'content': data.get('response', ''),
                'model': self.model_name,
                'usage': {}
            }
        except Exception as e:
            raise Exception(f"Ollama generation failed: {str(e)}")
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        prompt_parts = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)


class KimiLLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str = 'moonshot-v1-8k'):
        self.api_key = api_key
        self.model_name = model_name
        self.api_endpoint = "https://api.moonshot.cn/v1"
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2000)
        
        try:
            response = requests.post(
                f"{self.api_endpoint}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    'model': self.model_name,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'content': data['choices'][0]['message']['content'],
                'model': data['model'],
                'usage': data.get('usage', {})
            }
        except Exception as e:
            raise Exception(f"Kimi generation failed: {str(e)}")


class AnthropicLLMProvider(BaseLLMProvider):
    """Anthropic Claude API провайдер"""
    def __init__(self, api_key: str, model_name: str = 'claude-3-5-sonnet-20241022'):
        self.api_key = api_key
        self.model_name = model_name
        self.api_endpoint = "https://api.anthropic.com/v1"
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2000)
        
        # Anthropic API вимагає окремий system message
        system_message = None
        conversation_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                # Anthropic використовує 'user' та 'assistant' ролі
                conversation_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        try:
            # Формуємо запит для Anthropic API
            payload = {
                'model': self.model_name,
                'messages': conversation_messages,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            if system_message:
                payload['system'] = system_message
            
            response = requests.post(
                f"{self.api_endpoint}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            
            # Anthropic повертає content як масив текстових блоків
            content_parts = []
            if 'content' in data:
                for block in data['content']:
                    if block.get('type') == 'text':
                        content_parts.append(block.get('text', ''))
            
            content = ''.join(content_parts)
            
            return {
                'content': content,
                'model': data.get('model', self.model_name),
                'usage': data.get('usage', {})
            }
        except Exception as e:
            raise Exception(f"Anthropic generation failed: {str(e)}")


