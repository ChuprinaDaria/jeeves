"""Drop Matrix.org HITL fields.

Matrix-based HITL escalation was removed from the product. This migration
deletes the per-client Matrix HITL configuration fields and the per-
conversation Matrix room tracking fields.

WhatsApp bridge fields (whatsapp_bridge_matrix_user_id,
whatsapp_bridge_matrix_access_token, ClientBridgeConnection.matrix_access_token)
are intentionally kept — the WhatsApp integration still uses mautrix-whatsapp
as its transport and needs the Matrix access tokens for that bridge.

Must run after tools.0003_migrate_connections so that data migration can
still read the historical fields via apps.get_model.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0061_remove_clientwhatsappconversation_table'),
        ('tools', '0003_migrate_connections'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='client',
            name='matrix_hitl_enabled',
        ),
        migrations.RemoveField(
            model_name='client',
            name='matrix_manager_user_ids',
        ),
        migrations.RemoveField(
            model_name='client',
            name='matrix_homeserver_url',
        ),
        migrations.RemoveField(
            model_name='clientwhatsappconversation',
            name='matrix_room_id',
        ),
        migrations.RemoveField(
            model_name='clientwhatsappconversation',
            name='matrix_room_alias',
        ),
        migrations.RemoveField(
            model_name='clientwhatsappconversation',
            name='matrix_escalation_active',
        ),
        migrations.RemoveField(
            model_name='clientwhatsappconversation',
            name='matrix_last_event_id',
        ),
    ]
