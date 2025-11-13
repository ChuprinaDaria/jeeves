from django.db import migrations


class Migration(migrations.Migration):
    # Empty placeholder migration to satisfy dependency chain on servers
    # where schema changes were applied manually/faked.

    dependencies = [
        ('clients', '0019_client_meta_phone_number'),
    ]

    operations = [
        # Intentionally left empty. The actual schema exists already.
    ]


