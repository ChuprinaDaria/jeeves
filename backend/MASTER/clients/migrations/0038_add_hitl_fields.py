# Generated manually for HITL (Human-in-the-Loop) feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0037_add_rating_request_fields'),
    ]

    operations = [
        # Add HITL fields to Client model
        migrations.AddField(
            model_name='client',
            name='hitl_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Enable Human-in-the-Loop escalation to managers when AI cannot answer'
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='manager_telegram_ids',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of manager Telegram user IDs for escalation. Example: [123456789, 987654321]. Managers receive questions when AI cannot answer.'
            ),
        ),
        
        # Add HITL fields to ClientWhatsAppConversation model
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='is_waiting_for_manager',
            field=models.BooleanField(
                default=False,
                help_text='True when AI escalated the question to a human manager',
                verbose_name='Waiting for Manager'
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='manager_escalation_context',
            field=models.TextField(
                blank=True,
                help_text='Stores the question and context while waiting for manager response',
                verbose_name='Escalation Context'
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='last_escalation_message_id',
            field=models.CharField(
                blank=True,
                help_text='Telegram message_id of the escalation notification sent to manager (for reply tracking)',
                max_length=64,
                verbose_name='Escalation Message ID'
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='escalation_manager_id',
            field=models.CharField(
                blank=True,
                help_text='Telegram user_id of the manager who received the escalation',
                max_length=64,
                verbose_name='Escalation Manager ID'
            ),
        ),
    ]

