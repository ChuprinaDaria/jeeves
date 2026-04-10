# Generated manually for separating embedding and LLM statistics

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('processing', '0004_alter_usagestats_operation_type'),
        ('EmbeddingModel', '0004_llmprovider'),  # LLMProvider was added in this migration
    ]

    operations = [
        # Make embedding_model nullable to support LLM-only operations
        migrations.AlterField(
            model_name='usagestats',
            name='embedding_model',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='usage_stats',
                to='EmbeddingModel.embeddingmodel',
                help_text='Embedding model for embedding operations'
            ),
        ),
        # Add llm_provider field
        migrations.AddField(
            model_name='usagestats',
            name='llm_provider',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='usage_stats',
                to='EmbeddingModel.llmprovider',
                help_text='LLM provider for LLM operations'
            ),
        ),
        # Update operation_type choices to include new types
        migrations.AlterField(
            model_name='usagestats',
            name='operation_type',
            field=models.CharField(
                choices=[
                    ('create_embedding', 'Create Embedding'),
                    ('query', 'Query'),
                    ('scan_qr', 'Scan QR'),
                    ('rag_chat', 'RAG Chat'),
                    ('rag_chat_embedding', 'RAG Chat Embedding'),
                    ('rag_chat_llm', 'RAG Chat LLM'),
                ],
                max_length=20
            ),
        ),
        # Add constraint to ensure at least one model is set
        migrations.AddConstraint(
            model_name='usagestats',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(('embedding_model__isnull', False)) | models.Q(('llm_provider__isnull', False))
                ),
                name='at_least_one_model_set'
            ),
        ),
    ]

