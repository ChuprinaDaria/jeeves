from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import secrets
from django.utils import timezone
from pgvector.django import VectorField
from MASTER.EmbeddingModel.models import EmbeddingModel
from MASTER.branches.models import Branch
from MASTER.specializations.models import Specialization


def generate_api_key():
    return f"rag_{secrets.token_urlsafe(32)}"


def validate_file_size(_file):
            return None


class Client(models.Model):
    # Primary key (explicitly defined for type checking)
    id = models.AutoField(primary_key=True)
    
    # Client type choices
    TYPE_GENERIC = 'generic'
    TYPE_RESTAURANT = 'restaurant'
    TYPE_HOTEL = 'hotel'
    TYPE_MEDICAL = 'medical'
    TYPE_RETAIL = 'retail'
    CLIENT_TYPE_CHOICES = [
        (TYPE_GENERIC, 'Generic'),
        (TYPE_RESTAURANT, 'Restaurant'),
        (TYPE_HOTEL, 'Hotel'),
        (TYPE_MEDICAL, 'Medical'),
        (TYPE_RETAIL, 'Retail'),
    ]
    
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients'
    )
    
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients'
    )
    
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        help_text="Selected embedding model for this client. If not set, default model will be used."
    )
    
    user = models.CharField(max_length=255)
    company_name = models.CharField(max_length=200, blank=True)

    tag = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        help_text="Unique client token/tag for bootstrap authentication and portal access"
    )
    description = models.TextField()
    
    api_key = models.CharField(max_length=64, unique=True, editable=False)
    
    logo = models.ImageField(
        upload_to='clients/logos/',
        blank=True,
        null=True,
        verbose_name='Логотип',
        help_text='Логотип ресторану для QR-кодів'
    )
    is_active = models.BooleanField(default=True)
    
    # Client type for specific features
    client_type = models.CharField(
        max_length=20,
        choices=CLIENT_TYPE_CHOICES,
        default=TYPE_GENERIC,
        help_text="Type of client business for specific features"
    )
    
    # Features configuration (JSON field for flexibility)
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        Feature flags for this client. Example for restaurant:
        {
            "menu_chat": true,
            "allergens": true,
            "calories": true,
            "table_ordering": true,
            "multilingual": true,
            "photo_recognition": true,
            "pos_webhook": "https://restaurant.com/api/orders",
            "payment_enabled": false
        }
        """
    )
    
    # Custom system prompt for AI responses
    custom_system_prompt = models.TextField(
        blank=True,
        help_text="Custom system prompt for this client's AI assistant. Leave empty to use default."
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_clients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
        super().save(*args, **kwargs)
    
    def generate_api_key(self):
        return secrets.token_urlsafe(32)
    
    def __str__(self):
        return f"{self.company_name or 'Client'} ({self.tag})"
    
    def has_feature(self, feature_name):
        """Check if a specific feature is enabled for this client"""
        return self.features.get(feature_name, False) if self.features else False
    
    def get_feature_config(self, feature_name, default=None):
        """Get configuration value for a specific feature"""
        return self.features.get(feature_name, default) if self.features else default


class ClientAPIConfig(models.Model):
    LANG_PYTHON = 'python'
    LANG_NODEJS = 'nodejs'
    LANG_PHP = 'php'
    LANG_CURL = 'curl'
    LANGUAGE_CHOICES = [
        (LANG_PYTHON, 'Python'),
        (LANG_NODEJS, 'Node.js'),
        (LANG_PHP, 'PHP'),
        (LANG_CURL, 'cURL'),
    ]

    INTEGRATION_TELEGRAM = 'telegram'
    INTEGRATION_WHATSAPP = 'whatsapp'
    INTEGRATION_WEB = 'web'
    INTEGRATION_MOBILE = 'mobile'
    INTEGRATION_CHOICES = [
        (INTEGRATION_TELEGRAM, 'Telegram'),
        (INTEGRATION_WHATSAPP, 'WhatsApp'),
        (INTEGRATION_WEB, 'Web'),
        (INTEGRATION_MOBILE, 'Mobile'),
    ]

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='api_config'
    )
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default=LANG_PYTHON)
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_CHOICES, default=INTEGRATION_WEB)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Client API Config'
        verbose_name_plural = 'Client API Configs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client} — {self.language}/{self.integration_type}"

class ClientAPIKey(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    
    key = models.CharField(max_length=64, unique=True, default=generate_api_key)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    rate_limit_per_minute = models.IntegerField(default=60)
    rate_limit_per_day = models.IntegerField(default=10000)
    
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Client API Key'
        verbose_name_plural = 'Client API Keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key', 'is_active']),
        ]

    def __str__(self):
        return f"{self.client} - {self.name}"
    
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class ClientDocument(models.Model):
    # Primary key (explicitly defined for type checking)
    id = models.AutoField(primary_key=True)
    
    FILE_TYPES = [
        ('pdf', 'PDF'),
        ('txt', 'Text'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('docx', 'Word'),
    ]
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    knowledge_block = models.ForeignKey(
        'KnowledgeBlock',
        on_delete=models.SET_NULL,
        related_name='documents',
        null=True,
        blank=True,
        help_text="Knowledge block this document belongs to"
    )
    
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='clients/%Y/%m/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    file_size = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    chunks_count = models.IntegerField(default=0)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Client Document'
        verbose_name_plural = 'Client Documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.client} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.pk and self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def clean(self):
        # Максимум 100 документів на клієнта
        if not self.pk and self.client and self.client.documents.count() >= 100:
            raise ValidationError('Maximum of 100 documents per client is allowed for now.')


class ClientEmbedding(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='embeddings'
    )
    
    document = models.ForeignKey(
        ClientDocument,
        on_delete=models.CASCADE,
        related_name='embeddings',
        null=True,
        blank=True
    )
    
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.PROTECT,
        related_name='client_embeddings'
    )
    
    # TECHNICAL DEBT: Fixed at 3072 dimensions (max for text-embedding-3-large)
    # Most models use 1536 (text-embedding-3-small), wasting 50% storage
    # TODO: Consider dynamic dimensions or separate tables per model dimension
    # Current approach: pad smaller vectors with zeros (see save() method)
    vector = VectorField(dimensions=3072, null=True, blank=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Client Embedding'
        verbose_name_plural = 'Client Embeddings'
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['embedding_model']),
        ]

    def __str__(self):
        return f"Client {self.client.user.username} - {self.content[:50]}"
    
    def save(self, *args, **kwargs):
        if self.vector is not None and self.embedding_model:
            actual_dim = len(self.vector)
            if actual_dim > 3072:
                raise ValidationError(f"Vector dimensions exceed maximum: {actual_dim} > 3072")
            if actual_dim < 3072:
                self.vector = list(self.vector) + [0.0] * (3072 - actual_dim)
        super().save(*args, **kwargs)


class ClientZeroConfig(models.Model):
    """Per-client configuration and runtime state for the Mail-0 Zero service.

    Zero repo: https://github.com/Mail-0/Zero
    This model stores env/secrets, container routing, and lifecycle metadata so
    we can start/stop an isolated Zero instance per client.
    """

    STATUS_DISABLED = 'disabled'
    STATUS_STARTING = 'starting'
    STATUS_RUNNING = 'running'
    STATUS_STOPPING = 'stopping'
    STATUS_STOPPED = 'stopped'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_DISABLED, 'Disabled'),
        (STATUS_STARTING, 'Starting'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_STOPPING, 'Stopping'),
        (STATUS_STOPPED, 'Stopped'),
        (STATUS_ERROR, 'Error'),
    ]

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='zero_config'
    )

    # Enable/disable from admin
    enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DISABLED)

    # Image/repository
    image = models.CharField(max_length=200, blank=True, default='', help_text="Optional prebuilt image tag, e.g. ghcr.io/mail-0/zero:staging")
    repo_url = models.CharField(max_length=300, default='https://github.com/Mail-0/Zero')
    repo_branch = models.CharField(max_length=64, default='staging')

    # Networking/routing
    subdomain = models.CharField(max_length=100, blank=True, help_text="Optional subdomain for routing (e.g. client1)")
    domain = models.CharField(max_length=200, blank=True, help_text="Root domain for routing (e.g. example.com)")
    host_port = models.PositiveIntegerField(null=True, blank=True, help_text="Host port mapped to the Zero container (auto-assigned if empty)")

    # Container metadata
    container_name = models.CharField(max_length=150, blank=True)
    container_id = models.CharField(max_length=100, blank=True)

    # Database configuration for Zero (separate DB per client recommended)
    db_name = models.CharField(max_length=100, blank=True)
    db_user = models.CharField(max_length=100, blank=True)
    db_password = models.CharField(max_length=200, blank=True)
    db_host = models.CharField(max_length=200, blank=True, default='postgres')
    db_port = models.PositiveIntegerField(default=5432)

    # Required secrets/integrations (can be empty for minimal/local use)
    better_auth_secret = models.CharField(max_length=200, blank=True)
    google_client_id = models.CharField(max_length=300, blank=True)
    google_client_secret = models.CharField(max_length=300, blank=True)
    autumn_secret_key = models.CharField(max_length=300, blank=True)
    twilio_account_sid = models.CharField(max_length=200, blank=True)
    twilio_auth_token = models.CharField(max_length=200, blank=True)
    twilio_phone_number = models.CharField(max_length=50, blank=True)

    # Sync-related flags from project docs
    drop_agent_tables = models.BooleanField(default=False)
    thread_sync_max_count = models.PositiveIntegerField(default=500)
    thread_sync_loop = models.BooleanField(default=True)

    # Arbitrary extra env for future needs
    custom_env = models.JSONField(default=dict, blank=True)

    # Diagnostics
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Client Zero Config'
        verbose_name_plural = 'Client Zero Configs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
        ]

    def __str__(self) -> str:
        return f"Zero for {self.client} ({self.status})"

    @property
    def database_url(self) -> str:
        if not (self.db_user and self.db_password and self.db_host and self.db_name):
            return ''
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def build_env(self) -> dict:
        """Compose environment dict for the Zero container.

        Based on repo docs: https://github.com/Mail-0/Zero
        """
        env = {
            'BETTER_AUTH_SECRET': self.better_auth_secret or '',
            'GOOGLE_CLIENT_ID': self.google_client_id or '',
            'GOOGLE_CLIENT_SECRET': self.google_client_secret or '',
            'AUTUMN_SECRET_KEY': self.autumn_secret_key or '',
            'TWILIO_ACCOUNT_SID': self.twilio_account_sid or '',
            'TWILIO_AUTH_TOKEN': self.twilio_auth_token or '',
            'TWILIO_PHONE_NUMBER': self.twilio_phone_number or '',
            'DATABASE_URL': self.database_url,
            'DROP_AGENT_TABLES': 'true' if self.drop_agent_tables else 'false',
            'THREAD_SYNC_MAX_COUNT': str(self.thread_sync_max_count),
            'THREAD_SYNC_LOOP': 'true' if self.thread_sync_loop else 'false',
        }
        if self.host_port:
            env['PORT'] = str(self.host_port)
        # Merge custom env, do not overwrite defined keys
        for k, v in (self.custom_env or {}).items():
            if k not in env:
                env[k] = v
        return env

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from typing import Any, Protocol, cast

# Restaurant models moved to restaurant app


class _HasDelay(Protocol):
    def delay(self, *args: Any, **kwargs: Any) -> Any: ...


@receiver(post_save, sender=ClientDocument)
def trigger_document_processing(sender, instance, created, **kwargs):
    if created and not instance.is_processed:
        from MASTER.processing.tasks import process_client_document as _task
        cast(_HasDelay, _task).delay(instance.id)


@receiver(pre_save, sender=ClientEmbedding)
def auto_generate_client_embedding_vector(sender, instance, **kwargs):
    """Автоматично генерує вектор для ClientEmbedding, якщо його немає"""
    # Якщо вектор вже є, не генеруємо заново
    if instance.vector is not None:
        return
    
    # Якщо немає контенту, не можемо згенерувати вектор
    if not instance.content:
        return
    
    # Генеруємо вектор через EmbeddingService
    from MASTER.processing.embedding_service import EmbeddingService
    
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


class KnowledgeBlock(models.Model):
    """Knowledge block for organizing client documents and knowledge."""
    id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='knowledge_blocks'
    )
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text="Short description of the knowledge block")
    is_active = models.BooleanField(default=True)
    is_permanent = models.BooleanField(default=False, help_text="Permanent blocks cannot be edited or deleted")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Knowledge Block'
        verbose_name_plural = 'Knowledge Blocks'
        ordering = ['is_permanent', 'name']
        unique_together = [['client', 'name']]
    
    def __str__(self):
        return f"{self.client} - {self.name}"
    
    @property
    def entries_count(self):
        """Count of documents in this knowledge block."""
        return self.documents.count()
    
    def get_documents(self):
        """Get all documents in this knowledge block."""
        return ClientDocument.objects.filter(
            knowledge_block=self,
            client=self.client
        )


class ClientQRCode(models.Model):
    """QR codes for WhatsApp integration - available for all clients (up to 10 per client)"""
    id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='qr_codes',
        verbose_name='Client'
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name='Name',
        help_text='Name/label for this QR code (e.g., "Front Desk", "Reception", "Table 5")'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Description',
        help_text='Optional description of where this QR code is used'
    )
    
    # QR Code
    qr_code = models.ImageField(
        upload_to='clients/qr_codes/',
        blank=True,
        null=True,
        verbose_name='QR Code',
        help_text='QR code image for customer scanning'
    )
    
    qr_code_url = models.URLField(
        blank=True,
        editable=False,
        verbose_name='QR Code URL'
    )
    
    # Unique token for this QR code (used in WhatsApp prefill)
    qr_token = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        verbose_name='QR Token',
        help_text='Unique token for this QR code used in WhatsApp links'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        help_text='Whether this QR code is active'
    )
    
    # Metadata
    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Location',
        help_text='Where this QR code is placed (e.g., "Front Desk", "Table 5", "Reception")'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    class Meta:
        verbose_name = 'Client QR Code'
        verbose_name_plural = 'Client QR Codes'
        ordering = ['client', 'name']
        unique_together = [['client', 'name']]
        indexes = [
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['qr_token']),
        ]
    
    def __str__(self):
        return f"{self.client.company_name} - {self.name}"
    
    def clean(self):
        """Validate that client doesn't exceed 10 QR codes"""
        if self.pk is None and self.client:  # New instance
            existing_count = ClientQRCode.objects.filter(client=self.client).count()
            if existing_count >= 10:
                raise ValidationError("Maximum 10 QR codes allowed per client")
    
    def get_whatsapp_prefill(self) -> str:
        """Returns prefill text for WhatsApp"""
        c = self.client
        
        # Get parameters from client
        branch_slug = 'demo'
        specialization_slug = 'generic'
        client_token = f"client-{c.id}"
        
        if hasattr(c, 'specialization') and c.specialization:
            branch_slug = getattr(c.specialization.branch, 'slug', 'demo')
            specialization_slug = getattr(c.specialization, 'slug', 'generic')
        
        # Get client_token from API key
        api_key = c.api_keys.filter(is_active=True).first()
        if api_key:
            client_token = api_key.key
        
        # Use qr_token instead of table_number
        from MASTER.clients.qr_utils import build_start2_prefill
        return build_start2_prefill(branch_slug, specialization_slug, client_token, self.qr_token)
    
    def get_whatsapp_link(self) -> str:
        """Returns WhatsApp deep link for this QR code"""
        from MASTER.clients.qr_utils import build_wa_me_link
        return build_wa_me_link(self.get_whatsapp_prefill())
    
    def generate_qr_code(self):
        """Generate QR code with WhatsApp deep link and client logo"""
        if not self.client:
            raise ValidationError("Cannot generate QR code without client")
        
        link = self.get_whatsapp_link()
        logo_path = self.client.logo.path if getattr(self.client, "logo", None) and self.client.logo else None
        
        from MASTER.clients.qr_utils import render_qr_with_logo, save_qr_png_to_field
        png = render_qr_with_logo(link, logo_path)
        fname = f"qr_{self.pk}.png" if self.pk else f"qr_tmp_{self.client.id}_{self.name}.png"
        save_qr_png_to_field(self, "qr_code", png, fname)
        self.qr_code_url = link
    
    def save(self, *args, **kwargs):
        # Generate QR token if not exists
        if not self.qr_token:
            import secrets
            self.qr_token = secrets.token_urlsafe(32)
        
        # Validate before saving
        self.full_clean()
        
        # Generate QR code if not exists
        if not self.qr_code and not self.qr_code_url:
            try:
                self.generate_qr_code()
            except Exception as e:
                # Don't fail save if QR generation fails, but log it
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to generate QR code for {self}: {e}")
        
        super().save(*args, **kwargs)


class ClientWhatsAppConversation(models.Model):
    """WhatsApp conversation history for all clients (not just restaurants)"""
    id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='whatsapp_conversations',
        verbose_name='Client'
    )
    
    # QR code that started this conversation (optional)
    qr_code = models.ForeignKey(
        ClientQRCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='QR Code',
        help_text='QR code that started this conversation'
    )
    
    # Restaurant table (for backward compatibility, optional)
    table = models.ForeignKey(
        'restaurant.RestaurantTable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_conversations',
        verbose_name='Table',
        help_text='Restaurant table (for backward compatibility)'
    )
    
    customer_phone = models.CharField(
        max_length=20,
        verbose_name='Customer Phone',
        help_text='Customer phone number in format +380671234567'
    )
    
    messages = models.JSONField(
        default=list,
        verbose_name='Messages',
        help_text='List of messages in JSON format: [{"role": "user|assistant", "content": "...", "timestamp": "..."}]'
    )
    
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Conversation Start'
    )
    
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Conversation End',
        help_text='Time when conversation ended (null if active)'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        help_text='Whether conversation is active (less than 24 hours without messages)'
    )
    
    total_messages = models.IntegerField(
        default=0,
        verbose_name='Total Messages',
        help_text='Number of messages in conversation'
    )
    
    session_id = models.CharField(
        max_length=100,
        db_index=True,
        blank=True,
        verbose_name='Session ID'
    )
    
    language = models.CharField(
        max_length=10,
        default='uk',
        verbose_name='Language'
    )
    
    context_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Context Metadata'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    class Meta:
        verbose_name = 'Client WhatsApp Conversation'
        verbose_name_plural = 'Client WhatsApp Conversations'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['client', 'customer_phone']),
            models.Index(fields=['qr_code']),
            models.Index(fields=['table']),
            models.Index(fields=['started_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['session_id', 'created_at']),
        ]
    
    def __str__(self):
        qr_name = self.qr_code.name if self.qr_code else "No QR"
        return f"{self.client.company_name} - {self.customer_phone} - {qr_name}"
    
    def add_message(self, role: str, content: str):
        """Adds a message to the conversation"""
        if not self.messages:
            self.messages = []
        
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': timezone.now().isoformat()
        })
        
        self.total_messages = len(self.messages)
        self.save(update_fields=['messages', 'total_messages', 'updated_at'])
    
    def end_conversation(self):
        """Ends the conversation"""
        self.is_active = False
        self.ended_at = timezone.now()
        self.save(update_fields=['is_active', 'ended_at'])
    
    def update_activity_status(self):
        """Updates conversation activity status based on last message time"""
        if not self.messages:
            self.is_active = False
            self.save(update_fields=['is_active'])
            return
        
        # Get last message timestamp
        last_message = self.messages[-1]
        last_timestamp_str = last_message.get('timestamp')
        
        if last_timestamp_str:
            from datetime import datetime
            try:
                last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00'))
                now = timezone.now()
                
                # Conversation is active if last message was less than 24 hours ago
                if (now - last_timestamp).total_seconds() < 86400:
                    self.is_active = True
                else:
                    self.is_active = False
                    if not self.ended_at:
                        self.ended_at = last_timestamp
                
                self.save(update_fields=['is_active', 'ended_at'])
            except Exception:
                pass