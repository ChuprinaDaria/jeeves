from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Depend on the 0020 that actually creates ClientQRCode on servers
        ("clients", "0020_client_embedding_model_client_llm_model_name_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientqrcode",
            name="qr_code_url",
            field=models.URLField(blank=True, editable=False, max_length=500, verbose_name="QR Code URL"),
        ),
    ]


