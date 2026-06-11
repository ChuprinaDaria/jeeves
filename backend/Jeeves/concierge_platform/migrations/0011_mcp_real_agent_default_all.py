from django.db import migrations


def enable_for_all(apps, schema_editor):
    """MCP (A2A) agent architecture becomes the platform default."""
    FeatureFlag = apps.get_model("concierge_platform", "FeatureFlag")
    FeatureFlag.objects.filter(key="mcp_real_agent").update(rollout="all")


def revert_to_selected(apps, schema_editor):
    FeatureFlag = apps.get_model("concierge_platform", "FeatureFlag")
    FeatureFlag.objects.filter(key="mcp_real_agent").update(rollout="selected")


class Migration(migrations.Migration):

    dependencies = [
        ("concierge_platform", "0010_delete_platformlicense"),
    ]

    operations = [
        migrations.RunPython(enable_for_all, revert_to_selected),
    ]
