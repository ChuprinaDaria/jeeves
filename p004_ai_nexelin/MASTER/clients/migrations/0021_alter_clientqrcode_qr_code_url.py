from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Depend on the 0020 placeholder migration
        ("clients", "0020_client_embedding_model_alter_client_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientqrcode",
            name="qr_code_url",
            field=models.URLField(blank=True, editable=False, max_length=500, verbose_name="QR Code URL"),
        ),
    ]


