from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0020_client_embedding_model_alter_client_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='llm_provider',
            field=models.CharField(
                default='openai',
                max_length=50,
                choices=[
                    ('openai', 'OpenAI'),
                    ('ollama_main', 'Ollama Main (qwen2.5:7b)'),
                    ('ollama_light', 'Ollama Light (qwen2.5:1.5b)'),
                    ('kimi', 'Kimi (Moonshot AI)'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='llm_model_name',
            field=models.CharField(
                default='gpt-4o-mini',
                max_length=100,
                help_text='Model name: gpt-4o-mini, qwen2.5, llama3, etc.',
            ),
        ),
    ]


