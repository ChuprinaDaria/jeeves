from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from pgvector.django import VectorField
from MASTER.EmbeddingModel.models import EmbeddingModel
from MASTER.branches.models import Branch

from django.db.models.signals import post_save
from django.dispatch import receiver
from typing import Any, Protocol, cast


def validate_file_size(file):
    max_size_mb = 100
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'File size cannot exceed {max_size_mb}MB')


class Specialization(models.Model):
    # Primary key (explicitly defined for type checking)
    id = models.AutoField(primary_key=True)
    
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='specializations'
    )
    # ForeignKey field automatically creates this attribute for type checking
    branch_id: int
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Custom system prompt for this specialization
    custom_system_prompt = models.TextField(
        blank=True,
        help_text="Custom system prompt for this specialization. Leave empty to use branch default."
    )
    
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='specializations'
    )
    
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_specializations',
        limit_choices_to={'role__in': ['admin', 'owner']}
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_specializations'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Specialization'
        verbose_name_plural = 'Specializations'
        ordering = ['branch', 'name']
        unique_together = [['branch', 'slug']]
        indexes = [
            models.Index(fields=['branch', 'slug']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.branch.name} - {self.name}"
    
    def get_embedding_model(self):
        if self.embedding_model:
            return self.embedding_model
        if self.branch.embedding_model:
            return self.branch.embedding_model
        return EmbeddingModel.objects.filter(is_default=True).first()


class SpecializationDocument(models.Model):
    # Primary key (explicitly defined for type checking)
    id = models.AutoField(primary_key=True)
    
    FILE_TYPES = [
        ('pdf', 'PDF'),
        ('txt', 'Text'),
        ('csv', 'CSV'),
        ('xml', 'XML'),
        ('json', 'JSON'),
        ('docx', 'Word'),
    ]
    
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='specializations/%Y/%m/', validators=[validate_file_size])
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
        verbose_name = 'Specialization Document'
        verbose_name_plural = 'Specialization Documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['specialization', 'is_processed']),
        ]

    def __str__(self):
        return f"{self.specialization} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.pk and self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        SpecializationEmbedding.objects.filter(document=self).delete()
        return super().delete(*args, **kwargs)

    def clean(self):
        if not self.pk and self.specialization and self.specialization.documents.count() >= 100:
            raise ValidationError('Maximum of 100 documents per specialization is allowed for now.')


class SpecializationEmbedding(models.Model):
    # Primary key (explicitly defined for type checking)
    id = models.AutoField(primary_key=True)
    
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE,
        related_name='embeddings'
    )
    
    document = models.ForeignKey(
        SpecializationDocument,
        on_delete=models.CASCADE,
        related_name='embeddings',
        null=True,
        blank=True
    )
    
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.PROTECT,
        related_name='specialization_embeddings'
    )
    
    # Fixed at 1536 dimensions (pgvector limit <= 2000; matches text-embedding-3-small)
    # For larger provider vectors, we truncate; for smaller, we pad to 1536
    vector = VectorField(dimensions=1536)
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Specialization Embedding'
        verbose_name_plural = 'Specialization Embeddings'
        indexes = [
            models.Index(fields=['specialization']),
            models.Index(fields=['embedding_model']),
        ]

    def __str__(self):
        return f"Specialization {self.specialization} - {self.content[:50]}"
    
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


@receiver(post_save, sender=SpecializationDocument)
def trigger_document_processing(sender, instance, created, **kwargs):
    if created and not instance.is_processed:
        from MASTER.processing.tasks import process_specialization_document as _task
        cast(_HasDelay, _task).delay(instance.id)