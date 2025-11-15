"""
LLM Client Service for OpenAI ChatGPT integration.

Handles:
- Dynamic system prompts per client/branch/specialization
- Token counting and context management
- Streaming responses
- Error handling and retries
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Generator, Any, cast, Iterable

from django.conf import settings
from MASTER.rag.providers.llm import (
    OpenAILLMProvider,
    OllamaLLMProvider,
    KimiLLMProvider,
    BaseLLMProvider,
)

from MASTER.clients.models import Client
from MASTER.branches.models import Branch
from MASTER.specializations.models import Specialization

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    from openai import OpenAIError, RateLimitError, APITimeoutError
    from openai.types.chat import ChatCompletionMessageParam
    from openai.types.chat.chat_completion import ChatCompletion
    from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
except ImportError:
    OpenAI = None
    OpenAIError = Exception
    RateLimitError = Exception
    APITimeoutError = Exception
    ChatCompletionMessageParam = Any
    ChatCompletion = Any
    ChatCompletionChunk = Any
    logger.error("openai package not installed!")


class LLMClient:
    """LLM client with pluggable providers and dynamic prompts."""
    
    def __init__(self):
        self.config = settings.LLM_CONFIG
        self.temperature = self.config.get('temperature', 0.7)
        self.max_tokens = self.config.get('max_tokens', 1500)
        self.timeout = self.config.get('timeout_seconds', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay_seconds', 2)
    
    def _get_provider(self, client: Client | None) -> BaseLLMProvider:
        """
        Обираємо провайдера LLM з урахуванням нових моделей (LLMProvider) і старих полів.
        
        Пріоритет:
        1) client.llm_provider_model (FK на LLMProvider)
        2) client.llm_provider + client.llm_model_name (рядкові поля)
        3) дефолт з LLM_CONFIG (OpenAI)
        """
        # 1) Новий шлях: LLMProvider FK на клієнті
        llm_provider_obj = getattr(client, "llm_provider_model", None) if client else None
        if llm_provider_obj is not None:
            provider_type = getattr(llm_provider_obj, "provider_type", "openai").lower()
            model_name = getattr(llm_provider_obj, "model_name", self.config.get("model", "gpt-4o-mini"))

            if provider_type in ("ollama_main", "ollama_light"):
                # Вибираємо endpoint за типом сервера
                endpoint = getattr(settings, "OLLAMA_MAIN_ENDPOINT", "")
                if provider_type == "ollama_light":
                    endpoint = getattr(settings, "OLLAMA_LIGHT_ENDPOINT", endpoint)
                return OllamaLLMProvider(api_endpoint=endpoint, model_name=model_name)

            if provider_type == "kimi":
                api_key = getattr(settings, "KIMI_API_KEY", "").strip()
                if not api_key:
                    raise ValueError("KIMI_API_KEY is not configured")
                return KimiLLMProvider(api_key=api_key, model_name=model_name)

            if provider_type == "openai":
                api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
                if not api_key:
                    raise ValueError("OPENAI_API_KEY is not configured")
                return OpenAILLMProvider(model_name=model_name, api_key=api_key)

            # На всяк випадок: fallback до конфіга, якщо тип незнайомий
            logger.warning(f"Unsupported llm_provider_model.provider_type='{provider_type}', falling back to LLM_CONFIG")

        # 2) Старий шлях: рядкові поля на клієнті
        provider_name = (getattr(client, "llm_provider", None) or "openai").lower()
        model_name = getattr(client, "llm_model_name", None) or self.config.get("model", "gpt-4o-mini")
        
        if "ollama" in provider_name:
            endpoint = getattr(settings, "OLLAMA_MAIN_ENDPOINT", "")
            if provider_name == "ollama_light":
                endpoint = getattr(settings, "OLLAMA_LIGHT_ENDPOINT", endpoint)
            return OllamaLLMProvider(api_endpoint=endpoint, model_name=model_name)
        
        if provider_name == "kimi":
            api_key = getattr(settings, "KIMI_API_KEY", "").strip()
            if not api_key:
                raise ValueError("KIMI_API_KEY is not configured")
            return KimiLLMProvider(api_key=api_key, model_name=model_name)
        
        if provider_name == "openai":
            api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
            if not api_key:
                raise ValueError("OPENAI_API_KEY is not configured")
            return OpenAILLMProvider(model_name=model_name, api_key=api_key)
        
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    
    def generate_response(
        self,
        user_query: str,
        context: str,
        client: Client | None = None,
        specialization: Specialization | None = None,
        branch: Branch | None = None,
        stream: bool = True,
    ) -> str | Generator[str, None, None]:
        """
        Generate response from LLM.
        
        Args:
            user_query: User's question
            context: Assembled context from vector search
            client: Client for custom prompts (highest priority)
            specialization: Specialization for industry-specific prompts
            branch: Branch for general prompts
            stream: Whether to stream response
            
        Returns:
            Complete response string or generator of chunks if streaming
        """
        system_prompt = self._get_system_prompt(client, specialization, branch)
        
        messages: list[ChatCompletionMessageParam] = cast(
            list[ChatCompletionMessageParam],
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"{context}\n\n=== USER QUESTION ===\n{user_query}",
                },
            ],
        )
        
        logger.info(f"LLM request: provider={getattr(client, 'llm_provider', 'openai')}, model={getattr(client, 'llm_model_name', self.config.get('model'))}, stream={stream}")
        logger.debug(f"System prompt: {system_prompt[:200]}...")
        
        # Call provider (non-streaming unified path)
        provider = self._get_provider(client)
        msg_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}\n\n=== USER QUESTION ===\n{user_query}"},
        ]
        result = provider.generate(
            messages=msg_list,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = cast(str, result.get('content', ''))
        if not stream:
            return content
        # Streaming emulation: yield once
        def _one_shot() -> Generator[str, None, None]:
            yield content
        return _one_shot()
    
    def _get_system_prompt(
        self,
        client: Client | None,
        specialization: Specialization | None,
        branch: Branch | None,
    ) -> str:
        """
        Get system prompt with priority: Client > Specialization > Branch > Default.
        
        Priority order:
        1. Client custom prompt (if exists in client.metadata['system_prompt'])
        2. Specialization custom prompt (if exists in specialization.metadata['system_prompt'])
        3. Branch-specific prompt from SYSTEM_PROMPTS config
        4. Default prompt
        """
        # Priority 1: Client custom prompt
        if client:
            client_prompt = self._get_client_custom_prompt(client)
            if client_prompt:
                logger.info(f"Using custom prompt for client: {client.user}")
                return client_prompt
        
        # Priority 2: Specialization custom prompt
        if specialization:
            spec_prompt = self._get_specialization_custom_prompt(specialization)
            if spec_prompt:
                logger.info(f"Using custom prompt for specialization: {specialization.name}")
                return spec_prompt
        
        # Priority 3: Branch-specific prompt from config
        if branch:
            branch_key = self._get_branch_prompt_key(branch)
            if branch_key in settings.SYSTEM_PROMPTS:
                logger.info(f"Using branch prompt: {branch_key}")
                return settings.SYSTEM_PROMPTS[branch_key]
        
        # Priority 4: Default prompt
        logger.info("Using default system prompt")
        return settings.SYSTEM_PROMPTS['default']
    
    def _get_client_custom_prompt(self, client: Client) -> str | None:
        """Get custom prompt from client metadata."""
        # Check if client has custom_system_prompt field (could be added to Client model)
        custom_prompt = getattr(client, 'custom_system_prompt', None)
        if isinstance(custom_prompt, str) and custom_prompt:
            return custom_prompt
        
        # Or check metadata JSON field
        metadata = getattr(client, 'metadata', None)
        if isinstance(metadata, dict):
            value = metadata.get('system_prompt')
            if isinstance(value, str):
                return value
        
        return None
    
    def _get_specialization_custom_prompt(self, specialization: Specialization) -> str | None:
        """Get custom prompt from specialization metadata."""
        # Could add custom_system_prompt field to Specialization model
        custom_prompt = getattr(specialization, 'custom_system_prompt', None)
        if isinstance(custom_prompt, str) and custom_prompt:
            return custom_prompt
        
        # Or use metadata JSON if it exists
        # For now, return None - can be extended later
        return None
    
    def _get_branch_prompt_key(self, branch: Branch) -> str:
        """Map branch name to prompt key."""
        # Normalize branch name to match SYSTEM_PROMPTS keys
        name_lower = branch.name.lower()
        
        # Map common branch names to prompt keys
        mapping = {
            'medical': 'medical',
            'medicine': 'medical',
            'healthcare': 'medical',
            'legal': 'legal',
            'law': 'legal',
            'hotel': 'hotel',
            'hospitality': 'hotel',
            'restaurant': 'restaurant',
            'food': 'restaurant',
        }
        
        for key, prompt_key in mapping.items():
            if key in name_lower:
                return prompt_key
        
        return 'default'
    
    def _stream_response(self, response: Iterable[Any]) -> Generator[str, None, None]:
        """Stream response chunks from OpenAI."""
        for chunk in response:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield content


