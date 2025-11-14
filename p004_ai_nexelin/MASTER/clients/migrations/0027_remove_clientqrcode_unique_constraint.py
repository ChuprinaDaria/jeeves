from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0026_remove_client_llm_provider_model_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='clientqrcode',
            unique_together=set(),
        ),
    ]

