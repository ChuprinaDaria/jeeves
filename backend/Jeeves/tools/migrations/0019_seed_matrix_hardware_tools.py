from django.db import migrations


NEW_TOOLS = [
    {
        'name': 'Matrix Messaging',
        'slug': 'matrix',
        'tagline': 'Cross-platform DM via Matrix bridges',
        'tagline_i18n': {
            'en': 'Cross-platform DM via Matrix bridges',
            'uk': 'Універсальний мессенджинг через Matrix',
            'de': 'Plattformübergreifende DMs über Matrix-Bridges',
        },
        'description': (
            'Talk to clients across Instagram DM, FB Messenger, WhatsApp, Telegram '
            'and Google Chat through a single Matrix Client-Server API. Self-hosted '
            'Synapse + mautrix bridges.'
        ),
        'icon': 'message-circle',
        'color': '#0DBD8B',
        'category': 'communication',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.matrix.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'credentials',
        'auth_config': {
            'fields': [
                {'key': 'homeserver_url', 'label': 'Homeserver URL',
                 'placeholder': 'https://matrix.example.com', 'required': True},
                {'key': 'user_id', 'label': 'Matrix user id',
                 'placeholder': '@client-name:matrix.example.com', 'required': True},
                {'key': 'access_token', 'label': 'Access token',
                 'placeholder': 'syt_...', 'required': True, 'secret': True},
            ],
            'instructions_i18n': {
                'en': 'Log into your Matrix account in Element, open Settings → Help & About → Advanced → Access Token and copy it here. To pair WhatsApp/Telegram/Instagram, open a DM with the bridge bot and follow `!login`.',
                'uk': 'Зайди в Element/Matrix-клієнт, Settings → Help & About → Advanced → Access Token. Для WhatsApp/Telegram/Instagram — DM-ни bridge-бот і виконай `!login`.',
            },
        },
        'sort_order': 90,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
    {
        'name': 'Hardware Remote',
        'slug': 'hardware',
        'tagline': 'Wake-on-LAN, SSH, file ops on a workstation',
        'tagline_i18n': {
            'en': 'Wake-on-LAN, SSH, file ops on a workstation',
            'uk': 'Wake-on-LAN, SSH, керування файлами на ПК',
            'de': 'Wake-on-LAN, SSH, Dateiverwaltung auf einem Arbeitsplatz',
        },
        'description': (
            'Remote-control a workstation: wake via WoL, SSH commands, file read/write, '
            'screenshots, tmux workspaces. Ported from sloth/pi-remote.'
        ),
        'icon': 'cpu',
        'color': '#a855f7',
        'category': 'productivity',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.hardware.server',
        'is_builtin': True,
        'is_system': False,
        # Disabled by default — admin must drop config.yaml on the host first.
        'is_active': False,
        'auth_type': 'none',
        'auth_config': {
            'instructions_i18n': {
                'en': 'Drop `config.yaml` next to `mcp_servers/hardware/` (see `config.yaml.example`) with SSH host/MAC/timeouts, then flip `is_active` to True.',
                'uk': 'Поклади `config.yaml` поряд із `mcp_servers/hardware/` (дивись `config.yaml.example`) із SSH-хостом/MAC/timeouts, потім увімкни `is_active`.',
            },
        },
        'sort_order': 100,
        'skill_scopes': {'scopes': ['assistant']},
    },
]


def seed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    for tool in NEW_TOOLS:
        ToolCard.objects.update_or_create(slug=tool['slug'], defaults=tool)


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug__in=[t['slug'] for t in NEW_TOOLS], is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0018_add_installed_mcp_server'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
