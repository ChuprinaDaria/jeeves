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
    """OpenAI ChatGPT client with dynamic prompt support."""
    
    def __init__(self):
        if not OpenAI:
            raise ImportError("openai package required for LLMClient")
        
        self.config = settings.LLM_CONFIG
        
        # Очищаємо API ключ від зайвих пробілів та символів
        api_key = settings.OPENAI_API_KEY.strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set or empty")
        
        self.client = OpenAI(api_key=api_key)
        self.model = self.config['model']
        self.temperature = self.config['temperature']
        self.max_tokens = self.config['max_tokens']
        self.timeout = self.config['timeout_seconds']
        self.max_retries = self.config['max_retries']
        self.retry_delay = self.config['retry_delay_seconds']
    
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
        
        logger.info(f"LLM request: model={self.model}, stream={stream}")
        logger.debug(f"System prompt: {system_prompt[:200]}...")
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.config.get('top_p', 1.0),
                    frequency_penalty=self.config.get('frequency_penalty', 0.0),
                    presence_penalty=self.config.get('presence_penalty', 0.0),
                    stream=stream,
                    timeout=self.timeout,
                )
                
                if stream:
                    response_stream = cast(Iterable[Any], response)
                    return self._stream_response(response_stream)
                else:
                    completion = cast(Any, response)
                    return completion.choices[0].message.content or ""
            
            except RateLimitError as e:
                logger.warning(f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    raise
            
            except APITimeoutError as e:
                logger.warning(f"API timeout (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise
            
            except OpenAIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise
        
        raise Exception("Max retries exceeded")
    
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


