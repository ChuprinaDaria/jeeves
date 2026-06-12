from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0064_matrixroombinding"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="owner_telegram_chat_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Linked owner chat: messages from this chat_id talk to "
                    "Jeeves (assistant), not the consultant"
                ),
                max_length=32,
            ),
        ),
    ]
