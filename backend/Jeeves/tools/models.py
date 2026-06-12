from django.db import models
from Jeeves.concierge_platform.fields import EncryptedJSONField


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
        ('stdio', 'Stdio (local subprocess)'),
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


class InstalledMCPServer(models.Model):
    """Tracks an npm/pypi MCP server package installed by the owner."""

    PACKAGE_TYPE_CHOICES = [
        ('npm', 'npm'),
        ('pypi', 'PyPI'),
    ]

    STATUS_CHOICES = [
        ('installed', 'Installed'),
        ('failed', 'Failed'),
        ('removed', 'Removed'),
    ]

    tool_card = models.OneToOneField(
        ToolCard, on_delete=models.CASCADE, related_name='installed_server',
    )
    package_name = models.CharField(max_length=255, unique=True)
    package_type = models.CharField(max_length=10, choices=PACKAGE_TYPE_CHOICES)
    version = models.CharField(max_length=50, blank=True)
    run_command = models.CharField(max_length=500)
    run_args = models.JSONField(default=list, blank=True)
    env_config = models.JSONField(default=dict, blank=True)
    source_url = models.URLField(blank=True)
    installed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='installed',
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-installed_at']

    def __str__(self):
        return f"{self.package_name} ({self.package_type})"


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='clients.Client')
def auto_connect_system_tools(sender, instance, created, **kwargs):
    """Auto-connect system tools when a new client is created."""
    if not created:
        return
    from django.utils import timezone
    now = timezone.now()
    for card in ToolCard.objects.filter(is_system=True, is_active=True):
        scopes = card.skill_scopes.get('scopes', ['assistant', 'manager'])
        for scope in scopes:
            ToolConnection.objects.get_or_create(
                client=instance,
                tool_card=card,
                target=scope,
                defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
            )


class Skill(models.Model):
    """Reusable markdown skill — a prompt module appended to an agent's
    system prompt when assigned (e.g. 'Marketing Pro' for the consultant
    in Telegram, or a lead-qualification skill).

    Created by admins (Django admin) and attached per client/target either
    in the portal or by Jeeves via the canvas MCP server.
    """

    TARGET_CHOICES = [
        ('assistant', 'AI Assistant (Jeeves)'),
        ('manager', 'Consultant (customer-facing)'),
        ('leads', 'Lead handling'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.CharField(
        max_length=300, blank=True,
        help_text='One line shown in catalogs and to Jeeves')
    content = models.TextField(
        help_text='Markdown instructions appended to the agent system prompt')
    allowed_targets = models.JSONField(
        default=list, blank=True,
        help_text='Subset of ["assistant","manager","leads"]; empty = any target')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SkillAssignment(models.Model):
    """A skill attached to one of a client's agents."""

    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE, related_name='skill_assignments')
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name='assignments')
    target = models.CharField(max_length=20, choices=Skill.TARGET_CHOICES)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['client', 'skill', 'target']
        indexes = [models.Index(fields=['client', 'target', 'enabled'])]

    def __str__(self):
        return f'{self.client} — {self.skill.name} ({self.target})'
