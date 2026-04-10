from django.db import migrations


class Migration(migrations.Migration):
    """No-op retained for historical migration numbering.

    The `table` field and its index on `ClientWhatsAppConversation` were
    originally removed here, but migration 0026 was edited to never create
    them (it previously referenced `restaurant.restauranttable`, a dangling
    FK to an app that never existed). This migration is now a no-op so the
    migration graph stays linear.
    """

    dependencies = [
        ('clients', '0060_encrypt_matrix_access_token'),
    ]

    operations = [
    ]
