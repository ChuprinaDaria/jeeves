import django.db.models.deletion
from django.db import migrations, models

import Jeeves.concierge_platform.fields


class Migration(migrations.Migration):

    dependencies = [
        ("tools", "0025_custom_rest_integration"),
        ("clients", "0065_owner_telegram_chat"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationTrigger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("kind", models.CharField(choices=[("webhook", "Inbound webhook"), ("schedule", "Scheduled")], max_length=20)),
                ("target", models.CharField(choices=[("assistant", "AI Assistant (Jeeves)"), ("manager", "Consultant")], default="assistant", max_length=20)),
                ("instruction", models.TextField(help_text="What the agent should do when this fires; the event payload is appended")),
                ("token", models.CharField(blank=True, db_index=True, help_text="Unguessable URL path component for the inbound webhook", max_length=64, null=True, unique=True)),
                ("secret", Jeeves.concierge_platform.fields.EncryptedJSONField(blank=True, default=dict, help_text='{"header": "X-Webhook-Secret", "value": "..."} verified on each call')),
                ("interval_seconds", models.IntegerField(blank=True, help_text="For kind=schedule: how often to fire (seconds, min 60)", null=True)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("enabled", models.BooleanField(default=True)),
                ("fire_count", models.IntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integration_triggers", to="clients.client")),
                ("tool_card", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggers", to="tools.toolcard")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="integrationtrigger",
            index=models.Index(fields=["kind", "enabled", "next_run_at"], name="tools_integ_kind_2e6c7c_idx"),
        ),
        migrations.AddIndex(
            model_name="integrationtrigger",
            index=models.Index(fields=["client", "enabled"], name="tools_integ_client__9d4f1a_idx"),
        ),
    ]
