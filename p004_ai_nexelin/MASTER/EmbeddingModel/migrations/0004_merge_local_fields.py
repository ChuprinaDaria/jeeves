from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration to resolve multiple leaf nodes:
    - 0003_add_local_fields (repo-side)
    - 0003_embeddingmodel_api_endpoint_embeddingmodel_api_key_and_more (server-side)
    """

    dependencies = [
        ('EmbeddingModel', '0003_add_local_fields'),
        ('EmbeddingModel', '0003_embeddingmodel_api_endpoint_embeddingmodel_api_key_and_more'),
    ]

    operations = [
        # No schema changes; this merges the branches.
    ]


