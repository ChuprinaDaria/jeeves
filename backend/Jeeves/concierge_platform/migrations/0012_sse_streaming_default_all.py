from django.db import migrations


def enable_for_all(apps, schema_editor):
    """SSE streaming (tokens + tool status events) becomes the default."""
    FeatureFlag = apps.get_model("concierge_platform", "FeatureFlag")
    FeatureFlag.objects.filter(key="mcp_sse_streaming").update(rollout="all")


def revert_to_off(apps, schema_editor):
    FeatureFlag = apps.get_model("concierge_platform", "FeatureFlag")
    FeatureFlag.objects.filter(key="mcp_sse_streaming").update(rollout="off")


class Migration(migrations.Migration):

    dependencies = [
        ("concierge_platform", "0011_mcp_real_agent_default_all"),
    ]

    operations = [
        migrations.RunPython(enable_for_all, revert_to_off),
    ]
