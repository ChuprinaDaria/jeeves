from django.db import migrations


def forward(apps, schema_editor):
    """Migrate existing Client integration fields to ToolConnection records."""
    Client = apps.get_model('clients', 'Client')
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')

    tool_cards = {tc.slug: tc for tc in ToolCard.objects.all()}

    for client in Client.objects.iterator(chunk_size=100):

        # WhatsApp Meta
        if client.whatsapp_meta_enabled and client.meta_access_token:
            tc = tool_cards.get('whatsapp-meta')
            if tc:
                ToolConnection.objects.get_or_create(
                    client=client, tool_card=tc,
                    defaults={
                        'status': 'connected', 'enabled': True,
                        'credentials': {
                            'waba_id': client.meta_waba_id,
                            'app_id': client.meta_app_id,
                            'app_secret': client.meta_app_secret,
                            'access_token': client.meta_access_token,
                            'phone_number_id': client.meta_phone_number_id,
                            'verify_token': client.meta_verify_token,
                            'phone_number': client.meta_phone_number,
                        },
                        'connected_at': client.updated_at,
                    })

        # Telegram
        if client.telegram_enabled and client.telegram_bot_token:
            tc = tool_cards.get('telegram')
            if tc:
                ToolConnection.objects.get_or_create(
                    client=client, tool_card=tc,
                    defaults={
                        'status': 'connected', 'enabled': True,
                        'credentials': {'bot_token': client.telegram_bot_token},
                        'config': {'welcome_message': client.telegram_welcome_message or ''},
                        'connected_at': client.updated_at,
                    })

        # Email SMTP
        if client.email_smtp_enabled and client.email_smtp_host:
            tc = tool_cards.get('email-smtp')
            if tc:
                ToolConnection.objects.get_or_create(
                    client=client, tool_card=tc,
                    defaults={
                        'status': 'connected', 'enabled': True,
                        'credentials': {
                            'smtp_host': client.email_smtp_host,
                            'smtp_port': client.email_smtp_port,
                            'username': client.email_smtp_username,
                            'password': client.email_smtp_password,
                            'from_address': client.email_from_address,
                            'from_name': client.email_from_name,
                            'use_tls': client.email_smtp_use_tls,
                        },
                        'connected_at': client.updated_at,
                    })

        # WhatsApp Bridge
        if client.whatsapp_bridge_enabled:
            tc = tool_cards.get('whatsapp-bridge')
            if tc:
                status = 'connected' if client.whatsapp_bridge_status == 'connected' else 'pending'
                ToolConnection.objects.get_or_create(
                    client=client, tool_card=tc,
                    defaults={
                        'status': status, 'enabled': True,
                        'credentials': {
                            'phone': client.whatsapp_bridge_phone,
                            'matrix_user_id': client.whatsapp_bridge_matrix_user_id,
                            'matrix_access_token': client.whatsapp_bridge_matrix_access_token,
                        },
                        'connected_at': client.whatsapp_bridge_connected_at,
                        'last_error': client.whatsapp_bridge_error or '',
                    })

        # Web Widget
        if client.widget_enabled:
            tc = tool_cards.get('web-widget')
            if tc:
                ToolConnection.objects.get_or_create(
                    client=client, tool_card=tc,
                    defaults={'status': 'connected', 'enabled': True})

        # HITL Matrix
        if client.matrix_hitl_enabled:
            tc = tool_cards.get('hitl-matrix')
            if tc:
                ToolConnection.objects.get_or_create(
                    client=client, tool_card=tc,
                    defaults={
                        'status': 'connected', 'enabled': True,
                        'credentials': {
                            'manager_user_ids': client.matrix_manager_user_ids,
                            'homeserver_url': client.matrix_homeserver_url,
                        },
                    })


def reverse(apps, schema_editor):
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    ToolConnection.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0002_seed_tool_cards'),
        ('clients', '0049_lead_and_leads_enabled'),
    ]
    operations = [migrations.RunPython(forward, reverse)]
