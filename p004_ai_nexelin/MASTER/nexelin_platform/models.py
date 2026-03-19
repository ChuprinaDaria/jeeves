from django.db import models


class PlatformDefaults(models.Model):
    """Singleton. All platform default values. Admin edits. Zero hardcode."""

    class Meta:
        verbose_name = 'Platform Defaults'
        verbose_name_plural = 'Platform Defaults'

    default_llm_provider = models.ForeignKey(
        'EmbeddingModel.LLMProvider', on_delete=models.SET_NULL, null=True, blank=True)
    default_embedding_model = models.ForeignKey(
        'EmbeddingModel.EmbeddingModel', on_delete=models.SET_NULL, null=True, blank=True)
    default_temperature = models.FloatField(null=True, blank=True)
    default_max_tokens = models.IntegerField(null=True, blank=True)
    default_similarity_threshold = models.FloatField(null=True, blank=True)
    default_max_context_chunks = models.IntegerField(null=True, blank=True)
    default_top_k = models.IntegerField(null=True, blank=True)
    supported_languages = models.JSONField(default=list, blank=True)
    default_language = models.CharField(max_length=5, blank=True)
    language_detection_method = models.CharField(
        max_length=20,
        choices=[('llm', 'LLM-based'), ('library', 'lingua-py'), ('none', 'Disabled')],
        blank=True)
    default_greeting = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Platform Defaults'


class FeatureFlag(models.Model):
    """Per-client feature toggles. Test on srtyh, rollout to all."""

    ROLLOUT_CHOICES = [
        ('off', 'Off for everyone'),
        ('selected', 'Only selected clients'),
        ('all', 'On for everyone'),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    rollout = models.CharField(max_length=10, choices=ROLLOUT_CHOICES, default='off')
    enabled_clients = models.ManyToManyField('clients.Client', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.key} ({self.rollout})'

    @classmethod
    def is_enabled(cls, key: str, client=None) -> bool:
        from django.core.cache import cache
        cache_key = f'ff:{key}:{client.pk if client else "global"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        flag = cls.objects.filter(key=key).first()
        if not flag:
            result = False
        elif flag.rollout == 'all':
            result = True
        elif flag.rollout == 'selected' and client:
            result = flag.enabled_clients.filter(pk=client.pk).exists()
        else:
            result = False
        cache.set(cache_key, result, 60)
        return result


class SystemMessage(models.Model):
    """All UI/system translated strings. Admin edits. Cached."""

    key = models.CharField(max_length=100, unique=True, db_index=True)
    translations = models.JSONField(
        default=dict, help_text='{"en": "Text", "de": "Text"}')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key: str, lang: str = 'en') -> str:
        from django.core.cache import cache
        cache_key = f'sysmsg:{key}:{lang}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        msg = cls.objects.filter(key=key).first()
        if not msg:
            return ''
        text = msg.translations.get(lang) or msg.translations.get('en', '')
        cache.set(cache_key, text, 300)
        return text
