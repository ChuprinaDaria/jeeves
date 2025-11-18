# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0025_add_llm_provider_fk'),
    ]
    operations = [
        migrations.AddField(
            model_name='clientqrcode',
            name='integration_type',
            field=models.CharField(
                choices=[('whatsapp', 'WhatsApp'), ('web', 'Web Chat')],
                default='web',
                help_text='Type of integration this QR code is for',
                max_length=20,
                verbose_name='Integration Type'
            ),
        ),
    ]

