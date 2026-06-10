from django.db import migrations


TOOL = {
    'name': 'Content Planner',
    'slug': 'content-planner',
    'tagline': 'Editorial calendar for social content',
    'tagline_i18n': {
        'en': 'Editorial calendar for social content',
        'uk': 'Контент-план для соцмереж',
        'de': 'Redaktionskalender für Social-Media-Content',
    },
    'description': (
        'Plan and approve social-media posts. CRUD over ContentPlan / ContentPost / '
        'ContentIdea. Posts are delivered through the Matrix MCP (matrix_send_message) '
        'into bridged rooms (Telegram channel, FB Page, IG DM) — no direct Meta Graph '
        'API. LLM-driven strategy generation lands in a follow-up.'
    ),
    'icon': 'calendar',
    'color': '#f97316',
    'category': 'productivity',
    'transport_type': 'builtin',
    'builtin_handler': 'mcp_servers.content_planner.server',
    'is_builtin': True,
    'is_system': True,  # auto-connect for every client
    'is_active': True,
    'auth_type': 'none',
    'sort_order': 120,
    'skill_scopes': {'scopes': ['assistant', 'manager']},
}


def seed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.update_or_create(slug=TOOL['slug'], defaults=TOOL)


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug=TOOL['slug'], is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0020_seed_google_workspace_tool'),
        ('content_planner', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
