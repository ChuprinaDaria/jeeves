# Generated manually — WhatsApp Bridge (mautrix-whatsapp) integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0045_telephony_enabled_and_config'),
    ]

    operations = [
        # New fields on Client model
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_enabled',
            field=models.BooleanField(default=False, help_text='Enable WhatsApp via mautrix-whatsapp bridge for this client'),
        ),
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_phone',
            field=models.CharField(blank=True, max_length=20, help_text='Connected WhatsApp phone number (filled after successful login)'),
        ),
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_matrix_user_id',
            field=models.CharField(blank=True, max_length=255, help_text='Matrix user ID for this client\'s bridge bot'),
        ),
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_matrix_access_token',
            field=models.TextField(blank=True, help_text='Matrix access token for the bridge bot user'),
        ),
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_status',
            field=models.CharField(
                choices=[
                    ('disconnected', 'Disconnected'),
                    ('qr_pending', 'QR Pending'),
                    ('connected', 'Connected'),
                    ('error', 'Error'),
                ],
                default='disconnected',
                max_length=20,
                help_text='Current WhatsApp bridge connection status',
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_connected_at',
            field=models.DateTimeField(blank=True, null=True, help_text='When WhatsApp was successfully connected'),
        ),
        migrations.AddField(
            model_name='client',
            name='whatsapp_bridge_error',
            field=models.TextField(blank=True, help_text='Last error message from bridge connection'),
        ),

        # WhatsAppBridgeConfig singleton model
        migrations.CreateModel(
            name='WhatsAppBridgeConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False, help_text='Global toggle: allow WhatsApp Bridge integration for all clients')),
                ('homeserver_url', models.URLField(help_text='Synapse homeserver URL (e.g., http://synapse:8008)')),
                ('homeserver_domain', models.CharField(max_length=255, help_text='Matrix server domain (e.g., crm.local or grot.de)')),
                ('provisioning_url', models.URLField(help_text='mautrix-whatsapp provisioning API URL')),
                ('provisioning_secret', models.CharField(max_length=255, help_text='Provisioning shared secret from mautrix-whatsapp config')),
                ('registration_shared_secret', models.CharField(max_length=255, help_text='Synapse registration_shared_secret for creating Matrix users')),
                ('bot_username_template', models.CharField(default='nexelin_client_{client_id}', max_length=100, help_text='Template for Matrix bot usernames per client')),
            ],
            options={
                'verbose_name': 'WhatsApp Bridge Config',
                'verbose_name_plural': 'WhatsApp Bridge Config',
            },
        ),
    ]
