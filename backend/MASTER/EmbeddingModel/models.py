from django.db import models
from django.utils.text import slugify


class EmbeddingModel(models.Model):
    PROVIDERS = [
        ('openai', 'OpenAI'),
        ('huggingface', 'HuggingFace'),
        ('cohere', 'Cohere'),
        ('anthropic', 'Anthropic (Claude)'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    model_name = models.CharField(max_length=100)
    dimensions = models.IntegerField()
    api_endpoint = models.URLField(
        blank=True,
        null=True,
        help_text='API endpoint for local models'
    )
    is_local = models.BooleanField(
        default=False,
        help_text='Is this a locally hosted model?'
    )
    server_type = models.CharField(
        max_length=20,
        default='',
        choices=[
            ('', 'Cloud/API'),
            ('main', 'Main Server (192.168.0.51)'),
            ('light', 'Light Server (192.168.0.52)'),
        ],
        blank=True
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='API key for third-party services (Kimi, etc.)'
    )
    cost_per_1k_tokens = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    external_guid = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='GUID from mg.nexelin.com for AI model identification in usage stats API'
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    reindex_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'EmbeddingModel'
        verbose_name = 'Embedding Model'
        verbose_name_plural = 'Embedding Models'
        ordering = ['provider', 'name']
    
    def __str__(self):
        return f"{self.provider} - {self.name} ({self.dimensions}d)"
    
    def save(self, *args, **kwargs):
        # Генеруємо slug з name, якщо він не встановлений
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class LLMProvider(models.Model):
    """LLM провайдер для генерації відповідей (не для embeddings)"""
    
    PROVIDER_TYPES = [
        ('openai', 'OpenAI'),
        ('ollama_main', 'Ollama Main Server'),
        ('ollama_light', 'Ollama Light Server'),
        ('kimi', 'Kimi (Moonshot AI)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('custom', 'Custom'),
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Display name (e.g., "GPT-4o Mini", "Qwen2.5 7B Main")'
    )
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    provider_type = models.CharField(
        max_length=50,
        choices=PROVIDER_TYPES,
        help_text='Provider type'
    )
    model_name = models.CharField(
        max_length=100,
        help_text='Model identifier (e.g., "gpt-4o-mini", "qwen2.5:7b")'
    )
    api_endpoint = models.URLField(
        blank=True,
        null=True,
        help_text='API endpoint for Ollama/custom providers (e.g., http://192.168.0.51:11434)'
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='API key (для OpenAI, Anthropic, Kimi)'
    )
    
    # Ціноутворення
    cost_per_1k_input_tokens = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        help_text='Cost per 1000 input tokens (USD)'
    )
    cost_per_1k_output_tokens = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        help_text='Cost per 1000 output tokens (USD)'
    )
    
    # Параметри моделі
    max_tokens = models.IntegerField(
        default=4096,
        help_text='Maximum context length'
    )
    temperature = models.FloatField(
        default=0.7,
        help_text='Default temperature (0.0-2.0)'
    )
    
    # Статус
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Метадані
    description = models.TextField(
        blank=True,
        help_text='Description of the model capabilities'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    external_guid = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='GUID from mg.nexelin.com for LLM model identification in usage stats API'
    )
    
    class Meta:
        app_label = 'EmbeddingModel'
        verbose_name = 'LLM Provider'
        verbose_name_plural = 'LLM Providers'
        ordering = ['provider_type', 'name']
    
    def __str__(self):
        return f"{self.get_provider_type_display()} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Генеруємо slug з name, якщо він не встановлений
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ModelPair(models.Model):
    """
    Model pair (LLM + Embedding) with GUID.
    
    NOTE: This model is deprecated for usage statistics.
    Statistics are now sent separately for embedding and LLM models using their own GUIDs
    (EmbeddingModel.external_guid and LLMProvider.external_guid).
    This model may be kept for other purposes or removed in the future.
    """
    llm_provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.CASCADE,
        related_name='model_pairs',
        verbose_name='LLM Provider',
        help_text='LLM model for this pair'
    )
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.CASCADE,
        related_name='model_pairs',
        verbose_name='Embedding Model',
        help_text='Embedding model for this pair'
    )
    external_guid = models.CharField(
        max_length=255,
        unique=True,
        help_text='GUID from mg.nexelin.com for this model pair (LLM + Embedding) identification in usage stats API'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this pair is active and can be used'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'EmbeddingModel'
        verbose_name = 'Model Pair'
        verbose_name_plural = 'Model Pairs'
        ordering = ['llm_provider', 'embedding_model']
        unique_together = [['llm_provider', 'embedding_model']]
        indexes = [
            models.Index(fields=['llm_provider', 'embedding_model']),
            models.Index(fields=['external_guid']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.llm_provider.name} + {self.embedding_model.name} (GUID: {self.external_guid})"
