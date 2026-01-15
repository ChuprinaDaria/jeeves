# Generated migration for notification_language field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0039_add_telegram_welcome_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='notification_language',
            field=models.CharField(
                max_length=5,
                choices=[
                    ('en', 'English'),
                    ('de', 'Deutsch'),
                    ('fr', 'Français'),
                    ('es', 'Español'),
                    ('it', 'Italiano'),
                    ('nl', 'Nederlands'),
                    ('da', 'Dansk'),
                ],
                default='en',
                help_text="Default language for email reports, daily digests, and manager notifications. Customer-facing AI responses use customer's language."
            ),
        ),
    ]

