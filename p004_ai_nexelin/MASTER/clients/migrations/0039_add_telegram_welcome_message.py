# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0038_add_hitl_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='telegram_welcome_message',
            field=models.TextField(
                blank=True,
                help_text="Custom welcome message for Telegram bot. Shown when user sends /start. Use {name} for user's first name."
            ),
        ),
    ]

