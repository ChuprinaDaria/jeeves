# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0035_add_client_custom_prompts'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='notes',
            field=models.TextField(blank=True, help_text='Manual notes or comments about this conversation', verbose_name='Notes'),
        ),
    ]

