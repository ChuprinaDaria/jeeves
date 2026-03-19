from django.db import migrations


def forward(apps, schema_editor):
    PlatformDefaults = apps.get_model('nexelin_platform', 'PlatformDefaults')
    PlatformDefaults.objects.get_or_create(
        pk=1,
        defaults={
            'default_temperature': 0.7,
            'default_max_tokens': 2000,
            'default_similarity_threshold': 0.1,
            'default_max_context_chunks': 5,
            'default_top_k': 5,
            'supported_languages': ['en', 'de', 'fr', 'es', 'it', 'nl', 'da'],
            'default_language': 'en',
            'language_detection_method': 'library',
            'default_greeting': '',
        },
    )


def reverse(apps, schema_editor):
    PlatformDefaults = apps.get_model('nexelin_platform', 'PlatformDefaults')
    PlatformDefaults.objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [('nexelin_platform', '0001_initial')]
    operations = [migrations.RunPython(forward, reverse)]
