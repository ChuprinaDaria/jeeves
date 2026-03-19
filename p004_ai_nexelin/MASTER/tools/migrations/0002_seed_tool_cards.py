from django.db import migrations


def forward(apps, schema_editor):
    from MASTER.tools.seed_data import INITIAL_TOOLS
    ToolCard = apps.get_model('tools', 'ToolCard')
    for tool_data in INITIAL_TOOLS:
        ToolCard.objects.get_or_create(
            slug=tool_data['slug'],
            defaults={k: v for k, v in tool_data.items() if k != 'slug'})


def reverse(apps, schema_editor):
    from MASTER.tools.seed_data import INITIAL_TOOLS
    ToolCard = apps.get_model('tools', 'ToolCard')
    slugs = [t['slug'] for t in INITIAL_TOOLS]
    ToolCard.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [('tools', '0001_initial')]
    operations = [migrations.RunPython(forward, reverse)]
