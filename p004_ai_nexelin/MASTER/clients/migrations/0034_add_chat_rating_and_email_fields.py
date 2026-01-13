# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0033_clientwhatsappconversation_telegram_chat_id'),
    ]

    operations = [
        # Add rating fields to ClientWhatsAppConversation
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='user_rating',
            field=models.CharField(blank=True, choices=[('positive', '👍 Positive'), ('negative', '👎 Negative')], help_text='Rating given by user (👍 or 👎)', max_length=10, null=True, verbose_name='User Rating'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='ai_rating',
            field=models.CharField(blank=True, choices=[('positive', '👍 Positive'), ('negative', '👎 Negative')], help_text='Auto-rating by AI after 5 minutes of inactivity if user did not rate', max_length=10, null=True, verbose_name='AI Rating'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='rating_timestamp',
            field=models.DateTimeField(blank=True, help_text='When the rating was given (user or AI)', null=True, verbose_name='Rating Timestamp'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='email_sent',
            field=models.BooleanField(default=False, help_text='Whether summary email was sent to client', verbose_name='Email Sent'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='email_sent_at',
            field=models.DateTimeField(blank=True, help_text='When the summary email was sent', null=True, verbose_name='Email Sent At'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='summary',
            field=models.TextField(blank=True, help_text='AI-generated summary of the conversation', verbose_name='Chat Summary'),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='last_activity_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp of last message in conversation', null=True, verbose_name='Last Activity'),
        ),
        # Add email report fields to Client
        migrations.AddField(
            model_name='client',
            name='email_report_enabled',
            field=models.BooleanField(default=False, help_text='Enable automatic email reports for closed chat sessions'),
        ),
        migrations.AddField(
            model_name='client',
            name='email_report_recipients',
            field=models.JSONField(blank=True, default=list, help_text="List of email addresses to receive chat summary reports. Example: ['owner@example.com', 'support@example.com']"),
        ),
    ]

