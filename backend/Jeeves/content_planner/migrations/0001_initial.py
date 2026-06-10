import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clients", "0063_alter_bridgeconfig_bot_username_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("networks", models.JSONField(default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("generating", "Generating"),
                            ("pending_review", "Pending Review"),
                            ("approved", "Approved"),
                            ("archived", "Archived"),
                        ],
                        default="generating",
                        max_length=20,
                    ),
                ),
                ("generation_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_plans",
                        to="clients.client",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contentplan",
            index=models.Index(fields=["client", "-created_at"], name="content_pla_client__69bf72_idx"),
        ),
        migrations.AddIndex(
            model_name="contentplan",
            index=models.Index(fields=["client", "status"], name="content_pla_client__2e9a54_idx"),
        ),
        migrations.CreateModel(
            name="ContentPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "network",
                    models.CharField(
                        choices=[
                            ("instagram", "Instagram"),
                            ("threads", "Threads"),
                            ("telegram_channel", "Telegram Channel"),
                            ("facebook_page", "Facebook Page"),
                            ("facebook_group", "Facebook Group"),
                            ("linkedin", "LinkedIn"),
                        ],
                        max_length=30,
                    ),
                ),
                ("scheduled_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("approved", "Approved"),
                            ("rescheduled", "Rescheduled"),
                            ("rejected", "Rejected"),
                            ("scheduled", "Scheduled"),
                            ("published", "Published"),
                            ("failed", "Failed"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("text", models.TextField()),
                ("hashtags", models.JSONField(blank=True, default=list)),
                (
                    "post_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("image", "Image"),
                            ("video", "Video"),
                            ("carousel", "Carousel"),
                            ("story", "Story"),
                        ],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("shoot_suggestion", models.TextField(blank=True)),
                ("rejection_reason", models.TextField(blank=True)),
                ("matrix_room_id", models.CharField(blank=True, max_length=255)),
                ("matrix_event_id", models.CharField(blank=True, max_length=255)),
                ("engagement_hint", models.TextField(blank=True)),
                ("platform_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "content_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="posts",
                        to="content_planner.contentplan",
                    ),
                ),
            ],
            options={
                "ordering": ["scheduled_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contentpost",
            index=models.Index(fields=["content_plan", "status"], name="content_pla_content_ec633c_idx"),
        ),
        migrations.AddIndex(
            model_name="contentpost",
            index=models.Index(fields=["content_plan", "network", "scheduled_at"], name="content_pla_content_842882_idx"),
        ),
        migrations.CreateModel(
            name="ContentIdea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("network", models.CharField(blank=True, default="", max_length=50)),
                ("topic", models.CharField(max_length=500)),
                ("details", models.TextField(blank=True, default="")),
                ("source_message", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("used", "Used"), ("archived", "Archived")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_ideas",
                        to="clients.client",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contentidea",
            index=models.Index(fields=["client", "status"], name="content_pla_client__b5babd_idx"),
        ),
    ]
