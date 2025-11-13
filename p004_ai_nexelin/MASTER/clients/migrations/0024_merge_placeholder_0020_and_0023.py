from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration to resolve multiple leaf nodes in clients:
    - 0020_client_embedding_model_alter_client_id_and_more (placeholder branch)
    - 0023_merge_llm_fields (main branch)
    """

    dependencies = [
        ('clients', '0020_client_embedding_model_alter_client_id_and_more'),
        ('clients', '0023_merge_llm_fields'),
    ]

    operations = [
        # No schema changes; only merge branches.
    ]


