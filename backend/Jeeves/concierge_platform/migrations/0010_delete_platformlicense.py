from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0009_drop_platformdefaults_fk_fields'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PlatformLicense',
        ),
    ]
