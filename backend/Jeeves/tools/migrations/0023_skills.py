from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tools", "0022_normalize_matrix_field_keys"),
        ("clients", "0065_owner_telegram_chat"),
    ]

    operations = [
        migrations.CreateModel(
            name="Skill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(unique=True)),
                ("description", models.CharField(blank=True, help_text="One line shown in catalogs and to Jeeves", max_length=300)),
                ("content", models.TextField(help_text="Markdown instructions appended to the agent system prompt")),
                ("allowed_targets", models.JSONField(blank=True, default=list, help_text='Subset of ["assistant","manager","leads"]; empty = any target')),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SkillAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target", models.CharField(choices=[("assistant", "AI Assistant (Jeeves)"), ("manager", "Consultant (customer-facing)"), ("leads", "Lead handling")], max_length=20)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="skill_assignments", to="clients.client")),
                ("skill", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="tools.skill")),
            ],
            options={
                "unique_together": {("client", "skill", "target")},
                "indexes": [models.Index(fields=["client", "target", "enabled"], name="tools_skill_client__7ce2f4_idx")],
            },
        ),
    ]
