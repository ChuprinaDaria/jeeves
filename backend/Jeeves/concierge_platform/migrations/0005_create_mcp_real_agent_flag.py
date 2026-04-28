from django.db import migrations


def create_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('concierge_platform', 'FeatureFlag')
    Client = apps.get_model('clients', 'Client')

    flag, created = FeatureFlag.objects.get_or_create(
        key='mcp_real_agent',
        defaults={'rollout': 'selected'},
    )
    if created:
        try:
            client = Client.objects.get(tag='srtyh')
            flag.enabled_clients.add(client)
        except Client.DoesNotExist:
            pass  # Client may not exist in this environment — safe to skip


def remove_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('concierge_platform', 'FeatureFlag')
    FeatureFlag.objects.filter(key='mcp_real_agent').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0004_seed_feature_flags'),
        ('clients', '0049_lead_and_leads_enabled'),
    ]

    operations = [
        migrations.RunPython(create_flag, remove_flag),
    ]
