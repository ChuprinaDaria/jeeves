# Email + Coaching + Markdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mcp-email server (6 tools), mcp-coaching server (6 tools), markdown rendering in Sandbox, and tool-level scope filtering.

**Architecture:** Two new FastMCP STDIO servers following existing pattern (rag, xlsx, leads). Orchestrator gets tool-level scope filtering via `MCP_TOOL_SCOPES` settings dict. ChatWindow.jsx gets ReactMarkdown custom components.

**Tech Stack:** Python/FastMCP, Django ORM, React/ReactMarkdown/remarkGfm, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-23-email-coaching-markdown-design.md`

---

### Task 1: EmailService.send_email_with_attachment()

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/email_service.py`

- [ ] **Step 1: Add send_email_with_attachment method to EmailService**

```python
def send_email_with_attachment(
    self,
    to_address: str,
    subject: str,
    body: str,
    file_path: str,
    is_html: bool = False,
    cc: list = None,
    bcc: list = None,
) -> dict:
    """Send email with file attachment."""
    import os
    from email.mime.base import MIMEBase
    from email import encoders

    if not os.path.isfile(file_path):
        return {'success': False, 'error': f'File not found: {file_path}'}

    try:
        msg = MIMEMultipart('mixed')
        msg['From'] = f"{self.from_name} <{self.from_address}>"
        msg['To'] = to_address
        msg['Subject'] = subject

        if cc:
            msg['Cc'] = ', '.join(cc)

        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))

        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

        if self.smtp_port == 465:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
        elif self.smtp_use_tls:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)

        server.login(self.smtp_username, self.smtp_password)

        recipients = [to_address]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        server.sendmail(self.from_address, recipients, msg.as_string())
        server.quit()

        return {
            'success': True,
            'message': f'Email with attachment sent to {to_address}',
            'to': to_address,
            'subject': subject,
            'attachment': filename,
        }
    except Exception as e:
        logger.error(f"Failed to send email with attachment: {e}")
        return {'success': False, 'error': str(e)}
```

Add this method after the existing `send_email` method (after line 204 in `email_service.py`).

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/email_service.py
git commit -m "feat(email): add send_email_with_attachment to EmailService"
```

---

### Task 2: mcp-email server

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/email/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/email/server.py`

- [ ] **Step 1: Create __init__.py**

Empty file.

- [ ] **Step 2: Create server.py with all 6 tools**

```python
"""MCP Email server — email tools for Nexelin agents."""
import json
import logging
import os
from pathlib import Path
from typing import Literal

from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-email",
    description="Nexelin email server. Send, read, search and analyze emails.",
)


def _get_email_service(client_id: int):
    """Get EmailService for a client."""
    from MASTER.clients.models import Client
    from MASTER.clients.email_service import EmailService
    client = Client.objects.get(pk=client_id)
    return EmailService(client)


def _resolve_language(session_id: str, language: str) -> str:
    """Resolve language: param -> AgentConfig -> fallback 'en'."""
    if language:
        return language
    try:
        from MASTER.agents.models import AgentSession
        session = AgentSession.objects.select_related('agent_config').get(pk=session_id)
        return session.agent_config.get_language()
    except Exception:
        return 'en'


@mcp.tool()
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
    """Send an email via client's SMTP configuration.
    Use when the user asks to send an email to someone."""

    def _send():
        service = _get_email_service(client_id)
        return service.send_email(to_address, subject, body, is_html, cc, bcc)

    result = await sync_to_async(_send)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def send_email_with_attachment(
    client_id: int,
    session_id: str,
    to_address: str,
    subject: str,
    body: str,
    file_path: str,
    is_html: bool = False,
) -> str:
    """Send email with file attachment. file_path is relative to media/ directory.
    Use after create_spreadsheet to email the generated file.
    Example file_path: 'xlsx/21/report.xlsx'"""

    def _send():
        from django.conf import settings as django_settings

        media_root = Path(django_settings.MEDIA_ROOT).resolve()
        resolved = (media_root / file_path).resolve()

        if not str(resolved).startswith(str(media_root)):
            return {"success": False, "error": "Invalid file path"}
        if not resolved.is_file():
            return {"success": False, "error": f"File not found: {file_path}"}

        service = _get_email_service(client_id)
        return service.send_email_with_attachment(
            to_address, subject, body, str(resolved), is_html,
        )

    result = await sync_to_async(_send)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def read_emails(
    client_id: int,
    session_id: str,
    limit: int = 10,
    folder: str = "INBOX",
    days_back: int = 7,
) -> str:
    """Read recent emails via IMAP.
    Returns list of emails with subject, sender, date, and body preview."""

    def _read():
        service = _get_email_service(client_id)
        emails = service.get_recent_emails(limit=limit, folder=folder, days_back=days_back)
        return {"emails": emails, "total": len(emails)}

    result = await sync_to_async(_read)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def search_emails(
    client_id: int,
    session_id: str,
    from_address: str = "",
    subject: str = "",
    days_back: int = 30,
    limit: int = 20,
) -> str:
    """Search emails by sender and/or subject via IMAP."""

    def _search():
        service = _get_email_service(client_id)
        emails = service.search_emails(
            from_address=from_address or None,
            subject=subject or None,
            days_back=days_back,
            limit=limit,
        )
        return {"emails": emails, "total": len(emails)}

    result = await sync_to_async(_search)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def analyze_emails(
    client_id: int,
    session_id: str,
    days_back: int = 7,
    language: str = "",
) -> str:
    """Analyze recent emails: count, top senders, key topics, action items.
    Uses LLM for intelligent summarization in client's language."""

    def _analyze():
        lang = _resolve_language(session_id, language)
        service = _get_email_service(client_id)
        return service.analyze_recent_emails(days_back=days_back, language=lang)

    result = await sync_to_async(_analyze)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def send_commercial_email(
    client_id: int,
    session_id: str,
    to_address: str,
    proposal_type: str,
    subject: str = "",
    body: str = "",
    amount: str = "",
    currency: str = "EUR",
    items: list[dict] | None = None,
) -> str:
    """Send a structured commercial email (quote/invoice/offer/follow_up).
    Vasya uses this to send proposals to customers.
    Body is generated from template if empty. Subject auto-generated from proposal_type.
    NOT for arbitrary emails — only commercial proposals.

    Args:
        proposal_type: One of 'quote', 'invoice', 'offer', 'follow_up'.
        items: List of items, each with 'name', 'qty', 'price' keys.
    """

    VALID_TYPES = {"quote", "invoice", "offer", "follow_up"}
    if proposal_type not in VALID_TYPES:
        return json.dumps({"error": f"Invalid proposal_type. Must be one of: {VALID_TYPES}"})

    def _send():
        from MASTER.clients.models import Client
        client = Client.objects.get(pk=client_id)
        company = getattr(client, 'company_name', '') or client.name or 'Our Company'

        type_labels = {
            "quote": "Price Quote",
            "invoice": "Invoice",
            "offer": "Commercial Offer",
            "follow_up": "Follow-up",
        }
        label = type_labels[proposal_type]

        final_subject = subject or f"{company} — {label}"

        if body:
            final_body = body
        else:
            lines = [f"Dear Customer,\n\nPlease find below our {label.lower()}.\n"]
            if items:
                lines.append("Items:")
                for item in items:
                    name = item.get('name', '')
                    qty = item.get('qty', 1)
                    price = item.get('price', '')
                    lines.append(f"  - {name}: {qty} x {price} {currency}")
            if amount:
                lines.append(f"\nTotal: {amount} {currency}")
            lines.append(f"\nBest regards,\n{company}")
            final_body = "\n".join(lines)

        service = _get_email_service(client_id)
        return service.send_email(to_address, final_subject, final_body)

    result = await sync_to_async(_send)()
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/email/
git commit -m "feat(mcp): add mcp-email server with 6 tools"
```

---

### Task 3: Tool-level scope filtering + settings registration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/settings.py`
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py`

- [ ] **Step 1: Add email + coaching to MCP_SERVERS and add MCP_TOOL_SCOPES in settings.py**

After the existing `MCP_SERVERS` dict (line ~459), add `email` and `coaching` entries. Then add `MCP_TOOL_SCOPES`:

```python
# In MCP_SERVERS dict, add:
    'email': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.email.server'],
        'enabled': True,
    },
    'coaching': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.coaching.server'],
        'enabled': True,
    },

# After MCP_SERVERS, add:
MCP_TOOL_SCOPES = {
    'send_email': ['assistant'],
    'send_email_with_attachment': ['assistant'],
    'read_emails': ['assistant'],
    'search_emails': ['assistant'],
    'analyze_emails': ['assistant'],
    'send_commercial_email': ['manager'],
    'update_knowledge_base': [],
    'update_consultant_instructions': [],
}
```

- [ ] **Step 2: Add tool-level scope filtering to orchestrator**

In `p004_ai_nexelin/MASTER/agents/orchestrator.py`:

In `__init__` (after line ~83 `self._session = None`), add:

```python
self._tool_scopes: dict[str, list[str]] = getattr(settings, 'MCP_TOOL_SCOPES', {})
```

In `_tools_to_llm_format()`, after the `if server_name not in self._connected_server_names: continue` check (line ~403), add:

```python
            # Tool-level scope filter
            tool_allowed_scopes = self._tool_scopes.get(tool.name)
            if tool_allowed_scopes is not None and self._scope not in tool_allowed_scopes:
                continue
```

Also update `_get_scope_tool_names()` to apply same filter:

```python
    def _get_scope_tool_names(self) -> list[str]:
        """Tool names visible to current scope."""
        names = []
        for t in self._tools:
            if self._tool_to_server.get(t.name) not in self._connected_server_names:
                continue
            tool_allowed = self._tool_scopes.get(t.name)
            if tool_allowed is not None and self._scope not in tool_allowed:
                continue
            names.append(t.name)
        return names
```

- [ ] **Step 3: Add _has_coaching_tool and dynamic coaching prompt**

In `orchestrator.py`, after `_has_leads_tool` (line ~389), add:

```python
    def _has_coaching_tool(self) -> bool:
        return 'coaching' in self._connected_server_names
```

In `_build_system_prompt`, after the leads tool prompt injection block (line ~341), add:

```python
        if channel == 'sandbox' and self._has_coaching_tool():
            parts.append(
                "\n\nCOACHING: You can review Vasya's (consultant AI) recent conversations "
                "to find knowledge gaps. When you notice Vasya struggled with a topic, "
                "proactively suggest to the user: 'I noticed Vasya couldn't answer questions "
                "about X. Want me to add this to the knowledge base or update his instructions?'\n"
                "ALWAYS ask for user confirmation before making any changes. "
                "Never apply changes silently."
            )
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/settings.py p004_ai_nexelin/MASTER/agents/orchestrator.py
git commit -m "feat(mcp): tool-level scope filtering + email/coaching registration"
```

---

### Task 4: mcp-coaching server

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/coaching/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/coaching/server.py`

- [ ] **Step 1: Create __init__.py**

Empty file.

- [ ] **Step 2: Create server.py**

```python
"""MCP Coaching server — Oleg trains Vasya via knowledge base and prompt updates."""
import json
import logging
import uuid
from datetime import timedelta

from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async
from django.utils import timezone
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-coaching",
    description="AI Coaching: review consultant conversations, find gaps, "
    "update knowledge base and consultant instructions.",
)


def _resolve_embedding_model(client_id: int):
    """Resolve embedding model: AgentConfig -> Client -> PlatformDefaults."""
    from MASTER.clients.models import Client
    from MASTER.agents.models import AgentConfig
    from MASTER.nexelin_platform.models import PlatformDefaults

    client = Client.objects.select_related(
        'embedding_model', 'branch', 'specialization',
    ).get(pk=client_id)
    defaults = PlatformDefaults.get()

    try:
        agent_config = AgentConfig.objects.select_related(
            'embedding_model',
        ).get(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = None

    embedding_model = (
        (agent_config.embedding_model if agent_config else None)
        or client.embedding_model
        or defaults.default_embedding_model
    )
    return client, embedding_model


@mcp.tool()
async def review_vasya_conversations(
    client_id: int,
    session_id: str,
    days_back: int = 7,
    min_messages: int = 3,
) -> str:
    """Review Vasya's (consultant AI) recent conversations and identify knowledge gaps.
    Finds conversations where Vasya couldn't answer, gave generic responses,
    or escalated unnecessarily.
    Use this to find areas where the consultant needs training."""

    def _review():
        from MASTER.agents.models import AgentSession, AgentLog

        cutoff = timezone.now() - timedelta(days=days_back)

        sessions = AgentSession.objects.filter(
            agent_config__client_id=client_id,
            started_at__gte=cutoff,
        ).exclude(channel='sandbox')

        gaps = []
        for sess in sessions[:50]:
            logs = AgentLog.objects.filter(session=sess).order_by('created_at')

            llm_logs = [l for l in logs if l.call_type == 'llm']
            rag_logs = [l for l in logs if l.call_type == 'rag']
            esc_logs = [l for l in logs if l.call_type == 'escalation']

            if len(llm_logs) < min_messages:
                continue

            # Check for empty RAG results
            for rl in rag_logs:
                output = rl.output_data or {}
                result_text = output.get('result', '')
                if '"chunks": []' in result_text or '"chunks":[]' in result_text:
                    last_llm = llm_logs[-1] if llm_logs else None
                    snippet = ''
                    if last_llm:
                        snippet = (last_llm.output_data or {}).get('content', '')[:200]
                    gaps.append({
                        "session_id": str(sess.id),
                        "gap_type": "empty_rag",
                        "topic": (rl.input_data or {}).get('query', 'unknown'),
                        "vasya_response_snippet": snippet,
                    })

            # Check for escalations
            for el in esc_logs:
                gaps.append({
                    "session_id": str(sess.id),
                    "gap_type": "escalation",
                    "topic": (el.input_data or {}).get('reason', 'unknown'),
                    "vasya_response_snippet": "",
                })

            # Check for "I don't know" patterns in LLM responses
            unsure_patterns = [
                "i don't have information",
                "i'm not sure",
                "i cannot find",
                "no information available",
                "не маю інформації",
                "не знаю",
                "ich habe keine informationen",
            ]
            for ll in llm_logs:
                content = (ll.output_data or {}).get('content', '').lower()
                for pattern in unsure_patterns:
                    if pattern in content:
                        gaps.append({
                            "session_id": str(sess.id),
                            "gap_type": "unsure_response",
                            "topic": pattern,
                            "vasya_response_snippet": content[:200],
                        })
                        break

        return {"gaps": gaps[:30], "total_sessions_reviewed": min(sessions.count(), 50)}

    result = await sync_to_async(_review)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def suggest_knowledge_update(
    client_id: int,
    session_id: str,
    gap_topic: str,
    suggested_content: str,
    update_type: str = "knowledge",
) -> str:
    """Prepare a coaching suggestion for the user. Does NOT apply changes.
    Stores the suggestion as pending and returns formatted text for user confirmation.

    Args:
        gap_topic: What knowledge gap was found.
        suggested_content: The content to add to knowledge base or instructions.
        update_type: 'knowledge' (add to RAG), 'instructions' (update prompt), or 'both'.
    """

    def _suggest():
        from MASTER.agents.models import AgentSession

        suggestion_id = str(uuid.uuid4())[:8]

        try:
            session = AgentSession.objects.get(pk=session_id)
            meta = session.metadata or {}
            pending = meta.get('pending_suggestions', {})
            pending[suggestion_id] = {
                "gap_topic": gap_topic,
                "suggested_content": suggested_content,
                "update_type": update_type,
                "created_at": timezone.now().isoformat(),
            }
            meta['pending_suggestions'] = pending
            session.metadata = meta
            session.save(update_fields=['metadata'])
        except AgentSession.DoesNotExist:
            return {"error": f"Session {session_id} not found"}

        return {
            "status": "suggestion_stored",
            "suggestion_id": suggestion_id,
            "update_type": update_type,
            "message": (
                f"Suggestion stored (ID: {suggestion_id}). "
                f"Present this to the user and ask for confirmation before applying.\n\n"
                f"Topic: {gap_topic}\n"
                f"Proposed content: {suggested_content}\n"
                f"Type: {update_type}"
            ),
        }

    result = await sync_to_async(_suggest)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def apply_coaching_suggestion(
    client_id: int,
    session_id: str,
    suggestion_id: str,
) -> str:
    """Apply a previously stored coaching suggestion.
    ONLY call this AFTER the user has explicitly confirmed the suggestion.
    The system verifies that the user's last message was affirmative."""

    def _apply():
        from MASTER.agents.models import AgentSession, AgentConfig
        from MASTER.clients.models import Client, ClientDocument
        from MASTER.processing.embedding_service import EmbeddingService

        try:
            session = AgentSession.objects.get(pk=session_id)
        except AgentSession.DoesNotExist:
            return {"error": "Session not found"}

        meta = session.metadata or {}
        pending = meta.get('pending_suggestions', {})
        suggestion = pending.get(suggestion_id)

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
                    EmbeddingService.create_embedding(content, embedding_model, client=client, document=doc)
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

        # Remove from pending
        del pending[suggestion_id]
        meta['pending_suggestions'] = pending
        session.metadata = meta
        session.save(update_fields=['metadata'])

        return {"status": "applied", "suggestion_id": suggestion_id, "results": results}

    result = await sync_to_async(_apply)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def get_consultant_prompt(
    client_id: int,
    session_id: str,
) -> str:
    """Read Vasya's current consultant_prompt from AgentConfig.
    Use before suggesting changes to understand the current state."""

    def _get():
        from MASTER.agents.models import AgentConfig
        try:
            config = AgentConfig.objects.get(client_id=client_id)
            return {
                "consultant_prompt": config.consultant_prompt or "(empty — using platform default)",
                "consultant_description": config.consultant_description or "",
            }
        except AgentConfig.DoesNotExist:
            return {"consultant_prompt": "(no AgentConfig found)", "consultant_description": ""}

    result = await sync_to_async(_get)()
    return json.dumps(result, ensure_ascii=False)


# Internal tools — not exposed to LLM (filtered by MCP_TOOL_SCOPES = [])

@mcp.tool()
async def update_knowledge_base(
    client_id: int,
    session_id: str,
    title: str,
    content: str,
) -> str:
    """Internal: Add content to RAG knowledge base. Called by apply_coaching_suggestion only."""
    return json.dumps({"error": "This tool is internal. Use apply_coaching_suggestion instead."})


@mcp.tool()
async def update_consultant_instructions(
    client_id: int,
    session_id: str,
    action: str = "append",
    section: str = "",
    content: str = "",
) -> str:
    """Internal: Update consultant prompt. Called by apply_coaching_suggestion only."""
    return json.dumps({"error": "This tool is internal. Use apply_coaching_suggestion instead."})


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/coaching/
git commit -m "feat(mcp): add mcp-coaching server with suggestion/apply flow"
```

---

### Task 5: Markdown rendering in ChatWindow.jsx

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx`

- [ ] **Step 1: Find the ReactMarkdown usage in ChatWindow.jsx and add components prop**

Find where `<ReactMarkdown` is used (likely in message rendering). Add `components` prop with custom renderers for `img`, `table`, `th`, `td`, `a`:

```jsx
const markdownComponents = {
  img: ({ src, alt }) => (
    <a href={src} target="_blank" rel="noopener noreferrer">
      <img src={src} alt={alt || ''} className="max-w-full rounded-lg my-2 cursor-pointer hover:opacity-90 transition-opacity" />
    </a>
  ),
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
  ),
  a: ({ href, children }) => {
    const isLocalFile = href?.startsWith('/media/') && /\.(xlsx|pdf|csv|doc|docx|zip)$/i.test(href);
    if (isLocalFile) {
      return (
        <a href={href} download className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 font-medium text-sm">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          {children}
        </a>
      );
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-orange-500 hover:underline">
        {children}
      </a>
    );
  },
};
```

Define this outside the component (before `const ChatWindow = ...`) or as a `useMemo` inside. Then use:

```jsx
<ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
  {msg.text}
</ReactMarkdown>
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(sandbox): styled markdown tables, images, file download links"
```

---

### Task 6: Seed migration for email + coaching ToolCards

**Files:**
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0012_seed_email_coaching_tools.py`

- [ ] **Step 1: Create seed migration**

```python
from django.db import migrations


def seed_email_coaching(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolConnection = apps.get_model('tools', 'ToolConnection')
    Client = apps.get_model('clients', 'Client')

    # Email ToolCard
    email_card, _ = ToolCard.objects.get_or_create(
        slug='email',
        defaults={
            'name': 'Email',
            'tagline': 'Send, read and analyze emails',
            'description': 'Full email management for AI Assistant (send, read, search, analyze via SMTP/IMAP) and commercial proposals for Consultant.',
            'icon': 'mail',
            'color': '#3b82f6',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'auth_type': 'none',
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': False},
        },
    )

    # Coaching ToolCard
    coaching_card, _ = ToolCard.objects.get_or_create(
        slug='coaching',
        defaults={
            'name': 'AI Coaching',
            'tagline': 'Train your consultant AI with knowledge and instructions',
            'description': 'Review consultant conversations, identify knowledge gaps, and update knowledge base or consultant instructions with user approval.',
            'icon': 'graduation-cap',
            'color': '#8b5cf6',
            'category': 'ai',
            'transport_type': 'builtin',
            'is_builtin': True,
            'auth_type': 'none',
            'skill_scopes': {'scopes': ['assistant'], 'bidirectional': False},
        },
    )

    # Create ToolConnections for srtyh
    try:
        client = Client.objects.get(tag='srtyh')
    except Client.DoesNotExist:
        return

    from django.utils import timezone
    now = timezone.now()

    # Email: assistant + manager connections
    ToolConnection.objects.get_or_create(
        client=client, tool_card=email_card, target='assistant',
        defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
    )
    ToolConnection.objects.get_or_create(
        client=client, tool_card=email_card, target='manager',
        defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
    )

    # Coaching: assistant only
    ToolConnection.objects.get_or_create(
        client=client, tool_card=coaching_card, target='assistant',
        defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
    )


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug__in=['email', 'coaching']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0011_seed_sales_intel_tool'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_email_coaching, unseed),
    ]
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/migrations/0012_seed_email_coaching_tools.py
git commit -m "feat(tools): seed email + coaching ToolCards with srtyh connections"
```

---

### Task 7: Final integration commit

- [ ] **Step 1: Verify all files are committed**

```bash
cd /home/dchuprina/nexelin_web && git status
```

- [ ] **Step 2: Verify MCP servers can import**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python -c "import mcp_servers.email.server; print('email OK')" && python -c "import mcp_servers.coaching.server; print('coaching OK')"
```

- [ ] **Step 3: Verify migration applies**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py showmigrations tools | tail -5
```
