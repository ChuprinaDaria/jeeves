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
    TYPE_WHITE_LABEL = 'white_label'
    CLIENT_TYPE_CHOICES = [
        (TYPE_GENERIC, 'Generic'),
        (TYPE_RESTAURANT, 'Restaurant'),
        (TYPE_HOTEL, 'Hotel'),
        (TYPE_MEDICAL, 'Medical'),
        (TYPE_RETAIL, 'Retail'),
        (TYPE_WHITE_LABEL, 'White Label'),
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
    
    # LLM configuration (generation model) per client
    # New: ForeignKey to LLMProvider (preferred)
    llm_provider_model = models.ForeignKey(
        'EmbeddingModel.LLMProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        help_text="Selected LLM provider model. If not set, llm_provider and llm_model_name will be used."
    )
    # Legacy: CharField for backward compatibility
    llm_provider = models.CharField(
        max_length=50,
        default='openai',
        choices=[
            ('openai', 'OpenAI'),
            ('ollama_main', 'Ollama Main (qwen2.5:7b)'),
            ('ollama_light', 'Ollama Light (qwen2.5:1.5b)'),
            ('kimi', 'Kimi (Moonshot AI)'),
        ]
    )
    llm_model_name = models.CharField(
        max_length=100,
        default='gpt-4o-mini',
        help_text='Model name: gpt-4o-mini, qwen2.5, llama3, etc.'
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
    
    webchat_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Custom base domain for web chat and client portal (e.g. chat.example.com)"
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
        help_text="Custom system prompt for this client's AI assistant. Leave empty to use default. Note: Use custom_prompts for multiple prompts management."
    )
    
    # Active custom prompt (reference to ClientCustomPrompt)
    active_custom_prompt = models.ForeignKey(
        'ClientCustomPrompt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_for_clients',
        verbose_name='Active Custom Prompt',
        help_text='Currently active custom prompt (if using custom prompts system)'
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_clients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Meta WhatsApp Business per-client configuration
    whatsapp_meta_enabled = models.BooleanField(default=False, help_text="Enable Meta WhatsApp for this client")
    meta_waba_id = models.CharField(max_length=64, blank=True, help_text="Meta WhatsApp Business Account ID")
    meta_app_id = models.CharField(max_length=64, blank=True, help_text="Meta App ID")
    meta_app_secret = models.CharField(max_length=200, blank=True, help_text="Meta App Secret")
    meta_access_token = models.TextField(blank=True, help_text="Meta Graph API Access Token")
    meta_phone_number_id = models.CharField(max_length=64, blank=True, help_text="Meta Business Phone Number ID")
    meta_verify_token = models.CharField(max_length=128, blank=True, help_text="Webhook verify token for Meta")
    meta_phone_number = models.CharField(max_length=20, blank=True, help_text="Business phone number in E.164 format, e.g. +14155552671")

    # Telegram Bot per-client configuration
    telegram_enabled = models.BooleanField(default=False, help_text="Enable Telegram Bot for this client")
    telegram_bot_token = models.CharField(max_length=255, blank=True, help_text="Telegram Bot Token from @BotFather")
    telegram_webhook_url = models.URLField(blank=True, help_text="Telegram webhook URL (auto-generated)")
    telegram_welcome_message = models.TextField(
        blank=True,
        help_text="Custom welcome message for Telegram bot. Shown when user sends /start. Use {name} for user's first name."
    )

    greeting_message = models.TextField(
        blank=True,
        default='',
        help_text="Universal greeting message shown to customers on first contact in all channels (web, Telegram, WhatsApp). Displayed exactly as written."
    )

    # Web Widget configuration (only for white label clients)
    widget_enabled = models.BooleanField(default=False, help_text="Enable web widget for white label clients")

    # Browser extension (Chrome) configuration
    extension_enabled = models.BooleanField(
        default=False,
        help_text="Enable Google Chrome extension for web scraping & semantic analysis"
    )

    # Pixel art dashboard visualization
    pixel_dashboard_enabled = models.BooleanField(
        default=False,
        help_text="Enable pixel art dashboard visualization for this client"
    )

    # Telephony (voice AI)
    telephony_enabled = models.BooleanField(
        default=False,
        help_text="Enable telephony/voice AI for this client"
    )

    # Leads collection
    leads_enabled = models.BooleanField(
        default=False,
        help_text="Enable lead collection from messenger conversations. LLM will extract contact data and interest score."
    )

    # Usage statistics sync configuration
    sync_usage_stats = models.BooleanField(
        default=True,
        help_text="Enable/disable sending usage statistics to MG for this client"
    )

    # SMTP Email configuration
    email_smtp_enabled = models.BooleanField(default=False, help_text="Enable SMTP email for this client")
    email_smtp_host = models.CharField(max_length=255, blank=True, help_text="SMTP server host (e.g., smtp.gmail.com)")
    email_smtp_port = models.IntegerField(default=587, help_text="SMTP server port (usually 587 for TLS, 465 for SSL)")
    email_smtp_use_tls = models.BooleanField(default=True, help_text="Use TLS encryption for SMTP")
    email_smtp_username = models.CharField(max_length=255, blank=True, help_text="SMTP username (usually email address)")
    email_smtp_password = models.CharField(max_length=255, blank=True, help_text="SMTP password or app password")
    email_from_address = models.EmailField(blank=True, help_text="From email address for sending emails")
    email_from_name = models.CharField(max_length=255, blank=True, help_text="From name for sending emails")
    
    # Email report configuration for chat summaries
    email_report_enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic email reports for closed chat sessions"
    )
    email_report_recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="List of email addresses to receive chat summary reports. Example: ['owner@example.com', 'support@example.com']"
    )
    
    # Default language for notifications (emails, reports, manager messages)
    NOTIFICATION_LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('de', 'Deutsch'),
        ('fr', 'Français'),
        ('es', 'Español'),
        ('it', 'Italiano'),
        ('nl', 'Nederlands'),
        ('da', 'Dansk'),
        ('uk', 'Українська'),
        ('ru', 'Русский'),
    ]
    notification_language = models.CharField(
        max_length=5,
        choices=NOTIFICATION_LANGUAGE_CHOICES,
        default='en',
        help_text="Default language for email reports, daily digests, and manager notifications. Customer-facing AI responses use customer's language."
    )

    # HITL (Human-in-the-Loop) configuration for manager escalation
    hitl_enabled = models.BooleanField(
        default=False,
        help_text="Enable Human-in-the-Loop escalation to managers when AI cannot answer"
    )
    manager_telegram_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of manager Telegram user IDs for escalation. Example: [123456789, 987654321]. Managers receive questions when AI cannot answer."
    )
    
    # Matrix.org HITL configuration
    matrix_hitl_enabled = models.BooleanField(
        default=False,
        help_text="Enable Matrix.org for HITL escalations (unified interface for all channels)"
    )
    matrix_manager_user_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Matrix user IDs for managers (e.g., ['@manager1:matrix.org', '@manager2:matrix.org']). Managers receive escalations in Matrix rooms."
    )
    matrix_homeserver_url = models.CharField(
        max_length=255,
        default='https://matrix.org',
        blank=True,
        help_text="Matrix homeserver URL (default: https://matrix.org)"
    )

    # WhatsApp Bridge (mautrix-whatsapp) — per-client configuration
    whatsapp_bridge_enabled = models.BooleanField(
        default=False,
        help_text="Enable WhatsApp via mautrix-whatsapp bridge for this client"
    )
    whatsapp_bridge_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Connected WhatsApp phone number (filled after successful login)"
    )
    whatsapp_bridge_matrix_user_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Matrix user ID for this client's bridge bot (e.g., @concierge_client_42:crm.local)"
    )
    whatsapp_bridge_matrix_access_token = models.TextField(
        blank=True,
        help_text="Matrix access token for the bridge bot user"
    )
    WHATSAPP_BRIDGE_STATUS_CHOICES = [
        ('disconnected', 'Disconnected'),
        ('qr_pending', 'QR Pending'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ]
    whatsapp_bridge_status = models.CharField(
        max_length=20,
        default='disconnected',
        choices=WHATSAPP_BRIDGE_STATUS_CHOICES,
        help_text="Current WhatsApp bridge connection status"
    )
    whatsapp_bridge_connected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When WhatsApp was successfully connected"
    )
    whatsapp_bridge_error = models.TextField(
        blank=True,
        help_text="Last error message from bridge connection"
    )

    # Dashboard visibility settings
    dashboard_show_info_center = models.BooleanField(
        default=True,
        help_text="Show Info Center widget in client dashboard"
    )
    dashboard_show_top_prompts = models.BooleanField(
        default=True,
        help_text="Show Top Prompts widget in client dashboard"
    )
    
    # Dashboard layout configuration for White Label
    DASHBOARD_LAYOUT_CHOICES = [
        ('default', 'Default (Stats + InfoCenter + TopPrompts)'),
        ('minimal', 'Minimal (Stats only)'),
        ('white_label', 'White Label (Custom widgets only)'),
        ('hybrid', 'Hybrid (Standard + Custom widgets)'),
    ]
    dashboard_layout = models.CharField(
        max_length=20,
        choices=DASHBOARD_LAYOUT_CHOICES,
        default='default',
        help_text="Dashboard layout type for this client"
    )
    
    # Custom widgets configuration (JSON)
    dashboard_custom_widgets = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        Custom dashboard widgets configuration. Example:
        {
            "widgets": [
                {
                    "type": "html_block",
                    "title": "Welcome",
                    "content": "<h3>Welcome!</h3>",
                    "order": 1,
                    "enabled": true
                },
                {
                    "type": "iframe",
                    "title": "Analytics",
                    "url": "https://example.com/embed",
                    "height": 400,
                    "order": 2,
                    "enabled": true
                }
            ]
        }
        Supported types: html_block, markdown_block, iframe, video, image_banner, quick_links, announcement
        """
    )
    
    # Custom styling for White Label (JSON)
    dashboard_custom_style = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        Custom dashboard styling for white label clients. Example:
        {
            "primary_color": "#4F46E5",
            "secondary_color": "#10B981",
            "logo_url": "https://example.com/logo.png",
            "background_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "custom_css": ".dashboard-card { border-radius: 16px; }"
        }
        """
    )

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
        # Автоматично копіюємо user в company_name, якщо user встановлено
        # Якщо company_name порожнє або не встановлено, використовуємо user
        if self.user and (not self.company_name or self.company_name.strip() == ''):
            self.company_name = self.user
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

    def get_report_recipients(self) -> list[str]:
        """
        Return up to 5 cleaned email recipients for chat reports/digests.

        Backward-compatible:
        - If `email_report_recipients` is a list/JSON, it is used directly.
        - If it's a string, it is split by comma/semicolon.
        """
        raw = getattr(self, "email_report_recipients", None)
        items: list[str] = []

        if isinstance(raw, list):
            items = [str(x) for x in raw if x]
        elif isinstance(raw, str):
            # Allow "a@b.com, c@d.com; e@f.com"
            import re

            items = [p.strip() for p in re.split(r"[;,]", raw) if p and p.strip()]
        elif raw:
            # Any other JSON-ish value (dict, etc.) – treat as single token
            items = [str(raw).strip()]

        # Normalize + basic validation
        cleaned: list[str] = []
        seen: set[str] = set()
        for email_addr in items:
            email_norm = email_addr.strip().strip('"').strip("'")
            if not email_norm:
                continue
            # Basic sanity check (avoid heavy validators here)
            if "@" not in email_norm or "." not in email_norm.split("@")[-1]:
                continue
            email_norm_l = email_norm.lower()
            if email_norm_l in seen:
                continue
            seen.add(email_norm_l)
            cleaned.append(email_norm)
            if len(cleaned) >= 5:
                break

        return cleaned

    def get_manager_telegram_ids(self) -> list[int]:
        """
        Return list of manager Telegram user IDs for HITL escalation.
        
        Validates that IDs are integers and removes duplicates.
        """
        raw = getattr(self, "manager_telegram_ids", None)
        if not raw:
            return []
        
        if isinstance(raw, list):
            ids: list[int] = []
            seen: set[int] = set()
            for item in raw:
                try:
                    tid = int(item)
                    if tid > 0 and tid not in seen:
                        seen.add(tid)
                        ids.append(tid)
                except (ValueError, TypeError):
                    continue
            return ids
        
        # Single value case
        try:
            tid = int(raw)
            return [tid] if tid > 0 else []
        except (ValueError, TypeError):
            return []


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
        ('jpg', 'JPEG Image'),
        ('jpeg', 'JPEG Image'),
        ('png', 'PNG Image'),
        ('gif', 'GIF Image'),
        ('webp', 'WebP Image'),
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
        # Ліміт на кількість документів видалено
        pass


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
    
    # Fixed at 1536 dimensions (pgvector limit <= 2000; matches text-embedding-3-small)
    # For larger provider vectors, we truncate; for smaller, we pad to 1536
    vector = VectorField(dimensions=1536, null=True, blank=True)
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
        # client.user is CharField (username string), not ForeignKey
        return f"Client {self.client.user} - {self.content[:50]}"
    
    def save(self, *args, **kwargs):
        if self.vector is not None and self.embedding_model:
            actual_dim = len(self.vector)
            if actual_dim > 1536:
                raise ValidationError(f"Vector dimensions exceed maximum: {actual_dim} > 1536")
            if actual_dim < 1536:
                self.vector = list(self.vector) + [0.0] * (1536 - actual_dim)
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
from django.db.models import F
from django.dispatch import receiver
from typing import Any, Protocol, cast

class _HasDelay(Protocol):
    def delay(self, *args: Any, **kwargs: Any) -> Any: ...


@receiver(post_save, sender=ClientDocument)
def trigger_document_processing(sender, instance, created, **kwargs):
    if created and not instance.is_processed:
        from MASTER.processing.tasks import process_client_document as _task
        cast(_HasDelay, _task).delay(instance.id)


# Store old status before save
_old_parsing_status = {}

@receiver(pre_save, sender='clients.WebParsingRequest')
def store_old_parsing_status(sender, instance, **kwargs):
    """Store old status before save to detect changes"""
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            _old_parsing_status[instance.pk] = old_instance.status
        except sender.DoesNotExist:
            _old_parsing_status[instance.pk] = None

@receiver(post_save, sender='clients.WebParsingRequest')
def process_completed_parsing_request(sender, instance, created, **kwargs):
    """Automatically process parsing request when status changes to completed"""
    if not created and instance.pk:  # Only for existing instances
        try:
            old_status = _old_parsing_status.get(instance.pk)
            
            # Check if status changed to completed and path_to_documents is set
            if (old_status != instance.status and 
                instance.status == WebParsingRequest.STATUS_COMPLETED and 
                instance.path_to_documents and 
                not instance.knowledge_block):
                
                # Process the parsing request asynchronously
                from MASTER.clients.tasks import process_web_parsing_request
                process_web_parsing_request.delay(instance.id)
            
            # Clean up stored status
            if instance.pk in _old_parsing_status:
                del _old_parsing_status[instance.pk]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in process_completed_parsing_request: {e}", exc_info=True)


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

    TARGET_SCOPE_CHOICES = [
        ('all', 'All (available to everyone)'),
        ('assistant', 'Assistant only (Jeevs)'),
        ('manager', 'Manager only (Consultant)'),
    ]

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
    target_scope = models.CharField(
        max_length=20, choices=TARGET_SCOPE_CHOICES, default='all',
        help_text='Who can access this knowledge block')

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
        max_length=500,
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
        help_text='Where this QR code is placed (e.g., "Front Desk", "Table 5", "Reception") or URL for Web Chat'
    )
    
    # Integration type: 'whatsapp' or 'web'
    integration_type = models.CharField(
        max_length=20,
        default='web',
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('web', 'Web Chat'),
        ],
        verbose_name='Integration Type',
        help_text='Type of integration this QR code is for'
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
        if not c:
            return "START2"
        
        # Get parameters from client with better error handling
        branch_slug = 'demo'
        specialization_slug = 'generic'
        client_token = f"client-{c.id}"
        
        try:
            if hasattr(c, 'specialization') and c.specialization:
                # Safely get branch slug
                if hasattr(c.specialization, 'branch') and c.specialization.branch:
                    branch_slug = getattr(c.specialization.branch, 'slug', 'demo')
                # Get specialization slug
                specialization_slug = getattr(c.specialization, 'slug', 'generic')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error getting specialization for client {c.id}: {e}")
        
        # Get client_token from API key with error handling
        try:
            api_key = c.api_keys.filter(is_active=True).first()
            if api_key:
                client_token = api_key.key
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error getting API key for client {c.id}: {e}")
        
        # Use qr_token instead of table_number
        from MASTER.clients.qr_utils import build_start2_prefill
        return build_start2_prefill(branch_slug, specialization_slug, client_token, self.qr_token)
    
    def get_whatsapp_link(self) -> str:
        """Returns WhatsApp deep link for this QR code"""
        from MASTER.clients.qr_utils import build_wa_me_link
        return build_wa_me_link(self.get_whatsapp_prefill(), client=self.client)
    
    def get_web_chat_link(self) -> str:
        """Returns Web Chat link for this QR code - always uses current webchat_domain for white label clients"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Get client tag (priority: client.tag -> API key -> client ID)
        client_tag = None
        if hasattr(self.client, 'tag') and self.client.tag:
            client_tag = self.client.tag
        else:
            try:
                api_key = self.client.api_keys.filter(is_active=True).first()
                if api_key:
                    client_tag = api_key.key
            except Exception as e:
                logger.warning(f"Error getting API key for client {self.client.id}: {e}")
        
        if not client_tag:
            # Fallback: use client ID
            client_tag = f"client-{self.client.id}"
        
        # Construct Web Chat URL - always use current webchat_domain (don't rely on stored location)
        from django.conf import settings
        from urllib.parse import urlparse
        
        # 1) Custom per-client domain (white-label), if configured
        custom_domain = (getattr(self.client, "webchat_domain", "") or "").strip()
        logger.info(f"Client {self.client.id} webchat_domain: '{custom_domain}'")
        
        if custom_domain:
            # Allow both plain host (chat.example.com) and full URL (https://chat.example.com/anything?x=1)
            try:
                if custom_domain.startswith("http://") or custom_domain.startswith("https://"):
                    parsed = urlparse(custom_domain)
                else:
                    parsed = urlparse(f"https://{custom_domain}")
                
                if parsed.scheme and parsed.netloc:
                    # Use only scheme + host, ignore path/query for safety
                    base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                else:
                    # Fallback: strip trailing slash and any query/fragment manually
                    base_url = custom_domain.split("?")[0].split("#")[0].rstrip("/")
                    if not (base_url.startswith("http://") or base_url.startswith("https://")):
                        base_url = f"https://{base_url}".rstrip("/")
            except Exception as e:
                # As a last resort, fallback to https:// + host part
                logger.warning(f"Error parsing webchat_domain '{custom_domain}': {e}")
                host = custom_domain.split("/")[0]
                base_url = f"https://{host}".rstrip("/")
            
            logger.info(f"Using custom domain base_url: {base_url}")
        else:
            # 2) Fallback to global frontend URL
            frontend_url = getattr(settings, 'FRONTEND_URL', None) or getattr(settings, 'CLIENT_PORTAL_BASE_URL', 'http://localhost:3000')
            base_url = frontend_url.rstrip("/") if isinstance(frontend_url, str) else 'http://localhost:3000'
            logger.info(f"Using default FRONTEND_URL: {base_url}")
        
        web_chat_url = f"{base_url}/client?tag={client_tag}"
        logger.info(f"Generated web chat link for client {self.client.id}: {web_chat_url}")
        return web_chat_url
    
    def get_qr_link(self) -> str:
        """Returns the appropriate link based on integration type"""
        if self.integration_type == 'web':
            return self.get_web_chat_link()
        else:  # whatsapp (default)
            return self.get_whatsapp_link()
    
    def generate_qr_code(self):
        """Generate QR code with appropriate link (WhatsApp or Web Chat) and client logo"""
        if not self.client:
            raise ValidationError("Cannot generate QR code without client")
        
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get link based on integration type
            logger.info(f"Generating QR code for ClientQRCode {self.pk}, client {self.client.id}, type: {self.integration_type}")
            link = self.get_qr_link()
            logger.info(f"Link generated ({self.integration_type}): {link[:50]}...")
            
            # For Web Chat, update location if it's not already set or if it's outdated
            if self.integration_type == 'web':
                # Завжди оновлюємо location для web integration, щоб використовувати актуальний webchat_domain
                self.location = link
                logger.info(f"Updated location for web QR code {self.pk}: {link[:50]}...")
            
            # Safely get logo path
            logo_path = None
            try:
                if getattr(self.client, "logo", None) and self.client.logo:
                    logo_path = self.client.logo.path
                    logger.info(f"Using logo: {logo_path}")
            except Exception as e:
                logger.warning(f"Could not get logo path: {e}")
            
            # Generate QR code image
            from MASTER.clients.qr_utils import render_qr_with_logo, save_qr_png_to_field
            png = render_qr_with_logo(link, logo_path)
            fname = f"qr_{self.pk}.png" if self.pk else f"qr_tmp_{self.client.id}_{self.name}.png"
            save_qr_png_to_field(self, "qr_code", png, fname)
            self.qr_code_url = link
            logger.info(f"QR code generated successfully for ClientQRCode {self.pk}")
            
        except Exception as e:
            logger.error(f"Failed to generate QR code for ClientQRCode {self.pk}: {str(e)}", exc_info=True)
            raise
    
    def save(self, *args, **kwargs):
        # Generate QR token if not exists
        if not self.qr_token:
            import secrets
            self.qr_token = secrets.token_urlsafe(32)
        
        # Check if integration_type changed (for regeneration)
        integration_type_changed = False
        if self.pk:
            try:
                old_instance = ClientQRCode.objects.get(pk=self.pk)
                if old_instance.integration_type != self.integration_type:
                    integration_type_changed = True
            except ClientQRCode.DoesNotExist:
                pass
        
        # Validate before saving
        self.full_clean()
        
        # Generate QR code if not exists or if integration_type changed
        if not self.qr_code and not self.qr_code_url:
            try:
                self.generate_qr_code()
            except Exception as e:
                # Don't fail save if QR generation fails, but log it
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to generate QR code for {self}: {e}")
        elif integration_type_changed:
            # Regenerate QR code if integration type changed
            try:
                self.generate_qr_code()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to regenerate QR code for {self} after integration_type change: {e}")
        
        super().save(*args, **kwargs)


class WebParsingRequest(models.Model):
    """Web parsing request for extracting knowledge from websites"""
    
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]
    
    id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='web_parsing_requests',
        verbose_name='Client'
    )
    
    # Client-provided fields
    website_url = models.URLField(
        max_length=500,
        verbose_name='Website URL',
        help_text='URL of the website to parse'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Description',
        help_text='Description of the parsing request'
    )
    
    # Admin-only fields
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Price',
        help_text='Price for this parsing service (admin only)'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Status',
        help_text='Current status of the parsing request'
    )
    
    path_to_documents = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Path to Documents',
        help_text='Server URL and directory path where parsed documents are stored (admin only)'
    )
    
    # Knowledge block created from this parsing
    knowledge_block = models.ForeignKey(
        'KnowledgeBlock',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parsing_requests',
        verbose_name='Knowledge Block',
        help_text='Knowledge block created from this parsing'
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
        verbose_name = 'Web Parsing Request'
        verbose_name_plural = 'Web Parsing Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.client.company_name} - {self.website_url} ({self.get_status_display()})"


class ClientWhatsAppConversation(models.Model):
    """WhatsApp conversation history for all clients"""
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
    
    customer_phone = models.CharField(
        max_length=20,
        verbose_name='Customer Phone',
        help_text='Customer phone number in format +380671234567'
    )
    
    # Для Telegram зберігаємо окремо chat_id, щоб не плутати з номером телефону WhatsApp.
    # При цьому для сумісності ми все ще можемо зберігати значення виду "telegram_<chat_id>" в customer_phone.
    telegram_chat_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Telegram Chat ID',
        help_text='Telegram chat_id for this conversation (used for Telegram integrations)'
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
        default='',
        blank=True,
        verbose_name='Language'
    )
    
    last_user_language = models.CharField(
        max_length=10,
        default='',
        blank=True,
        verbose_name='Last User Language',
        help_text='Language of the most recent user message (updated on every incoming message)'
    )
    
    forced_language = models.CharField(
        max_length=10,
        default='',
        blank=True,
        verbose_name='Forced Language',
        help_text='Language explicitly requested by user (e.g., "speak to me in German"). Cleared only by another explicit request.'
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
    
    # Rating and satisfaction fields
    user_rating = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[('positive', '👍 Positive'), ('negative', '👎 Negative')],
        verbose_name='User Rating',
        help_text='Rating given by user (👍 or 👎)'
    )
    
    ai_rating = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[('positive', '👍 Positive'), ('negative', '👎 Negative')],
        verbose_name='AI Rating',
        help_text='Auto-rating by AI after 5 minutes of inactivity if user did not rate'
    )

    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    ]

    sentiment = models.CharField(
        max_length=16,
        choices=SENTIMENT_CHOICES,
        default='neutral',
        db_index=True,
    )

    rating_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Rating Timestamp',
        help_text='When the rating was given (user or AI)'
    )
    
    # Email report fields
    email_sent = models.BooleanField(
        default=False,
        verbose_name='Email Sent',
        help_text='Whether summary email was sent to client'
    )
    
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Email Sent At',
        help_text='When the summary email was sent'
    )
    
    rating_request_sent = models.BooleanField(
        default=False,
        verbose_name='Rating Request Sent',
        help_text='Whether rating request message was sent to user'
    )
    
    rating_request_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Rating Request Sent At',
        help_text='When the rating request was sent'
    )
    
    summary = models.TextField(
        blank=True,
        verbose_name='Chat Summary',
        help_text='AI-generated summary of the conversation'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notes',
        help_text='Manual notes or comments about this conversation'
    )
    
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last Activity',
        help_text='Timestamp of last message in conversation'
    )
    
    # HITL (Human-in-the-Loop) escalation fields
    is_waiting_for_manager = models.BooleanField(
        default=False,
        verbose_name='Waiting for Manager',
        help_text='True when AI escalated the question to a human manager'
    )
    
    manager_escalation_context = models.TextField(
        blank=True,
        verbose_name='Escalation Context',
        help_text='Stores the question and context while waiting for manager response'
    )
    
    last_escalation_message_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Escalation Message ID',
        help_text='Telegram message_id of the escalation notification sent to manager (for reply tracking)'
    )
    
    escalation_manager_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Escalation Manager ID',
        help_text='Telegram user_id of the manager who received the escalation'
    )
    
    escalation_started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Escalation Started At',
        help_text='When the escalation was triggered (for timeout tracking)'
    )
    
    escalation_original_query = models.TextField(
        blank=True,
        verbose_name='Original Escalation Query',
        help_text='The original user query that triggered escalation (for context when manager responds)'
    )
    
    escalation_language = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Escalation Language',
        help_text='Language of the original query for localized responses'
    )

    last_user_language = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name='Last User Language',
        help_text='Language detected from the most recent user message'
    )

    forced_language = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name='Forced Language',
        help_text='Explicitly requested language (persists until user requests a change)'
    )

    # Matrix.org HITL fields
    matrix_room_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Matrix Room ID',
        help_text="Matrix room ID for HITL escalation (e.g., !abc123:matrix.org)"
    )
    matrix_room_alias = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Matrix Room Alias',
        help_text="Matrix room alias (e.g., #escalation-123:matrix.org)"
    )
    matrix_escalation_active = models.BooleanField(
        default=False,
        verbose_name='Matrix Escalation Active',
        help_text="Whether there's an active escalation in Matrix room"
    )
    matrix_last_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Matrix Last Event ID',
        help_text="Last processed Matrix event ID (for sync)"
    )
    
    class Meta:
        verbose_name = 'Client WhatsApp Conversation'
        verbose_name_plural = 'Client WhatsApp Conversations'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['client', 'customer_phone']),
            models.Index(fields=['qr_code']),
            models.Index(fields=['started_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['session_id', 'created_at']),
            models.Index(fields=['telegram_chat_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'session_id'],
                name='unique_client_session',
                condition=models.Q(session_id__isnull=False) & ~models.Q(session_id=''),
            ),
        ]
    
    def __str__(self):
        qr_name = self.qr_code.name if self.qr_code else "No QR"
        return f"{self.client.company_name} - {self.customer_phone} - {qr_name}"
    
    def set_matrix_room(self, room_id: str, room_alias: str = None, event_id: str = None):
        """Store Matrix room information for HITL escalation."""
        self.matrix_room_id = room_id
        if room_alias:
            self.matrix_room_alias = room_alias
        if event_id:
            self.matrix_last_event_id = event_id
        self.matrix_escalation_active = True
        self.save(update_fields=['matrix_room_id', 'matrix_room_alias', 'matrix_last_event_id', 'matrix_escalation_active'])
    
    def mark_matrix_escalation_resolved(self):
        """Mark Matrix escalation as resolved."""
        self.matrix_escalation_active = False
        self.save(update_fields=['matrix_escalation_active'])
    
    def add_message(self, role: str, content: str):
        """Adds a message to the conversation"""
        if not self.messages:
            self.messages = []
        
        now = timezone.now()
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': now.isoformat()
        })
        
        self.total_messages = len(self.messages)
        self.last_activity_at = now
        self.save(update_fields=['messages', 'total_messages', 'updated_at', 'last_activity_at'])
    
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


class Prompt(models.Model):
    """Public prompt library - доступний для всіх користувачів"""
    CATEGORY_CHOICES = [
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('hr', 'HR / Recruitment'),
        ('customer_support', 'Customer Support'),
        ('legal', 'Legal / Compliance'),
        ('finance', 'Finance / Analytics'),
        ('tech', 'Software Development'),
        ('content', 'Content Creation'),
    ]

    INDUSTRY_CHOICES = [
        ('retail', 'Retail'),
        ('healthcare', 'Healthcare'),
        ('finance', 'Finance'),
        ('tech', 'Technology'),
        ('education', 'Education'),
        ('all', 'All Industries'),
    ]

    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    industry = models.CharField(max_length=100, choices=INDUSTRY_CHOICES, default='all')
    description = models.TextField()
    prompt_template = models.TextField(help_text="Prompt template with {{variables}}")
    variables = models.JSONField(default=list, help_text="List of variable definitions")
    examples = models.JSONField(default=list, blank=True, help_text="Example inputs and outputs")
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_prompts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI model settings
    model = models.CharField(max_length=50, default='gpt-4', help_text="Recommended model")
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=1500)
    
    # Statistics
    usage_count = models.IntegerField(default=0)
    likes_count = models.IntegerField(default=0)
    dislikes_count = models.IntegerField(default=0)
    
    tags = models.JSONField(default=list, blank=True)
    is_public = models.BooleanField(default=True, help_text="Public prompts are visible to all users")
    is_featured = models.BooleanField(default=False, help_text="Featured prompts appear first")

    class Meta:
        verbose_name = 'Prompt'
        verbose_name_plural = 'Prompts'
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['category', 'industry']),
            models.Index(fields=['is_public', '-likes_count']),
            models.Index(fields=['is_featured', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"
    
    def get_like_ratio(self):
        """Calculate like/dislike ratio"""
        total = self.likes_count + self.dislikes_count
        if total == 0:
            return 0.0
        return self.likes_count / total


class PromptVote(models.Model):
    """User votes on prompts (like/dislike)"""
    VOTE_CHOICES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
    ]
    
    prompt = models.ForeignKey(
        Prompt,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prompt_votes'
    )
    # Для анонімних користувачів зберігаємо IP або session
    user_identifier = models.CharField(
        max_length=255,
        help_text="IP address or session ID for anonymous users"
    )
    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Prompt Vote'
        verbose_name_plural = 'Prompt Votes'
        unique_together = [['prompt', 'user_identifier']]
        indexes = [
            models.Index(fields=['prompt', 'vote']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else self.user_identifier
        return f"{user_str} - {self.vote} on {self.prompt.title}"


class ClientCustomPrompt(models.Model):
    """Custom prompts saved by clients for their AI training"""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='custom_prompts',
        verbose_name='Client'
    )
    
    # Reference to Prompt Book (optional - if added from library)
    source_prompt = models.ForeignKey(
        Prompt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_customizations',
        verbose_name='Source Prompt',
        help_text='Original prompt from Prompt Book (if added from library)'
    )
    
    # Prompt content
    title = models.CharField(
        max_length=200,
        verbose_name='Title',
        help_text='Name of this prompt'
    )
    
    prompt_text = models.TextField(
        verbose_name='Prompt Text',
        help_text='The actual prompt/system message for AI'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Description',
        help_text='Optional description of what this prompt does'
    )
    
    # Metadata
    is_active = models.BooleanField(
        default=False,
        verbose_name='Active',
        help_text='Whether this is the currently active prompt for the client'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    # Order for display
    order = models.IntegerField(
        default=0,
        verbose_name='Order',
        help_text='Display order (lower numbers appear first)'
    )
    
    class Meta:
        verbose_name = 'Client Custom Prompt'
        verbose_name_plural = 'Client Custom Prompts'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['client', 'order']),
        ]
    
    def __str__(self):
        active_status = " (Active)" if self.is_active else ""
        return f"{self.client.company_name} - {self.title}{active_status}"
    
    def save(self, *args, **kwargs):
        # Ensure only one active prompt per client
        if self.is_active:
            ClientCustomPrompt.objects.filter(
                client=self.client,
                is_active=True
            ).exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs)


class News(models.Model):
    """System news and updates for dashboard"""
    NEWS_TYPES = [
        ('integration', 'Integration'),
        ('model', 'Model'),
        ('feature', 'Feature'),
        ('update', 'Update'),
        ('announcement', 'Announcement'),
    ]
    
    title = models.CharField(max_length=255, help_text="Title in English (default language)")
    description = models.TextField(help_text="Description in English (default language)")
    # Translations stored as JSON: {"en": {"title": "...", "description": "..."}, "de": {...}, ...}
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Translations for title and description in all supported languages (en, de, es, fr, it, nl, da)"
    )
    news_type = models.CharField(max_length=20, choices=NEWS_TYPES, default='update')
    image = models.ImageField(
        upload_to='news/images/',
        blank=True,
        null=True,
        help_text="Upload image file for this news item"
    )
    image_url = models.URLField(
        blank=True,
        null=True,
        help_text="Image URL from Unsplash or other source (used if image file is not uploaded)"
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Featured news appear first")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata for automatic news generation
    related_integration = models.CharField(max_length=50, blank=True, help_text="Related integration name")
    related_model = models.CharField(max_length=100, blank=True, help_text="Related model name")
    related_feature = models.CharField(max_length=100, blank=True, help_text="Related feature name")
    
    class Meta:
        verbose_name = 'News'
        verbose_name_plural = 'News'
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['news_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.news_type})"


class ExtensionPage(models.Model):
    """Single web page captured by the browser extension."""

    id = models.AutoField(primary_key=True)

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='extension_pages',
        verbose_name='Client',
    )

    url = models.URLField(
        max_length=1000,
        verbose_name='Page URL',
        help_text='Exact URL of the page where the extension was used',
    )
    site_name = models.CharField(
        max_length=255,
        verbose_name='Site',
        help_text='Domain of the website (example.com)',
    )
    title = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Page title',
    )

    # Structured content captured from DOM
    headings = models.JSONField(default=list, blank=True, help_text="List of headings with levels and text")
    lists = models.JSONField(default=list, blank=True, help_text="Lists (ul/ol) with items")
    tables = models.JSONField(default=list, blank=True, help_text="Tables with header/rows")
    quotes = models.JSONField(default=list, blank=True, help_text="Quotes / highlighted text blocks")

    # Raw visible text (flattened)
    full_text = models.TextField(blank=True, help_text="Raw visible text content of the page")

    # Knowledge block this page belongs to (per site)
    knowledge_block = models.ForeignKey(
        'KnowledgeBlock',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extension_pages',
        help_text='Per-site knowledge block created for extension content',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Extension Page'
        verbose_name_plural = 'Extension Pages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'site_name']),
            models.Index(fields=['client', 'url']),
        ]

    def __str__(self) -> str:
        return f"{self.client.company_name} - {self.site_name} - {self.title or self.url}"


class ExtensionEntity(models.Model):
    """Structured entities (emails/phones/addresses) extracted from extension pages."""

    id = models.AutoField(primary_key=True)

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='extension_entities',
        verbose_name='Client',
    )

    page = models.ForeignKey(
        ExtensionPage,
        on_delete=models.CASCADE,
        related_name='entities',
        null=True,
        blank=True,
        verbose_name='Extension Page',
    )

    site_name = models.CharField(
        max_length=255,
        verbose_name='Site',
        help_text='Domain of the website (example.com)',
    )
    url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name='Page URL',
    )

    emails = models.JSONField(default=list, blank=True, help_text='List of unique emails found on the page/site')
    phones = models.JSONField(default=list, blank=True, help_text='List of unique phone numbers')
    addresses = models.JSONField(default=list, blank=True, help_text='List of detected postal addresses')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Extension Entity'
        verbose_name_plural = 'Extension Entities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'site_name']),
        ]

    def __str__(self) -> str:
        return f"{self.client.company_name} - {self.site_name} entities"

class ClientTelephonyConfig(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    VOICE_MODEL_CHOICES = [
        ('alloy', 'Alloy — Neutral, balanced'),
        ('echo', 'Echo — Male, warm tone'),
        ('fable', 'Fable — Male, expressive'),
        ('onyx', 'Onyx — Male, deep and authoritative'),
        ('nova', 'Nova — Female, friendly'),
        ('shimmer', 'Shimmer — Female, calm and clear'),
    ]

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='telephony_config'
    )
    phone_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    voice_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"model": "alloy", "speed": 1.0, "language": "en-US"}'
    )
    response_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"mode": "prompt_only", "system_prompt": "...", "max_response_tokens": 150, "temperature": 0.3, "rag_enabled": false, "rag_max_chunks": 2}'
    )

    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Client Telephony Config'
        verbose_name_plural = 'Client Telephony Configs'

    def __str__(self):
        return f"{self.client.company_name} — {self.phone_number} ({self.status})"


class WhatsAppBridgeConfig(models.Model):
    """
    Singleton model for global mautrix-whatsapp bridge configuration.
    Managed only by superusers via Django admin.
    """
    is_enabled = models.BooleanField(
        default=False,
        help_text="Global toggle: allow WhatsApp Bridge integration for all clients"
    )
    homeserver_url = models.URLField(
        help_text="Synapse homeserver URL (e.g., http://synapse:8008)"
    )
    homeserver_domain = models.CharField(
        max_length=255,
        help_text="Matrix server domain (e.g., matrix.example.com)"
    )
    provisioning_url = models.URLField(
        help_text="mautrix-whatsapp provisioning API URL (e.g., http://mautrix-whatsapp:29318)"
    )
    provisioning_secret = models.CharField(
        max_length=255,
        help_text="Provisioning shared secret from mautrix-whatsapp config"
    )
    registration_shared_secret = models.CharField(
        max_length=255,
        help_text="Synapse registration_shared_secret for creating Matrix users"
    )
    mautrix_db_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="Password for mautrix PostgreSQL database (also use in docker-compose .env as POSTGRES_MAUTRIX_PASSWORD)"
    )
    bot_username_template = models.CharField(
        max_length=100,
        default='concierge_client_{client_id}',
        help_text="Template for Matrix bot usernames per client"
    )
    appservice_as_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Appservice AS token from mautrix-whatsapp registration.yaml — used to invite users to bridged rooms"
    )

    class Meta:
        verbose_name = 'WhatsApp Bridge Config'
        verbose_name_plural = 'WhatsApp Bridge Config'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion of singleton

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'homeserver_url': 'http://synapse:8008',
            'homeserver_domain': 'crm.local',
            'provisioning_url': 'http://mautrix-whatsapp:29318',
            'provisioning_secret': '',
            'registration_shared_secret': '',
            'mautrix_db_password': '',
        })
        return obj

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"WhatsApp Bridge ({self.homeserver_domain}) — {status}"


class Lead(models.Model):
    """Lead collected from messenger conversations via LLM extraction."""

    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_CONVERTED = 'converted'
    STATUS_LOST = 'lost'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_CONVERTED, 'Converted'),
        (STATUS_LOST, 'Lost'),
    ]

    SOURCE_WEB = 'web'
    SOURCE_TELEGRAM = 'telegram'
    SOURCE_WHATSAPP = 'whatsapp'
    SOURCE_EMAIL = 'email'
    SOURCE_CHOICES = [
        (SOURCE_WEB, 'Web Chat'),
        (SOURCE_TELEGRAM, 'Telegram'),
        (SOURCE_WHATSAPP, 'WhatsApp'),
        (SOURCE_EMAIL, 'Email'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='leads')
    conversation = models.ForeignKey(
        'ClientWhatsAppConversation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    agent_session = models.ForeignKey(
        'agents.AgentSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leads',
        help_text='MCP pipeline session that generated this lead',
    )

    name = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    request_summary = models.TextField(blank=True, default='')

    interest_score = models.IntegerField(
        default=3,
        help_text="Interest level 1-5, determined by LLM based on conversation context"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_WEB,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['client', 'status']),
        ]

    def __str__(self):
        return f"Lead: {self.name or self.email or self.phone or 'Unknown'} ({self.get_status_display()})"

from .models_auto_reply import ChannelAutoReply  # noqa: E402, F401
