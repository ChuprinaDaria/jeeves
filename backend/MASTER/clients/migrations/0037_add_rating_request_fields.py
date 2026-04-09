# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0036_add_notes_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='rating_request_sent',
            field=models.BooleanField(default=False, help_text='Whether rating request message was sent to user', verbose_name='Rating Request Sent'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='rating_request_sent_at',
            field=models.DateTimeField(blank=True, help_text='When the rating request was sent', null=True, verbose_name='Rating Request Sent At'),
        ),
    ]

