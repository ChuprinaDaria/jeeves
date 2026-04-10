from MASTER.concierge_platform.models import FeatureFlag


FIELD_MAP = {
    ('whatsapp-meta', 'waba_id'): 'meta_waba_id',
    ('whatsapp-meta', 'app_id'): 'meta_app_id',
    ('whatsapp-meta', 'app_secret'): 'meta_app_secret',
    ('whatsapp-meta', 'access_token'): 'meta_access_token',
    ('whatsapp-meta', 'phone_number_id'): 'meta_phone_number_id',
    ('whatsapp-meta', 'verify_token'): 'meta_verify_token',
    ('whatsapp-meta', 'phone_number'): 'meta_phone_number',
    ('telegram', 'bot_token'): 'telegram_bot_token',
    ('email-smtp', 'smtp_host'): 'email_smtp_host',
    ('email-smtp', 'smtp_port'): 'email_smtp_port',
    ('email-smtp', 'username'): 'email_smtp_username',
    ('email-smtp', 'password'): 'email_smtp_password',
    ('email-smtp', 'from_address'): 'email_from_address',
    ('email-smtp', 'from_name'): 'email_from_name',
    ('email-smtp', 'use_tls'): 'email_smtp_use_tls',
    ('whatsapp-bridge', 'phone'): 'whatsapp_bridge_phone',
    ('whatsapp-bridge', 'matrix_user_id'): 'whatsapp_bridge_matrix_user_id',
    ('whatsapp-bridge', 'matrix_access_token'): 'whatsapp_bridge_matrix_access_token',
}

ENABLED_MAP = {
    'whatsapp-meta': 'whatsapp_meta_enabled',
    'telegram': 'telegram_enabled',
    'email-smtp': 'email_smtp_enabled',
    'whatsapp-bridge': 'whatsapp_bridge_enabled',
    'web-widget': 'widget_enabled',
}


def get_credentials(client, tool_slug: str, field: str, default=''):
    """Read credential: ToolConnection first, fallback to old Client fields."""
    if FeatureFlag.is_enabled('mcp_agent_config', client):
        from MASTER.tools.models import ToolConnection
        connection = ToolConnection.objects.filter(
            client=client, tool_card__slug=tool_slug, status='connected'
        ).first()
        if connection:
            return connection.credentials.get(field, default)
    old_field = FIELD_MAP.get((tool_slug, field))
    if old_field:
        return getattr(client, old_field, default)
    return default


def is_tool_connected(client, tool_slug: str) -> bool:
    """Check if tool is connected for client."""
    if FeatureFlag.is_enabled('mcp_agent_config', client):
        from MASTER.tools.models import ToolConnection
        return ToolConnection.objects.filter(
            client=client, tool_card__slug=tool_slug,
            status='connected', enabled=True,
        ).exists()
    old_field = ENABLED_MAP.get(tool_slug)
    if old_field:
        return bool(getattr(client, old_field, False))
    return False
