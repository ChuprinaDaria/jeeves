from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration to resolve multiple leaf nodes:
    - 0020_client_embedding_model_client_llm_model_name_and_more (server-side)
    - 0022_client_llm_fields (repo-side)
    """

    dependencies = [
        ('clients', '0020_client_embedding_model_client_llm_model_name_and_more'),
        ('clients', '0022_client_llm_fields'),
    ]

    operations = [
        # No schema changes; this merges the branches.
    ]


