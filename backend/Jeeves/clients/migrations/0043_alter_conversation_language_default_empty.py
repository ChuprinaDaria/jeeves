from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0042_merge_leaf_nodes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientwhatsappconversation',
            name='language',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='Language'),
        ),
        migrations.AlterField(
            model_name='client',
            name='notification_language',
            field=models.CharField(
                choices=[
                    ('en', 'English'),
                    ('de', 'Deutsch'),
                    ('fr', 'Français'),
                    ('es', 'Español'),
                    ('it', 'Italiano'),
                    ('nl', 'Nederlands'),
                    ('da', 'Dansk'),
                    ('uk', 'Українська'),
                    ('ru', 'Русский'),
                ],
                default='en',
                help_text="Default language for email reports, daily digests, and manager notifications. Customer-facing AI responses use customer's language.",
                max_length=5,
            ),
        ),
    ]
