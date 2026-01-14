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
    AnthropicLLMProvider,
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
                return OllamaLLMProvider(
                    api_endpoint=endpoint,
                    model_name=model_name,
                    server_type="light" if provider_type == "ollama_light" else "main",
                )

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

            if provider_type == "anthropic":
                # Використовуємо API key з LLMProvider об'єкта (якщо є) або з settings
                api_key = getattr(llm_provider_obj, "api_key", "").strip()
                if not api_key:
                    # Fallback до settings
                    api_key = getattr(settings, "ANTHROPIC_API_KEY", "").strip()
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY is not configured (neither in LLMProvider nor in settings)")
                return AnthropicLLMProvider(api_key=api_key, model_name=model_name)

            # На всяк випадок: fallback до конфіга, якщо тип незнайомий
            logger.warning(f"Unsupported llm_provider_model.provider_type='{provider_type}', falling back to LLM_CONFIG")

        # 2) Старий шлях: рядкові поля на клієнті
        provider_name = (getattr(client, "llm_provider", None) or "openai").lower()
        model_name = getattr(client, "llm_model_name", None) or self.config.get("model", "gpt-4o-mini")
        
        if "ollama" in provider_name:
            endpoint = getattr(settings, "OLLAMA_MAIN_ENDPOINT", "")
            server_type = "main"
            if provider_name == "ollama_light":
                endpoint = getattr(settings, "OLLAMA_LIGHT_ENDPOINT", endpoint)
                server_type = "light"
            return OllamaLLMProvider(api_endpoint=endpoint, model_name=model_name, server_type=server_type)
        
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
        
        if provider_name == "anthropic":
            api_key = getattr(settings, "ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY is not configured")
            return AnthropicLLMProvider(api_key=api_key, model_name=model_name)
        
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    
    def generate_response(
        self,
        user_query: str,
        context: str,
        client: Client | None = None,
        specialization: Specialization | None = None,
        branch: Branch | None = None,
        stream: bool = True,
    ) -> str | Generator[str, None, None] | dict[str, Any]:
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
            If stream=False: dict with 'content' and 'usage' keys
            If stream=True: generator of chunks (for backward compatibility)
        """
        # Перезавантажуємо клієнта з БД, щоб гарантувати свіжість custom_system_prompt і моделей
        if client is not None and client.pk:
            try:
                client = Client.objects.get(pk=client.pk)
            except Client.DoesNotExist:
                pass  # якщо видалений — використовуємо переданий
        
        system_prompt = self._get_system_prompt(client, specialization, branch)
        
        # Додаємо явну вказівку мови до system prompt для кращого розуміння моделлю
        # (особливо важливо для Ollama)
        language_instruction = ""
        # Визначаємо мову з Accept-Language або дефолт
        # (можна було б передавати language як параметр, але поки беремо з контексту або дефолт)
        # Для початку просто додаємо універсальну інструкцію
        language_instruction = "\n\nIMPORTANT: Always respond in the same language as the user's question. Detect the language automatically."
        
        # Додаємо інструкцію не використовувати markdown
        no_markdown_instruction = "\n\nCRITICAL: Do NOT use markdown formatting in your response. Write plain text only. Do not use **bold**, *italic*, `code blocks`, # headers, - lists, or any other markdown syntax. Use only plain text."
        
        enhanced_system_prompt = system_prompt + language_instruction + no_markdown_instruction
        
        messages: list[ChatCompletionMessageParam] = cast(
            list[ChatCompletionMessageParam],
            [
                {"role": "system", "content": enhanced_system_prompt},
                {
                    "role": "user",
                    "content": f"{context}\n\n=== USER QUESTION ===\n{user_query}",
                },
            ],
        )
        
        logger.info(f"LLM request: provider={getattr(client, 'llm_provider', 'openai')}, model={getattr(client, 'llm_model_name', self.config.get('model'))}, stream={stream}")
        logger.debug(f"System prompt: {system_prompt[:200]}...")
        
        # Call provider (non-streaming unified path) з fallback з main -> light
        provider = self._get_provider(client)
        msg_list = [
            {"role": "system", "content": enhanced_system_prompt},
            {"role": "user", "content": f"{context}\n\n=== USER QUESTION ===\n{user_query}"},
        ]

        def _call_provider(p: BaseLLMProvider) -> dict[str, Any]:
            return p.generate(
                messages=msg_list,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        try:
            result = _call_provider(provider)
        except Exception as e:
            # Якщо це повільний main-сервер Ollama і стався timeout — пробуємо легку пару
            from MASTER.rag.providers.llm import OllamaLLMProvider  # локальний імпорт, щоб уникнути циклів
            is_ollama_main = isinstance(provider, OllamaLLMProvider) and getattr(provider, "server_type", "") == "main"
            err_text = str(e)
            if is_ollama_main and "Read timed out" in err_text:
                logger.warning("Ollama MAIN timed out, falling back to LIGHT server")
                # Беремо легкий endpoint і модель з settings (qwen2.5:1.5b)
                light_endpoint = getattr(settings, "OLLAMA_LIGHT_ENDPOINT", "")
                light_model = getattr(settings, "OLLAMA_LIGHT_LLM_MODEL", "qwen2.5:1.5b")
                fallback = OllamaLLMProvider(
                    api_endpoint=light_endpoint,
                    model_name=light_model,
                    server_type="light",
                )
                result = _call_provider(fallback)
            else:
                # Інші помилки пробросуємо як є
                raise
        
        content = cast(str, result.get('content', ''))
        usage = result.get('usage', {})
        model_name = result.get('model', '')
        
        # Get provider info for metadata - extract from client correctly
        provider_type = 'openai'
        model_name_from_client = None
        if client:
            # Priority 1: Check llm_provider_model (FK)
            llm_provider_obj = getattr(client, "llm_provider_model", None)
            if llm_provider_obj is not None:
                provider_type = getattr(llm_provider_obj, "provider_type", "openai").lower()
                model_name_from_client = getattr(llm_provider_obj, "model_name", None)
            else:
                # Priority 2: Check legacy string fields
                provider_type = (getattr(client, 'llm_provider', None) or 'openai').lower()
                model_name_from_client = getattr(client, 'llm_model_name', None)
        
        # Use model_name from result if available, otherwise from client
        if not model_name and model_name_from_client:
            model_name = model_name_from_client
        
        if not stream:
            # Return dict with content and usage for non-streaming
            return {
                'content': content,
                'usage': usage,
                'model': model_name,
                'provider': provider_type,
            }
        
        # Streaming emulation: yield once (for backward compatibility)
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
                # Add email capabilities info if enabled
                email_info = self._get_email_capabilities_info(client)
                if email_info:
                    client_prompt = client_prompt + "\n\n" + email_info
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
        default_prompt = settings.SYSTEM_PROMPTS.get('default', 'You are a helpful AI assistant.')
        
        # Add email capabilities info if client has email enabled
        if client:
            email_info = self._get_email_capabilities_info(client)
            if email_info:
                default_prompt = default_prompt + "\n\n" + email_info
        
        return default_prompt
    
    def _get_email_capabilities_info(self, client: Client) -> str | None:
        """Get email capabilities information for system prompt if email is enabled."""
        if not getattr(client, 'email_smtp_enabled', False):
            return None
        
        return """EMAIL CAPABILITIES:
You have access to email functionality through SMTP. You can help users with:
- Sending emails: When user asks to "create email", "send email", "write email to [address]", extract recipient, subject, and body, then send the email.
- Analyzing recent emails: When user asks "analyze recent emails", "what's in my emails", provide summary of recent emails.
- Finding emails: When user asks "find emails from [sender]", "show emails from [address]", search and display matching emails.
- Getting recent emails: When user asks "show recent emails", "what's new in email", retrieve and summarize recent emails.

Commands you can understand:
- "створи мейл для [email]" / "send email to [email]" - Send email
- "дай аналіз останніх мейлів" / "analyze recent emails" - Analyze emails
- "знайди мейли від [email]" / "find emails from [email]" - Search emails
- "покажи останні мейли" / "show recent emails" - Get recent emails

Always confirm email actions and provide clear feedback about what was done."""
    
    def _get_client_custom_prompt(self, client: Client) -> str | None:
        """Get custom prompt from client.
        
        Priority:
        1. active_custom_prompt (if using custom prompts system)
        2. custom_system_prompt (legacy field)
        3. metadata['system_prompt'] (if exists)
        """
        # Priority 1: Check active_custom_prompt
        active_custom_prompt = getattr(client, 'active_custom_prompt', None)
        if active_custom_prompt:
            prompt_text = getattr(active_custom_prompt, 'prompt_text', None)
            if isinstance(prompt_text, str) and prompt_text:
                return prompt_text
        
        # Priority 2: Check custom_system_prompt field (legacy)
        custom_prompt = getattr(client, 'custom_system_prompt', None)
        if isinstance(custom_prompt, str) and custom_prompt:
            return custom_prompt
        
        # Priority 3: Check metadata JSON field
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


