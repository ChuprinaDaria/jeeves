"""Remove /api prefix from whatsapp-bridge auth_config URLs.

The frontend axios instance already has /api in its baseURL,
so seed_data URLs must NOT include the /api prefix.
"""
from django.db import migrations


def forward(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    try:
        tool = ToolCard.objects.get(slug='whatsapp-bridge')
    except ToolCard.DoesNotExist:
        return

    auth_config = tool.auth_config or {}
    changed = False

    for key in ('initiate_url', 'status_url'):
        url = auth_config.get(key, '')
        if url.startswith('/api/'):
            auth_config[key] = url[4:]  # strip leading /api
            changed = True

    if changed:
        tool.auth_config = auth_config
        tool.save(update_fields=['auth_config'])


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    try:
        tool = ToolCard.objects.get(slug='whatsapp-bridge')
    except ToolCard.DoesNotExist:
        return

    auth_config = tool.auth_config or {}
    for key in ('initiate_url', 'status_url'):
        url = auth_config.get(key, '')
        if url and not url.startswith('/api/'):
            auth_config[key] = '/api' + url

    tool.auth_config = auth_config
    tool.save(update_fields=['auth_config'])


class Migration(migrations.Migration):
    dependencies = [('tools', '0008_multi_connection_scopes')]
    operations = [migrations.RunPython(forward, reverse)]
