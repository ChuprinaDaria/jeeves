from django.db import migrations, models
from django.apps.registry import Apps
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def forwards_copy_entity_fields(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UsageStats = apps.get_model("processing", "UsageStats")
    # Copy entity_id -> corresponding FK based on entity_type
    for row in UsageStats.objects.all().only("id", "entity_type", "entity_id"):
        if row.entity_type == "branch" and row.entity_id is not None:
            UsageStats.objects.filter(pk=row.pk).update(branch_id=row.entity_id)
        elif row.entity_type == "specialization" and row.entity_id is not None:
            UsageStats.objects.filter(pk=row.pk).update(specialization_id=row.entity_id)
        elif row.entity_type == "client" and row.entity_id is not None:
            UsageStats.objects.filter(pk=row.pk).update(client_id=row.entity_id)


def backwards_copy_entity_fields(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UsageStats = apps.get_model("processing", "UsageStats")
    # Restore entity_type/entity_id from the FKs
    for row in UsageStats.objects.all().only("id", "branch_id", "specialization_id", "client_id"):
        if getattr(row, "branch_id", None):
            UsageStats.objects.filter(pk=row.pk).update(entity_type="branch", entity_id=row.branch_id)
        elif getattr(row, "specialization_id", None):
            UsageStats.objects.filter(pk=row.pk).update(entity_type="specialization", entity_id=row.specialization_id)
        elif getattr(row, "client_id", None):
            UsageStats.objects.filter(pk=row.pk).update(entity_type="client", entity_id=row.client_id)


class Migration(migrations.Migration):
    dependencies = [
        ("processing", "0001_initial"),
        ("branches", "0002_branchdocument_metadata"),
        ("specializations", "0002_specializationdocument_metadata"),
        ("clients", "0005_clientdocument_metadata"),
    ]

    operations = [
        # 1) Add new nullable FKs
        migrations.AddField(
            model_name="usagestats",
            name="branch",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="usage_stats", to="branches.branch"),
        ),
        migrations.AddField(
            model_name="usagestats",
            name="client",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="usage_stats", to="clients.client"),
        ),
        migrations.AddField(
            model_name="usagestats",
            name="specialization",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="usage_stats", to="specializations.specialization"),
        ),
        # 2) Copy data from old fields into new FKs
        migrations.RunPython(forwards_copy_entity_fields, backwards_copy_entity_fields),
        # 3) Drop old index that referenced entity_type/entity_id
        migrations.RemoveIndex(
            model_name="usagestats",
            name="processing__entity__4d4e7f_idx",
        ),
        # 4) Remove old fields
        migrations.RemoveField(
            model_name="usagestats",
            name="content_type",
        ),
        migrations.RemoveField(
            model_name="usagestats",
            name="entity_id",
        ),
        migrations.RemoveField(
            model_name="usagestats",
            name="entity_type",
        ),
        # 5) Add new indexes and constraint
        migrations.AddIndex(
            model_name="usagestats",
            index=models.Index(fields=["branch", "date"], name="usage_branch_date_idx"),
        ),
        migrations.AddIndex(
            model_name="usagestats",
            index=models.Index(fields=["specialization", "date"], name="usage_spec_date_idx"),
        ),
        migrations.AddIndex(
            model_name="usagestats",
            index=models.Index(fields=["client", "date"], name="usage_client_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="usagestats",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(branch__isnull=False, specialization__isnull=True, client__isnull=True)
                    | models.Q(branch__isnull=True, specialization__isnull=False, client__isnull=True)
                    | models.Q(branch__isnull=True, specialization__isnull=True, client__isnull=False)
                ),
                name="only_one_entity_set",
            ),
        ),
    ]


