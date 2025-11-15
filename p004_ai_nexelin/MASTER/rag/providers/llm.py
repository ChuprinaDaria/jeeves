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
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
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


