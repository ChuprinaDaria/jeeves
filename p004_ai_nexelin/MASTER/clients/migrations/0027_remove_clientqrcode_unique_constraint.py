from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0025_add_llm_provider_fk'),
    ]

    operations = [
        # Try to remove unique_together constraint if it exists
        # This will work regardless of whether 0026 was applied or not
        migrations.AlterUniqueTogether(
            name='clientqrcode',
            unique_together=set(),
        ),
    ]

