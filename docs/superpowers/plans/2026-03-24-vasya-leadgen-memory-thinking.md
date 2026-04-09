# Vasya Lead Gen + Agent Memory + Sequential Thinking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vasya collect leads naturally (value-first), add persistent memory and structured thinking to both agents as system tools visible in UI.

**Architecture:** Rewrite DEFAULT_CONSULTANT_PROMPT for low-friction lead gen. Fix prompt layering (default always base, custom on top). Add `is_system` flag to ToolCard for non-disconnectable tools. New `mcp-memory` server using existing Qdrant+Cohere. Register `sequential-thinking` npm MCP server.

**Tech Stack:** Django 5.x, FastMCP (Python), Qdrant, Cohere embeddings, React, `@modelcontextprotocol/server-sequential-thinking` (npm)

**Spec:** `docs/superpowers/specs/2026-03-23-vasya-leadgen-memory-thinking-design.md`

---

### Task 1: ToolCard `is_system` Field + Migration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/models.py:57` (add field after `is_featured`)
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0013_toolcard_is_system.py`

- [ ] **Step 1: Add `is_system` field to ToolCard model**

In `p004_ai_nexelin/MASTER/tools/models.py`, after line 58 (`is_featured`):

```python
is_system = models.BooleanField(default=False, help_text='System tool — always connected, cannot be disconnected')
```

- [ ] **Step 2: Generate migration**

Run: `cd p004_ai_nexelin && python manage.py makemigrations tools --name toolcard_is_system`
Expected: Creates `0013_toolcard_is_system.py`

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/models.py p004_ai_nexelin/MASTER/tools/migrations/0013_toolcard_is_system.py
git commit -m "feat(tools): add is_system field to ToolCard for non-disconnectable system tools"
```

---

### Task 2: Seed System Tools + Auto-Connect Migration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/seed_data.py` (add 2 entries)
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0014_seed_system_tools.py`

- [ ] **Step 1: Add memory and sequential-thinking to seed_data.py**

Append to `INITIAL_TOOLS` list in `p004_ai_nexelin/MASTER/tools/seed_data.py`:

```python
    {
        'slug': 'memory',
        'name': 'Agent Memory',
        'tagline': 'Persistent memory across conversations',
        'tagline_i18n': {
            'en': 'Persistent memory across conversations',
            'de': 'Persistenter Speicher über Gespräche hinweg',
        },
        'icon': 'brain',
        'category': 'ai',
        'color': '#8b5cf6',
        'transport_type': 'builtin',
        'is_builtin': True,
        'is_system': True,
        'builtin_handler': 'mcp_hub.builtin.memory',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
    {
        'slug': 'sequential-thinking',
        'name': 'Deep Thinking',
        'tagline': 'Structured reasoning for complex problems',
        'tagline_i18n': {
            'en': 'Structured reasoning for complex problems',
            'de': 'Strukturiertes Denken für komplexe Probleme',
        },
        'icon': 'brain-circuit',
        'category': 'ai',
        'color': '#6366f1',
        'transport_type': 'builtin',
        'is_builtin': True,
        'is_system': True,
        'builtin_handler': 'mcp_hub.builtin.sequential_thinking',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
```

- [ ] **Step 2: Create seed + auto-connect migration**

Create `p004_ai_nexelin/MASTER/tools/migrations/0014_seed_system_tools.py`:

```python
"""Seed Agent Memory and Deep Thinking system tools + auto-connect for all clients."""
from django.db import migrations
from django.utils import timezone


SYSTEM_TOOLS = [
    {
        'slug': 'memory',
        'name': 'Agent Memory',
        'tagline': 'Persistent memory across conversations',
        'tagline_i18n': {'en': 'Persistent memory across conversations', 'de': 'Persistenter Speicher über Gespräche hinweg'},
        'description': 'Persistent conversational memory for AI agents across sessions.',
        'icon': 'brain',
        'category': 'ai',
        'color': '#8b5cf6',
        'transport_type': 'builtin',
        'is_builtin': True,
        'is_system': True,
        'builtin_handler': 'mcp_hub.builtin.memory',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
    {
        'slug': 'sequential-thinking',
        'name': 'Deep Thinking',
        'tagline': 'Structured reasoning for complex problems',
        'tagline_i18n': {'en': 'Structured reasoning for complex problems', 'de': 'Strukturiertes Denken für komplexe Probleme'},
        'description': 'Structured step-by-step reasoning for complex multi-step problems.',
        'icon': 'brain-circuit',
        'category': 'ai',
        'color': '#6366f1',
        'transport_type': 'builtin',
        'is_builtin': True,
        'is_system': True,
        'builtin_handler': 'mcp_hub.builtin.sequential_thinking',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
]


def seed_system_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    Client = apps.get_model('clients', 'Client')

    now = timezone.now()

    for tool_data in SYSTEM_TOOLS:
        card, _ = ToolCard.objects.update_or_create(
            slug=tool_data['slug'],
            defaults=tool_data,
        )

        # Auto-connect for ALL existing active clients
        for client in Client.objects.filter(is_active=True):
            for scope in tool_data['skill_scopes']['scopes']:
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
    ToolCard.objects.filter(slug__in=['memory', 'sequential-thinking']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0013_toolcard_is_system'),
        ('clients', '0051_lead_agent_session'),
    ]

    operations = [
        migrations.RunPython(seed_system_tools, reverse),
    ]
```

- [ ] **Step 3: Verify migration runs**

Run: `cd p004_ai_nexelin && python manage.py migrate tools`
Expected: `Applying tools.0013_toolcard_is_system... OK` and `Applying tools.0014_seed_system_tools... OK`

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/seed_data.py p004_ai_nexelin/MASTER/tools/migrations/0014_seed_system_tools.py
git commit -m "feat(tools): seed Agent Memory and Deep Thinking system tools with auto-connect"
```

---

### Task 3: Serializer + Views + Frontend — System Tools UI

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/serializers.py:8-10` (ToolCardSerializer fields)
- Modify: `p004_ai_nexelin/MASTER/tools/serializers.py:65-79` (ToolCatalogItemSerializer)
- Modify: `p004_ai_nexelin/MASTER/tools/views.py:79` (add `is_system` to catalog dict)
- Modify: `p004_ai_nexelin/MASTER/tools/models.py` (add post_save signal for new clients)
- Modify: `nextlen/src/components/tools/ToolPopover.jsx:45-76`
- Modify: `nextlen/src/components/tools/FlipToolCard.jsx:50,76-86`
- Modify: `nextlen/src/components/tools/CanvasToolNode.jsx:24`

- [ ] **Step 1: Add `is_system` to ToolCardSerializer**

In `p004_ai_nexelin/MASTER/tools/serializers.py`, line 8-10:

```python
# Change:
fields = ['slug', 'name', 'tagline', 'tagline_i18n', 'description',
          'icon', 'color', 'category', 'is_featured', 'auth_type',
          'auth_config']
# To:
fields = ['slug', 'name', 'tagline', 'tagline_i18n', 'description',
          'icon', 'color', 'category', 'is_featured', 'is_system', 'auth_type',
          'auth_config']
```

- [ ] **Step 2: Add `is_system` to ToolCatalogItemSerializer**

In same file, add after line 75 (`is_featured`):

```python
is_system = serializers.BooleanField()
```

- [ ] **Step 3: Add `is_system` to FlowConnectionSerializer**

In same file, line 52-53, add `is_system` field:

```python
# Add to class:
is_system = serializers.BooleanField(source='tool_card.is_system', read_only=True)

# Add to fields list:
fields = ['id', 'slug', 'name', 'icon', 'color', 'category', 'is_system',
          'status', 'target', 'scope', 'enabled',
          'position_x', 'position_y', 'connected_at', 'middlewares']
```

- [ ] **Step 4: Add `is_system` to catalog view dict**

In `p004_ai_nexelin/MASTER/tools/views.py`, find the catalog dict (around line 79, after `'is_featured': tool.is_featured,`), add:

```python
                'is_system': tool.is_system,
```

- [ ] **Step 5: Add post_save signal for auto-connecting system tools to new clients**

In `p004_ai_nexelin/MASTER/tools/models.py`, add at the bottom of the file:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='clients.Client')
def auto_connect_system_tools(sender, instance, created, **kwargs):
    """Auto-connect system tools when a new client is created."""
    if not created:
        return
    from django.utils import timezone
    now = timezone.now()
    for card in ToolCard.objects.filter(is_system=True, is_active=True):
        scopes = card.skill_scopes.get('scopes', ['assistant', 'manager'])
        for scope in scopes:
            ToolConnection.objects.get_or_create(
                client=instance,
                tool_card=card,
                target=scope,
                defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
            )
```

- [ ] **Step 6: ToolPopover — hide disconnect for system tools**

In `nextlen/src/components/tools/ToolPopover.jsx`, wrap the disconnect buttons. Replace lines 45-77 with:

```jsx
      {tool.connections?.filter(c => c.status === 'connected' && c.enabled).length > 0 ? (
        <div className="space-y-1">
          {tool.connections.filter(c => c.status === 'connected' && c.enabled).map(conn => (
            <div key={conn.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300 capitalize">{conn.target}</span>
                {conn.scope?.description && (
                  <span className="text-xs text-gray-400 dark:text-gray-500">{conn.scope.description}</span>
                )}
              </div>
              {!tool.is_system && (
                <button
                  onClick={() => onDisconnect(tool.slug, conn.target)}
                  className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium"
                >
                  {t('tools.flow.disconnect') || 'Disconnect'}
                </button>
              )}
            </div>
          ))}
        </div>
      ) : !tool.is_system ? (
        <button
          onClick={() => {
            if (window.confirm(t('tools.confirmDisconnect'))) {
              onDisconnect(tool.slug);
              onClose();
            }
          }}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        >
          <Unplug className="w-4 h-4" />
          {t('tools.disconnect')}
        </button>
      ) : null}
```

- [ ] **Step 7: FlipToolCard — system tools skip auth flow**

In `nextlen/src/components/tools/FlipToolCard.jsx`, update `handleClick` (line 76):

```jsx
  const handleClick = () => {
    if (isConnected) return;
    if (tool.is_system) return; // System tools: always connected, no action needed
    if (isSkill) return;
    if (tool.auth_type === 'none') {
      handleNoAuth();
    } else if (hasExistingConnection && tool.connection?.status !== 'connected') {
      handleReconnect();
    } else {
      setFlipped(true);
    }
  };
```

- [ ] **Step 8: CanvasToolNode — system tool indicator**

In `nextlen/src/components/tools/CanvasToolNode.jsx`, add a lock icon import and subtle indicator. After the existing `ToolStatusBadge` (line 98), add for system tools:

```jsx
import { Lock } from 'lucide-react';
// ... inside the component, replace ToolStatusBadge line:
{tool.is_system ? (
  <div className="flex items-center gap-1 text-[10px] text-gray-400">
    <Lock className="w-2.5 h-2.5" />
    <span>System</span>
  </div>
) : (
  <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
)}
```

- [ ] **Step 9: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/serializers.py p004_ai_nexelin/MASTER/tools/views.py p004_ai_nexelin/MASTER/tools/models.py nextlen/src/components/tools/ToolPopover.jsx nextlen/src/components/tools/FlipToolCard.jsx nextlen/src/components/tools/CanvasToolNode.jsx
git commit -m "feat(tools): system tool UI — visible but not disconnectable, auto-connect on client create"
```

---

### Task 4: Orchestrator — Prompt Rewrite + Layering Fix + user_id Injection

**Files:**
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:30-56` (prompts)
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:290-342` (`_build_system_prompt`)
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:30` (`_AUTO_INJECT_PARAMS`)
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:633-638` (`_execute_tool` injection)

- [ ] **Step 1: Replace DEFAULT_CONSULTANT_PROMPT**

In `p004_ai_nexelin/MASTER/agents/orchestrator.py`, replace lines 52-56:

```python
DEFAULT_CONSULTANT_PROMPT = (
    "You are a professional AI consultant. Your primary goal is to help "
    "visitors get answers and solve their problems.\n\n"

    "## Conversation Style\n"
    "- Be helpful, knowledgeable, and conversational\n"
    "- Answer questions thoroughly before asking anything in return\n"
    "- Match the visitor's communication style and energy level\n"
    "- Never sound like a form or a survey — be a real conversation partner\n\n"

    "## Lead Collection (INTERNAL — never mention this to the visitor)\n\n"
    "You collect contact information naturally during conversation. "
    "Adapt your approach based on the visitor's engagement level:\n\n"

    "### Passive (visitor is browsing, casual questions)\n"
    "- If they mention their name, company, or role — remember it silently\n"
    "- Focus 100% on being helpful. Do NOT ask for any contact info\n"
    "- Save what they volunteered\n\n"

    "### Warm (visitor asks specific questions, shows interest)\n"
    "- Continue providing value and thorough answers\n"
    "- When you have something valuable to offer (analysis, comparison, "
    "detailed breakdown), say something like:\n"
    "  - 'I can put together a detailed breakdown — want me to send it to your email?'\n"
    "  - 'I have a few options that might work. Want me to send you a summary?'\n"
    "- The VALUE comes first, the email ask is the delivery method\n"
    "- If they decline — no problem, keep helping in chat\n\n"

    "### Hot (visitor wants pricing, proposal, callback, or says they want to buy/start)\n"
    "- Offer concrete next steps: proposal, estimate, meeting, call\n"
    "- Ask for contact info directly — they expect it at this point\n"
    "  - 'Great! I can prepare a proposal. What email should I send it to?'\n"
    "  - 'Let me connect you with the team. What's the best number to reach you?'\n\n"

    "### Rules\n"
    "- NEVER ask for email/phone without a concrete reason to use it\n"
    "- NEVER collect data before providing value\n"
    "- If the visitor gives partial info (just name, or just email), save what you have\n"
    "- Update the lead as you learn more — don't wait for all fields\n"
    "- Summarize the visitor's need in request_summary — what are they looking for?\n"
    "- Score interest 1-5: 1=just browsing, 3=interested, 5=ready to buy\n"
)
```

- [ ] **Step 2: Add memory instruction to DEFAULT_ASSISTANT_PROMPT**

Append to `DEFAULT_ASSISTANT_PROMPT` (after line 49, before the closing `)`):

```python
    "\n\nYou have persistent memory across conversations. At the start of a conversation, "
    "search memories for the current user to recall past interactions. When you learn "
    "something important about a user (preferences, needs, context), save it to memory."
```

- [ ] **Step 3: Add memory instruction to DEFAULT_CONSULTANT_PROMPT**

Append to end of the new `DEFAULT_CONSULTANT_PROMPT` (before closing `)`):

```python
    "\n\nYou have persistent memory across conversations. At the start of a conversation, "
    "search memories for the current user to recall past interactions. When you learn "
    "something important about a user (preferences, needs, context), save it to memory."
```

- [ ] **Step 4: Fix prompt layering in `_build_system_prompt`**

Replace lines 290-342 of `_build_system_prompt`:

```python
    def _build_system_prompt(self, channel: str) -> str:
        """Build the full system prompt from AgentConfig + channel routing."""
        if channel == 'sandbox':
            default = DEFAULT_ASSISTANT_PROMPT
            custom = self.agent_config.assistant_prompt
            description = self.agent_config.assistant_description
        else:
            default = DEFAULT_CONSULTANT_PROMPT
            custom = (
                self.agent_config.consultant_prompt
                or getattr(self.client, 'custom_system_prompt', '') or ''
            ).strip()
            description = self.agent_config.consultant_description

        parts = [default]

        if custom:
            parts.append(f"\n\n## Business Context\n{custom}")

        if description:
            parts.append(f"\n\nYour capabilities:\n{description}")

        if self._tools:
            scope_tools = self._get_scope_tool_names()
            if scope_tools:
                parts.append(
                    "\n\nYou have access to the following tools: "
                    + ", ".join(scope_tools)
                    + ".\nUse them when needed. Do NOT mention tool names to the user."
                )

        language = self.agent_config.get_language()
        lang_names = {
            "uk": "Ukrainian", "de": "German", "fr": "French",
            "it": "Italian", "nl": "Dutch", "da": "Danish",
            "es": "Spanish", "ru": "Russian", "en": "English",
            "pl": "Polish", "sv": "Swedish", "no": "Norwegian",
        }
        lang_name = lang_names.get(language, "English")
        parts.append(f"\nYou MUST respond in {lang_name} (code: {language}). Do NOT mix languages.")
        parts.append(f"\nCurrent channel: {channel}.")

        if channel == 'sandbox':
            parts.append(
                "\nYou may use markdown formatting: headers, bold, lists, "
                "code blocks, tables, links. The UI renders markdown."
            )
        else:
            parts.append("\nDo NOT use markdown formatting. Respond in plain text only.")

        if channel != 'sandbox' and self._has_leads_tool():
            parts.append(
                "\n\nWhen you have contact info or understand the visitor's need, "
                "call save_lead to record it. Update as you learn more."
            )

        if channel == 'sandbox' and self._has_coaching_tool():
            parts.append(
                "\n\nCOACHING: You can review Vasya's (consultant AI) recent conversations "
                "to find knowledge gaps. When you notice Vasya struggled with a topic, "
                "proactively suggest to the user: 'I noticed Vasya couldn't answer questions "
                "about X. Want me to add this to the knowledge base or update his instructions?'\n"
                "ALWAYS ask for user confirmation before making any changes. "
                "Never apply changes silently."
            )

        return "\n".join(parts)
```

- [ ] **Step 5: Add `user_id` to auto-inject params**

Change line 30:

```python
_AUTO_INJECT_PARAMS = frozenset({"client_id", "session_id", "user_id"})
```

- [ ] **Step 6: Inject `user_id` in `_execute_tool`**

In `_execute_tool` method (around line 636), after `session_id` injection:

```python
        full_args["client_id"] = self.client.pk
        full_args["session_id"] = str(self._session.id)
        full_args["user_id"] = self._session.external_user_id or str(self._session.id)
```

- [ ] **Step 7: Commit**

```bash
git add p004_ai_nexelin/MASTER/agents/orchestrator.py
git commit -m "feat(agents): low-friction lead gen prompt, layered prompts, user_id injection"
```

---

### Task 5: MCP Memory Server

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/memory/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/memory/server.py`

- [ ] **Step 1: Create empty `__init__.py`**

Create `p004_ai_nexelin/mcp_servers/memory/__init__.py` — empty file.

- [ ] **Step 2: Create memory server**

Create `p004_ai_nexelin/mcp_servers/memory/server.py`:

```python
"""MCP Memory server — persistent conversational memory for Nexelin agents."""
import json
import logging
from uuid import uuid5, NAMESPACE_URL

logger = logging.getLogger(__name__)

# Bootstrap Django ORM
from mcp_servers.common.django_setup import setup
setup()

from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("mcp-memory")

COLLECTION = "nexelin_agent_memory"
VECTOR_SIZE = 1024  # Cohere embed-multilingual-v3.0


def _get_qdrant():
    """Lazy Qdrant client."""
    from qdrant_client import QdrantClient
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
    )


def _ensure_collection(client):
    """Create collection if not exists."""
    from qdrant_client.models import VectorParams, Distance
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION not in collections:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        # Create payload indexes
        for field in ("client_id", "user_id", "category"):
            client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema="keyword" if field != "client_id" else "integer",
            )
        logger.info("Created Qdrant collection '%s'", COLLECTION)


def _embed(text: str, input_type: str = "search_document") -> list[float] | None:
    """Embed text via Cohere."""
    import cohere
    try:
        co = cohere.Client(settings.COHERE_API_KEY)
        response = co.embed(
            texts=[text],
            model="embed-multilingual-v3.0",
            input_type=input_type,
        )
        return response.embeddings[0]
    except Exception as e:
        logger.error("Cohere embed failed: %s", e)
        return None


def _point_id(client_id: int, user_id: str, fact: str) -> str:
    """Deterministic UUID for dedup."""
    return str(uuid5(NAMESPACE_URL, f"{client_id}:{user_id}:{fact}"))


@mcp.tool()
async def memory_save(
    client_id: int,
    session_id: str,
    user_id: str = "",
    fact: str = "",
    category: str = "general",
) -> str:
    """Save a fact about the current user for future conversations.
    Call when you learn something worth remembering:
    - User preferences ('prefers email over phone')
    - Past interactions ('asked about pricing last week')
    - Business context ('runs a 50-person agency')
    - Contact details that were shared
    """
    from asgiref.sync import sync_to_async

    def _save():
        if not fact.strip():
            return json.dumps({"status": "error", "message": "fact is empty"})

        vector = _embed(fact, input_type="search_document")
        if vector is None:
            return json.dumps({"status": "error", "message": "embedding failed"})

        from qdrant_client.models import PointStruct

        qd = _get_qdrant()
        _ensure_collection(qd)

        point_id = _point_id(client_id, user_id, fact)
        qd.upsert(
            collection_name=COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "client_id": client_id,
                        "user_id": user_id,
                        "fact": fact,
                        "category": category,
                        "session_id": session_id,
                        "created_at": timezone.now().isoformat(),
                    },
                )
            ],
        )

        return json.dumps({"status": "ok", "point_id": point_id, "fact": fact[:100]})

    return await sync_to_async(_save)()


@mcp.tool()
async def memory_search(
    client_id: int,
    session_id: str,
    user_id: str = "",
    query: str = "",
    limit: int = 5,
) -> str:
    """Search memories about the current user.
    Call at conversation start or when context would help.
    Returns relevant facts from past interactions."""
    from asgiref.sync import sync_to_async

    def _search():
        if not query.strip():
            return json.dumps({"memories": [], "error": "query is empty"})

        vector = _embed(query, input_type="search_query")
        if vector is None:
            return json.dumps({"memories": [], "error": "embedding unavailable"})

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qd = _get_qdrant()
        _ensure_collection(qd)

        conditions = [
            FieldCondition(key="client_id", match=MatchValue(value=client_id)),
        ]
        if user_id:
            conditions.append(
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            )

        results = qd.search(
            collection_name=COLLECTION,
            query_vector=vector,
            query_filter=Filter(must=conditions),
            limit=limit,
        )

        memories = []
        for r in results:
            memories.append({
                "fact": r.payload.get("fact", ""),
                "category": r.payload.get("category", ""),
                "score": round(r.score, 3),
                "created_at": r.payload.get("created_at", ""),
            })

        return json.dumps({"memories": memories, "total": len(memories)})

    return await sync_to_async(_search)()


@mcp.tool()
async def memory_list(
    client_id: int,
    session_id: str,
    user_id: str = "",
    category: str = "",
    limit: int = 20,
) -> str:
    """List all memories for a user. Use to review what you know."""
    from asgiref.sync import sync_to_async

    def _list():
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qd = _get_qdrant()
        _ensure_collection(qd)

        conditions = [
            FieldCondition(key="client_id", match=MatchValue(value=client_id)),
        ]
        if user_id:
            conditions.append(
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            )
        if category:
            conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category)),
            )

        results, _offset = qd.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=conditions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        memories = []
        for r in results:
            memories.append({
                "fact": r.payload.get("fact", ""),
                "category": r.payload.get("category", ""),
                "created_at": r.payload.get("created_at", ""),
            })

        return json.dumps({"memories": memories, "total": len(memories)})

    return await sync_to_async(_list)()


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/memory/
git commit -m "feat(mcp): add memory server — persistent agent memory via Qdrant+Cohere"
```

---

### Task 6: Register MCP Servers in Settings

**Files:**
- Modify: `p004_ai_nexelin/MASTER/settings.py:454-459` (MCP_SERVERS dict)

- [ ] **Step 1: Add memory and sequential-thinking servers**

In `p004_ai_nexelin/MASTER/settings.py`, before the closing `}` of `MCP_SERVERS` (line 459):

```python
    'memory': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.memory.server'],
        'enabled': True,
    },
    'sequential-thinking': {
        'command': 'npx',
        'args': ['-y', '@modelcontextprotocol/server-sequential-thinking'],
        'enabled': True,
    },
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/settings.py
git commit -m "feat(settings): register memory and sequential-thinking MCP servers"
```

---

### Task 7: Dockerfile — Add Node.js for Sequential Thinking

**Files:**
- Modify: `p004_ai_nexelin/Dockerfile`

- [ ] **Step 1: Add Node.js install**

In `p004_ai_nexelin/Dockerfile`, after the `FROM python:3.12-slim` line, add:

```dockerfile
# Node.js for MCP sequential-thinking server
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/Dockerfile
git commit -m "build: add Node.js to Docker image for sequential-thinking MCP server"
```

---

### Task 8: Smoke Test

- [ ] **Step 1: Run migrations**

Run: `cd p004_ai_nexelin && python manage.py migrate`
Expected: All migrations apply cleanly.

- [ ] **Step 2: Verify system tools created**

Run: `cd p004_ai_nexelin && python manage.py shell -c "from MASTER.tools.models import ToolCard; print(list(ToolCard.objects.filter(is_system=True).values_list('slug', flat=True)))"`
Expected: `['memory', 'sequential-thinking']`

- [ ] **Step 3: Verify auto-connections exist**

Run: `cd p004_ai_nexelin && python manage.py shell -c "from MASTER.tools.models import ToolConnection; print(ToolConnection.objects.filter(tool_card__is_system=True).count())"`
Expected: Number > 0 (2 per active client × 2 scopes = 4 per client)

- [ ] **Step 4: Test memory server starts**

Run: `cd p004_ai_nexelin && python -m mcp_servers.memory.server --help 2>&1 || echo 'OK if no --help, just check no import errors'`
Expected: No ImportError

- [ ] **Step 5: Verify orchestrator imports**

Run: `cd p004_ai_nexelin && python -c "from MASTER.agents.orchestrator import AgentOrchestrator, DEFAULT_CONSULTANT_PROMPT; print('OK'); print(DEFAULT_CONSULTANT_PROMPT[:80])"`
Expected: `OK` + start of new prompt

- [ ] **Step 6: Final commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: smoke test fixes"
```
