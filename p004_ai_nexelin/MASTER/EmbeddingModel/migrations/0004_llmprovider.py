from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('EmbeddingModel', '0003_add_local_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='LLMProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Display name (e.g., "GPT-4o Mini", "Qwen2.5 7B Main")', max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=100, unique=True)),
                ('provider_type', models.CharField(choices=[('openai', 'OpenAI'), ('ollama_main', 'Ollama Main Server'), ('ollama_light', 'Ollama Light Server'), ('kimi', 'Kimi (Moonshot AI)'), ('anthropic', 'Anthropic (Claude)'), ('custom', 'Custom')], help_text='Provider type', max_length=50)),
                ('model_name', models.CharField(help_text='Model identifier (e.g., "gpt-4o-mini", "qwen2.5:7b")', max_length=100)),
                ('api_endpoint', models.URLField(blank=True, help_text='API endpoint for Ollama/custom providers (e.g., http://192.168.0.51:11434)', null=True)),
                ('api_key', models.CharField(blank=True, help_text='API key (для OpenAI, Anthropic, Kimi)', max_length=255, null=True)),
                ('cost_per_1k_input_tokens', models.DecimalField(decimal_places=6, default=0, help_text='Cost per 1000 input tokens (USD)', max_digits=10)),
                ('cost_per_1k_output_tokens', models.DecimalField(decimal_places=6, default=0, help_text='Cost per 1000 output tokens (USD)', max_digits=10)),
                ('max_tokens', models.IntegerField(default=4096, help_text='Maximum context length')),
                ('temperature', models.FloatField(default=0.7, help_text='Default temperature (0.0-2.0)')),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('description', models.TextField(blank=True, help_text='Description of the model capabilities')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'LLM Provider',
                'verbose_name_plural': 'LLM Providers',
                'ordering': ['provider_type', 'name'],
            },
        ),
    ]

