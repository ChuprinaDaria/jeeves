from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0025_add_llm_provider_fk'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='clientqrcode',
            unique_together=set(),
        ),
    ]

