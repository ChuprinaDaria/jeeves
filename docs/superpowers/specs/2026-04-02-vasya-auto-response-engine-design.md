# Vasya Auto-Response Engine — Design Spec

**Date:** 2026-04-02
**Scope:** Backend model + API + Settings UI for per-channel schedule and contact filtering
**Sub-project:** 1 of 3 (followed by Universal Bridge Framework, then Oleg as Configurator)

---

## 1. Overview

Each client can configure per-channel auto-reply behavior for Vasya (consultant AI):
- **Schedule:** When Vasya responds — always (24/7) or during specific hours per day of week
- **Contact filtering:** Who Vasya responds to — all, all except specific contacts, or only specific contacts
- **Per-channel:** Each messaging channel (WhatsApp, Telegram, future Meta/LinkedIn/iMessage) has independent settings

**Web widget is excluded** — always responds 24/7 to all visitors, no configuration needed.

---

## 2. Data Model

### New model: `ChannelAutoReply`

```python
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

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='channel_auto_replies')
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES)

    # Master switch
    enabled = models.BooleanField(default=True)

    # Schedule
    schedule_mode = models.CharField(max_length=10, choices=SCHEDULE_MODE_CHOICES, default='always')
    timezone = models.CharField(max_length=50, default='UTC')
    schedule = models.JSONField(
        default=list,
        blank=True,
        help_text='Weekly schedule: [{"day": 0, "start": "09:00", "end": "18:00", "enabled": true}, ...]'
    )

    # Contact filtering
    contact_mode = models.CharField(max_length=15, choices=CONTACT_MODE_CHOICES, default='all')
    contact_list = models.JSONField(
        default=list,
        blank=True,
        help_text='List of contact identifiers to include/exclude: ["48571079588", "@username", ...]'
    )

    class Meta:
        unique_together = [['client', 'channel']]

    def __str__(self):
        return f"{self.client} — {self.get_channel_display()}"
```

**Schedule JSON format:**
```json
[
  {"day": 0, "start": "09:00", "end": "18:00", "enabled": true},
  {"day": 1, "start": "09:00", "end": "18:00", "enabled": true},
  {"day": 2, "start": "09:00", "end": "18:00", "enabled": true},
  {"day": 3, "start": "09:00", "end": "18:00", "enabled": true},
  {"day": 4, "start": "09:00", "end": "18:00", "enabled": true},
  {"day": 5, "start": "10:00", "end": "14:00", "enabled": false},
  {"day": 6, "start": "10:00", "end": "14:00", "enabled": false}
]
```

Days: 0=Monday, 6=Sunday. When `enabled=false` for a day, Vasya does not respond that day. When `schedule_mode='always'`, the schedule array is ignored.

**Contact list format:**
```json
["48571079588", "48123456789"]
```

For WhatsApp: phone numbers without `+` prefix.
For Telegram: chat_id as string (e.g. `"123456789"`).
For future bridges: platform-specific identifiers.

---

## 3. Default Behavior

When a channel has **no** `ChannelAutoReply` record:
- Vasya **responds to all contacts, 24/7** (same as `enabled=True, schedule_mode='always', contact_mode='all'`)

When a record exists with `enabled=False`:
- Vasya **does not respond** on this channel at all

When `schedule_mode='scheduled'` and current time is **outside** all enabled day windows:
- Vasya **does not respond**

When `contact_mode='all_except'` and contact is in `contact_list`:
- Vasya **does not respond** to this contact

When `contact_mode='only'` and contact is **not** in `contact_list`:
- Vasya **does not respond** to this contact

---

## 4. Backend: Guard Function

A single function used by all message handlers before calling the orchestrator:

```python
# Location: MASTER/clients/auto_reply.py

from datetime import datetime
from zoneinfo import ZoneInfo

from .models import ChannelAutoReply


def should_vasya_respond(client, channel: str, contact_id: str) -> bool:
    """
    Check if Vasya should auto-respond to this message.

    Args:
        client: Client instance
        channel: Channel identifier ('whatsapp_bridge', 'telegram', etc.)
        contact_id: Contact identifier (phone number, chat_id, etc.)

    Returns:
        True if Vasya should respond, False to skip.
    """
    # Web widget always responds
    if channel in ('web', 'sandbox'):
        return True

    try:
        config = ChannelAutoReply.objects.get(client=client, channel=channel)
    except ChannelAutoReply.DoesNotExist:
        return True  # No config = respond to all, always

    if not config.enabled:
        return False

    # Schedule check
    if config.schedule_mode == 'scheduled' and config.schedule:
        try:
            tz = ZoneInfo(config.timezone)
        except (KeyError, ValueError):
            tz = ZoneInfo('UTC')

        now = datetime.now(tz)
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        current_time = now.strftime('%H:%M')

        day_entry = next((d for d in config.schedule if d.get('day') == weekday), None)
        if not day_entry or not day_entry.get('enabled', False):
            return False

        start = day_entry.get('start', '00:00')
        end = day_entry.get('end', '23:59')
        if not (start <= current_time <= end):
            return False

    # Contact filter check
    normalized = contact_id.lstrip('+')
    contact_list_normalized = [c.lstrip('+') for c in (config.contact_list or [])]

    if config.contact_mode == 'all_except':
        if normalized in contact_list_normalized:
            return False
    elif config.contact_mode == 'only':
        if normalized not in contact_list_normalized:
            return False

    return True
```

---

## 5. Integration Points

### WhatsApp bridge (Celery polling task)

**File:** `MASTER/clients/tasks.py` — `_process_bridge_message()`

Before calling the orchestrator:
```python
from MASTER.clients.auto_reply import should_vasya_respond

def _process_bridge_message(client, phone, message_text, room_id):
    if not should_vasya_respond(client, 'whatsapp_bridge', phone):
        return  # Silent skip — message still visible in Activity but no auto-reply

    # ... existing orchestrator logic ...
```

Message is still saved to `ClientWhatsAppConversation` (for Activity page visibility), but Vasya does not respond.

### Telegram webhook

**File:** `MASTER/clients/views_telegram.py` — webhook handler

Before calling the orchestrator:
```python
from MASTER.clients.auto_reply import should_vasya_respond

# In webhook processing:
chat_id = str(update['message']['chat']['id'])
if not should_vasya_respond(client, 'telegram', chat_id):
    return  # Save message but skip auto-reply
```

### Future bridges (Meta, LinkedIn, iMessage)

Same pattern — call `should_vasya_respond(client, channel, contact_id)` before orchestrator.

---

## 6. API Endpoints

### `GET /api/clients/channel-auto-reply/`

Returns all channel configs for current client:
```json
{
  "results": [
    {
      "channel": "whatsapp_bridge",
      "channel_display": "WhatsApp",
      "enabled": true,
      "schedule_mode": "scheduled",
      "timezone": "Europe/Warsaw",
      "schedule": [
        {"day": 0, "start": "09:00", "end": "18:00", "enabled": true},
        ...
      ],
      "contact_mode": "all_except",
      "contact_list": ["48571079588"]
    }
  ]
}
```

### `PUT /api/clients/channel-auto-reply/<channel>/`

Create or update config for a specific channel:
```json
{
  "enabled": true,
  "schedule_mode": "scheduled",
  "timezone": "Europe/Warsaw",
  "schedule": [...],
  "contact_mode": "all_except",
  "contact_list": ["48571079588"]
}
```

Uses `update_or_create` on `(client, channel)`.

### `GET /api/clients/channel-auto-reply/<channel>/contacts/`

Returns existing conversations for this channel (for contact picker UI):
```json
{
  "contacts": [
    {"id": "48571079588", "label": "+48 571 079 588", "last_message": "Hello", "last_activity": "2026-04-01T12:00:00Z"},
    {"id": "48123456789", "label": "+48 123 456 789", "last_message": "Hi there", "last_activity": "2026-03-30T15:30:00Z"}
  ]
}
```

For WhatsApp: queries `ClientWhatsAppConversation` where `context_metadata.platform = 'whatsapp_bridge'`.
For Telegram: queries `ClientWhatsAppConversation` where `context_metadata.platform = 'telegram'` or `telegram_chat_id IS NOT NULL`.

---

## 7. Frontend — Settings Page Redesign

### Tab Structure

```
Settings Page
├── Tab: General
│   ├── Company Logo (existing)
│   ├── Greeting Message (existing)
│   └── Report Settings (existing)
│
└── Tab: Channels
    ├── Channel: WhatsApp (only if connected)
    │   ├── Enable/Disable toggle
    │   ├── Schedule section
    │   └── Contact filter section
    │
    ├── Channel: Telegram (only if connected)
    │   ├── Enable/Disable toggle
    │   ├── Schedule section
    │   └── Contact filter section
    │
    └── (Future: Instagram, LinkedIn, iMessage — same pattern)
```

### Channel Card Layout

Each connected channel renders as a card/section:

```
┌─────────────────────────────────────────────────────┐
│ [WhatsApp icon] WhatsApp              [toggle: ON]  │
│ Connected: +48 727 842 737                          │
├─────────────────────────────────────────────────────┤
│ Schedule                                            │
│ ○ Always (24/7)                                     │
│ ● Scheduled hours                                   │
│                                                     │
│ Timezone: [Europe/Warsaw          ▼]                │
│                                                     │
│ ┌─────┬───────────┬───────────┬─────────┐           │
│ │ Day │   Start   │    End    │ Enabled │           │
│ ├─────┼───────────┼───────────┼─────────┤           │
│ │ Mon │  09:00    │  18:00    │  [✓]    │           │
│ │ Tue │  09:00    │  18:00    │  [✓]    │           │
│ │ Wed │  09:00    │  18:00    │  [✓]    │           │
│ │ Thu │  09:00    │  18:00    │  [✓]    │           │
│ │ Fri │  09:00    │  18:00    │  [✓]    │           │
│ │ Sat │  10:00    │  14:00    │  [ ]    │           │
│ │ Sun │  10:00    │  14:00    │  [ ]    │           │
│ └─────┴───────────┴───────────┴─────────┘           │
├─────────────────────────────────────────────────────┤
│ Contact Filter                                      │
│ ○ Respond to all contacts                           │
│ ● Respond to all except:                            │
│ ○ Respond only to:                                  │
│                                                     │
│ ┌───────────────────────────────────────────┐       │
│ │ +48 571 079 588                      [✕]  │       │
│ │ +48 123 456 789                      [✕]  │       │
│ └───────────────────────────────────────────┘       │
│ [+ Add contact]  (manual input or select from list) │
│                                                     │
│                              [Save Changes]         │
└─────────────────────────────────────────────────────┘
```

### Add Contact Modal

When user clicks "+ Add contact":

```
┌──────────────────────────────────────┐
│ Add Contact                     [✕]  │
│                                      │
│ Enter phone number:                  │
│ [+48...                           ]  │
│                                      │
│ — or select from recent chats —      │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │ ○ +48 571 079 588               │ │
│ │   Last: "Hello" · 2h ago        │ │
│ │ ○ +48 999 888 777               │ │
│ │   Last: "Thanks" · 1d ago       │ │
│ └──────────────────────────────────┘ │
│                                      │
│              [Cancel]  [Add]         │
└──────────────────────────────────────┘
```

Recent chats fetched from `/api/clients/channel-auto-reply/<channel>/contacts/`.

### UI Details

- **Language:** English only (all labels, placeholders, tooltips in English). Use i18n keys but English-only for now.
- **Timezone dropdown:** Grouped by region (Europe, America, Asia, etc.). Show UTC offset. Use `Intl.supportedValuesOf('timeZone')` for list.
- **Time inputs:** 24h format, HH:MM. Use `<input type="time">`.
- **Day names:** English abbreviations (Mon, Tue, Wed, Thu, Fri, Sat, Sun).
- **Disconnected channels:** Not shown in Channels tab. Show hint: "Connect channels in Integrations to configure auto-reply."
- **Save behavior:** Per-channel save button. Shows toast on success.
- **Loading state:** Skeleton loader while fetching config.

---

## 8. Timezone Handling

- Client selects timezone once per channel (stored in `ChannelAutoReply.timezone`).
- Default timezone: detected from browser via `Intl.DateTimeFormat().resolvedOptions().timeZone` and sent to backend on first save.
- Backend compares schedule against `datetime.now(ZoneInfo(config.timezone))` — all comparison happens server-side.
- No DST surprises — `ZoneInfo` handles DST transitions automatically.

---

## 9. Edge Cases

**Channel disconnected after config saved:**
- Config remains in DB. If channel reconnects, config still applies.
- UI hides channel card when disconnected but does not delete config.

**Empty schedule (all days disabled):**
- Equivalent to `enabled=False` — Vasya never responds.
- UI shows warning: "No active days — Consultant will not respond."

**Contact in both exclude and include list (impossible):**
- UI enforces single mode: `all`, `all_except`, or `only`. Contact list applies to current mode only.

**Multiple phone formats:**
- Backend normalizes: strips `+`, spaces, dashes before comparison.
- Store in contact_list as digits only (e.g., `"48571079588"`).

**Overnight schedule (e.g., 22:00 - 06:00):**
- Not supported in v1. Each day has a single start-end window within the same day.
- If needed later: split into two entries or add `crosses_midnight` flag.

---

## 10. Files to Create/Modify

### Backend
- **Create:** `MASTER/clients/auto_reply.py` — `should_vasya_respond()` function
- **Create:** `MASTER/clients/models.py` — `ChannelAutoReply` model
- **Create:** migration for `ChannelAutoReply`
- **Create:** `MASTER/clients/serializers.py` — `ChannelAutoReplySerializer`
- **Create:** `MASTER/clients/views_auto_reply.py` — API views
- **Modify:** `MASTER/clients/urls.py` — register new endpoints
- **Modify:** `MASTER/clients/tasks.py` — add guard to `_process_bridge_message()`
- **Modify:** `MASTER/clients/views_telegram.py` — add guard to webhook handler
- **Modify:** `MASTER/clients/admin.py` — register `ChannelAutoReply` in admin

### Frontend
- **Modify:** `nextlen/src/pages/SettingsPage.jsx` — add tab system, refactor existing into "General" tab
- **Create:** `nextlen/src/components/settings/ChannelsTab.jsx` — channels tab container
- **Create:** `nextlen/src/components/settings/ChannelCard.jsx` — per-channel config card
- **Create:** `nextlen/src/components/settings/ScheduleGrid.jsx` — weekly schedule grid
- **Create:** `nextlen/src/components/settings/ContactFilter.jsx` — contact mode + list
- **Create:** `nextlen/src/components/settings/AddContactModal.jsx` — modal for adding contacts
- **Create:** `nextlen/src/api/autoReply.js` — API client for channel auto-reply endpoints
- **Modify:** `nextlen/src/locales/en/translation.json` — add English strings

---

## 11. What This Spec Does NOT Cover

- Web widget auto-reply settings (always on, 24/7)
- Multi-bridge framework (Meta, LinkedIn, iMessage) — separate spec (Sub-project 2)
- Oleg as configurator (QR from chat, tool setup) — separate spec (Sub-project 3)
- Overnight schedules (22:00-06:00 crossing midnight)
- Per-contact custom schedule (same schedule for all contacts on a channel)
- Auto-reply message customization (Vasya uses existing consultant prompt)
