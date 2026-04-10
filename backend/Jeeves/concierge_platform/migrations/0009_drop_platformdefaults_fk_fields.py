from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0008_alter_platformlicense_id'),
        ('EmbeddingModel', '0010_encrypted_api_keys'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='platformdefaults',
            name='default_llm_provider',
        ),
        migrations.RemoveField(
            model_name='platformdefaults',
            name='default_embedding_model',
        ),
    ]
