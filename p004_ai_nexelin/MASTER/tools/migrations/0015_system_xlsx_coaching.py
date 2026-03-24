"""Mark xlsx-processor, coaching, email as system tools + auto-connect all clients."""
from django.db import migrations
from django.utils import timezone


def forward(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    Client = apps.get_model('clients', 'Client')

    now = timezone.now()

    # slug -> (mark_system, scopes_to_connect)
    cards_to_update = {
        'xlsx-processor': (True, ['assistant', 'manager']),
        'coaching': (True, ['assistant']),
        'email': (True, ['assistant', 'manager']),
    }

    for slug, (mark_system, scopes) in cards_to_update.items():
        try:
            card = ToolCard.objects.get(slug=slug)
        except ToolCard.DoesNotExist:
            continue

        if mark_system:
            card.is_system = True
            card.save(update_fields=['is_system'])

        for client in Client.objects.filter(is_active=True):
            for scope in scopes:
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
    ToolConnection = apps.get_model('tools', 'ToolConnection')

    for slug in ('xlsx-processor', 'coaching', 'email'):
        try:
            card = ToolCard.objects.get(slug=slug)
            card.is_system = False
            card.save(update_fields=['is_system'])
            ToolConnection.objects.filter(
                tool_card=card, credentials={},
            ).delete()
        except ToolCard.DoesNotExist:
            pass


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0014_seed_system_tools'),
        ('clients', '0051_lead_agent_session'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
