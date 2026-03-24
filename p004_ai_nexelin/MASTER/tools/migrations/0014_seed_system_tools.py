"""Seed Agent Memory and Deep Thinking system tools + auto-connect for all clients."""
from django.db import migrations
from django.utils import timezone


SYSTEM_TOOLS = [
    {
        'slug': 'memory',
        'name': 'Agent Memory',
        'tagline': 'Persistent memory across conversations',
        'tagline_i18n': {'en': 'Persistent memory across conversations', 'de': 'Persistenter Speicher über Gespräche hinweg'},
        'description': 'Persistent conversational memory for AI agents across sessions.',
        'icon': 'brain',
        'category': 'ai',
        'color': '#8b5cf6',
        'transport_type': 'builtin',
        'is_builtin': True,
        'is_system': True,
        'builtin_handler': 'mcp_hub.builtin.memory',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
    {
        'slug': 'sequential-thinking',
        'name': 'Deep Thinking',
        'tagline': 'Structured reasoning for complex problems',
        'tagline_i18n': {'en': 'Structured reasoning for complex problems', 'de': 'Strukturiertes Denken für komplexe Probleme'},
        'description': 'Structured step-by-step reasoning for complex multi-step problems.',
        'icon': 'brain-circuit',
        'category': 'ai',
        'color': '#6366f1',
        'transport_type': 'builtin',
        'is_builtin': True,
        'is_system': True,
        'builtin_handler': 'mcp_hub.builtin.sequential_thinking',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
]


def seed_system_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    Client = apps.get_model('clients', 'Client')

    now = timezone.now()

    for tool_data in SYSTEM_TOOLS:
        card, _ = ToolCard.objects.update_or_create(
            slug=tool_data['slug'],
            defaults=tool_data,
        )

        # Auto-connect for ALL existing active clients
        for client in Client.objects.filter(is_active=True):
            for scope in tool_data['skill_scopes']['scopes']:
                ToolConnection.objects.get_or_create(
                    client=client,
                    tool_card=card,
                    target=scope,
                    defaults={
                        'status': 'connected',
                        'enabled': True,
                        'connected_at': now,
                    },
                )


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug__in=['memory', 'sequential-thinking']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0013_toolcard_is_system'),
        ('clients', '0051_lead_agent_session'),
    ]

    operations = [
        migrations.RunPython(seed_system_tools, reverse),
    ]
