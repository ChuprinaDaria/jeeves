from django.db import migrations


def seed_bridge_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')

    bridges = [
        {
            'slug': 'meta-facebook',
            'name': 'Facebook Messenger',
            'tagline': 'Bridge Facebook Messenger conversations',
            'description': 'Connect Facebook Messenger via mautrix bridge.',
            'icon': 'facebook',
            'color': '#1877F2',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.bridge_tools',
            'auth_type': 'cookies',
            'auth_config': {
                'popup_url': 'https://www.messenger.com/',
                'cookie_domains': ['.facebook.com', '.messenger.com'],
                'required_cookies': ['c_user', 'xs', 'datr', 'sb'],
            },
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
            'is_active': True,
        },
        {
            'slug': 'meta-instagram',
            'name': 'Instagram DM',
            'tagline': 'Bridge Instagram Direct Messages',
            'description': 'Connect Instagram DM via mautrix bridge.',
            'icon': 'instagram',
            'color': '#E4405F',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.bridge_tools',
            'auth_type': 'cookies',
            'auth_config': {
                'popup_url': 'https://www.instagram.com/',
                'cookie_domains': ['.instagram.com'],
                'required_cookies': ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
            },
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
            'is_active': True,
        },
        {
            'slug': 'linkedin',
            'name': 'LinkedIn Messages',
            'tagline': 'Bridge LinkedIn Messages for lead generation',
            'description': 'Connect LinkedIn Messages via mautrix bridge.',
            'icon': 'linkedin',
            'color': '#0A66C2',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.bridge_tools',
            'auth_type': 'cookies',
            'auth_config': {
                'popup_url': 'https://www.linkedin.com/',
                'cookie_domains': ['.linkedin.com'],
                'required_cookies': ['li_at', 'JSESSIONID', 'lidc'],
            },
            'skill_scopes': {'scopes': ['leads'], 'bidirectional': True},
            'is_active': True,
        },
    ]

    for data in bridges:
        ToolCard.objects.get_or_create(slug=data['slug'], defaults=data)


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug__in=['meta-facebook', 'meta-instagram', 'linkedin']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0015_system_xlsx_coaching'),
    ]

    operations = [
        migrations.RunPython(seed_bridge_tools, reverse),
    ]
