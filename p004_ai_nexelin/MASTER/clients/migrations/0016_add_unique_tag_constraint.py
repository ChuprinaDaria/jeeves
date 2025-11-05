# Generated manually for fixing client duplication issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0015_change_user_to_charfield'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='tag',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Unique client token/tag for bootstrap authentication and portal access',
                max_length=255,
                null=True,
                unique=True
            ),
        ),
    ]
