from django.db import migrations


def seed_leads_tool(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.get_or_create(
        slug='leads',
        defaults={
            'name': 'Lead Management',
            'tagline': 'Збір та управління лідами з усіх каналів',
            'tagline_i18n': {
                'en': 'Lead collection and management across all channels',
                'de': 'Lead-Erfassung und -Verwaltung über alle Kanäle',
            },
            'description': 'Collect, qualify and search leads from all messenger channels.',
            'icon': 'user-plus',
            'category': 'crm',
            'color': '#10b981',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.leads',
            'auth_type': 'none',
            'skill_scopes': {
                'scopes': ['assistant', 'manager'],
                'bidirectional': False,
            },
        },
    )


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug='leads').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0009_fix_whatsapp_bridge_urls'),
    ]

    operations = [
        migrations.RunPython(seed_leads_tool, unseed),
    ]
