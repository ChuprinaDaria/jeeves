from django.db import models
from MASTER.nexelin_platform.fields import EncryptedJSONField


class ToolCard(models.Model):
    """Tool catalog entry. Admin creates. Client sees as card on dashboard."""

    CATEGORY_CHOICES = [
        ('communication', 'Communication'),
        ('productivity', 'Productivity'),
        ('analytics', 'Analytics'),
        ('ai', 'AI & Knowledge'),
        ('crm', 'CRM & Sales'),
        ('custom', 'Custom'),
    ]

    TRANSPORT_CHOICES = [
        ('builtin', 'Built-in Django handler'),
        ('sse', 'SSE (Server-Sent Events)'),
        ('streamable_http', 'Streamable HTTP'),
    ]

    AUTH_TYPE_CHOICES = [
        ('none', 'No auth required'),
        ('oauth2', 'OAuth 2.0'),
        ('api_key', 'API Key'),
        ('credentials', 'Custom credentials form'),
        ('qr_code', 'QR Code scan'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=200)
    tagline_i18n = models.JSONField(
        default=dict, blank=True,
        help_text='{"en": "...", "uk": "...", "de": "..."} — overrides tagline per locale')
    description = models.TextField()
    icon = models.CharField(max_length=50)
    color = models.CharField(max_length=7)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    mcp_server_url = models.CharField(max_length=500, blank=True)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_CHOICES)
    is_builtin = models.BooleanField(default=False)
    builtin_handler = models.CharField(max_length=200, blank=True)
    tools_schema = models.JSONField(default=list, blank=True)

    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES)
    auth_config = models.JSONField(default=dict, blank=True)
    skill_scopes = models.JSONField(
        default=dict, blank=True,
        help_text='{"scopes": ["assistant","manager","escalation"], "bidirectional": true}')
    scope_schema = models.JSONField(
        default=dict, blank=True,
        help_text='Available scope options for UI rendering')

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False, help_text='System tool — always connected, cannot be disconnected')
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ToolConnection(models.Model):
    """Client connected a tool. Credentials encrypted at rest."""

    STATUS_CHOICES = [
        ('pending', 'Pending setup'),
        ('connected', 'Connected'),
        ('error', 'Error'),
        ('disconnected', 'Disconnected'),
        ('expired', 'Token expired'),
    ]

    TARGET_CHOICES = [
        ('assistant', 'AI Assistant'),
        ('manager', 'Client Manager'),
        ('leads', 'Leads'),
    ]

    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE,
        related_name='tool_connections')
    tool_card = models.ForeignKey(ToolCard, on_delete=models.CASCADE,
        related_name='connections')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='assistant')
    credentials = EncryptedJSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    scope = models.JSONField(
        default=dict, blank=True,
        help_text='Per-target permissions/scope for this connection')
    enabled = models.BooleanField(default=True)

    # Canvas position (optional — frontend can compute defaults)
    position_x = models.FloatField(null=True, blank=True)
    position_y = models.FloatField(null=True, blank=True)

    connected_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    error_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['client', 'tool_card', 'target']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['tool_card', 'status']),
        ]

    def __str__(self):
        return f'{self.client} — {self.tool_card.name} ({self.status})'


class EdgeMiddleware(models.Model):
    """Skill attached to a connection edge as middleware/filter."""

    connection = models.ForeignKey(
        ToolConnection, on_delete=models.CASCADE,
        related_name='middlewares',
        help_text='The edge this skill is attached to')
    skill_card = models.ForeignKey(
        ToolCard, on_delete=models.CASCADE,
        related_name='middleware_usages',
        help_text='The skill acting as middleware')
    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE,
        related_name='edge_middlewares')
    order = models.IntegerField(default=0, help_text='Execution order on this edge')
    enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True,
        help_text='Per-edge config overrides for this skill')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        unique_together = ['connection', 'skill_card']
        indexes = [
            models.Index(fields=['client', 'connection']),
        ]

    def __str__(self):
        return f'{self.skill_card.name} on {self.connection}'
