from django.db import models
from django.utils import timezone

from MASTER.concierge_platform.fields import EncryptedTextField


class BridgeConfig(models.Model):
    """Global config for each bridge type (one row per bridge)."""

    BRIDGE_TYPE_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('meta-facebook', 'Facebook Messenger'),
        ('meta-instagram', 'Instagram DM'),
        ('linkedin', 'LinkedIn Messages'),
    ]

    AUTH_FLOW_CHOICES = [
        ('qr_code', 'QR Code'),
        ('cookies', 'Browser Cookies'),
    ]

    bridge_type = models.CharField(
        max_length=30, unique=True, choices=BRIDGE_TYPE_CHOICES
    )
    is_enabled = models.BooleanField(default=False)
    provisioning_url = models.URLField(
        help_text='mautrix provisioning API base URL'
    )
    provisioning_secret = models.CharField(max_length=255)
    bot_username = models.CharField(
        max_length=255,
        help_text='Matrix bot user e.g. @facebookbot:matrix.example.com',
    )
    auth_flow = models.CharField(
        max_length=20, choices=AUTH_FLOW_CHOICES
    )
    default_scopes = models.JSONField(
        default=list, help_text='Default targets'
    )
    display_name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50)
    popup_url = models.URLField(
        blank=True, help_text='Login URL for cookie auth'
    )
    cookie_domains = models.JSONField(default=list)
    required_cookies = models.JSONField(default=list)

    class Meta:
        app_label = 'clients'
        verbose_name = 'Bridge Config'

    def __str__(self):
        return f'{self.display_name} ({self.bridge_type})'


class ClientBridgeConnection(models.Model):
    """Per-client connection state for a bridge."""

    STATUS_CHOICES = [
        ('disconnected', 'Disconnected'),
        ('pending', 'Pending'),
        ('connected', 'Connected'),
        ('expired', 'Expired'),
        ('error', 'Error'),
    ]

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='bridge_connections',
    )
    bridge_config = models.ForeignKey(
        BridgeConfig,
        on_delete=models.CASCADE,
        related_name='connections',
    )
    matrix_user_id = models.CharField(max_length=255, blank=True)
    matrix_access_token = EncryptedTextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='disconnected'
    )
    remote_id = models.CharField(max_length=255, blank=True, null=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    login_process_id = models.CharField(max_length=255, blank=True)
    login_step_id = models.CharField(max_length=255, blank=True)
    login_flow_id = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'clients'
        unique_together = [('client', 'bridge_config')]

    def __str__(self):
        return f'{self.client} — {self.bridge_config} [{self.status}]'

    def mark_connected(self, remote_id=None):
        self.status = 'connected'
        self.connected_at = timezone.now()
        self.error = ''
        self.login_process_id = ''
        self.login_step_id = ''
        self.login_flow_id = ''
        if remote_id is not None:
            self.remote_id = remote_id
        self.save()

    def mark_error(self, error_msg):
        self.status = 'error'
        self.error = error_msg
        self.save()

    def mark_expired(self):
        self.status = 'expired'
        self.save()

    def mark_disconnected(self):
        self.status = 'disconnected'
        self.connected_at = None
        self.error = ''
        self.remote_id = None
        self.matrix_user_id = ''
        self.matrix_access_token = ''
        self.login_process_id = ''
        self.login_step_id = ''
        self.login_flow_id = ''
        self.save()
