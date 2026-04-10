from django.db import migrations


def _filter_known_fields(model_cls, data):
    """Return only the keys from data that correspond to concrete fields on
    model_cls. seed_data.py is written against the *current* model and may
    include fields (e.g. tagline_i18n) that don't exist yet at this
    migration's state."""
    known = {f.name for f in model_cls._meta.get_fields()}
    return {k: v for k, v in data.items() if k in known}


def forward(apps, schema_editor):
    from MASTER.tools.seed_data import INITIAL_TOOLS
    ToolCard = apps.get_model('tools', 'ToolCard')
    for tool_data in INITIAL_TOOLS:
        known = _filter_known_fields(ToolCard, tool_data)
        ToolCard.objects.get_or_create(
            slug=known['slug'],
            defaults={k: v for k, v in known.items() if k != 'slug'},
        )


def reverse(apps, schema_editor):
    from MASTER.tools.seed_data import INITIAL_TOOLS
    ToolCard = apps.get_model('tools', 'ToolCard')
    slugs = [t['slug'] for t in INITIAL_TOOLS]
    ToolCard.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [('tools', '0001_initial')]
    operations = [migrations.RunPython(forward, reverse)]
