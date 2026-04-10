from django.db import migrations


def forward(apps, schema_editor):
    """Create AgentConfig for each existing Client from their current fields."""
    Client = apps.get_model('clients', 'Client')
    AgentConfig = apps.get_model('agents', 'AgentConfig')

    for client in Client.objects.iterator(chunk_size=100):
        AgentConfig.objects.get_or_create(
            client=client,
            defaults={
                'llm_provider_id': client.llm_provider_model_id,
                'embedding_model_id': client.embedding_model_id,
                'system_prompt': client.custom_system_prompt or '',
                'greeting_message': client.greeting_message or '',
                'escalation_enabled': client.hitl_enabled,
                'language': client.notification_language or '',
            })


def reverse(apps, schema_editor):
    AgentConfig = apps.get_model('agents', 'AgentConfig')
    AgentConfig.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0001_initial'),
        ('clients', '0049_lead_and_leads_enabled'),
    ]
    operations = [migrations.RunPython(forward, reverse)]
