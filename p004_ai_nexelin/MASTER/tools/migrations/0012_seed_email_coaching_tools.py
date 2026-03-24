from django.db import migrations


def seed_email_coaching(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    Client = apps.get_model('clients', 'Client')

    # Email ToolCard
    email_card, _ = ToolCard.objects.get_or_create(
        slug='email',
        defaults={
            'name': 'Email',
            'tagline': 'Send, read and analyze emails',
            'description': (
                'Full email management for AI Assistant '
                '(send, read, search, analyze via SMTP/IMAP) '
                'and commercial proposals for Consultant.'
            ),
            'icon': 'mail',
            'color': '#3b82f6',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'auth_type': 'none',
            'skill_scopes': {
                'scopes': ['assistant', 'manager'],
                'bidirectional': False,
            },
        },
    )

    # Coaching ToolCard
    coaching_card, _ = ToolCard.objects.get_or_create(
        slug='coaching',
        defaults={
            'name': 'AI Coaching',
            'tagline': 'Train your consultant AI with knowledge and instructions',
            'description': (
                'Review consultant conversations, identify knowledge gaps, '
                'and update knowledge base or consultant instructions '
                'with user approval.'
            ),
            'icon': 'graduation-cap',
            'color': '#8b5cf6',
            'category': 'ai',
            'transport_type': 'builtin',
            'is_builtin': True,
            'auth_type': 'none',
            'skill_scopes': {
                'scopes': ['assistant'],
                'bidirectional': False,
            },
        },
    )

    # Create ToolConnections for srtyh
    try:
        client = Client.objects.get(tag='srtyh')
    except Client.DoesNotExist:
        return

    from django.utils import timezone
    now = timezone.now()

    # Email: assistant + manager connections
    ToolConnection.objects.get_or_create(
        client=client, tool_card=email_card, target='assistant',
        defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
    )
    ToolConnection.objects.get_or_create(
        client=client, tool_card=email_card, target='manager',
        defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
    )

    # Coaching: assistant only
    ToolConnection.objects.get_or_create(
        client=client, tool_card=coaching_card, target='assistant',
        defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
    )


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug__in=['email', 'coaching']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0011_seed_sales_intel_tool'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_email_coaching, unseed),
    ]
