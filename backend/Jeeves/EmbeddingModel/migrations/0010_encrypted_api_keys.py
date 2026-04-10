from django.db import migrations

import Jeeves.concierge_platform.fields


class Migration(migrations.Migration):

    dependencies = [
        ('EmbeddingModel', '0009_alter_embeddingmodel_external_guid_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='embeddingmodel',
            name='api_key',
            field=Jeeves.concierge_platform.fields.EncryptedTextField(
                blank=True,
                help_text='API key (encrypted at rest)',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='llmprovider',
            name='api_key',
            field=Jeeves.concierge_platform.fields.EncryptedTextField(
                blank=True,
                help_text='API key (encrypted at rest)',
                null=True,
            ),
        ),
    ]
