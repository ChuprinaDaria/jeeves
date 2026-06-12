from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tools", "0024_seed_standard_skills"),
        ("clients", "0065_owner_telegram_chat"),
    ]

    operations = [
        migrations.AddField(
            model_name="toolcard",
            name="owner_client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="owned_tool_cards",
                to="clients.client",
                help_text="If set, this card is a private custom integration for one client",
            ),
        ),
        migrations.AlterField(
            model_name="toolcard",
            name="transport_type",
            field=models.CharField(
                choices=[
                    ("builtin", "Built-in Django handler"),
                    ("sse", "SSE (Server-Sent Events)"),
                    ("streamable_http", "Streamable HTTP"),
                    ("stdio", "Stdio (local subprocess)"),
                    ("http_rest", "Custom REST API"),
                ],
                max_length=20,
            ),
        ),
    ]
