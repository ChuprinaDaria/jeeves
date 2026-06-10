"""Normalize matrix ToolCard auth_config fields to use 'name' instead of 'key'.

The 0019 seed used `{'key': ...}`, but every other tool seed (and the
frontend FlipToolCard / ConnectModal forms + the ToolConnectView validator)
expects `{'name': ...}`. Re-key in place so the Matrix tool can be connected
via the UI without a 500.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    try:
        card = ToolCard.objects.get(slug='matrix')
    except ToolCard.DoesNotExist:
        return
    cfg = card.auth_config or {}
    fields = cfg.get('fields') or []
    changed = False
    for f in fields:
        if 'key' in f and 'name' not in f:
            f['name'] = f.pop('key')
            changed = True
    if changed:
        card.auth_config = cfg
        card.save(update_fields=['auth_config'])


def backwards(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    try:
        card = ToolCard.objects.get(slug='matrix')
    except ToolCard.DoesNotExist:
        return
    cfg = card.auth_config or {}
    for f in cfg.get('fields') or []:
        if 'name' in f and 'key' not in f:
            f['key'] = f.pop('name')
    card.auth_config = cfg
    card.save(update_fields=['auth_config'])


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0021_seed_content_planner_tool'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
