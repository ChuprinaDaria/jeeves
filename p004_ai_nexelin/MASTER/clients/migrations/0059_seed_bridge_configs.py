from django.db import migrations


def seed_bridge_configs(apps, schema_editor):
    BridgeConfig = apps.get_model('clients', 'BridgeConfig')

    configs = [
        {
            'bridge_type': 'meta-facebook',
            'is_enabled': False,
            'provisioning_url': 'http://localhost:29319',
            'provisioning_secret': '',
            'bot_username': '@facebookbot:grot.de',
            'auth_flow': 'cookies',
            'default_scopes': ['assistant', 'manager'],
            'display_name': 'Facebook Messenger',
            'icon': 'facebook',
            'popup_url': 'https://www.messenger.com/',
            'cookie_domains': ['.facebook.com', '.messenger.com'],
            'required_cookies': ['c_user', 'xs', 'datr', 'sb'],
        },
        {
            'bridge_type': 'meta-instagram',
            'is_enabled': False,
            'provisioning_url': 'http://localhost:29320',
            'provisioning_secret': '',
            'bot_username': '@instagrambot:grot.de',
            'auth_flow': 'cookies',
            'default_scopes': ['assistant', 'manager'],
            'display_name': 'Instagram DM',
            'icon': 'instagram',
            'popup_url': 'https://www.instagram.com/',
            'cookie_domains': ['.instagram.com'],
            'required_cookies': ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
        },
        {
            'bridge_type': 'linkedin',
            'is_enabled': False,
            'provisioning_url': 'http://localhost:29321',
            'provisioning_secret': '',
            'bot_username': '@linkedinbot:grot.de',
            'auth_flow': 'cookies',
            'default_scopes': ['leads'],
            'display_name': 'LinkedIn Messages',
            'icon': 'linkedin',
            'popup_url': 'https://www.linkedin.com/',
            'cookie_domains': ['.linkedin.com'],
            'required_cookies': ['li_at', 'JSESSIONID', 'lidc'],
        },
    ]

    for data in configs:
        BridgeConfig.objects.get_or_create(bridge_type=data['bridge_type'], defaults=data)


def reverse(apps, schema_editor):
    BridgeConfig = apps.get_model('clients', 'BridgeConfig')
    BridgeConfig.objects.filter(
        bridge_type__in=['meta-facebook', 'meta-instagram', 'linkedin']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('clients', '0058_bridge_config_models'),
    ]

    operations = [
        migrations.RunPython(seed_bridge_configs, reverse),
    ]
