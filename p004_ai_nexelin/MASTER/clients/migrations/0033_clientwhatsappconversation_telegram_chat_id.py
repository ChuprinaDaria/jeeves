from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0032_remove_client_llm_provider_fk_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientwhatsappconversation",
            name="telegram_chat_id",
            field=models.CharField(
                max_length=64,
                blank=True,
                verbose_name="Telegram Chat ID",
                help_text="Telegram chat_id for this conversation (used for Telegram integrations)",
            ),
        ),
        migrations.AddIndex(
            model_name="clientwhatsappconversation",
            index=models.Index(
                fields=["telegram_chat_id"],
                name="clients_cli_telegram_chat_id_idx",
            ),
        ),
    ]


