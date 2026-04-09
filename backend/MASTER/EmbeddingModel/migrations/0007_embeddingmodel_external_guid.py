# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('EmbeddingModel', '0006_alter_embeddingmodel_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='embeddingmodel',
            name='external_guid',
            field=models.CharField(blank=True, help_text='GUID from mg.nexelin.com for AI model identification in usage stats API', max_length=255, null=True),
        ),
    ]

