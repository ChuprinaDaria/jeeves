from django.db import models


class PlatformDefaults(models.Model):
    """Singleton. All platform default values. Admin edits. Zero hardcode."""

    class Meta:
        verbose_name = 'Platform Defaults'
        verbose_name_plural = 'Platform Defaults'

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

    @classmethod
    def get_default_llm_provider(cls):
        """Return the active LLMProvider flagged as default, or None."""
        from Jeeves.EmbeddingModel.models import LLMProvider
        return LLMProvider.objects.filter(is_default=True, is_active=True).first()

    @classmethod
    def get_default_embedding_model(cls):
        """Return the active EmbeddingModel flagged as default, or None."""
        from Jeeves.EmbeddingModel.models import EmbeddingModel
        return EmbeddingModel.objects.filter(is_default=True, is_active=True).first()

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


class PlatformLicense(models.Model):
    """Singleton. Holds Gumroad license key + validation state."""

    class LicenseStatus(models.TextChoices):
        MISSING = 'missing', 'Missing'
        VALID = 'valid', 'Valid'
        GRACE = 'grace', 'Grace'
        EXPIRED = 'expired', 'Expired'

    license_key = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=10,
        choices=LicenseStatus.choices,
        default=LicenseStatus.MISSING,
    )

    setup_completed_at = models.DateTimeField(null=True, blank=True)

    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    gumroad_product_id = models.CharField(max_length=100, blank=True)
    gumroad_purchase_email = models.EmailField(blank=True)
    gumroad_uses = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform License'
        verbose_name_plural = 'Platform License'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_setup_complete(self) -> bool:
        return self.setup_completed_at is not None

    @property
    def grace_period_days(self) -> int:
        return 7

    def _grace_anchor(self):
        """Return the datetime from which the grace window is measured."""
        return self.last_verified_at or self.last_attempt_at

    @property
    def is_in_grace_period(self) -> bool:
        if self.status != self.LicenseStatus.GRACE:
            return False
        anchor = self._grace_anchor()
        if anchor is None:
            return False
        from datetime import timedelta
        from django.utils import timezone
        return (timezone.now() - anchor) < timedelta(days=self.grace_period_days)

    @property
    def grace_days_remaining(self):
        """Integer days until grace window expires, or None if not in grace."""
        if self.status != self.LicenseStatus.GRACE:
            return None
        anchor = self._grace_anchor()
        if anchor is None:
            return 0
        import math
        from datetime import timedelta
        from django.utils import timezone
        remaining = (anchor + timedelta(days=self.grace_period_days)) - timezone.now()
        return max(0, math.ceil(remaining.total_seconds() / 86400))
