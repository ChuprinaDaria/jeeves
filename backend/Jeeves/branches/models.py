from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from pgvector.django import VectorField
from Jeeves.EmbeddingModel.models import EmbeddingModel

from django.db.models.signals import post_save
from django.dispatch import receiver
from typing import Any, Protocol, cast


def validate_file_size(file):
    max_size_mb = 100
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'File size cannot exceed {max_size_mb}MB')


class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='branches'
    )
    
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_branches',
        limit_choices_to={'role__in': ['admin', 'owner']}
    )
        
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_branches'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name
    
    def get_embedding_model(self):
        if self.embedding_model:
            return self.embedding_model
        return EmbeddingModel.objects.filter(is_default=True).first()


class BranchDocument(models.Model):
    FILE_TYPES = [
        ('pdf', 'PDF'),
        ('txt', 'Text'),
        ('csv', 'CSV'),
        ('xml', 'XML'),
        ('json', 'JSON'),
        ('docx', 'Word'),
    ]
    
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='branches/%Y/%m/', validators=[validate_file_size])
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    file_size = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    chunks_count = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Branch Document'
        verbose_name_plural = 'Branch Documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['branch', 'is_processed']),
        ]

    def __str__(self):
        return f"{self.branch.name} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.pk and self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def clean(self):
        # Ліміт на кількість документів видалено
        pass
    
    def delete(self, *args, **kwargs):
        BranchEmbedding.objects.filter(document=self).delete()
        return super().delete(*args, **kwargs)


class BranchEmbedding(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='embeddings'
    )
    
    document = models.ForeignKey(
        BranchDocument,
        on_delete=models.CASCADE,
        related_name='embeddings',
        null=True,
        blank=True
    )
    
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.PROTECT,
        related_name='branch_embeddings'
    )
    
    # Fixed at 1536 dimensions (pgvector limit <= 2000; matches text-embedding-3-small)
    # For larger provider vectors, we truncate; for smaller, we pad to 1536
    vector = VectorField(dimensions=1536, null=True, blank=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Branch Embedding'
        verbose_name_plural = 'Branch Embeddings'
        indexes = [
            models.Index(fields=['branch']),
            models.Index(fields=['embedding_model']),
        ]

    def __str__(self):
        return f"Branch {self.branch.name} - {self.content[:50]}"
    
    def save(self, *args, **kwargs):
        if self.vector is not None and self.embedding_model:
            expected_dim = self.embedding_model.dimensions
            actual_dim = len(self.vector)
            if actual_dim > 1536:
                raise ValidationError(f"Vector dimensions exceed maximum: {actual_dim} > 1536")
            if actual_dim < 1536:
                self.vector = list(self.vector) + [0.0] * (1536 - actual_dim)
        super().save(*args, **kwargs)


class _HasDelay(Protocol):
    def delay(self, *args: Any, **kwargs: Any) -> Any: ...


@receiver(post_save, sender=BranchDocument)
def trigger_document_processing(sender, instance, created, **kwargs):
    if created and not instance.is_processed:
        from Jeeves.processing.tasks import process_branch_document as _task
        cast(_HasDelay, _task).delay(instance.id)


from django.db.models.signals import pre_save


@receiver(pre_save, sender=BranchEmbedding)
def auto_generate_embedding_vector(sender, instance, **kwargs):
    """Автоматично генерує вектор для BranchEmbedding, якщо його немає"""
    # Якщо вектор вже є, не генеруємо заново
    if instance.vector is not None:
        return
    
    # Якщо немає контенту, не можемо згенерувати вектор
    if not instance.content:
        return
    
    # Генеруємо вектор через EmbeddingService
    from Jeeves.processing.embedding_service import EmbeddingService
    
    try:
        result = EmbeddingService.create_embedding(
            text=instance.content,
            embedding_model=instance.embedding_model
        )
        instance.vector = result['vector']
        
        # Оновлюємо metadata з інформацією про вектор
        if not instance.metadata:
            instance.metadata = {}
        instance.metadata['dimensions'] = result['dimensions']
        instance.metadata['token_count'] = result.get('token_count', 0)
        instance.metadata['auto_generated'] = True
    except Exception as e:
        # Якщо не вдалося згенерувати, залишаємо помилку в metadata
        if not instance.metadata:
            instance.metadata = {}
        instance.metadata['generation_error'] = str(e)