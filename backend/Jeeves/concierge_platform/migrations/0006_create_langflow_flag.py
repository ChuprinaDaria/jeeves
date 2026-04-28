from django.db import migrations


def create_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('concierge_platform', 'FeatureFlag')
    Client = apps.get_model('clients', 'Client')

    flag, created = FeatureFlag.objects.get_or_create(
        key='langflow_enabled',
        defaults={
            'rollout': 'selected',
            'description': 'Langflow visual AI workflow builder',
        },
    )
    if created:
        try:
            client = Client.objects.get(tag='srtyh')
            flag.enabled_clients.add(client)
        except Client.DoesNotExist:
            pass  # Client may not exist in this environment — safe to skip


def remove_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('concierge_platform', 'FeatureFlag')
    FeatureFlag.objects.filter(key='langflow_enabled').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0005_create_mcp_real_agent_flag'),
        ('clients', '0060_encrypt_matrix_access_token'),
    ]

    operations = [
        migrations.RunPython(create_flag, remove_flag),
    ]
