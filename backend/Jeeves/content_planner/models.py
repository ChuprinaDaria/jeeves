"""Content Planner models — ported and simplified from sloth/apps/content.

Per-client (multi-tenant via ``clients.Client`` FK). Publishing happens through
the Matrix MCP (``matrix_send_message``) for Telegram channels, IG DM, FB pages
exposed via bridges — not via direct Meta Graph API. The ``scheduled_at`` /
``status`` fields here only describe the editorial pipeline.
"""
from django.db import models


class ContentPlan(models.Model):
    STATUS_CHOICES = [
        ("generating", "Generating"),
        ("pending_review", "Pending Review"),
        ("approved", "Approved"),
        ("archived", "Archived"),
    ]
    NETWORK_CHOICES = [
        ("instagram", "Instagram"),
        ("threads", "Threads"),
        ("telegram_channel", "Telegram Channel"),
        ("facebook_page", "Facebook Page"),
        ("facebook_group", "Facebook Group"),
        ("linkedin", "LinkedIn"),
    ]

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="content_plans",
    )
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    networks = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="generating")
    generation_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "-created_at"]),
            models.Index(fields=["client", "status"]),
        ]

    def __str__(self):
        return f"ContentPlan {self.title} ({self.status})"

    def approve(self):
        self.posts.filter(status="draft").update(status="scheduled")
        self.status = "approved"
        self.save(update_fields=["status", "updated_at"])


class ContentPost(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("rescheduled", "Rescheduled"),
        ("rejected", "Rejected"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
        ("failed", "Failed"),
    ]
    POST_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("video", "Video"),
        ("carousel", "Carousel"),
        ("story", "Story"),
    ]

    content_plan = models.ForeignKey(
        ContentPlan, on_delete=models.CASCADE, related_name="posts",
    )
    network = models.CharField(max_length=30, choices=ContentPlan.NETWORK_CHOICES)
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    text = models.TextField()
    hashtags = models.JSONField(default=list, blank=True)
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default="text")

    shoot_suggestion = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # Matrix room for delivery (one Matrix room may bridge a TG channel / FB page).
    matrix_room_id = models.CharField(max_length=255, blank=True)
    matrix_event_id = models.CharField(max_length=255, blank=True)

    engagement_hint = models.TextField(blank=True)
    platform_metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["content_plan", "status"]),
            models.Index(fields=["content_plan", "network", "scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.network} post @ {self.scheduled_at} ({self.status})"

    def reschedule(self, new_dt):
        self.scheduled_at = new_dt
        self.status = "rescheduled"
        self.save(update_fields=["scheduled_at", "status", "updated_at"])


class ContentIdea(models.Model):
    """Free-form ideas captured from chat or research, fed into plan generation."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("used", "Used"),
        ("archived", "Archived"),
    ]

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="content_ideas",
    )
    network = models.CharField(max_length=50, blank=True, default="")
    topic = models.CharField(max_length=500)
    details = models.TextField(blank=True, default="")
    source_message = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status"]),
        ]

    def __str__(self):
        return f"Idea: {self.topic[:50]} ({self.status})"
