# MCP Dual Agent + Leads + Middleware — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Feature flag `mcp_real_agent`, `rollout='selected'`, client `srtyh` only

---

## Context

Current MCP pipeline has:
- Single `system_prompt` in `AgentConfig` — no distinction between assistant and consultant
- Lead collection via `[LEAD_DATA]` tag hack in legacy pipeline — not connected to MCP
- `EdgeMiddleware` model exists but orchestrator ignores it completely
- Sandbox uses legacy pipeline (`ragAPI` → `LLMClient` with specialization/branch prompts)

## Goals

1. Two AI agents with separate prompts and tool scopes
2. Separate MCP server for lead qualification and search
3. EdgeMiddleware actually executes in orchestrator pipeline
4. Sandbox switches to MCP pipeline
5. Zero impact on legacy users (everything behind `mcp_real_agent` flag, only `srtyh`)

---

## 1. Dual Agent — AgentConfig Changes

### New Fields

| Field | Type | Purpose |
|---|---|---|
| `assistant_prompt` | TextField | Oleg's system prompt (Sandbox) |
| `consultant_prompt` | TextField | Vasya's system prompt (messengers) |
| `assistant_description` | TextField | What Oleg can do (UI + prompt) |
| `consultant_description` | TextField | What Vasya can do (UI + prompt) |

### Migration

- Copy existing `system_prompt` → `consultant_prompt` (it was used for messenger responses)
- `assistant_prompt` — empty (uses default)
- `system_prompt` field remains for backward compat but is no longer read by MCP pipeline

### Agent Roles

| | Vasya (consultant) | Oleg (assistant) |
|---|---|---|
| **Where** | Telegram, WhatsApp, Web Widget | Sandbox |
| **Who uses** | End customers (B2C) | Nexelin business user |
| **Tool scope** | `manager` (limited) | `assistant` (full) |
| **Prompt field** | `consultant_prompt` | `assistant_prompt` |
| **Description** | `consultant_description` | `assistant_description` |
| **Focus** | Sales, consulting, lead collection | Management, analytics, lead search |

### Prompt Building in Orchestrator

`_build_system_prompt(channel)` determines agent role:

```python
if channel == 'sandbox':
    base = agent_config.assistant_prompt or DEFAULT_ASSISTANT_PROMPT
    description = agent_config.assistant_description
    scope = 'assistant'
else:
    base = agent_config.consultant_prompt or DEFAULT_CONSULTANT_PROMPT
    description = agent_config.consultant_description
    scope = 'manager'
```

Final prompt assembly:
1. `base` prompt
2. `+ description` (if set)
3. `+ auto-generated capabilities` (from connected tools matching scope)
4. `+ language instruction`
5. `+ channel context`
6. `+ no markdown`

Auto-generated capabilities — orchestrator filters `_tools` by scope from `ToolConnection` and generates: "You have access to: knowledge base search, lead management, escalation."

### Tool Scope Filtering

Orchestrator must filter tools by scope before passing to LLM:

```python
# In connect() or process():
scope = 'assistant' if channel == 'sandbox' else 'manager'
connected_tools = ToolConnection.objects.filter(
    client=self.client, enabled=True, status='connected',
    target=scope,
)
# Only expose tools from connected_tools to LLM
```

This means `_tools_to_llm_format()` must respect scope — Vasya sees only `manager` tools, Oleg sees only `assistant` tools.

### How Scope Filtering Works

Orchestrator still spawns **all** enabled MCP servers from `settings.MCP_SERVERS` (rag, escalation, leads). But `_tools_to_llm_format()` filters discovered tools against `ToolConnection` records:

```python
def _tools_to_llm_format(self, scope: str) -> list[dict] | None:
    # Get tool slugs this client has connected for this scope
    connected_slugs = set(
        ToolConnection.objects.filter(
            client=self.client, enabled=True, status='connected',
            target=scope,
        ).values_list('tool_card__slug', flat=True)
    )

    # Build _tool_to_connection mapping for middleware lookup
    self._tool_to_connection = {}
    for conn in ToolConnection.objects.filter(...):
        self._tool_to_connection[conn.tool_card.slug] = conn

    # Filter self._tools — only include tools whose server name
    # matches a connected slug
    for tool in self._tools:
        server_name = self._tool_to_server[tool.name]
        if server_name in connected_slugs:
            # include in llm_tools
```

This avoids complexity of conditional subprocess spawning — all servers start, but LLM only sees tools matching the current scope.

### Auto-Injected Parameters

Orchestrator auto-injects (hidden from LLM):
- `client_id` — existing, from `self.client.pk`
- `session_id` — new, from `AgentSession.id` (UUID string)

Both added to `_AUTO_INJECT_PARAMS`. This allows `save_lead` to link leads to sessions without LLM needing to know the session ID.

---

## 2. MCP Server: mcp-leads

### Location

`mcp_servers/leads/server.py` — FastMCP, STDIO subprocess.

### Tools

#### `save_lead` (scope: manager — Vasya calls this)

```python
async def save_lead(
    client_id: int,
    session_id: str,  # auto-injected, AgentSession UUID
    name: str = "",
    email: str = "",
    phone: str = "",
    request_summary: str = "",
    interest_score: int = 3,
    source: str = "web",
) -> str:
    """Save or update a lead from conversation.
    Creates new lead or updates existing for same session.
    Returns lead ID and status."""
```

`session_id` is auto-injected by orchestrator (same as `client_id`). LLM never sees it.

Replaces the `[LEAD_DATA]` tag hack. Vasya calls this via native tool calling — more reliable, no parsing needed.

#### `qualify_conversation` (scope: manager — Vasya calls this)

```python
async def qualify_conversation(
    client_id: int,
    session_id: str,  # auto-injected
) -> str:
    """Analyze current session's conversation history,
    identify contact info, assess interest level.
    Returns qualified lead data.
    Vasya calls this at end of conversation or when prompted."""
```

Trigger: orchestrator appends to consultant prompt: "At the end of a conversation or when the user seems interested, call qualify_conversation to assess the lead."

#### `search_leads` (scope: assistant — Oleg calls this)

```python
async def search_leads(
    client_id: int,
    status: str = "",
    source: str = "",
    min_interest: int = 0,
    search: str = "",
    period: str = "",  # "7d", "30d", "2026-03"
    limit: int = 25,
) -> str:
    """Search existing leads with filters.
    Returns list of leads matching criteria."""
```

#### `get_lead_stats` (scope: assistant — Oleg calls this)

```python
async def get_lead_stats(
    client_id: int,
    period: str = "30d",
) -> str:
    """Lead statistics: count by status, by source,
    average interest score, conversion rate."""
```

### Seed Data

New ToolCard entry:

```python
{
    'slug': 'leads',
    'name': 'Lead Management',
    'tagline': 'Збір та управління лідами з усіх каналів',
    'icon': 'user-plus',
    'category': 'crm',
    'color': '#10b981',
    'transport_type': 'builtin',
    'is_builtin': True,
    'builtin_handler': 'mcp_hub.builtin.leads',
    'auth_type': 'none',
    'skill_scopes': {
        'scopes': ['assistant', 'manager'],
        'bidirectional': False,
    },
}
```

### Settings Registration

```python
MCP_SERVERS = {
    'rag': { ... },
    'escalation': { ... },
    'leads': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.leads.server'],
        'enabled': True,
    },
}
```

### Consultant Prompt Addition

Orchestrator auto-appends to `consultant_prompt` when leads tool is connected:

```
When you learn the user's name, email, phone, or understand their need,
call save_lead with the information you have. Update as you learn more.
Do NOT mention lead collection to the user. Be natural.
```

---

## 3. EdgeMiddleware Execution

### Current Problem

`EdgeMiddleware` records exist in DB but `orchestrator._execute_tool()` calls MCP session directly, never reading middlewares.

### Solution

Add middleware pipeline in `_execute_tool`:

```python
async def _execute_tool(self, tool_name, arguments):
    # 1. Find ToolConnection for this tool + current scope
    connection = self._tool_to_connection.get(tool_name)  # built during _tools_to_llm_format

    # 2. Load middlewares
    middlewares = EdgeMiddleware.objects.filter(
        connection=connection, enabled=True,
    ).select_related('skill_card').order_by('order')

    pre_middlewares = [m for m in middlewares if m.order < 0]
    post_middlewares = [m for m in middlewares if m.order >= 0]

    # 3. Pre-execution
    processed_args = arguments
    for mw in pre_middlewares:
        processed_args = await self._run_middleware(mw, processed_args, stage='pre')

    # 4. Execute tool
    result_text, status = await self._call_mcp_tool(tool_name, processed_args)

    # 5. Post-execution
    for mw in post_middlewares:
        result_text = await self._run_middleware(mw, result_text, stage='post')

    return result_text, status
```

### Middleware Execution

Each middleware is a tool call to the middleware's `skill_card`:

```python
async def _run_middleware(self, middleware, data, stage):
    skill = middleware.skill_card
    # Call the skill's MCP tool (e.g., translation)
    # with data + middleware.config as arguments
    # Return transformed data
    # On error: log warning, return original data (don't break flow)
```

### Stage Convention

- `order < 0` → pre-execution (transform input before tool call)
- `order >= 0` → post-execution (transform output after tool call)
- Default `order=0` → post-execution

### Validation

- On EdgeMiddleware save: validate `skill_card` supports the connection's scope
- On execution: if middleware tool unavailable → skip + log, don't break main flow

---

## 4. Sandbox → MCP Pipeline

### Channel Routing

`AgentSession.CHANNEL_CHOICES` — add `('sandbox', 'Sandbox')`.

`ChatSSEView._stream_mcp` must read `channel` from request body JSON and pass it to orchestrator:

```python
async def _stream_mcp(self, request, client, data):
    channel = data.get('channel', 'api')  # frontend sends 'sandbox'
    # ...
    result = await orchestrator.process(
        message=message, session=session,
        conversation=conversation, channel=channel,
    )
```

`dispatch.py` — same pattern: read channel, pass through.

Orchestrator uses channel to determine scope:

```python
if channel == 'sandbox':
    scope = 'assistant'  # Oleg
else:
    scope = 'manager'  # Vasya
```

### Frontend Changes

`ChatWindow.jsx`:
- When `mcp_real_agent` flag is enabled → use SSE endpoint `/api/mcp/chat/` with `{message, channel: 'sandbox'}`
- When flag is off → legacy `ragAPI` (no changes)

### What Stays Unchanged

- Legacy `LLMClient` with specialization/branch/default prompt hierarchy — untouched
- All clients without `mcp_real_agent` flag — untouched
- Existing Telegram/WhatsApp webhook handlers — only `srtyh` routes through MCP

---

## 5. Feature Flag Strategy

All changes gated by existing `mcp_real_agent` flag:
- `rollout='selected'`
- `enabled_clients = [srtyh]`

No new feature flags needed. Legacy users see zero changes.

---

## 6. Files to Change

| File | Change |
|---|---|
| `agents/models.py` | Add `assistant_prompt`, `consultant_prompt`, `assistant_description`, `consultant_description` fields |
| `agents/orchestrator.py` | Dual prompt building, scope-based tool filtering, middleware execution |
| `agents/dispatch.py` | Pass `channel` for scope routing |
| `mcp_servers/leads/server.py` | New MCP server (4 tools) |
| `mcp_servers/leads/requirements.txt` | Dependencies |
| `tools/seed_data.py` | Add leads ToolCard |
| `tools/models.py` | No changes needed |
| `mcp_hub/views.py` | Pass channel to orchestrator |
| `settings.py` | Register leads MCP server |
| `nextlen/src/components/sandbox/ChatWindow.jsx` | SSE endpoint switch (behind flag) |
| `nextlen/src/api/agent.js` | Add MCP chat API call |
| Migration | New fields + data migration (system_prompt → consultant_prompt) |

---

## 7. Lead Model Changes

Add nullable FK to `AgentSession` on existing `Lead` model:

```python
agent_session = models.ForeignKey(
    'agents.AgentSession', on_delete=models.SET_NULL,
    null=True, blank=True, related_name='leads',
)
```

Existing `conversation` FK (to `ClientWhatsAppConversation`) stays — used by legacy pipeline. MCP pipeline uses `agent_session` instead. This allows leads from any channel (Telegram, WhatsApp, Web) without being tied to WhatsApp-specific model.

---

## 8. Seed Migration

New seed migration required (existing `0002_seed_tool_cards` has already run). Create `tools/migrations/0009_seed_leads_tool.py` that adds the `leads` ToolCard entry.

---

## 9. Rollback Safety

If feature needs rollback: set `mcp_real_agent` flag to `rollout='off'`. Legacy pipeline reads `system_prompt` (unchanged), new fields are ignored. No data loss — `consultant_prompt` is a copy, `system_prompt` stays.

---

## 10. Out of Scope

- Legacy prompt hierarchy cleanup (specialization/branch) — stays for non-MCP clients
- External lead sources integration — future, architecture supports it
- UI for assistant_description/consultant_description editing — can use admin for now
- `Lead.conversation` FK refactoring — `agent_session` FK covers MCP pipeline needs
