from django.db import models


class ChannelAutoReply(models.Model):
    CHANNEL_CHOICES = [
        ('whatsapp_bridge', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('meta_instagram', 'Instagram'),
        ('meta_messenger', 'Facebook Messenger'),
        ('linkedin', 'LinkedIn'),
        ('imessage', 'iMessage'),
    ]

    SCHEDULE_MODE_CHOICES = [
        ('always', 'Always (24/7)'),
        ('scheduled', 'Scheduled hours'),
    ]

    CONTACT_MODE_CHOICES = [
        ('all', 'Respond to all'),
        ('all_except', 'Respond to all except listed'),
        ('only', 'Respond only to listed'),
    ]

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='channel_auto_replies',
    )
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES)

    # Master switch
    enabled = models.BooleanField(default=True)

    # Schedule
    schedule_mode = models.CharField(
        max_length=10,
        choices=SCHEDULE_MODE_CHOICES,
        default='always',
    )
    timezone = models.CharField(max_length=50, default='UTC')
    schedule = models.JSONField(
        default=list,
        blank=True,
        help_text='Weekly schedule: [{"day": 0, "start": "09:00", "end": "18:00", "enabled": true}, ...]',
    )

    # Contact filtering
    contact_mode = models.CharField(
        max_length=15,
        choices=CONTACT_MODE_CHOICES,
        default='all',
    )
    contact_list = models.JSONField(
        default=list,
        blank=True,
        help_text='List of contact identifiers: ["48571079588", ...]',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'channel'],
                name='unique_client_channel',
            ),
        ]

    def __str__(self):
        return f"{self.client} — {self.get_channel_display()}"
