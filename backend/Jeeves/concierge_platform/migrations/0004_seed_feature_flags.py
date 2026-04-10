from django.db import migrations

FLAGS = [
    ('mcp_tools_dashboard', 'New tools dashboard UI'),
    ('mcp_agent_config', 'New AgentConfig instead of Client fields'),
    ('mcp_sse_streaming', 'SSE streaming for chat'),
    ('language_detection_v2', 'lingua-py instead of word lists'),
    ('system_messages', 'SystemMessage instead of hardcoded strings'),
]


def forward(apps, schema_editor):
    FeatureFlag = apps.get_model('concierge_platform', 'FeatureFlag')
    for key, desc in FLAGS:
        FeatureFlag.objects.get_or_create(
            key=key, defaults={'description': desc, 'rollout': 'off'})


def reverse(apps, schema_editor):
    FeatureFlag = apps.get_model('concierge_platform', 'FeatureFlag')
    keys = [f[0] for f in FLAGS]
    FeatureFlag.objects.filter(key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [('concierge_platform', '0003_seed_system_messages')]
    operations = [migrations.RunPython(forward, reverse)]
