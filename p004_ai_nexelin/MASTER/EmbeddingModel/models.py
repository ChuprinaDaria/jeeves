from django.db import models
from django.utils.text import slugify


class EmbeddingModel(models.Model):
    PROVIDERS = [
        ('openai', 'OpenAI'),
        ('huggingface', 'HuggingFace'),
        ('cohere', 'Cohere'),
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
            ('light', 'Light Server (192.168.0.53)'),
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
            # Перевіряємо унікальність
            original_slug = self.slug
            counter = 1
            while EmbeddingModel.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Якщо модель стає дефолтною — скинути прапор у інших
        if self.is_default:
            # Використовуємо pk замість id для підтримки типізації
            EmbeddingModel.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)