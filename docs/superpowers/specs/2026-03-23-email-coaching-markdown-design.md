# Email + Coaching + Markdown Rendering — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Feature flag `mcp_real_agent`, client `srtyh` only
**Depends on:** MCP Dual Agent spec (2026-03-23)

---

## Context

Current MCP pipeline for client `srtyh` has:
- No email capabilities — `EmailService` exists in legacy pipeline but not exposed as MCP tool
- No way for Oleg to train Vasya — agents are fully isolated
- Sandbox ChatWindow uses ReactMarkdown + remarkGfm but lacks styled tables, images, and file download links
- Tool scope filtering works at server level, not individual tool level

## Goals

1. `mcp-email` server — full email for Oleg, commercial-only for Vasya
2. `mcp-coaching` server — Oleg reviews Vasya's gaps, proposes knowledge/prompt updates
3. Markdown rendering improvements in Sandbox — tables, images, file links
4. Tool-level scope filtering in orchestrator

---

## 1. mcp-email Server

### Location

`mcp_servers/email/server.py` — FastMCP, STDIO subprocess.

### Tools

| Tool | Scope | Purpose |
|------|-------|---------|
| `send_email` | assistant | Send arbitrary email (to, subject, body, is_html, cc, bcc) |
| `send_email_with_attachment` | assistant | Send email with file from media/ (e.g. xlsx report) |
| `read_emails` | assistant | Get recent N emails via IMAP (limit, folder, days_back) |
| `search_emails` | assistant | Search by sender/subject via IMAP (from_address, subject, days_back) |
| `analyze_emails` | assistant | LLM analysis of inbox for period (days_back, language) |
| `send_commercial_email` | manager | Send structured commercial proposal/invoice only |

### Tool Signatures

#### send_email (assistant)

```python
async def send_email(
    client_id: int,
    session_id: str,
    to_address: str,
    subject: str,
    body: str,
    is_html: bool = False,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> str:
    """Send an email via client's SMTP configuration."""
```

#### send_email_with_attachment (assistant)

```python
async def send_email_with_attachment(
    client_id: int,
    session_id: str,
    to_address: str,
    subject: str,
    body: str,
    file_path: str,  # relative to media/, e.g. "xlsx/21/report.xlsx"
    is_html: bool = False,
) -> str:
    """Send email with file attachment. file_path is relative to MEDIA_ROOT.
    Use after create_spreadsheet to email the generated file."""
```

**Path traversal protection (mandatory):**

```python
from django.conf import settings

resolved = (settings.MEDIA_ROOT / file_path).resolve()
media_root = settings.MEDIA_ROOT.resolve()
if not str(resolved).startswith(str(media_root)):
    return json.dumps({"error": "Invalid file path"})
if not resolved.is_file():
    return json.dumps({"error": f"File not found: {file_path}"})
```

**New method needed:** `EmailService.send_email()` currently does not support attachments. Implementation must add a new `send_email_with_attachment()` method to `EmailService` that:
1. Creates `MIMEMultipart('mixed')` instead of `MIMEMultipart('alternative')`
2. Attaches body as `MIMEText`
3. Reads file, adds as `MIMEBase('application', 'octet-stream')` with `Content-Disposition: attachment`
4. Uses existing SMTP connection logic from `send_email()`

#### read_emails (assistant)

```python
async def read_emails(
    client_id: int,
    session_id: str,
    limit: int = 10,
    folder: str = "INBOX",
    days_back: int = 7,
) -> str:
    """Read recent emails via IMAP. Returns list of {subject, from, date, body}."""
```

#### search_emails (assistant)

```python
async def search_emails(
    client_id: int,
    session_id: str,
    from_address: str = "",
    subject: str = "",
    days_back: int = 30,
    limit: int = 20,
) -> str:
    """Search emails by sender and/or subject via IMAP."""
```

#### analyze_emails (assistant)

```python
async def analyze_emails(
    client_id: int,
    session_id: str,
    days_back: int = 7,
    language: str = "",
) -> str:
    """Analyze recent emails: count, top senders, key topics, action items.
    Uses LLM for intelligent summarization. Language auto-detected from
    AgentConfig if not provided."""
```

Wraps existing `EmailService.analyze_recent_emails()`. Language resolution chain:
1. If `language` param provided — use it
2. Otherwise: `AgentSession.objects.get(pk=session_id)` -> `session.agent_config.get_language()`
3. Fallback: `'en'`

#### send_commercial_email (manager)

```python
async def send_commercial_email(
    client_id: int,
    session_id: str,
    to_address: str,
    proposal_type: Literal["quote", "invoice", "offer", "follow_up"],
    subject: str = "",
    body: str = "",
    amount: str = "",
    currency: str = "EUR",
    items: list[dict] | None = None,  # [{name, qty, price}]
) -> str:
    """Send a structured commercial email (quote/invoice/offer).
    Vasya uses this to send proposals to customers.
    Body is generated from template if empty. Subject auto-generated from proposal_type.
    NOT for arbitrary emails — only commercial proposals."""
```

If `subject` is empty — auto-generated: `"{company_name} — {proposal_type_label}"`.
If `body` is empty — generated from template with company name, items table, amount, currency.
Vasya cannot send arbitrary free-text emails through this tool.

### SMTP/IMAP Credentials

All tools use `Client` model fields (`email_smtp_host`, `email_smtp_username`, etc.) via existing `EmailService`. No separate credentials needed — reuses what's already configured in legacy pipeline.

### Tool Scopes Declaration

```python
TOOL_SCOPES = {
    'send_email': ['assistant'],
    'send_email_with_attachment': ['assistant'],
    'read_emails': ['assistant'],
    'search_emails': ['assistant'],
    'analyze_emails': ['assistant'],
    'send_commercial_email': ['manager'],
}
```

Exposed via `meta://tool_scopes` MCP resource (see Section 4).

### Settings Registration

```python
# settings.py MCP_SERVERS
'email': {
    'command': 'python',
    'args': ['-m', 'mcp_servers.email.server'],
    'enabled': True,
},
```

### Seed ToolCard

```python
{
    'slug': 'email',
    'name': 'Email',
    'tagline': 'Send, read and analyze emails',
    'description': 'Full email management for AI Assistant (send, read, search, analyze via SMTP/IMAP) and commercial proposals for Consultant.',
    'icon': 'mail',
    'category': 'communication',
    'color': '#3b82f6',
    'transport_type': 'builtin',
    'is_builtin': True,
    'auth_type': 'none',
    'skill_scopes': {
        'scopes': ['assistant', 'manager'],
        'bidirectional': False,
    },
}
```

---

## 2. Markdown Rendering in Sandbox

### Current State

`ChatWindow.jsx` uses `ReactMarkdown` + `remarkGfm`. Tables, images, and file links render but lack styling.

### Changes

Add `components` prop to `ReactMarkdown` in `ChatWindow.jsx`:

#### Images

```jsx
img: ({ src, alt }) => (
  <a href={src} target="_blank" rel="noopener noreferrer">
    <img src={src} alt={alt} className="max-w-full rounded-lg my-2 cursor-pointer hover:opacity-90 transition-opacity" />
  </a>
)
```

Click opens image in new tab.

#### Tables

```jsx
table: ({ children }) => (
  <div className="overflow-x-auto my-2">
    <table className="min-w-full border border-gray-200 dark:border-gray-700 text-sm">
      {children}
    </table>
  </div>
),
th: ({ children }) => (
  <th className="border border-gray-200 dark:border-gray-700 px-3 py-1.5 bg-gray-50 dark:bg-gray-800 font-medium text-left">
    {children}
  </th>
),
td: ({ children }) => (
  <td className="border border-gray-200 dark:border-gray-700 px-3 py-1.5">
    {children}
  </td>
)
```

#### Links and File Downloads

```jsx
a: ({ href, children }) => {
  const isLocalFile = href?.startsWith('/media/') && /\.(xlsx|pdf|csv|doc|docx|zip)$/i.test(href);
  if (isLocalFile) {
    return (
      <a href={href} download className="inline-flex items-center gap-1 text-orange-500 hover:underline font-medium">
        {children}
      </a>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-orange-500 hover:underline">
      {children}
    </a>
  );
}
```

File extensions get `download` attribute. Regular links open in new tab.

### What Stays Unchanged

- SSE protocol — no new event types needed
- Orchestrator — LLM generates markdown naturally
- System prompt already says "You may use markdown formatting" for sandbox channel

---

## 3. mcp-coaching Server

### Location

`mcp_servers/coaching/server.py` — FastMCP, STDIO subprocess. Scope: `assistant` only.

### Tools

| Tool | Purpose |
|------|---------|
| `review_vasya_conversations` | Find where Vasya struggled — knowledge gaps, failed answers |
| `suggest_knowledge_update` | Format suggestion for user confirmation (does NOT apply changes) |
| `update_knowledge_base` | Add content to RAG (requires `confirmed=True`) |
| `update_consultant_instructions` | Update Vasya's `consultant_prompt` (requires `confirmed=True`) |
| `get_consultant_prompt` | Read Vasya's current prompt for analysis |

### Tool Signatures

#### review_vasya_conversations

```python
async def review_vasya_conversations(
    client_id: int,
    session_id: str,
    days_back: int = 7,
    min_messages: int = 3,
) -> str:
    """Review Vasya's recent conversations and identify knowledge gaps.
    Finds conversations where Vasya couldn't answer, gave generic responses,
    or escalated unnecessarily.
    Returns list of gaps: [{conversation_id, gap_type, topic, vasya_response_snippet}]."""
```

Logic:
1. Filter `AgentSession` where `channel != 'sandbox'` (Vasya sessions)
2. Read `AgentLog` — look for patterns:
   - Escalations without clear reason
   - Responses containing "I don't have information", "I'm not sure" etc.
   - RAG searches returning 0 results
   - Sessions with high message count but low tool usage
3. Return gap list with conversation context

#### suggest_knowledge_update

```python
async def suggest_knowledge_update(
    client_id: int,
    session_id: str,
    gap_topic: str,
    suggested_content: str,
    update_type: str = "knowledge",  # "knowledge" | "instructions" | "both"
) -> str:
    """Prepare a suggestion for the user. Does NOT apply any changes.
    Returns formatted text for Oleg to present to user for confirmation."""
```

Returns structured suggestion text. Oleg shows this to user and asks "Confirm? (yes/no)".

#### update_knowledge_base

```python
async def update_knowledge_base(
    client_id: int,
    session_id: str,
    title: str,
    content: str,
) -> str:
    """Add content to RAG knowledge base as a new document.
    This tool is gated by orchestrator confirmation — it is NOT exposed
    to the LLM directly. See Confirmation Flow below."""
```

#### update_consultant_instructions

```python
async def update_consultant_instructions(
    client_id: int,
    session_id: str,
    action: str = "append",  # "append" | "replace_section"
    section: str = "",       # for replace_section — which section to replace
    content: str = "",
) -> str:
    """Update Vasya's consultant_prompt in AgentConfig.
    This tool is gated by orchestrator confirmation — it is NOT exposed
    to the LLM directly. See Confirmation Flow below."""
```

### Confirmation Flow (Critical Security)

**Problem:** If `confirmed` is a tool parameter, LLM can trivially pass `True` and bypass user approval.

**Solution:** `update_knowledge_base` and `update_consultant_instructions` are **not exposed to the LLM** in `_tools_to_llm_format()`. Instead, Oleg uses a two-step flow:

1. Oleg calls `suggest_knowledge_update(gap_topic, suggested_content, update_type)` — this is exposed to LLM. It returns a formatted suggestion but applies nothing.
2. The user replies "yes" / "tak" / confirms in chat.
3. Oleg then calls `apply_coaching_suggestion(suggestion_id)` — a new tool that:
   - Looks up the pending suggestion by ID (stored in `AgentSession.metadata['pending_suggestions']`)
   - Only applies if the previous user message in conversation contains affirmative intent
   - Executes the actual `update_knowledge_base` or `update_consultant_instructions` internally

**Orchestrator-side gate:** `apply_coaching_suggestion` checks the conversation history — the message immediately before the tool call must be from `role: user` and contain affirmative text. If not, returns error.

Updated tool table:

| Tool | Exposed to LLM | Purpose |
|------|----------------|---------|
| `review_vasya_conversations` | Yes | Find gaps |
| `suggest_knowledge_update` | Yes | Format suggestion, store as pending |
| `apply_coaching_suggestion` | Yes | Apply pending suggestion (checks user confirmation in conversation) |
| `update_knowledge_base` | No (internal) | Actual RAG write |
| `update_consultant_instructions` | No (internal) | Actual prompt write |
| `get_consultant_prompt` | Yes | Read current prompt |

### Embedding Model Resolution for update_knowledge_base

`update_knowledge_base` creates embeddings via `EmbeddingService.create_embedding()` which requires an `EmbeddingModel` instance. Resolution chain (same as `mcp-rag` server):

```python
client = Client.objects.select_related('embedding_model', 'branch', 'specialization').get(pk=client_id)
agent_config = AgentConfig.objects.select_related('embedding_model').get(client=client)
defaults = PlatformDefaults.get()

# Priority: AgentConfig -> Client -> PlatformDefaults
embedding_model = (
    agent_config.embedding_model
    or client.embedding_model
    or defaults.default_embedding_model
)
```

#### get_consultant_prompt

```python
async def get_consultant_prompt(
    client_id: int,
    session_id: str,
) -> str:
    """Read Vasya's current consultant_prompt from AgentConfig.
    Use before update_consultant_instructions to understand current state."""
```

### Proactive Behavior

Coaching instructions are **dynamically appended** to the assistant prompt (not hardcoded in `DEFAULT_ASSISTANT_PROMPT`), same pattern as leads tool injection. In `_build_system_prompt()`:

```python
if self._has_coaching_tool():
    parts.append(
        "\n\nCOACHING: You can review Vasya's (consultant AI) recent conversations "
        "to find knowledge gaps. When you notice Vasya struggled with a topic, "
        "proactively suggest to the user: 'I noticed Vasya couldn't answer questions "
        "about X. Want me to add this to the knowledge base or update his instructions?'\n"
        "ALWAYS ask for user confirmation before making any changes. "
        "Never apply changes silently."
    )
```

This ensures non-coaching clients don't get confusing coaching instructions in their prompt.

Add helper:

```python
def _has_coaching_tool(self) -> bool:
    return 'coaching' in self._connected_server_names
```

### Settings Registration

```python
'coaching': {
    'command': 'python',
    'args': ['-m', 'mcp_servers.coaching.server'],
    'enabled': True,
},
```

### Seed ToolCard

```python
{
    'slug': 'coaching',
    'name': 'AI Coaching',
    'tagline': 'Train your consultant AI with knowledge and instructions',
    'description': 'Review consultant conversations, identify knowledge gaps, and update knowledge base or consultant instructions with user approval.',
    'icon': 'graduation-cap',
    'category': 'ai',
    'color': '#8b5cf6',
    'transport_type': 'builtin',
    'is_builtin': True,
    'auth_type': 'none',
    'skill_scopes': {'scopes': ['assistant'], 'bidirectional': False},
}
```

---

## 4. Tool-Level Scope Filtering

### Problem

Current `_tools_to_llm_format()` filters by server name (slug matching against `_connected_server_names`). When `email` server is connected for both `assistant` and `manager`, Vasya sees all 6 email tools instead of only `send_commercial_email`.

### Solution: Tool Name Convention + Settings Dict

Avoid `read_resource` (untested over STDIO transport in this codebase). Instead, use a simple settings-based registry:

```python
# settings.py
MCP_TOOL_SCOPES = {
    # tool_name -> list of allowed scopes
    'send_email': ['assistant'],
    'send_email_with_attachment': ['assistant'],
    'read_emails': ['assistant'],
    'search_emails': ['assistant'],
    'analyze_emails': ['assistant'],
    'send_commercial_email': ['manager'],
}
```

### Orchestrator Changes

In `__init__`, add:

```python
self._tool_scopes: dict[str, list[str]] = getattr(settings, 'MCP_TOOL_SCOPES', {})
```

In `_tools_to_llm_format()`, add after server-level filter:

```python
# Existing: server-level filter
if server_name not in self._connected_server_names:
    continue

# NEW: tool-level scope filter
tool_allowed_scopes = self._tool_scopes.get(tool.name)
if tool_allowed_scopes and self._scope not in tool_allowed_scopes:
    continue
```

### Why Settings Instead of MCP Resource

1. `read_resource()` over STDIO has never been used in this codebase — risk of silent failure
2. Settings dict is simple, testable, and explicit
3. Only one server (`email`) needs tool-level scoping — no need for a protocol-level solution
4. If more servers need per-tool scopes later, can migrate to MCP resource approach

### Backward Compatibility

Tools not listed in `MCP_TOOL_SCOPES` — visible to whatever scope the server is connected for. Zero impact on existing servers.

### Coaching Tools Filtering

`update_knowledge_base` and `update_consultant_instructions` are internal tools (not exposed to LLM). They are filtered out by the coaching server's `suggest/apply` flow, not by scope filtering. However, for defense-in-depth, add them to `MCP_TOOL_SCOPES`:

```python
'update_knowledge_base': [],      # never exposed to LLM directly
'update_consultant_instructions': [],  # never exposed to LLM directly
```

Empty list = hidden from all scopes.

---

## 5. Files to Change

| File | Change |
|------|--------|
| `mcp_servers/email/__init__.py` | New |
| `mcp_servers/email/server.py` | New — 6 tools wrapping EmailService |
| `mcp_servers/coaching/__init__.py` | New |
| `mcp_servers/coaching/server.py` | New — 6 tools (3 exposed + 2 internal + 1 apply) |
| `MASTER/clients/email_service.py` | New `send_email_with_attachment()` method |
| `MASTER/agents/orchestrator.py` | Tool-level scope filtering, `_has_coaching_tool()`, dynamic prompt |
| `MASTER/settings.py` | Register email + coaching in MCP_SERVERS + MCP_TOOL_SCOPES |
| `MASTER/tools/seed_data.py` | Add email + coaching ToolCards |
| `nextlen/src/components/sandbox/ChatWindow.jsx` | ReactMarkdown components for tables, images, file links |
| Migration | Seed email + coaching ToolCards |

### ToolConnection Prerequisites

For email to work for both scopes, client `srtyh` must have **two** `ToolConnection` records for the `email` ToolCard:

| tool_card | target | Notes |
|-----------|--------|-------|
| email | assistant | Oleg sees send_email, read_emails, etc. |
| email | manager | Vasya sees send_commercial_email only |

The seed migration creates both connections for `srtyh`. `unique_together = ['client', 'tool_card', 'target']` already supports this.

---

## 6. Seed Migration

New migration that adds `email` and `coaching` ToolCard entries + ToolConnection records for `srtyh`.

**Migration numbering:** verify latest migration number before creating. Currently `0008_multi_connection_scopes.py` exists; check for `0009` before assigning number.

---

## 7. Rollback Safety

- Feature flag `mcp_real_agent` gates everything — disable for instant rollback
- New MCP servers are additive — removing them from `MCP_SERVERS` disables them
- No existing data modified — `consultant_prompt` changes by coaching tool are logged in `AgentLog`
- Markdown rendering changes are cosmetic — no functional impact if reverted

---

## 8. Out of Scope

- Email MCP for non-srtyh clients — future rollout
- Vasya reading emails — only Oleg reads, Vasya sends commercial only
- Automatic coaching without user confirmation — always requires approval
- Email templates UI — Vasya uses hardcoded templates, admin can customize later
- Attachment support for commercial emails — Phase 2 if needed
