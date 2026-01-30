from django.db import models
from MASTER.EmbeddingModel.models import EmbeddingModel, LLMProvider


class UsageStats(models.Model):
    OPERATION_TYPES = [
        ('create_embedding', 'Create Embedding'),
        ('query', 'Query'),
        ('scan_qr', 'Scan QR'),
        ('rag_chat', 'RAG Chat'),
        ('rag_chat_embedding', 'RAG Chat Embedding'),
        ('rag_chat_llm', 'RAG Chat LLM'),
    ]

    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='usage_stats'
    )
    specialization = models.ForeignKey(
        'specializations.Specialization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='usage_stats'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='usage_stats'
    )
    
    embedding_model = models.ForeignKey(
        EmbeddingModel, 
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='usage_stats',
        help_text='Embedding model for embedding operations'
    )
    
    llm_provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='usage_stats',
        help_text='LLM provider for LLM operations'
    )
    
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES)
    
    tokens_used = models.IntegerField()
    cost = models.DecimalField(max_digits=12, decimal_places=6)
    
    date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    metadata = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'Usage Statistics'
        verbose_name_plural = 'Usage Statistics'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch', 'date']),
            models.Index(fields=['specialization', 'date']),
            models.Index(fields=['client', 'date']),
            models.Index(fields=['date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(branch__isnull=False, specialization__isnull=True, client__isnull=True) |
                    models.Q(branch__isnull=True, specialization__isnull=False, client__isnull=True) |
                    models.Q(branch__isnull=True, specialization__isnull=True, client__isnull=False)
                ),
                name='only_one_entity_set'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(embedding_model__isnull=False) | models.Q(llm_provider__isnull=False)
                ),
                name='at_least_one_model_set'
            )
        ]

    def __str__(self):
        target = self.branch or self.specialization or self.client
        model = self.embedding_model or self.llm_provider
        return f"{target} - {model} - {self.tokens_used} tokens - ${self.cost}"

