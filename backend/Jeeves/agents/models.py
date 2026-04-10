from uuid import uuid4
from django.db import models
from Jeeves.concierge_platform.models import PlatformDefaults


class AgentConfig(models.Model):
    """Per-client AI agent config. All nullable — falls back to PlatformDefaults."""

    client = models.OneToOneField('clients.Client', on_delete=models.CASCADE,
        related_name='agent_config')

    # LLM — null = platform default
    llm_provider = models.ForeignKey('EmbeddingModel.LLMProvider',
        on_delete=models.SET_NULL, null=True, blank=True)
    embedding_model = models.ForeignKey('EmbeddingModel.EmbeddingModel',
        on_delete=models.SET_NULL, null=True, blank=True)

    # Prompts
    system_prompt = models.TextField(blank=True)
    greeting_message = models.TextField(blank=True)

    # Dual-agent prompts (MCP pipeline only)
    assistant_prompt = models.TextField(
        blank=True,
        help_text='System prompt for Jeeves (assistant, Sandbox). Empty = platform default.')
    consultant_prompt = models.TextField(
        blank=True,
        help_text='System prompt for Concierge (concierge, messengers). Empty = platform default.')
    assistant_description = models.TextField(
        blank=True,
        help_text='Description of assistant capabilities (shown in UI + added to prompt)')
    consultant_description = models.TextField(
        blank=True,
        help_text='Description of concierge capabilities (shown in UI + added to prompt)')

    # Generation — null = platform default
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)

    # RAG — null = platform default
    similarity_threshold = models.FloatField(null=True, blank=True)
    max_context_chunks = models.IntegerField(null=True, blank=True)
    top_k = models.IntegerField(null=True, blank=True)

    # Language — empty = platform default
    language = models.CharField(max_length=5, blank=True)
    supported_languages = models.JSONField(default=list, blank=True)
    language_detection = models.BooleanField(null=True, blank=True)

    # Behaviour
    escalation_enabled = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agent Config'
        verbose_name_plural = 'Agent Configs'

    def __str__(self):
        return f'Agent: {self.client}'

    def get_temperature(self):
        if self.temperature is not None:
            return self.temperature
        return PlatformDefaults.get().default_temperature

    def get_max_tokens(self):
        if self.max_tokens is not None:
            return self.max_tokens
        return PlatformDefaults.get().default_max_tokens

    def get_similarity_threshold(self):
        if self.similarity_threshold is not None:
            return self.similarity_threshold
        return PlatformDefaults.get().default_similarity_threshold

    def get_max_context_chunks(self):
        if self.max_context_chunks is not None:
            return self.max_context_chunks
        return PlatformDefaults.get().default_max_context_chunks

    def get_top_k(self):
        if self.top_k is not None:
            return self.top_k
        return PlatformDefaults.get().default_top_k

    def get_language(self):
        if self.language:
            return self.language
        return PlatformDefaults.get().default_language or 'en'

    def get_llm_provider(self):
        return self.llm_provider or PlatformDefaults.get_default_llm_provider()

    def get_embedding_model(self):
        return self.embedding_model or PlatformDefaults.get_default_embedding_model()

    def get_connected_tools(self):
        """Available tools — derived from ToolConnection, not M2M."""
        from Jeeves.tools.models import ToolConnection
        return ToolConnection.objects.filter(
            client=self.client, enabled=True, status='connected'
        ).select_related('tool_card')


class AgentSession(models.Model):
    """Conversation session with an agent."""

    CHANNEL_CHOICES = [
        ('web', 'Web Chat'),
        ('telegram', 'Telegram'),
        ('whatsapp_meta', 'WhatsApp Meta'),
        ('whatsapp_bridge', 'WhatsApp Bridge'),
        ('email', 'Email'),
        ('api', 'API'),
        ('sandbox', 'Sandbox'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    agent_config = models.ForeignKey(AgentConfig, on_delete=models.CASCADE,
        related_name='sessions')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    external_user_id = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=5, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Session {self.id} ({self.channel})'


class AgentLog(models.Model):
    """Log of every tool/LLM call. For analytics and debugging."""

    CALL_TYPE_CHOICES = [
        ('llm', 'LLM Generation'),
        ('tool', 'MCP Tool Call'),
        ('rag', 'RAG Search'),
        ('escalation', 'HITL Escalation'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ok', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
    ]

    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE,
        related_name='logs')
    tool_connection = models.ForeignKey('tools.ToolConnection',
        on_delete=models.SET_NULL, null=True, blank=True)
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES)
    tool_name = models.CharField(max_length=100, blank=True)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    latency_ms = models.IntegerField(null=True)
    tokens_used = models.IntegerField(null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['call_type', 'status']),
            models.Index(fields=['tool_connection', 'created_at']),
        ]

    def __str__(self):
        return f'{self.call_type} {self.tool_name} ({self.status})'
