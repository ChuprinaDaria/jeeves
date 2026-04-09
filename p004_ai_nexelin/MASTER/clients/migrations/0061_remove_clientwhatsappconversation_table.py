from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0060_encrypt_matrix_access_token'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clientwhatsappconversation',
            field_name='table',
        ),
    ]
