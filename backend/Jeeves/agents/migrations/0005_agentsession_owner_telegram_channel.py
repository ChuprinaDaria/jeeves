from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0004_alter_agentconfig_assistant_prompt_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agentsession",
            name="channel",
            field=models.CharField(
                choices=[
                    ("web", "Web Chat"),
                    ("telegram", "Telegram"),
                    ("whatsapp_meta", "WhatsApp Meta"),
                    ("whatsapp_bridge", "WhatsApp Bridge"),
                    ("email", "Email"),
                    ("api", "API"),
                    ("sandbox", "Sandbox"),
                    ("owner_telegram", "Owner Telegram"),
                ],
                max_length=20,
            ),
        ),
    ]
