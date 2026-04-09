# Vasya Auto-Response Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-channel schedule and contact filtering for Vasya auto-replies (WhatsApp Bridge, Telegram).

**Architecture:** New `ChannelAutoReply` model stores per-channel config. A single guard function `should_vasya_respond()` is called before the orchestrator in every message handler. Settings UI gets a "Channels" tab with per-channel cards.

**Tech Stack:** Django 5.x, DRF, React 18, Tailwind CSS, i18n

**Spec:** `docs/superpowers/specs/2026-04-02-vasya-auto-response-engine-design.md`

---

## File Map

### Backend — Create
| File | Responsibility |
|------|---------------|
| `MASTER/clients/models_auto_reply.py` | `ChannelAutoReply` model |
| `MASTER/clients/auto_reply.py` | `should_vasya_respond()` guard function |
| `MASTER/clients/views_auto_reply.py` | API views (list, upsert, contacts) |
| `MASTER/clients/serializers_auto_reply.py` | `ChannelAutoReplySerializer` with schedule/contact validation |
| `MASTER/clients/migrations/0009_channelauto_reply.py` | Migration (auto-generated) |
| `MASTER/clients/tests_auto_reply.py` | Tests for guard + API |

### Backend — Modify
| File | Change |
|------|--------|
| `MASTER/clients/models.py` | Import `ChannelAutoReply` at bottom for Django discovery |
| `MASTER/clients/urls.py` | Register 3 new endpoints |
| `MASTER/clients/tasks.py:3753` | Add guard call before orchestrator in `_process_bridge_message()` |
| `MASTER/clients/views_telegram.py:696` | Add guard call before orchestrator/RAG in `handle_regular_message()` |
| `MASTER/clients/admin.py` | Register `ChannelAutoReply` |

### Frontend — Create
| File | Responsibility |
|------|---------------|
| `nextlen/src/api/autoReply.js` | API client for channel auto-reply endpoints |
| `nextlen/src/components/settings/ChannelsTab.jsx` | Tab container: loads connected channels, renders cards |
| `nextlen/src/components/settings/ChannelCard.jsx` | Per-channel config card (toggle, schedule, contacts, save) |
| `nextlen/src/components/settings/ScheduleGrid.jsx` | 7-day schedule grid with time inputs |
| `nextlen/src/components/settings/ContactFilter.jsx` | Contact mode radio + contact list + add modal |

### Frontend — Modify
| File | Change |
|------|--------|
| `nextlen/src/pages/SettingsPage.jsx` | Add tab navigation (General / Channels) |
| `nextlen/src/locales/en/translation.json` | Add `settings.channels.*` keys |

---

## Task 1: ChannelAutoReply Model

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/models_auto_reply.py`
- Modify: `p004_ai_nexelin/MASTER/clients/models.py` (add import at end)

- [ ] **Step 1: Create model file**

```python
# MASTER/clients/models_auto_reply.py
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
```

- [ ] **Step 2: Add import to models.py for Django model discovery**

At the very end of `p004_ai_nexelin/MASTER/clients/models.py` (after line 2307), add:

```python
from .models_auto_reply import ChannelAutoReply  # noqa: E402, F401
```

- [ ] **Step 3: Generate migration**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py makemigrations clients --name channelauto_reply`

Expected: creates migration file in `MASTER/clients/migrations/`

- [ ] **Step 4: Verify migration applies**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py migrate clients`

Expected: `Applying clients.0009_channelauto_reply... OK`

- [ ] **Step 5: Register in admin**

In `p004_ai_nexelin/MASTER/clients/admin.py`, add to the imports (line 5-19):

```python
from .models_auto_reply import ChannelAutoReply
```

Then add after the existing admin registrations:

```python
@admin.register(ChannelAutoReply)
class ChannelAutoReplyAdmin(admin.ModelAdmin):
    list_display = ['client', 'channel', 'enabled', 'schedule_mode', 'contact_mode', 'timezone']
    list_filter = ['channel', 'enabled', 'schedule_mode']
    search_fields = ['client__company_name', 'client__tag']
```

- [ ] **Step 6: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models_auto_reply.py p004_ai_nexelin/MASTER/clients/models.py p004_ai_nexelin/MASTER/clients/migrations/ p004_ai_nexelin/MASTER/clients/admin.py
git commit -m "feat(auto-reply): add ChannelAutoReply model with per-channel schedule and contact filtering"
```

---

## Task 2: Guard Function + Tests

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/auto_reply.py`
- Create: `p004_ai_nexelin/MASTER/clients/tests_auto_reply.py`

- [ ] **Step 1: Write tests for the guard function**

```python
# MASTER/clients/tests_auto_reply.py
from datetime import datetime
from unittest.mock import patch
from django.test import TestCase
from MASTER.clients.models import Client
from MASTER.clients.models_auto_reply import ChannelAutoReply
from MASTER.clients.auto_reply import should_vasya_respond


class ShouldVasyaRespondTest(TestCase):
    def setUp(self):
        from MASTER.accounts.models import User
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client_obj = Client.objects.create(user=self.user, tag='test')

    # --- Web/sandbox always responds ---
    def test_web_channel_always_responds(self):
        self.assertTrue(should_vasya_respond(self.client_obj, 'web', 'any'))

    def test_sandbox_channel_always_responds(self):
        self.assertTrue(should_vasya_respond(self.client_obj, 'sandbox', 'any'))

    # --- No config = respond to all ---
    def test_no_config_responds(self):
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Master switch ---
    def test_disabled_does_not_respond(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=False,
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    def test_enabled_always_responds(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='always',
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Schedule ---
    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_within_window_responds(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 30, tzinfo=ZoneInfo('UTC'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_outside_window_does_not_respond(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 20, 0, tzinfo=ZoneInfo('UTC'))  # Monday 20:00
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_day_disabled_does_not_respond(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 0, tzinfo=ZoneInfo('UTC'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': False}],
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_scheduled_day_missing_does_not_respond(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 0, tzinfo=ZoneInfo('UTC'))  # Monday=0
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='UTC',
            schedule=[{'day': 2, 'start': '09:00', 'end': '18:00', 'enabled': True}],  # Wednesday only
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Contact filtering ---
    def test_all_except_blocks_listed_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all_except', contact_list=['48571079588'],
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    def test_all_except_allows_unlisted_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all_except', contact_list=['48571079588'],
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48999888777'))

    def test_only_allows_listed_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='only', contact_list=['48571079588'],
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    def test_only_blocks_unlisted_contact(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='only', contact_list=['48571079588'],
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48999888777'))

    def test_contact_plus_prefix_normalized(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all_except', contact_list=['48571079588'],
        )
        self.assertFalse(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '+48571079588'))

    def test_contact_mode_all_ignores_list(self):
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            contact_mode='all', contact_list=['48571079588'],
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    # --- Timezone ---
    @patch('MASTER.clients.auto_reply.datetime')
    def test_timezone_conversion(self, mock_dt):
        from zoneinfo import ZoneInfo
        # 10:00 UTC = 12:00 Warsaw (CEST, UTC+2)
        mock_dt.now.return_value = datetime(2026, 7, 6, 12, 0, tzinfo=ZoneInfo('Europe/Warsaw'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='Europe/Warsaw',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))

    @patch('MASTER.clients.auto_reply.datetime')
    def test_invalid_timezone_falls_back_to_utc(self, mock_dt):
        from zoneinfo import ZoneInfo
        mock_dt.now.return_value = datetime(2026, 4, 6, 10, 0, tzinfo=ZoneInfo('UTC'))  # Monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ChannelAutoReply.objects.create(
            client=self.client_obj, channel='whatsapp_bridge', enabled=True,
            schedule_mode='scheduled', timezone='Invalid/Zone',
            schedule=[{'day': 0, 'start': '09:00', 'end': '18:00', 'enabled': True}],
        )
        self.assertTrue(should_vasya_respond(self.client_obj, 'whatsapp_bridge', '48571079588'))
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py test MASTER.clients.tests_auto_reply -v 2`

Expected: `ImportError: cannot import name 'should_vasya_respond'`

- [ ] **Step 3: Implement the guard function**

```python
# MASTER/clients/auto_reply.py
from datetime import datetime
from zoneinfo import ZoneInfo

from .models_auto_reply import ChannelAutoReply


def should_vasya_respond(client, channel: str, contact_id: str) -> bool:
    """
    Check if Vasya should auto-respond to this message.
    Returns True if Vasya should respond, False to skip.
    """
    if channel in ('web', 'sandbox'):
        return True

    try:
        config = ChannelAutoReply.objects.get(client=client, channel=channel)
    except ChannelAutoReply.DoesNotExist:
        return True

    if not config.enabled:
        return False

    # Schedule check
    if config.schedule_mode == 'scheduled' and config.schedule:
        try:
            tz = ZoneInfo(config.timezone)
        except (KeyError, ValueError):
            tz = ZoneInfo('UTC')

        now = datetime.now(tz)
        current_time = now.strftime('%H:%M')

        day_entry = next(
            (d for d in config.schedule if d.get('day') == now.weekday()),
            None,
        )
        if not day_entry or not day_entry.get('enabled', False):
            return False

        start = day_entry.get('start', '00:00')
        end = day_entry.get('end', '23:59')
        if not (start <= current_time <= end):
            return False

    # Contact filter check
    if config.contact_mode == 'all':
        return True

    normalized = contact_id.lstrip('+')
    normalized_list = [c.lstrip('+') for c in (config.contact_list or [])]

    if config.contact_mode == 'all_except':
        if normalized in normalized_list:
            return False
    elif config.contact_mode == 'only':
        if normalized not in normalized_list:
            return False

    return True
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py test MASTER.clients.tests_auto_reply -v 2`

Expected: all 16 tests pass

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/auto_reply.py p004_ai_nexelin/MASTER/clients/tests_auto_reply.py
git commit -m "feat(auto-reply): add should_vasya_respond guard function with tests"
```

---

## Task 3: Serializer with Validation

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/serializers_auto_reply.py`

- [ ] **Step 1: Create the serializer with schedule and contact validation**

```python
# MASTER/clients/serializers_auto_reply.py
import re
from rest_framework import serializers
from .models_auto_reply import ChannelAutoReply

TIME_RE = re.compile(r'^\d{2}:\d{2}$')


class ChannelAutoReplySerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)

    class Meta:
        model = ChannelAutoReply
        fields = [
            'channel', 'channel_display', 'enabled',
            'schedule_mode', 'timezone', 'schedule',
            'contact_mode', 'contact_list',
        ]
        read_only_fields = ['channel']

    def validate_schedule(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Schedule must be a list.')
        seen_days = set()
        for entry in value:
            if not isinstance(entry, dict):
                raise serializers.ValidationError('Each schedule entry must be an object.')
            day = entry.get('day')
            if day is None or not isinstance(day, int) or not (0 <= day <= 6):
                raise serializers.ValidationError(f'Invalid day: {day}. Must be 0-6.')
            if day in seen_days:
                raise serializers.ValidationError(f'Duplicate day: {day}.')
            seen_days.add(day)
            for field in ('start', 'end'):
                t = entry.get(field, '')
                if not TIME_RE.match(str(t)):
                    raise serializers.ValidationError(f'Invalid {field} time: {t}. Use HH:MM format.')
            if entry.get('start', '00:00') >= entry.get('end', '23:59'):
                raise serializers.ValidationError(
                    f'Day {day}: start must be before end (overnight not supported).'
                )
            if 'enabled' not in entry:
                raise serializers.ValidationError(f'Day {day}: "enabled" field is required.')
        return value

    def validate_contact_list(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Contact list must be a list.')
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise serializers.ValidationError(f'Invalid contact: {item}')
            cleaned.append(item.lstrip('+').replace(' ', '').replace('-', ''))
        return cleaned

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, KeyError):
            raise serializers.ValidationError(f'Invalid timezone: {value}')
        return value
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/serializers_auto_reply.py
git commit -m "feat(auto-reply): add ChannelAutoReplySerializer with schedule/contact validation"
```

---

## Task 4: API Views + URL Registration

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/views_auto_reply.py`
- Modify: `p004_ai_nexelin/MASTER/clients/urls.py`

- [ ] **Step 1: Create API views**

```python
# MASTER/clients/views_auto_reply.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models_auto_reply import ChannelAutoReply
from .models import ClientWhatsAppConversation
from .serializers_auto_reply import ChannelAutoReplySerializer


class ChannelAutoReplyListView(APIView):
    """GET /api/clients/channel-auto-reply/ — all configs for current client."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = request.user.client
        configs = ChannelAutoReply.objects.filter(client=client)
        serializer = ChannelAutoReplySerializer(configs, many=True)
        return Response({'results': serializer.data})


class ChannelAutoReplyDetailView(APIView):
    """PUT /api/clients/channel-auto-reply/<channel>/ — create or update config."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel):
        client = request.user.client
        try:
            config = ChannelAutoReply.objects.get(client=client, channel=channel)
        except ChannelAutoReply.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ChannelAutoReplySerializer(config)
        return Response(serializer.data)

    def put(self, request, channel):
        client = request.user.client
        valid_channels = dict(ChannelAutoReply.CHANNEL_CHOICES)
        if channel not in valid_channels:
            return Response(
                {'detail': f'Invalid channel: {channel}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, created = ChannelAutoReply.objects.get_or_create(
            client=client,
            channel=channel,
        )
        serializer = ChannelAutoReplySerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChannelAutoReplyContactsView(APIView):
    """GET /api/clients/channel-auto-reply/<channel>/contacts/ — existing contacts for picker."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel):
        client = request.user.client
        conversations = ClientWhatsAppConversation.objects.filter(
            client=client,
        ).order_by('-last_activity_at')

        if channel == 'whatsapp_bridge':
            conversations = conversations.filter(
                context_metadata__platform='whatsapp_bridge',
            )
        elif channel == 'telegram':
            conversations = conversations.exclude(telegram_chat_id='').exclude(
                telegram_chat_id__isnull=True,
            )
        else:
            return Response({'contacts': []})

        contacts = []
        seen = set()
        for conv in conversations[:50]:
            if channel == 'whatsapp_bridge':
                contact_id = conv.customer_phone
                label = f"+{contact_id}" if contact_id and not contact_id.startswith('+') else contact_id
            elif channel == 'telegram':
                contact_id = conv.telegram_chat_id
                username = (conv.context_metadata or {}).get('username', '')
                first_name = (conv.context_metadata or {}).get('first_name', '')
                label = f"@{username}" if username else first_name or contact_id

            if not contact_id or contact_id in seen:
                continue
            seen.add(contact_id)

            last_msg = ''
            if conv.messages:
                for m in reversed(conv.messages):
                    if m.get('role') == 'user':
                        last_msg = m.get('content', '')[:100]
                        break

            contacts.append({
                'id': contact_id,
                'label': label,
                'last_message': last_msg,
                'last_activity': conv.last_activity_at.isoformat() if conv.last_activity_at else None,
            })

        return Response({'contacts': contacts})
```

- [ ] **Step 2: Register URLs**

In `p004_ai_nexelin/MASTER/clients/urls.py`, add import at top (after line 20):

```python
from .views_auto_reply import (
    ChannelAutoReplyListView,
    ChannelAutoReplyDetailView,
    ChannelAutoReplyContactsView,
)
```

Add routes before the `# Leads` comment (before line 68):

```python
    # Channel Auto-Reply
    path('channel-auto-reply/', ChannelAutoReplyListView.as_view(), name='channel-auto-reply-list'),
    path('channel-auto-reply/<str:channel>/', ChannelAutoReplyDetailView.as_view(), name='channel-auto-reply-detail'),
    path('channel-auto-reply/<str:channel>/contacts/', ChannelAutoReplyContactsView.as_view(), name='channel-auto-reply-contacts'),
```

- [ ] **Step 3: Verify server starts without errors**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py check`

Expected: `System check identified no issues.`

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views_auto_reply.py p004_ai_nexelin/MASTER/clients/urls.py
git commit -m "feat(auto-reply): add API endpoints for channel auto-reply config"
```

---

## Task 5: Integrate Guard into Message Handlers

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/tasks.py:3753-3772`
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py:696`

- [ ] **Step 1: Add guard to WhatsApp bridge handler**

In `p004_ai_nexelin/MASTER/clients/tasks.py`, in `_process_bridge_message()` function, after `conversation.add_message('user', message_text)` (line 3772), add:

```python
    conversation.add_message('user', message_text)

    # Check if Vasya should auto-respond on this channel for this contact
    from MASTER.clients.auto_reply import should_vasya_respond
    if not should_vasya_respond(client, 'whatsapp_bridge', phone):
        return  # Message saved to conversation but no auto-reply

    # Process via MCP orchestrator (Vasya — consultant agent)
```

This replaces the empty line between `conversation.add_message('user', message_text)` and `# Process via MCP orchestrator`.

- [ ] **Step 2: Add guard to Telegram handler**

In `p004_ai_nexelin/MASTER/clients/views_telegram.py`, in `handle_regular_message()`, before the MCP dual-mode block (line 696), add:

```python
                if updated_fields:
                    conversation.save(update_fields=updated_fields)

            # Check if Vasya should auto-respond on this channel for this contact
            from MASTER.clients.auto_reply import should_vasya_respond
            if not should_vasya_respond(client, 'telegram', str(chat_id)):
                return HttpResponse("OK")  # Message saved but no auto-reply

            # MCP dual-mode: route to orchestrator for flagged clients
```

This goes between the `conversation.save()` block (line 694) and the `# MCP dual-mode` comment (line 696).

- [ ] **Step 3: Verify server still starts**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py check`

Expected: `System check identified no issues.`

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/tasks.py p004_ai_nexelin/MASTER/clients/views_telegram.py
git commit -m "feat(auto-reply): integrate guard into WhatsApp bridge and Telegram handlers"
```

---

## Task 6: Frontend API Client

**Files:**
- Create: `nextlen/src/api/autoReply.js`

- [ ] **Step 1: Create API client**

```javascript
// nextlen/src/api/autoReply.js
import api from './axios';

export const autoReplyAPI = {
  /** GET /api/clients/channel-auto-reply/ */
  list() {
    return api.get('/clients/channel-auto-reply/');
  },

  /** GET /api/clients/channel-auto-reply/<channel>/ */
  get(channel) {
    return api.get(`/clients/channel-auto-reply/${channel}/`);
  },

  /** PUT /api/clients/channel-auto-reply/<channel>/ */
  save(channel, data) {
    return api.put(`/clients/channel-auto-reply/${channel}/`, data);
  },

  /** GET /api/clients/channel-auto-reply/<channel>/contacts/ */
  getContacts(channel) {
    return api.get(`/clients/channel-auto-reply/${channel}/contacts/`);
  },
};
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/api/autoReply.js
git commit -m "feat(auto-reply): add frontend API client for channel auto-reply"
```

---

## Task 7: i18n Keys

**Files:**
- Modify: `nextlen/src/locales/en/translation.json`

- [ ] **Step 1: Add channel settings translation keys**

In `nextlen/src/locales/en/translation.json`, add inside the `"settings"` object (after the existing keys):

```json
    "tabGeneral": "General",
    "tabChannels": "Channels",
    "channelsSubtitle": "Configure auto-reply for each messaging channel",
    "noChannelsConnected": "No channels connected. Connect channels in Integrations to configure auto-reply.",
    "enabled": "Enabled",
    "disabled": "Disabled",
    "scheduleTitle": "Schedule",
    "scheduleAlways": "Always (24/7)",
    "scheduleScheduled": "Scheduled hours",
    "timezone": "Timezone",
    "dayMon": "Mon",
    "dayTue": "Tue",
    "dayWed": "Wed",
    "dayThu": "Thu",
    "dayFri": "Fri",
    "daySat": "Sat",
    "daySun": "Sun",
    "start": "Start",
    "end": "End",
    "contactFilterTitle": "Contact Filter",
    "contactModeAll": "Respond to all contacts",
    "contactModeAllExcept": "Respond to all except:",
    "contactModeOnly": "Respond only to:",
    "addContact": "Add contact",
    "addContactTitle": "Add Contact",
    "enterPhone": "Enter phone number",
    "orSelectRecent": "— or select from recent chats —",
    "cancel": "Cancel",
    "add": "Add",
    "saveChanges": "Save Changes",
    "saved": "Settings saved",
    "noDaysActive": "No active days — Consultant will not respond.",
    "connected": "Connected"
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/locales/en/translation.json
git commit -m "feat(auto-reply): add i18n keys for channel settings UI"
```

---

## Task 8: ScheduleGrid Component

**Files:**
- Create: `nextlen/src/components/settings/ScheduleGrid.jsx`

- [ ] **Step 1: Create schedule grid component**

```jsx
// nextlen/src/components/settings/ScheduleGrid.jsx
import { useTranslation } from 'react-i18next';

const DAYS = [
  { key: 0, i18n: 'dayMon' },
  { key: 1, i18n: 'dayTue' },
  { key: 2, i18n: 'dayWed' },
  { key: 3, i18n: 'dayThu' },
  { key: 4, i18n: 'dayFri' },
  { key: 5, i18n: 'daySat' },
  { key: 6, i18n: 'daySun' },
];

const DEFAULT_SCHEDULE = DAYS.map(d => ({
  day: d.key,
  start: d.key < 5 ? '09:00' : '10:00',
  end: d.key < 5 ? '18:00' : '14:00',
  enabled: d.key < 5,
}));

const ScheduleGrid = ({ schedule, onChange }) => {
  const { t } = useTranslation();

  // Ensure all 7 days exist
  const fullSchedule = DAYS.map(d => {
    const existing = (schedule || []).find(s => s.day === d.key);
    return existing || DEFAULT_SCHEDULE.find(s => s.day === d.key);
  });

  const updateDay = (dayIndex, field, value) => {
    const updated = fullSchedule.map(entry =>
      entry.day === dayIndex ? { ...entry, [field]: value } : entry
    );
    onChange(updated);
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400">
            <th className="py-2 pr-4 font-medium">{t('settings.dayMon').replace(t('settings.dayMon'), '')|| 'Day'}</th>
            <th className="py-2 px-2 font-medium">{t('settings.start')}</th>
            <th className="py-2 px-2 font-medium">{t('settings.end')}</th>
            <th className="py-2 pl-2 font-medium text-center">{t('settings.enabled')}</th>
          </tr>
        </thead>
        <tbody>
          {DAYS.map(d => {
            const entry = fullSchedule.find(s => s.day === d.key);
            return (
              <tr key={d.key} className={`border-t border-gray-100 dark:border-gray-700 ${!entry.enabled ? 'opacity-50' : ''}`}>
                <td className="py-2 pr-4 font-medium text-gray-700 dark:text-gray-300">
                  {t(`settings.${d.i18n}`)}
                </td>
                <td className="py-2 px-2">
                  <input
                    type="time"
                    value={entry.start}
                    onChange={e => updateDay(d.key, 'start', e.target.value)}
                    disabled={!entry.enabled}
                    className="w-28 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm disabled:opacity-40"
                  />
                </td>
                <td className="py-2 px-2">
                  <input
                    type="time"
                    value={entry.end}
                    onChange={e => updateDay(d.key, 'end', e.target.value)}
                    disabled={!entry.enabled}
                    className="w-28 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm disabled:opacity-40"
                  />
                </td>
                <td className="py-2 pl-2 text-center">
                  <input
                    type="checkbox"
                    checked={entry.enabled}
                    onChange={e => updateDay(d.key, 'enabled', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export { DEFAULT_SCHEDULE };
export default ScheduleGrid;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/settings/ScheduleGrid.jsx
git commit -m "feat(auto-reply): add ScheduleGrid component"
```

---

## Task 9: ContactFilter Component

**Files:**
- Create: `nextlen/src/components/settings/ContactFilter.jsx`

- [ ] **Step 1: Create contact filter component with add modal**

```jsx
// nextlen/src/components/settings/ContactFilter.jsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Plus } from 'lucide-react';
import { autoReplyAPI } from '../../api/autoReply';

const ContactFilter = ({ channel, contactMode, contactList, onModeChange, onListChange }) => {
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);
  const [phoneInput, setPhoneInput] = useState('');
  const [recentContacts, setRecentContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);
  const [loadingContacts, setLoadingContacts] = useState(false);

  const removeContact = (id) => {
    onListChange(contactList.filter(c => c !== id));
  };

  const openModal = async () => {
    setShowModal(true);
    setPhoneInput('');
    setSelectedContact(null);
    setLoadingContacts(true);
    try {
      const res = await autoReplyAPI.getContacts(channel);
      setRecentContacts(res.data.contacts || []);
    } catch {
      setRecentContacts([]);
    } finally {
      setLoadingContacts(false);
    }
  };

  const addContact = () => {
    const id = selectedContact || phoneInput.replace(/[\s\-+]/g, '');
    if (!id) return;
    if (!contactList.includes(id)) {
      onListChange([...contactList, id]);
    }
    setShowModal(false);
  };

  const showList = contactMode === 'all_except' || contactMode === 'only';

  return (
    <div>
      <div className="space-y-2">
        {['all', 'all_except', 'only'].map(mode => (
          <label key={mode} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name={`contact-mode-${channel}`}
              value={mode}
              checked={contactMode === mode}
              onChange={() => onModeChange(mode)}
              className="w-4 h-4 text-primary-500 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {t(`settings.contactMode${mode === 'all' ? 'All' : mode === 'all_except' ? 'AllExcept' : 'Only'}`)}
            </span>
          </label>
        ))}
      </div>

      {showList && (
        <div className="mt-3 space-y-2">
          {contactList.map(id => (
            <div key={id} className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {id.startsWith('telegram_') ? id : `+${id}`}
              </span>
              <button onClick={() => removeContact(id)} className="text-gray-400 hover:text-red-500">
                <X size={16} />
              </button>
            </div>
          ))}
          <button
            onClick={openModal}
            className="flex items-center gap-1 text-sm text-primary-500 hover:text-primary-600"
          >
            <Plus size={16} />
            {t('settings.addContact')}
          </button>
        </div>
      )}

      {/* Add Contact Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {t('settings.addContactTitle')}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="mb-4">
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                {t('settings.enterPhone')}
              </label>
              <input
                type="text"
                value={phoneInput}
                onChange={e => { setPhoneInput(e.target.value); setSelectedContact(null); }}
                placeholder="+48..."
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            {recentContacts.length > 0 && (
              <div className="mb-4">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  {t('settings.orSelectRecent')}
                </p>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {recentContacts
                    .filter(c => !contactList.includes(c.id))
                    .map(c => (
                      <label key={c.id} className="flex items-start gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                        <input
                          type="radio"
                          name="recent-contact"
                          checked={selectedContact === c.id}
                          onChange={() => { setSelectedContact(c.id); setPhoneInput(''); }}
                          className="mt-1 w-4 h-4 text-primary-500"
                        />
                        <div>
                          <div className="text-sm text-gray-700 dark:text-gray-300">{c.label}</div>
                          {c.last_message && (
                            <div className="text-xs text-gray-400 truncate max-w-[250px]">
                              {c.last_message}
                            </div>
                          )}
                        </div>
                      </label>
                    ))}
                </div>
              </div>
            )}

            {loadingContacts && (
              <p className="text-sm text-gray-400 mb-4">Loading...</p>
            )}

            <div className="flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="btn-secondary text-sm">
                {t('settings.cancel')}
              </button>
              <button
                onClick={addContact}
                disabled={!phoneInput && !selectedContact}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {t('settings.add')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContactFilter;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/settings/ContactFilter.jsx
git commit -m "feat(auto-reply): add ContactFilter component with add-contact modal"
```

---

## Task 10: ChannelCard Component

**Files:**
- Create: `nextlen/src/components/settings/ChannelCard.jsx`

- [ ] **Step 1: Create per-channel config card**

```jsx
// nextlen/src/components/settings/ChannelCard.jsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import ScheduleGrid, { DEFAULT_SCHEDULE } from './ScheduleGrid';
import ContactFilter from './ContactFilter';
import { autoReplyAPI } from '../../api/autoReply';

const TIMEZONE_REGIONS = ['Africa', 'America', 'Asia', 'Atlantic', 'Australia', 'Europe', 'Indian', 'Pacific'];

const getTimezones = () => {
  try {
    return Intl.supportedValuesOf('timeZone');
  } catch {
    return ['UTC', 'Europe/Warsaw', 'Europe/Berlin', 'America/New_York'];
  }
};

const ChannelCard = ({ channel, channelLabel, connectionInfo, initialConfig }) => {
  const { t } = useTranslation();

  const [enabled, setEnabled] = useState(initialConfig?.enabled ?? true);
  const [scheduleMode, setScheduleMode] = useState(initialConfig?.schedule_mode || 'always');
  const [timezone, setTimezone] = useState(
    initialConfig?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  );
  const [schedule, setSchedule] = useState(initialConfig?.schedule || DEFAULT_SCHEDULE);
  const [contactMode, setContactMode] = useState(initialConfig?.contact_mode || 'all');
  const [contactList, setContactList] = useState(initialConfig?.contact_list || []);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const allTimezones = getTimezones();
  const noDaysActive = scheduleMode === 'scheduled' && schedule.every(d => !d.enabled);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await autoReplyAPI.save(channel, {
        enabled,
        schedule_mode: scheduleMode,
        timezone,
        schedule,
        contact_mode: contactMode,
        contact_list: contactList,
      });
      setMessage({ type: 'success', text: t('settings.saved') });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      const detail = err.response?.data?.detail || err.response?.data?.schedule?.[0] || 'Error saving';
      setMessage({ type: 'error', text: String(detail) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{channelLabel}</h3>
          {connectionInfo && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t('settings.connected')}: {connectionInfo}
            </p>
          )}
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => setEnabled(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500" />
        </label>
      </div>

      {enabled && (
        <div className="px-6 py-4 space-y-6">
          {/* Schedule Section */}
          <div>
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              {t('settings.scheduleTitle')}
            </h4>
            <div className="space-y-2 mb-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name={`schedule-${channel}`}
                  checked={scheduleMode === 'always'}
                  onChange={() => setScheduleMode('always')}
                  className="w-4 h-4 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {t('settings.scheduleAlways')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name={`schedule-${channel}`}
                  checked={scheduleMode === 'scheduled'}
                  onChange={() => setScheduleMode('scheduled')}
                  className="w-4 h-4 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {t('settings.scheduleScheduled')}
                </span>
              </label>
            </div>

            {scheduleMode === 'scheduled' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                    {t('settings.timezone')}
                  </label>
                  <select
                    value={timezone}
                    onChange={e => setTimezone(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  >
                    {TIMEZONE_REGIONS.map(region => {
                      const tzs = allTimezones.filter(tz => tz.startsWith(region + '/'));
                      if (tzs.length === 0) return null;
                      return (
                        <optgroup key={region} label={region}>
                          {tzs.map(tz => (
                            <option key={tz} value={tz}>{tz.replace('_', ' ')}</option>
                          ))}
                        </optgroup>
                      );
                    })}
                    <option value="UTC">UTC</option>
                  </select>
                </div>
                <ScheduleGrid schedule={schedule} onChange={setSchedule} />
                {noDaysActive && (
                  <p className="text-sm text-amber-600 dark:text-amber-400">
                    {t('settings.noDaysActive')}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Contact Filter Section */}
          <div>
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              {t('settings.contactFilterTitle')}
            </h4>
            <ContactFilter
              channel={channel}
              contactMode={contactMode}
              contactList={contactList}
              onModeChange={setContactMode}
              onListChange={setContactList}
            />
          </div>

          {/* Message */}
          {message && (
            <div className={`text-sm px-3 py-2 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
            }`}>
              {message.text}
            </div>
          )}

          {/* Save Button */}
          <div className="flex justify-end">
            <button onClick={handleSave} disabled={saving} className="btn-primary text-sm flex items-center gap-2">
              {saving && <Loader2 size={16} className="animate-spin" />}
              {t('settings.saveChanges')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChannelCard;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/settings/ChannelCard.jsx
git commit -m "feat(auto-reply): add ChannelCard component with schedule, contacts, and save"
```

---

## Task 11: ChannelsTab Component

**Files:**
- Create: `nextlen/src/components/settings/ChannelsTab.jsx`

- [ ] **Step 1: Create channels tab container**

```jsx
// nextlen/src/components/settings/ChannelsTab.jsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import api from '../../api/axios';
import { autoReplyAPI } from '../../api/autoReply';
import ChannelCard from './ChannelCard';

const CHANNEL_DEFS = [
  {
    key: 'whatsapp_bridge',
    label: 'WhatsApp',
    getConnectionInfo: (data) => data.bridgePhone ? `+${data.bridgePhone}` : null,
    isConnected: (data) => data.bridgeStatus === 'connected',
  },
  {
    key: 'telegram',
    label: 'Telegram',
    getConnectionInfo: () => null,
    isConnected: (data) => data.telegramEnabled,
  },
];

const ChannelsTab = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [channelData, setChannelData] = useState({});
  const [configs, setConfigs] = useState({});

  useEffect(() => {
    const loadData = async () => {
      try {
        const [bridgeRes, meRes, autoReplyRes] = await Promise.all([
          api.get('/clients/whatsapp/bridge/config/').catch(() => ({ data: {} })),
          api.get('/clients/me/').catch(() => ({ data: {} })),
          autoReplyAPI.list().catch(() => ({ data: { results: [] } })),
        ]);

        setChannelData({
          bridgeStatus: bridgeRes.data.whatsapp_bridge_status,
          bridgePhone: bridgeRes.data.whatsapp_bridge_phone,
          telegramEnabled: meRes.data.telegram_enabled,
        });

        const configMap = {};
        for (const cfg of (autoReplyRes.data.results || [])) {
          configMap[cfg.channel] = cfg;
        }
        setConfigs(configMap);
      } catch (err) {
        console.error('Failed to load channel data:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-gray-400" size={32} />
      </div>
    );
  }

  const connectedChannels = CHANNEL_DEFS.filter(ch => ch.isConnected(channelData));

  if (connectedChannels.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        {t('settings.noChannelsConnected')}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {t('settings.channelsSubtitle')}
      </p>
      {connectedChannels.map(ch => (
        <ChannelCard
          key={ch.key}
          channel={ch.key}
          channelLabel={ch.label}
          connectionInfo={ch.getConnectionInfo(channelData)}
          initialConfig={configs[ch.key] || null}
        />
      ))}
    </div>
  );
};

export default ChannelsTab;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/settings/ChannelsTab.jsx
git commit -m "feat(auto-reply): add ChannelsTab container component"
```

---

## Task 12: Refactor SettingsPage with Tabs

**Files:**
- Modify: `nextlen/src/pages/SettingsPage.jsx`

- [ ] **Step 1: Add tab navigation and Channels tab to SettingsPage**

At the top of SettingsPage.jsx, add the import (after existing imports, line 6):

```javascript
import ChannelsTab from '../components/settings/ChannelsTab';
```

Add tab state after the existing state declarations (after line 24):

```javascript
  const [activeTab, setActiveTab] = useState('general');
```

In the JSX, find the page title section. Wrap the existing content in a tab system. After the `<h1>` title and subtitle (the first `<div>` with `space-y-6`), add tab buttons before the content:

Replace the structure so the page renders like this:

```jsx
{/* Tab Navigation — add after the title/subtitle header, before the first content section */}
<div className="flex gap-2 mb-6">
  {['general', 'channels'].map(tab => (
    <button
      key={tab}
      onClick={() => setActiveTab(tab)}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        activeTab === tab
          ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-700'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
      }`}
    >
      {t(`settings.tab${tab === 'general' ? 'General' : 'Channels'}`)}
    </button>
  ))}
</div>
```

Wrap the existing three sections (Logo, Greeting, Reports) in a conditional:

```jsx
{activeTab === 'general' && (
  <>
    {/* ...existing Logo Upload, Greeting Message, Report Settings sections... */}
  </>
)}

{activeTab === 'channels' && (
  <ChannelsTab />
)}
```

- [ ] **Step 2: Verify the page renders correctly**

Run: `cd /home/dchuprina/nexelin_web/nextlen && npm run build`

Expected: Build succeeds without errors.

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/pages/SettingsPage.jsx
git commit -m "feat(auto-reply): add tab navigation to SettingsPage with Channels tab"
```

---

## Summary

| Task | Description | Estimated |
|------|-------------|-----------|
| 1 | ChannelAutoReply model + migration + admin | Backend |
| 2 | Guard function + 16 tests | Backend |
| 3 | Serializer with validation | Backend |
| 4 | API views + URL registration | Backend |
| 5 | Integrate guard into message handlers | Backend |
| 6 | Frontend API client | Frontend |
| 7 | i18n keys | Frontend |
| 8 | ScheduleGrid component | Frontend |
| 9 | ContactFilter component + modal | Frontend |
| 10 | ChannelCard component | Frontend |
| 11 | ChannelsTab container | Frontend |
| 12 | SettingsPage tab refactor | Frontend |

Tasks 1-5 are backend (can be done first). Tasks 6-12 are frontend (depend on API from Task 4). Tasks 8-9 are independent and can be parallelized. Task 12 depends on Task 11 which depends on Tasks 8-10.
