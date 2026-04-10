from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('EmbeddingModel', '0002_vector_dimensions_fixed'),
    ]

    operations = [
        migrations.AddField(
            model_name='embeddingmodel',
            name='slug',
            field=models.SlugField(max_length=100, unique=True, blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='embeddingmodel',
            name='reindex_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='embeddingmodel',
            name='api_endpoint',
            field=models.URLField(blank=True, null=True, help_text='API endpoint for local models'),
        ),
        migrations.AddField(
            model_name='embeddingmodel',
            name='is_local',
            field=models.BooleanField(default=False, help_text='Is this a locally hosted model?'),
        ),
        migrations.AddField(
            model_name='embeddingmodel',
            name='server_type',
            field=models.CharField(
                max_length=20,
                default='',
                choices=[
                    ('', 'Cloud/API'),
                    ('main', 'Main Server (192.168.0.51)'),
                    ('light', 'Light Server (192.168.0.53)'),
                ],
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name='embeddingmodel',
            name='api_key',
            field=models.CharField(max_length=255, blank=True, null=True, help_text='API key for third-party services (Kimi, etc.)'),
        ),
    ]


