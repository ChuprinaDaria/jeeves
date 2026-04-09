# Vasya Low-Friction Lead Gen + Agent Memory + Sequential Thinking

**Date:** 2026-03-24
**Status:** Draft
**Scope:** DEFAULT_CONSULTANT_PROMPT rewrite, prompt layering fix, mcp-memory server, sequential-thinking registration

---

## 1. Problem

1. `DEFAULT_CONSULTANT_PROMPT` — generic "You are a helpful AI consultant", не збирає ліди
2. Prompt layering broken — `consultant_prompt` **замінює** default замість додавання поверх
3. Агенти не мають persistent memory між сесіями
4. Агенти не мають структурованого мислення для складних задач

---

## 2. DEFAULT_CONSULTANT_PROMPT — Low-Friction Lead Gen

### Principles

- **Value first** — завжди дай відповідь/користь перед тим як просити дані
- **Adaptive tone** — читай рівень зацікавленості юзера:
  - Casual/browsing → passive collection only (якщо юзер сам назвав ім'я — зберігай)
  - Interested/asking specifics → value-first, потім soft offer: "Хочеш, скину результати на пошту?"
  - Hot/ready → direct: "Залиш контакт, підготую пропозицію"
- **Never ask email/phone without reason** — завжди є конкретний привід (відправити файл, розрахунок, пропозицію)
- **Natural conversation** — не форма, не анкета

### New DEFAULT_CONSULTANT_PROMPT

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

Note: The prompt does NOT reference `save_lead` tool by name. The lead collection instructions in `_build_system_prompt()` are conditional — only appended when `_has_leads_tool()` returns True (see Section 3). This way the prompt works even without the leads MCP server connected.

### What Changes in orchestrator.py

Keep the existing `_has_leads_tool()` gate (lines 335-340) but update the instruction text to be lighter — the default prompt already covers the *behavior*, the gated instruction just tells the LLM which tool to call:

```python
if channel != 'sandbox' and self._has_leads_tool():
    parts.append(
        "\n\nWhen you have contact info or understand the visitor's need, "
        "call save_lead to record it. Update as you learn more."
    )
```

---

## 3. Prompt Layering Fix

### Current (broken)

```python
# OR chain — custom REPLACES default
base = (
    self.agent_config.consultant_prompt
    or getattr(self.client, 'custom_system_prompt', '') or ''
).strip() or DEFAULT_CONSULTANT_PROMPT
```

### New (layered)

```python
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

parts = [default]  # default ALWAYS present

if custom:
    parts.append(f"\n\n## Business Context\n{custom}")
```

**Result:** Default prompt (lead gen behavior, conversation style) is always the base. Custom prompt adds business-specific info on top under "Business Context" header.

Same logic for Oleg — `DEFAULT_ASSISTANT_PROMPT` always present, `assistant_prompt` layers on top.

---

## 4. System Tools — Visible but Not Disconnectable

Memory and Sequential Thinking are **system tools** — visible on the Tools canvas/catalog, showing which agents they're connected to, but users cannot disconnect them.

### Model Changes

#### ToolCard — new field

```python
is_system = models.BooleanField(default=False, help_text='System tool — always connected, cannot be disconnected')
```

Migration: `tools/migrations/0012_toolcard_is_system.py`

#### Auto-connection on Client Creation

When a new client is created (or on migration for existing clients), auto-create `ToolConnection` records for all `is_system=True` ToolCards:

```python
# In post_save signal or migration
for card in ToolCard.objects.filter(is_system=True, is_active=True):
    for scope in card.skill_scopes.get('scopes', ['assistant', 'manager']):
        ToolConnection.objects.get_or_create(
            client=client,
            tool_card=card,
            target=scope,
            defaults={'status': 'connected', 'enabled': True},
        )
```

#### Seed Data — new entries

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

#### Frontend Changes

**ToolPopover.jsx** — hide disconnect button for system tools:
```jsx
{!tool.is_system && (
  <button onClick={onDisconnect}>Disconnect</button>
)}
```

**FlipToolCard.jsx** — system tools show as always-connected, no auth form flip:
```jsx
const isSystem = tool.is_system;
// System tools: always show connected state, click opens info only
```

**CanvasToolNode.jsx** — system tools rendered with a subtle "system" indicator (e.g., lock icon or different border style).

**Serializer** — add `is_system` to ToolCard serializer response.

#### Orchestrator Changes

With system tools having proper `ToolConnection` records, the `_ALWAYS_ON_SERVERS` hack is **no longer needed**. System tools go through normal scope filtering via `ToolConnection` — they just happen to always have connections for both scopes.

Remove `_ALWAYS_ON_SERVERS`. The existing `_build_scope_filter()` + `_get_scope_tool_names()` + `_tools_to_llm_format()` work unchanged because system tools have real ToolConnection records.

---

## 5. MCP Server: mcp-memory (system tool)

### Purpose

Persistent conversational memory for both agents. Stores facts about users across sessions.

### Location

`mcp_servers/memory/server.py`

### Storage

Uses existing Qdrant instance (via Django settings `QDRANT_HOST`, `QDRANT_PORT`).
New collection: `nexelin_agent_memory` (separate from knowledge base `nexelin_embeddings`).
Embeddings: Cohere `embed-multilingual-v3.0` (via Django settings `COHERE_API_KEY`).

Memory server bootstraps Django ORM via `mcp_servers.common.django_setup` (same pattern as all existing MCP servers) and reads settings from `django.conf.settings`.

### user_id Resolution

Memory is scoped per visitor. The orchestrator needs to inject `user_id` so memory tools know which visitor they're working with.

**Source:** `self._session.external_user_id` (already populated by dispatch.py when creating AgentSession).

**Implementation:**
1. Add `"user_id"` to `_AUTO_INJECT_PARAMS` frozenset
2. In `_execute_tool()`, populate alongside `client_id` and `session_id`:

```python
full_args["client_id"] = self.client.pk
full_args["session_id"] = str(self._session.id)
full_args["user_id"] = self._session.external_user_id or str(self._session.id)
```

**Fallback for anonymous visitors:** When `external_user_id` is empty (sandbox, web widget without auth), use `session_id` as `user_id`. This isolates memories per session — anonymous visitors don't see each other's memories. When the same phone/telegram_chat_id returns, they get their cross-session memories.

### Tools

#### `memory_save` (both scopes)

```python
async def memory_save(
    client_id: int,
    session_id: str,   # auto-injected
    user_id: str = "",  # auto-injected (external_user_id or session_id)
    fact: str = "",     # what to remember
    category: str = "general",  # general, preference, contact, need
) -> str:
    """Save a fact about the current user for future conversations.
    Call when you learn something worth remembering:
    - User preferences ('prefers email over phone')
    - Past interactions ('asked about pricing last week')
    - Business context ('runs a 50-person agency')
    - Contact details that were shared
    """
```

Implementation:
1. Embed `fact` via Cohere with `input_type="search_document"`
2. Upsert to Qdrant `nexelin_agent_memory` with payload: `{client_id, user_id, fact, category, created_at, session_id}`
3. Point ID: `uuid5(NAMESPACE_URL, f"{client_id}:{user_id}:{fact}")` — deterministic, process-safe dedup (NOT `hash()` — it's non-deterministic across processes)
4. On Cohere API error: return `{"status": "error", "message": "..."}`, do NOT crash

#### `memory_search` (both scopes)

```python
async def memory_search(
    client_id: int,
    session_id: str,   # auto-injected
    user_id: str = "",  # auto-injected
    query: str = "",    # what to look up
    limit: int = 5,
) -> str:
    """Search memories about the current user.
    Call at conversation start or when context would help.
    Returns relevant facts from past interactions."""
```

Implementation:
1. Embed `query` via Cohere with `input_type="search_query"`
2. Search Qdrant with filter `{client_id, user_id}`, top_k=limit
3. Return matched facts with scores
4. On Cohere API error: return `{"memories": [], "error": "embedding unavailable"}`

#### `memory_list` (both scopes)

```python
async def memory_list(
    client_id: int,
    session_id: str,   # auto-injected
    user_id: str = "",  # auto-injected
    category: str = "",
    limit: int = 20,
) -> str:
    """List all memories for a user. Use to review what you know."""
```

Scroll Qdrant with filter, no embedding needed.

### Registration in MASTER/settings.py

```python
MCP_SERVERS = {
    ...existing...,
    'memory': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.memory.server'],
        'enabled': True,
    },
}
```

### Prompt Integration

Add to both DEFAULT prompts (at the end, before closing):

```
You have persistent memory across conversations. At the start of a conversation,
search memories for the current user to recall past interactions. When you learn
something important about a user (preferences, needs, context), save it to memory.
```

### Error Handling

- Cohere embed call fails → return error JSON, do not crash tool
- Qdrant unreachable → return error JSON, do not crash tool
- Categories are free-form strings, not validated — LLM picks what fits

---

## 6. Sequential Thinking — Registration (system tool)

### Approach

Use official npm package as-is: `@modelcontextprotocol/server-sequential-thinking`

### Prerequisite: Node.js in Docker

Production Dockerfile needs `node` and `npm`/`npx`. Add to Dockerfile:

```dockerfile
# Install Node.js for MCP sequential-thinking server
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*
```

If adding Node.js to the prod image is undesirable, alternative: pre-install the package during build:

```dockerfile
RUN npm install -g @modelcontextprotocol/server-sequential-thinking
```

Then use `command: 'sequential-thinking-server'` instead of `npx`.

### Registration in MASTER/settings.py

```python
MCP_SERVERS = {
    ...existing...,
    'sequential-thinking': {
        'command': 'npx',
        'args': ['-y', '@modelcontextprotocol/server-sequential-thinking'],
        'enabled': True,
    },
}
```

### No Prompt Changes Needed

The tool is self-describing — LLM sees it via function calling schema and uses it when reasoning through complex multi-step problems.

System tool with proper ToolCard + ToolConnection records (see Section 4). Visible on canvas, connected to both agents, cannot be disconnected.

---

## 8. Files to Change

| File | Change |
|---|---|
| `MASTER/agents/orchestrator.py` | New DEFAULT_CONSULTANT_PROMPT, prompt layering fix, `user_id` auto-injection |
| `MASTER/tools/models.py` | Add `is_system` field to ToolCard |
| `MASTER/tools/seed_data.py` | Add memory + sequential-thinking ToolCard entries |
| `MASTER/tools/migrations/0012_toolcard_is_system.py` | New field migration |
| `MASTER/tools/migrations/0013_seed_system_tools.py` | Seed data + auto-connect for existing clients |
| `MASTER/clients/serializers.py` | Add `is_system` to ToolCard serializer |
| `mcp_servers/memory/__init__.py` | New — empty |
| `mcp_servers/memory/server.py` | New — FastMCP memory server (~150 lines) |
| `MASTER/settings.py` | Register `memory` and `sequential-thinking` in MCP_SERVERS |
| `Dockerfile` (or `docker-compose.yml`) | Add Node.js for sequential-thinking |
| `nextlen/src/components/tools/ToolPopover.jsx` | Hide disconnect for `is_system` tools |
| `nextlen/src/components/tools/FlipToolCard.jsx` | System tool rendering (always connected, no auth) |
| `nextlen/src/components/tools/CanvasToolNode.jsx` | System tool indicator |

### NOT changed

- No changes to orchestrator scope filtering (system tools have real ToolConnection records)
- No `_ALWAYS_ON_SERVERS` hack needed

---

## 7. Qdrant Collection Schema (memory)

```
Collection: nexelin_agent_memory
Vector size: 1024 (Cohere embed-multilingual-v3.0)
Distance: Cosine

Payload fields:
- client_id: int (indexed)
- user_id: str (indexed)
- fact: str
- category: str (indexed)
- created_at: str (ISO)
- session_id: str
```

Create collection on first write if not exists.

---

## 9. Rollback

- Memory server: disable in `MCP_SERVERS` → agents lose memory tools, no side effects
- Sequential thinking: same — disable entry
- Prompt changes: revert orchestrator.py
- Qdrant collection: can drop `nexelin_agent_memory` independently of knowledge base
- No migrations to rollback

---

## 10. Future Considerations (out of scope)

- **Memory TTL / garbage collection** — memories accumulate forever. Future: add `memory_forget` tool or auto-expire after N days
- **Memory admin UI** — view/delete memories per user in Nexelin dashboard
- **Batch embedding** — if save volume grows, batch Cohere calls instead of one per fact
