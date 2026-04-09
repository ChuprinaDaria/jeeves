from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0023_merge_llm_fields'),
        ('EmbeddingModel', '0004_llmprovider'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='llm_provider_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='clients_using_llm',
                to='EmbeddingModel.llmprovider',
                help_text='LLM provider for response generation',
                verbose_name='LLM Provider'
            ),
        ),
    ]
