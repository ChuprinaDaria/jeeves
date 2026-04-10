from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0060_encrypt_matrix_access_token'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='clientwhatsappconversation',
            name='clients_cli_table_i_1dce13_idx',
        ),
        migrations.RemoveField(
            model_name='clientwhatsappconversation',
            name='table',
        ),
    ]
