# Generated — add mautrix_db_password to WhatsAppBridgeConfig

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0046_whatsapp_bridge'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappbridgeconfig',
            name='mautrix_db_password',
            field=models.CharField(
                blank=True,
                max_length=255,
                help_text='Password for mautrix PostgreSQL database (also use in docker-compose .env as POSTGRES_MAUTRIX_PASSWORD)',
            ),
        ),
    ]
