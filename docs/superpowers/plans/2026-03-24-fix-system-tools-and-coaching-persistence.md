# Fix System Tools & Coaching Persistence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make XLSX and Coaching tools visible to all clients, fix coaching suggestion persistence across messages.

**Architecture:** Two fixes: (1) migration to mark xlsx-processor/coaching as system tools and auto-connect for all existing clients, (2) move coaching pending_suggestions storage from per-session AgentSession.metadata to persistent AgentConfig metadata so suggestions survive across messages (each message creates a new AgentSession).

**Tech Stack:** Django migrations, Python

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `MASTER/tools/migrations/0015_system_xlsx_coaching.py` | Create | Migration: mark xlsx-processor + coaching as is_system, auto-connect all clients |
| `MASTER/tools/seed_data.py` | Modify | Add `is_system: True` to xlsx-processor and coaching entries |
| `mcp_servers/coaching/server.py` | Modify | Store/read pending_suggestions in AgentConfig metadata instead of AgentSession metadata |

---

### Task 1: Migration — make xlsx-processor and coaching system tools

**Files:**
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0015_system_xlsx_coaching.py`
- Modify: `p004_ai_nexelin/MASTER/tools/seed_data.py`

- [ ] **Step 1: Create migration file**

Pattern: copy structure from `0014_seed_system_tools.py`. Update `xlsx-processor` and `coaching` ToolCards to `is_system=True`, then create ToolConnections for all existing active clients.

```python
"""Mark xlsx-processor and coaching as system tools + auto-connect all clients."""
from django.db import migrations
from django.utils import timezone


def forward(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    Client = apps.get_model('clients', 'Client')

    now = timezone.now()

    # Mark as system tools
    cards_to_update = {
        'xlsx-processor': ['assistant', 'manager'],
        'coaching': ['assistant'],
    }

    for slug, scopes in cards_to_update.items():
        try:
            card = ToolCard.objects.get(slug=slug)
        except ToolCard.DoesNotExist:
            continue

        card.is_system = True
        card.save(update_fields=['is_system'])

        # Auto-connect for ALL existing active clients
        for client in Client.objects.filter(is_active=True):
            for scope in scopes:
                ToolConnection.objects.get_or_create(
                    client=client,
                    tool_card=card,
                    target=scope,
                    defaults={
                        'status': 'connected',
                        'enabled': True,
                        'connected_at': now,
                    },
                )


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    for slug in ('xlsx-processor', 'coaching'):
        try:
            card = ToolCard.objects.get(slug=slug)
            card.is_system = False
            card.save(update_fields=['is_system'])
        except ToolCard.DoesNotExist:
            pass


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0014_seed_system_tools'),
        ('clients', '0051_lead_agent_session'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
```

- [ ] **Step 2: Update seed_data.py**

Add `'is_system': True` to both `xlsx-processor` and `coaching` entries so new deployments get it right from seed data.

In `seed_data.py`, `xlsx-processor` entry (after line 189):
```python
'is_system': True,
```

Note: `coaching` is NOT in seed_data.py (only in migration 0012), so no change needed there.

- [ ] **Step 3: Verify migration**

Run: `cd p004_ai_nexelin && python manage.py showmigrations tools`
Expected: `0015_system_xlsx_coaching` appears as unapplied.

Run: `cd p004_ai_nexelin && python manage.py migrate tools`
Expected: Migration applies without errors.

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/migrations/0015_system_xlsx_coaching.py p004_ai_nexelin/MASTER/tools/seed_data.py
git commit -m "fix(tools): make xlsx-processor and coaching system tools with auto-connect"
```

---

### Task 2: Fix coaching suggestion persistence

**Files:**
- Modify: `p004_ai_nexelin/mcp_servers/coaching/server.py` (lines 136-261)

**Problem:** `suggest_knowledge_update` stores suggestions in `AgentSession.metadata`, but `dispatch.py:43` and `mcp_hub/views.py:70,117` create a NEW AgentSession per message. When the user confirms, the new session doesn't have the suggestion.

**Fix:** Store pending_suggestions in `AgentConfig.metadata` (persists across sessions, one per client) instead of `AgentSession.metadata`.

Note: `AgentConfig` doesn't have a `metadata` field yet. We need to either add one or use an existing persistent field. Since AgentConfig is per-client and persists, we can add a JSONField. BUT to keep changes minimal, we'll store in the Client model's existing fields or just add a simple JSONField to AgentConfig.

Actually, simplest approach: store in a dedicated cache — but that adds complexity. The cleanest fix is to keep using the same session. Let me reconsider...

**Revised approach:** The simplest fix with minimal blast radius is to look up the suggestion across ALL sessions for this client's agent_config, not just the current session. This requires zero schema changes.

- [ ] **Step 1: Fix `suggest_knowledge_update` — no changes needed**

The suggest function stores correctly in session metadata. The issue is only in retrieval.

- [ ] **Step 2: Fix `apply_coaching_suggestion` to search across all sessions**

In `mcp_servers/coaching/server.py`, replace the `_apply()` inner function (lines 201-258):

```python
def _apply():
    from MASTER.agents.models import AgentSession, AgentConfig
    from MASTER.clients.models import Client, ClientDocument
    from MASTER.processing.embedding_service import EmbeddingService

    # Search across ALL recent sessions for this client (not just current)
    try:
        current_session = AgentSession.objects.get(pk=session_id)
        config = current_session.agent_config
    except AgentSession.DoesNotExist:
        return {"error": "Session not found"}

    # Look through recent sessions for the pending suggestion
    suggestion = None
    source_session = None
    recent_sessions = AgentSession.objects.filter(
        agent_config=config,
    ).order_by('-started_at')[:50]

    for sess in recent_sessions:
        meta = sess.metadata or {}
        pending = meta.get('pending_suggestions', {})
        if suggestion_id in pending:
            suggestion = pending[suggestion_id]
            source_session = sess
            break

    if not suggestion:
        return {"error": f"Suggestion {suggestion_id} not found or already applied"}

    update_type = suggestion['update_type']
    content = suggestion['suggested_content']
    topic = suggestion['gap_topic']
    results = []

    client, embedding_model = _resolve_embedding_model(client_id)

    if update_type in ('knowledge', 'both'):
        try:
            doc = ClientDocument.objects.create(
                client=client,
                title=f"Coaching: {topic}",
                content=content,
                source='coaching',
            )
            if embedding_model:
                EmbeddingService.create_embedding(
                    content, embedding_model, client=client, document=doc,
                )
            results.append(f"Knowledge base updated: document '{doc.title}' created")
        except Exception as e:
            results.append(f"Knowledge base update failed: {e}")

    if update_type in ('instructions', 'both'):
        try:
            agent_config = AgentConfig.objects.get(client=client)
            current = agent_config.consultant_prompt or ''
            agent_config.consultant_prompt = current.rstrip() + f"\n\n{content}"
            agent_config.save(update_fields=['consultant_prompt'])
            results.append("Consultant instructions updated")
        except AgentConfig.DoesNotExist:
            results.append("AgentConfig not found — cannot update instructions")
        except Exception as e:
            results.append(f"Instructions update failed: {e}")

    # Clean up suggestion from source session
    meta = source_session.metadata or {}
    pending = meta.get('pending_suggestions', {})
    del pending[suggestion_id]
    meta['pending_suggestions'] = pending
    source_session.metadata = meta
    source_session.save(update_fields=['metadata'])

    return {"status": "applied", "suggestion_id": suggestion_id, "results": results}
```

- [ ] **Step 3: Verify coaching server starts**

Run: `cd p004_ai_nexelin && python -c "import mcp_servers.coaching.server; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/coaching/server.py
git commit -m "fix(coaching): search suggestions across all sessions, not just current"
```

---

## Verification

After both tasks, verify:

1. **XLSX tool visible:** In sandbox chat, ask Oleg "create an Excel report" — he should call `create_spreadsheet` instead of saying "I don't have this tool"
2. **Coaching works:** In sandbox, ask Oleg to review Vasya's conversations and suggest an update. Confirm the suggestion. It should apply without "not found" error.
3. **Email with attachment:** After XLSX is generated, ask Oleg to email the file — should use `send_email_with_attachment` with the real file path.
