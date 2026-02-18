# Generated migration for Matrix.org HITL integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0040_client_notification_language'),
    ]

    operations = [
        # Add Matrix fields to Client model
        migrations.AddField(
            model_name='client',
            name='matrix_hitl_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Enable Matrix.org for HITL escalations (unified interface for all channels)'
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_manager_user_ids',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of Matrix user IDs for managers (e.g., ['@manager1:matrix.org', '@manager2:matrix.org']). Managers receive escalations in Matrix rooms."
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_homeserver_url',
            field=models.CharField(
                blank=True,
                default='https://matrix.org',
                help_text='Matrix homeserver URL (default: https://matrix.org)',
                max_length=255
            ),
        ),
        # Add Matrix fields to ClientWhatsAppConversation model
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_room_id',
            field=models.CharField(
                blank=True,
                help_text='Matrix room ID for HITL escalation (e.g., !abc123:matrix.org)',
                max_length=255,
                null=True,
                verbose_name='Matrix Room ID'
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_room_alias',
            field=models.CharField(
                blank=True,
                help_text='Matrix room alias (e.g., #escalation-123:matrix.org)',
                max_length=255,
                null=True,
                verbose_name='Matrix Room Alias'
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_escalation_active',
            field=models.BooleanField(
                default=False,
                help_text="Whether there's an active escalation in Matrix room",
                verbose_name='Matrix Escalation Active'
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_last_event_id',
            field=models.CharField(
                blank=True,
                help_text='Last processed Matrix event ID (for sync)',
                max_length=255,
                null=True,
                verbose_name='Matrix Last Event ID'
            ),
        ),
    ]

