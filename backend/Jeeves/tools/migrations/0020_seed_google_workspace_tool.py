from django.db import migrations


TOOL = {
    'name': 'Google Workspace',
    'slug': 'google-workspace',
    'tagline': 'Google Calendar, Sheets and Business Reviews',
    'tagline_i18n': {
        'en': 'Google Calendar, Sheets and Business Reviews',
        'uk': 'Google Calendar, Sheets та Business Reviews',
        'de': 'Google Kalender, Sheets und Business-Bewertungen',
    },
    'description': (
        'OAuth-connected Google Workspace tools: schedule events, suggest free time, '
        'read/write Sheets, list and reply to Google Business reviews. Per-client '
        'OAuth tokens stored encrypted in ToolConnection.credentials.'
    ),
    'icon': 'briefcase',
    'color': '#4285F4',
    'category': 'productivity',
    'transport_type': 'builtin',
    'builtin_handler': 'mcp_servers.google_workspace.server',
    'is_builtin': True,
    'is_system': False,
    'is_active': True,
    'auth_type': 'oauth2',
    'auth_config': {
        'provider': 'google',
        'scopes': [
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/business.manage',
            'https://www.googleapis.com/auth/userinfo.email',
        ],
        'instructions_i18n': {
            'en': 'Sign in with Google and grant Calendar / Sheets / Business Profile permissions.',
            'uk': 'Увійди через Google і дозволь доступ до Calendar / Sheets / Business Profile.',
        },
    },
    'sort_order': 110,
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
        ('tools', '0019_seed_matrix_hardware_tools'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
