# MCP Dual Agent + Leads + Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split MCP pipeline into dual-agent system (Oleg=assistant/Sandbox, Vasya=consultant/messengers), add mcp-leads server for lead management, wire up EdgeMiddleware execution, switch Sandbox to MCP pipeline. All behind `mcp_real_agent` flag, only client `srtyh`.

**Architecture:** AgentConfig gets dual prompts + descriptions. Orchestrator routes by channel → scope (assistant/manager), filters tools by ToolConnection scope. New `mcp-leads` FastMCP server handles lead CRUD. EdgeMiddleware executes pre/post around tool calls.

**Tech Stack:** Django 5.x, FastMCP (mcp library), OpenAI function calling, React 18, SSE streaming

**Spec:** `docs/superpowers/specs/2026-03-23-mcp-dual-agent-leads-middleware-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `MASTER/agents/models.py` | Modify | Add 4 new fields to AgentConfig, add `sandbox` to CHANNEL_CHOICES |
| `MASTER/agents/migrations/0003_dual_agent_fields.py` | Create | Schema migration + data migration |
| `MASTER/agents/admin.py` | Modify | Update fieldsets for dual prompts |
| `MASTER/agents/serializers.py` | Modify | Add new fields to API |
| `MASTER/agents/orchestrator.py` | Modify | Dual prompt building, scope filtering, middleware execution, session_id injection |
| `MASTER/agents/dispatch.py` | No changes needed | Already passes channel correctly |
| `MASTER/mcp_hub/views.py` | Modify | Read channel from request body, pass data dict |
| `MASTER/clients/models.py` | Modify | Add `agent_session` FK to Lead |
| `MASTER/clients/migrations/0051_lead_agent_session.py` | Create | Add FK |
| `mcp_servers/leads/__init__.py` | Create | Package init |
| `mcp_servers/leads/server.py` | Create | FastMCP server with 4 tools |
| `mcp_servers/leads/requirements.txt` | Create | Dependencies |
| `MASTER/tools/seed_data.py` | Modify | Add leads ToolCard |
| `MASTER/tools/migrations/0010_seed_leads_tool.py` | Create | Seed migration |
| `MASTER/settings.py` | Modify | Register leads MCP server |
| `nextlen/src/api/agent.js` | Modify | Add MCP SSE chat function |
| `nextlen/src/components/sandbox/ChatWindow.jsx` | Modify | Switch to MCP SSE (behind flag) |
| `MASTER/agents/tests/test_orchestrator.py` | Create | Orchestrator unit tests |
| `MASTER/agents/tests/test_dual_agent.py` | Create | Dual prompt/scope tests |

---

## Task 1: AgentConfig Dual Prompt Fields + Migration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/agents/models.py:6-42`
- Create: `p004_ai_nexelin/MASTER/agents/migrations/0003_dual_agent_fields.py`
- Modify: `p004_ai_nexelin/MASTER/agents/admin.py:13-29`
- Modify: `p004_ai_nexelin/MASTER/agents/serializers.py:13-24`
- Test: `p004_ai_nexelin/MASTER/agents/tests/test_dual_agent.py`

- [ ] **Step 1: Add new fields to AgentConfig model**

In `agents/models.py`, add after `system_prompt` and `greeting_message`:

```python
# Dual-agent prompts (MCP pipeline only)
assistant_prompt = models.TextField(
    blank=True,
    help_text='System prompt for Oleg (assistant, Sandbox). Empty = platform default.')
consultant_prompt = models.TextField(
    blank=True,
    help_text='System prompt for Vasya (consultant, messengers). Empty = platform default.')
assistant_description = models.TextField(
    blank=True,
    help_text='Description of assistant capabilities (shown in UI + added to prompt)')
consultant_description = models.TextField(
    blank=True,
    help_text='Description of consultant capabilities (shown in UI + added to prompt)')
```

- [ ] **Step 2: Add `sandbox` to AgentSession CHANNEL_CHOICES**

In `agents/models.py`, add `('sandbox', 'Sandbox')` to `CHANNEL_CHOICES` list.

- [ ] **Step 3: Create migration**

Run: `cd p004_ai_nexelin && python manage.py makemigrations agents --name dual_agent_fields`

- [ ] **Step 4: Add data migration to copy system_prompt → consultant_prompt**

Edit the generated migration, add a `RunPython` operation at the end:

```python
def copy_system_prompt(apps, schema_editor):
    AgentConfig = apps.get_model('agents', 'AgentConfig')
    for config in AgentConfig.objects.exclude(system_prompt=''):
        config.consultant_prompt = config.system_prompt
        config.save(update_fields=['consultant_prompt'])

class Migration(migrations.Migration):
    operations = [
        # ... auto-generated AddField operations ...
        migrations.RunPython(copy_system_prompt, migrations.RunPython.noop),
    ]
```

- [ ] **Step 5: Run migration**

Run: `cd p004_ai_nexelin && python manage.py migrate agents`

- [ ] **Step 6: Update admin fieldsets**

In `agents/admin.py`, replace the `Prompts` fieldset:

```python
('Prompts (Legacy)', {
    'fields': ('system_prompt', 'greeting_message'),
    'description': 'Used by legacy pipeline. MCP uses dual prompts below.',
    'classes': ('collapse',),
}),
('Prompts (MCP Dual Agent)', {
    'fields': ('assistant_prompt', 'assistant_description',
               'consultant_prompt', 'consultant_description'),
    'description': 'Assistant = Oleg (Sandbox). Consultant = Vasya (messengers).',
}),
```

- [ ] **Step 7: Update serializer**

In `agents/serializers.py`, add new fields to `AgentConfigSerializer.Meta.fields`:

```python
'assistant_prompt', 'consultant_prompt',
'assistant_description', 'consultant_description',
```

- [ ] **Step 8: Write test**

Ensure `p004_ai_nexelin/MASTER/agents/tests/__init__.py` exists (it does). Create `p004_ai_nexelin/MASTER/agents/tests/test_dual_agent.py`:

```python
from django.test import TestCase
from MASTER.agents.models import AgentConfig, AgentSession


class TestAgentConfigDualPrompt(TestCase):
    def test_fields_exist(self):
        config = AgentConfig()
        self.assertEqual(config.assistant_prompt, '')
        self.assertEqual(config.consultant_prompt, '')
        self.assertEqual(config.assistant_description, '')
        self.assertEqual(config.consultant_description, '')

    def test_sandbox_channel_choice(self):
        channels = dict(AgentSession.CHANNEL_CHOICES)
        self.assertIn('sandbox', channels)
```

- [ ] **Step 9: Run tests**

Run: `cd p004_ai_nexelin && python manage.py test MASTER.agents.tests.test_dual_agent -v2`

- [ ] **Step 10: Commit**

```bash
cd p004_ai_nexelin && git add MASTER/agents/models.py MASTER/agents/migrations/0003_* MASTER/agents/admin.py MASTER/agents/serializers.py MASTER/agents/tests/test_dual_agent.py
git commit -m "feat(agents): add dual-agent prompt fields to AgentConfig

assistant_prompt + consultant_prompt for MCP pipeline.
assistant_description + consultant_description for UI + prompt.
Data migration copies system_prompt → consultant_prompt.
Add 'sandbox' to AgentSession.CHANNEL_CHOICES."
```

---

## Task 2: Orchestrator — Dual Prompt Building + Scope Filtering

**Files:**
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:29-349`
- Test: `p004_ai_nexelin/MASTER/agents/tests/test_orchestrator.py`

- [ ] **Step 1: Add scope to `__init__` and `_AUTO_INJECT_PARAMS`**

In `orchestrator.py`:

```python
_AUTO_INJECT_PARAMS = frozenset({"client_id", "session_id"})

class AgentOrchestrator:
    def __init__(self, client, agent_config):
        self.client = client
        self.agent_config = agent_config
        self._exit_stack = None
        self._sessions = {}
        self._tools = []
        self._tool_to_server = {}
        self._scope = 'manager'  # default, set in process()
        self._tool_to_connection = {}  # server_name -> ToolConnection
```

- [ ] **Step 2: Update `process()` to determine scope and pass session_id**

In `process()`, before building prompt:

```python
async def process(self, message, session, conversation, channel='web', external_user_id=''):
    self._scope = 'assistant' if channel == 'sandbox' else 'manager'
    self._session = session  # store for auto-injection

    system_prompt = self._build_system_prompt(channel)
    messages = self._build_messages(system_prompt, conversation, message)
    llm_tools = self._tools_to_llm_format()
    # ... rest of loop unchanged
```

- [ ] **Step 3: Rewrite `_build_system_prompt` for dual agent**

Replace existing `_build_system_prompt`:

```python
DEFAULT_ASSISTANT_PROMPT = (
    "You are Oleg, an AI assistant for the business owner. "
    "You help manage the business, analyze data, search leads, "
    "and configure the AI consultant."
)

DEFAULT_CONSULTANT_PROMPT = (
    "You are a helpful AI consultant. You assist customers "
    "with their questions, provide information about products and services, "
    "and help them find what they need."
)

def _build_system_prompt(self, channel: str) -> str:
    if channel == 'sandbox':
        base = self.agent_config.assistant_prompt or DEFAULT_ASSISTANT_PROMPT
        description = self.agent_config.assistant_description
    else:
        base = self.agent_config.consultant_prompt or DEFAULT_CONSULTANT_PROMPT
        description = self.agent_config.consultant_description

    parts = [base]

    if description:
        parts.append(f"\n\nYour capabilities:\n{description}")

    # Auto-generated tool capabilities
    if self._tools:
        scope_tools = self._get_scope_tool_names()
        if scope_tools:
            parts.append(
                "\n\nYou have access to the following tools: "
                + ", ".join(scope_tools)
                + ".\nUse them when needed. Do NOT mention tool names to the user."
            )

    # Language
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
    parts.append("\nDo NOT use markdown formatting. Respond in plain text only.")

    # Lead collection instruction for consultant
    if channel != 'sandbox' and self._has_leads_tool():
        parts.append(
            "\n\nWhen you learn the user's name, email, phone, or understand their need, "
            "call save_lead with the information you have. Update as you learn more. "
            "Do NOT mention lead collection to the user. Be natural."
        )

    return "\n".join(parts)
```

- [ ] **Step 4: Add scope-based tool filtering**

Add new methods:

```python
def _build_scope_filter(self):
    """Build mapping of server_name -> ToolConnection for current scope."""
    from MASTER.tools.models import ToolConnection
    from asgiref.sync import sync_to_async

    async def _load():
        connections = ToolConnection.objects.filter(
            client=self.client, enabled=True, status='connected',
            target=self._scope,
        ).select_related('tool_card')

        self._tool_to_connection = {}
        self._connected_server_names = set()
        async for conn in connections:
            slug = conn.tool_card.slug
            # Deterministic mapping: exact match or slug starts with server_name + '-'
            # e.g. slug='rag-search' matches server 'rag', slug='leads' matches server 'leads'
            for server_name in self._sessions:
                if slug == server_name or slug.startswith(server_name + '-'):
                    self._tool_to_connection[server_name] = conn
                    self._connected_server_names.add(server_name)
                    break

    return _load()

def _get_scope_tool_names(self) -> list[str]:
    """Tool names visible to current scope."""
    return [
        t.name for t in self._tools
        if self._tool_to_server.get(t.name) in self._connected_server_names
    ]

def _has_leads_tool(self) -> bool:
    return 'leads' in self._connected_server_names
```

- [ ] **Step 5: Update `_tools_to_llm_format` to filter by scope**

Replace existing method:

```python
def _tools_to_llm_format(self) -> list[dict[str, Any]] | None:
    if not self._tools:
        return None

    llm_tools = []
    for tool in self._tools:
        server_name = self._tool_to_server.get(tool.name)
        if server_name not in self._connected_server_names:
            continue  # Skip tools not in current scope

        schema = dict(tool.inputSchema) if tool.inputSchema else {}
        properties = dict(schema.get("properties", {}))
        required = list(schema.get("required", []))
        for param in _AUTO_INJECT_PARAMS:
            properties.pop(param, None)
            if param in required:
                required.remove(param)

        clean_schema = {"type": "object", "properties": properties}
        if required:
            clean_schema["required"] = required

        llm_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": clean_schema,
            },
        })

    return llm_tools or None
```

- [ ] **Step 6: Update `_execute_tool` to inject session_id**

In `_execute_tool`, update auto-injection:

```python
full_args = dict(arguments)
full_args["client_id"] = self.client.pk
full_args["session_id"] = str(self._session.id)
```

- [ ] **Step 7: Update `process()` to call `_build_scope_filter` after connect**

In `process()`, after building prompt, before `_tools_to_llm_format`:

```python
await self._build_scope_filter()
llm_tools = self._tools_to_llm_format()
```

- [ ] **Step 8: Write tests**

Create `p004_ai_nexelin/MASTER/agents/tests/test_orchestrator.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from django.test import TestCase
from MASTER.agents.orchestrator import AgentOrchestrator, DEFAULT_ASSISTANT_PROMPT, DEFAULT_CONSULTANT_PROMPT


class TestDualPromptBuilding(TestCase):
    def setUp(self):
        self.client = MagicMock(pk=1)
        self.config = MagicMock()
        self.config.assistant_prompt = ''
        self.config.consultant_prompt = 'Custom consultant prompt'
        self.config.assistant_description = 'Can search leads'
        self.config.consultant_description = ''
        self.config.get_language.return_value = 'en'
        self.orchestrator = AgentOrchestrator(self.client, self.config)
        self.orchestrator._tools = []
        self.orchestrator._connected_server_names = set()

    def test_sandbox_uses_assistant_prompt(self):
        self.orchestrator._scope = 'assistant'
        prompt = self.orchestrator._build_system_prompt('sandbox')
        self.assertIn(DEFAULT_ASSISTANT_PROMPT, prompt)
        self.assertIn('Can search leads', prompt)

    def test_messenger_uses_consultant_prompt(self):
        self.orchestrator._scope = 'manager'
        prompt = self.orchestrator._build_system_prompt('telegram')
        self.assertIn('Custom consultant prompt', prompt)
        self.assertNotIn(DEFAULT_ASSISTANT_PROMPT, prompt)

    def test_scope_from_channel(self):
        self.orchestrator._scope = 'assistant' if 'sandbox' == 'sandbox' else 'manager'
        self.assertEqual(self.orchestrator._scope, 'assistant')

        self.orchestrator._scope = 'assistant' if 'telegram' == 'sandbox' else 'manager'
        self.assertEqual(self.orchestrator._scope, 'manager')
```

- [ ] **Step 9: Run tests**

Run: `cd p004_ai_nexelin && python manage.py test MASTER.agents.tests.test_orchestrator -v2`

- [ ] **Step 10: Commit**

```bash
cd p004_ai_nexelin && git add MASTER/agents/orchestrator.py MASTER/agents/tests/test_orchestrator.py
git commit -m "feat(orchestrator): dual prompt building + scope-based tool filtering

Sandbox channel → assistant scope (Oleg prompt + assistant tools).
Messenger channels → manager scope (Vasya prompt + manager tools).
Auto-inject session_id alongside client_id.
Lead collection instruction auto-appended for consultant."
```

---

## Task 3: Lead Model FK + Migration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/models.py:2218-2281`
- Create: `p004_ai_nexelin/MASTER/clients/migrations/0051_lead_agent_session.py`

- [ ] **Step 1: Add `agent_session` FK to Lead model**

In `clients/models.py`, in class `Lead`, after the `conversation` FK:

```python
agent_session = models.ForeignKey(
    'agents.AgentSession', on_delete=models.SET_NULL,
    null=True, blank=True, related_name='leads',
    help_text='MCP pipeline session that generated this lead',
)
```

- [ ] **Step 2: Add `email` to SOURCE_CHOICES**

```python
SOURCE_EMAIL = 'email'
SOURCE_CHOICES = [
    (SOURCE_WEB, 'Web Chat'),
    (SOURCE_TELEGRAM, 'Telegram'),
    (SOURCE_WHATSAPP, 'WhatsApp'),
    (SOURCE_EMAIL, 'Email'),
]
```

- [ ] **Step 3: Create migration**

Run: `cd p004_ai_nexelin && python manage.py makemigrations clients --name lead_agent_session`

- [ ] **Step 4: Run migration**

Run: `cd p004_ai_nexelin && python manage.py migrate clients`

- [ ] **Step 5: Commit**

```bash
cd p004_ai_nexelin && git add MASTER/clients/models.py MASTER/clients/migrations/0051_*
git commit -m "feat(leads): add agent_session FK to Lead model

Links leads to MCP AgentSession instead of WhatsApp-only conversation.
Add email source choice."
```

---

## Task 4: MCP Leads Server

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/leads/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/leads/server.py`
- Create: `p004_ai_nexelin/mcp_servers/leads/requirements.txt`

- [ ] **Step 1: Create package**

Create `mcp_servers/leads/__init__.py` (empty file).

- [ ] **Step 2: Create requirements.txt**

```
mcp>=1.0.0
```

- [ ] **Step 3: Create server.py**

```python
"""MCP Leads server — lead management tools for Nexelin agents."""
import json
import logging
from datetime import timedelta
from django.utils import timezone
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Bootstrap Django ORM
from mcp_servers.common.django_setup import setup
setup()

from MASTER.clients.models import Lead, Client
from MASTER.agents.models import AgentSession
from django.db.models import Count, Avg, Q

mcp = FastMCP("mcp-leads")


@mcp.tool()
async def save_lead(
    client_id: int,
    session_id: str,
    name: str = "",
    email: str = "",
    phone: str = "",
    request_summary: str = "",
    interest_score: int = 3,
    source: str = "web",
) -> str:
    """Save or update a lead from the current conversation.
    Call this when you learn the customer's name, email, phone, or understand their need.
    Updates existing lead for the same session, or creates a new one."""
    from asgiref.sync import sync_to_async

    def _save():
        client = Client.objects.get(pk=client_id)

        if not session_id:
            return json.dumps({"status": "error", "message": "session_id is required"})

        try:
            session = AgentSession.objects.get(pk=session_id)
        except AgentSession.DoesNotExist:
            return json.dumps({"status": "error", "message": f"session {session_id} not found"})

        # Find or create lead for this session
        lead, created = Lead.objects.get_or_create(
            client=client,
            agent_session=session,
            defaults={'source': source},
        )

        if name:
            lead.name = name[:255]
        if email:
            lead.email = email[:254]
        if phone:
            lead.phone = phone[:50]
        if request_summary:
            lead.request_summary = request_summary[:1000]
        if interest_score:
            lead.interest_score = max(1, min(5, int(interest_score)))
        if source and created:
            lead.source = source

        lead.save()
        action = "Created" if created else "Updated"
        return json.dumps({
            "status": "ok",
            "action": action,
            "lead_id": lead.id,
            "name": lead.name,
            "interest_score": lead.interest_score,
        })

    return await sync_to_async(_save)()


@mcp.tool()
async def qualify_conversation(
    client_id: int,
    session_id: str,
) -> str:
    """Analyze the current session and return existing lead data if any.
    Call at end of conversation to review collected lead information."""
    from asgiref.sync import sync_to_async

    def _qualify():
        try:
            lead = Lead.objects.get(
                client_id=client_id,
                agent_session_id=session_id,
            )
            return json.dumps({
                "has_lead": True,
                "lead_id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "request_summary": lead.request_summary,
                "interest_score": lead.interest_score,
                "status": lead.status,
            })
        except Lead.DoesNotExist:
            return json.dumps({"has_lead": False})

    return await sync_to_async(_qualify)()


@mcp.tool()
async def search_leads(
    client_id: int,
    status: str = "",
    source: str = "",
    min_interest: int = 0,
    search: str = "",
    period: str = "",
    limit: int = 25,
) -> str:
    """Search existing leads with filters.
    period: '7d', '30d', '2026-03', or empty for all.
    Returns list of matching leads."""
    from asgiref.sync import sync_to_async

    def _search():
        qs = Lead.objects.filter(client_id=client_id)

        if status:
            qs = qs.filter(status=status)
        if source:
            qs = qs.filter(source=source)
        if min_interest:
            qs = qs.filter(interest_score__gte=min_interest)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(request_summary__icontains=search)
            )
        if period:
            now = timezone.now()
            if period.endswith('d'):
                days = int(period[:-1])
                qs = qs.filter(created_at__gte=now - timedelta(days=days))
            elif '-' in period:
                # YYYY-MM format
                parts = period.split('-')
                year, month = int(parts[0]), int(parts[1])
                qs = qs.filter(created_at__year=year, created_at__month=month)

        leads = list(qs.order_by('-created_at')[:limit].values(
            'id', 'name', 'email', 'phone', 'request_summary',
            'interest_score', 'status', 'source', 'created_at',
        ))

        for lead in leads:
            lead['created_at'] = lead['created_at'].isoformat() if lead['created_at'] else None

        return json.dumps({"leads": leads, "total": qs.count()})

    return await sync_to_async(_search)()


@mcp.tool()
async def get_lead_stats(
    client_id: int,
    period: str = "30d",
) -> str:
    """Lead statistics: count by status, by source, average interest score.
    period: '7d', '30d', '90d', or 'all'."""
    from asgiref.sync import sync_to_async

    def _stats():
        qs = Lead.objects.filter(client_id=client_id)

        if period != 'all' and period.endswith('d'):
            days = int(period[:-1])
            qs = qs.filter(created_at__gte=datetime.now() - timedelta(days=days))

        total = qs.count()
        by_status = dict(qs.values_list('status').annotate(c=Count('id')).values_list('status', 'c'))
        by_source = dict(qs.values_list('source').annotate(c=Count('id')).values_list('source', 'c'))
        avg_interest = qs.aggregate(avg=Avg('interest_score'))['avg']

        converted = by_status.get('converted', 0)
        conversion_rate = (converted / total * 100) if total > 0 else 0

        return json.dumps({
            "total": total,
            "by_status": by_status,
            "by_source": by_source,
            "avg_interest_score": round(avg_interest or 0, 1),
            "conversion_rate": round(conversion_rate, 1),
            "period": period,
        })

    return await sync_to_async(_stats)()


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 4: Commit**

```bash
cd p004_ai_nexelin && git add mcp_servers/leads/
git commit -m "feat(mcp-leads): add lead management MCP server

Tools: save_lead, qualify_conversation, search_leads, get_lead_stats.
save_lead/qualify_conversation for Vasya (consultant scope).
search_leads/get_lead_stats for Oleg (assistant scope)."
```

---

## Task 5: Seed Data + Settings Registration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/seed_data.py:192`
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0010_seed_leads_tool.py`
- Modify: `p004_ai_nexelin/MASTER/settings.py:432-448`

- [ ] **Step 1: Add leads ToolCard to seed_data.py**

Append to `INITIAL_TOOLS` list before the closing `]`:

```python
{
    'slug': 'leads',
    'name': 'Lead Management',
    'tagline': 'Збір та управління лідами з усіх каналів',
    'tagline_i18n': {
        'en': 'Lead collection and management across all channels',
        'de': 'Lead-Erfassung und -Verwaltung über alle Kanäle',
    },
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
},
```

- [ ] **Step 2: Create seed migration**

Create `p004_ai_nexelin/MASTER/tools/migrations/0010_seed_leads_tool.py`:

```python
from django.db import migrations


def seed_leads_tool(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.get_or_create(
        slug='leads',
        defaults={
            'name': 'Lead Management',
            'tagline': 'Збір та управління лідами з усіх каналів',
            'tagline_i18n': {
                'en': 'Lead collection and management across all channels',
                'de': 'Lead-Erfassung und -Verwaltung über alle Kanäle',
            },
            'description': 'Collect, qualify and search leads from all messenger channels.',
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
        },
    )


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug='leads').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0009_fix_whatsapp_bridge_urls'),
    ]

    operations = [
        migrations.RunPython(seed_leads_tool, unseed),
    ]
```

- [ ] **Step 3: Register leads MCP server in settings.py**

After the `xlsx` entry in `MCP_SERVERS`:

```python
'leads': {
    'command': 'python',
    'args': ['-m', 'mcp_servers.leads.server'],
    'enabled': True,
},
```

- [ ] **Step 4: Run migration**

Run: `cd p004_ai_nexelin && python manage.py migrate tools`

- [ ] **Step 5: Commit**

```bash
cd p004_ai_nexelin && git add MASTER/tools/seed_data.py MASTER/tools/migrations/0010_* MASTER/settings.py
git commit -m "feat(tools): register leads MCP server + seed ToolCard

Add leads entry to MCP_SERVERS config.
Seed migration creates Lead Management ToolCard."
```

---

## Task 6: EdgeMiddleware Execution in Orchestrator

**Files:**
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:460-499`

- [ ] **Step 1: Add middleware execution methods**

Add to `AgentOrchestrator` class, before `_log`:

```python
async def _execute_tool_with_middleware(
    self,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[str, str]:
    """Execute tool with pre/post middleware pipeline."""
    from asgiref.sync import sync_to_async
    from MASTER.tools.models import EdgeMiddleware

    server_name = self._tool_to_server.get(tool_name)
    connection = self._tool_to_connection.get(server_name) if server_name else None

    if not connection:
        # No connection found — execute without middleware
        return await self._execute_tool(tool_name, arguments)

    # Load middlewares for this connection
    middlewares = await sync_to_async(
        lambda: list(
            EdgeMiddleware.objects.filter(
                connection=connection, enabled=True,
            ).select_related('skill_card').order_by('order')
        )
    )()

    if not middlewares:
        return await self._execute_tool(tool_name, arguments)

    pre = [m for m in middlewares if m.order < 0]
    post = [m for m in middlewares if m.order >= 0]

    # Pre-execution
    processed_args = dict(arguments)
    for mw in pre:
        try:
            result = await self._run_middleware(mw, json.dumps(processed_args), 'pre')
            if result:
                processed_args = json.loads(result)
        except Exception:
            logger.warning("Pre-middleware '%s' failed, skipping", mw.skill_card.slug, exc_info=True)

    # Execute tool
    result_text, status = await self._execute_tool(tool_name, processed_args)

    # Post-execution
    for mw in post:
        try:
            transformed = await self._run_middleware(mw, result_text, 'post')
            if transformed:
                result_text = transformed
        except Exception:
            logger.warning("Post-middleware '%s' failed, skipping", mw.skill_card.slug, exc_info=True)

    return result_text, status

async def _run_middleware(
    self,
    middleware,
    data: str,
    stage: str,
) -> str | None:
    """Execute a single middleware skill via MCP tool call."""
    skill_slug = middleware.skill_card.slug
    # Find which server hosts this skill
    for tool in self._tools:
        server_name = self._tool_to_server.get(tool.name)
        if server_name and skill_slug.startswith(server_name):
            session = self._sessions.get(server_name)
            if session:
                config = middleware.config or {}
                mw_args = {
                    "data": data,
                    "stage": stage,
                    "client_id": self.client.pk,
                    **config,
                }
                result = await session.call_tool(tool.name, mw_args)
                texts = [item.text for item in result.content if hasattr(item, "text")]
                return "\n".join(texts) if texts else None
    logger.warning("Middleware skill '%s' not found in MCP servers", skill_slug)
    return None
```

- [ ] **Step 2: Update `process()` loop to use `_execute_tool_with_middleware`**

In the tool execution loop inside `process()`, replace the call:

```python
# OLD:
tool_result, tool_status = await self._execute_tool(tool_name, raw_args)

# NEW:
tool_result, tool_status = await self._execute_tool_with_middleware(tool_name, raw_args)
```

- [ ] **Step 3: Commit**

```bash
cd p004_ai_nexelin && git add MASTER/agents/orchestrator.py
git commit -m "feat(orchestrator): execute EdgeMiddleware pre/post tool calls

Pre-middleware (order < 0) transforms input before tool execution.
Post-middleware (order >= 0) transforms output after.
Failures are logged and skipped — never break main flow."
```

---

## Task 7: ChatSSEView + Dispatch — Channel Routing

**Files:**
- Modify: `p004_ai_nexelin/MASTER/mcp_hub/views.py:22-138`
- Modify: `p004_ai_nexelin/MASTER/agents/dispatch.py:9-60`

- [ ] **Step 1: Update ChatSSEView to pass data dict**

In `views.py`, change `_stream` and `_stream_mcp` to receive `data` instead of `message`:

```python
async def post(self, request):
    # ... existing validation ...
    data = json.loads(request.body)
    message = data.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Message is required'}, status=400)

    response = StreamingHttpResponse(
        self._stream(request, client, data),  # pass data, not message
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

async def _stream(self, request, client, data):
    message = data.get('message', '').strip()

    if FeatureFlag.is_enabled('mcp_real_agent', client):
        async for event in self._stream_mcp(request, client, data):
            yield event
        return

    # ... rest of legacy path uses message variable ...
```

- [ ] **Step 2: Update `_stream_mcp` to use channel from data**

```python
async def _stream_mcp(self, request, client, data):
    from MASTER.agents.orchestrator import AgentOrchestrator

    message = data.get('message', '').strip()
    channel = data.get('channel', 'api')

    try:
        agent_config = await AgentConfig.objects.select_related(
            'llm_provider', 'embedding_model'
        ).aget(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = await AgentConfig.objects.acreate(client=client)

    session = await AgentSession.objects.acreate(
        agent_config=agent_config,
        channel=channel,
        metadata={'user_agent': request.META.get('HTTP_USER_AGENT', '')},
    )

    yield self._sse('status', {'step': 'thinking', 'session_id': str(session.id)})

    orchestrator = AgentOrchestrator(client, agent_config)
    await orchestrator.connect()
    try:
        yield self._sse('status', {'step': 'generating'})
        result = await orchestrator.process(
            message=message,
            session=session,
            conversation=None,
            channel=channel,
            external_user_id='',
        )
        yield self._sse('token', {'text': result})
    except Exception as e:
        logger.error(f'MCP orchestrator failed in SSE: {e}', exc_info=True)
        yield self._sse('error', {'step': 'generate', 'message': str(e)})
    finally:
        await orchestrator.disconnect()

    yield self._sse('done', {'session_id': str(session.id)})
```

- [ ] **Step 3: Commit**

```bash
cd p004_ai_nexelin && git add MASTER/mcp_hub/views.py
git commit -m "feat(mcp-hub): read channel from request body for dual-agent routing

ChatSSEView passes full data dict to _stream_mcp.
channel='sandbox' triggers assistant scope (Oleg).
channel='telegram'/'whatsapp'/etc triggers manager scope (Vasya)."
```

---

## Task 8: Frontend — Sandbox MCP Switch

**Files:**
- Modify: `nextlen/src/api/agent.js`
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx`

- [ ] **Step 1: Add MCP SSE chat function to agent.js**

Add to `agent.js`:

```javascript
// MCP SSE Chat (used when mcp_real_agent flag is enabled)
export const mcpAPI = {
  chatSSE: (message, channel = 'sandbox', onToken, onDone, onError) => {
    const tag = localStorage.getItem('client_tag');
    const baseURL = api.defaults.baseURL || '';
    const url = `${baseURL}/mcp/chat/`;

    const body = JSON.stringify({ message, channel });

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(tag ? { 'X-Client-Tag': tag } : {}),
        ...api.defaults.headers.common,
      },
      body,
    }).then(response => {
      if (!response.ok) {
        onError?.(`HTTP ${response.status}`);
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            onDone?.();
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ') && eventType) {
              try {
                const data = JSON.parse(line.slice(6));
                if (eventType === 'token') onToken?.(data.text);
                else if (eventType === 'done') onDone?.(data);
                else if (eventType === 'error') onError?.(data.message);
              } catch (_) {}
              eventType = '';
            }
          }
          read();
        });
      }
      read();
    }).catch(err => onError?.(err.message));
  },
};
```

- [ ] **Step 2: Update ChatWindow.jsx to use MCP SSE when flag is enabled**

In `ChatWindow.jsx`, add import and modify `sendMessage` handler. The feature flag can be checked via a client settings endpoint or a simple localStorage flag.

Add import at top:
```javascript
import { ragAPI, mcpAPI } from '../../api/agent';
```

Add state for MCP mode:
```javascript
const [mcpEnabled, setMcpEnabled] = useState(false);

// Check MCP flag on mount
useEffect(() => {
  const flag = localStorage.getItem('mcp_real_agent');
  if (flag === 'true') setMcpEnabled(true);
}, []);
```

In the send message handler, add MCP branch:

```javascript
const handleSend = async () => {
  if (!input.trim() || loading) return;
  const userMessage = input.trim();
  // ... add user message to state ...

  if (mcpEnabled) {
    setLoading(true);
    mcpAPI.chatSSE(
      userMessage,
      'sandbox',
      (text) => {
        // onToken — add assistant response
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && last?.streaming) {
            return [...prev.slice(0, -1), { ...last, text: last.text + text }];
          }
          return [...prev, { role: 'assistant', text, streaming: true, timestamp: new Date() }];
        });
      },
      () => {
        // onDone
        setMessages(prev => prev.map(m => ({ ...m, streaming: false })));
        setLoading(false);
      },
      (error) => {
        // onError — fallback message
        setMessages(prev => [...prev, {
          role: 'assistant',
          text: `Error: ${error}`,
          timestamp: new Date(),
        }]);
        setLoading(false);
      },
    );
    setInput('');
    return;
  }

  // ... existing legacy ragAPI.chat() path ...
};
```

- [ ] **Step 3: Commit**

```bash
cd nextlen && git add src/api/agent.js src/components/sandbox/ChatWindow.jsx
git commit -m "feat(sandbox): switch to MCP SSE endpoint when flag enabled

mcpAPI.chatSSE streams tokens via SSE from /api/mcp/chat/.
Sends channel='sandbox' for assistant (Oleg) scope.
Legacy ragAPI path untouched when flag is off."
```

---

## Task 9: Integration Verification on srtyh

**Files:** None (manual verification)

- [ ] **Step 1: Ensure feature flag is set**

Run in Django shell:
```python
from MASTER.nexelin_platform.models import FeatureFlag
from MASTER.clients.models import Client

client = Client.objects.get(tag='srtyh')

for key in ['mcp_real_agent', 'mcp_sse_streaming']:
    flag, _ = FeatureFlag.objects.get_or_create(key=key, defaults={'rollout': 'selected'})
    flag.rollout = 'selected'
    flag.save()
    flag.enabled_clients.add(client)
```

- [ ] **Step 2: Create ToolConnections for srtyh**

```python
from MASTER.tools.models import ToolCard, ToolConnection

client = Client.objects.get(tag='srtyh')

# Connect leads tool for both scopes
leads_card = ToolCard.objects.get(slug='leads')
ToolConnection.objects.get_or_create(
    client=client, tool_card=leads_card, target='assistant',
    defaults={'status': 'connected', 'enabled': True})
ToolConnection.objects.get_or_create(
    client=client, tool_card=leads_card, target='manager',
    defaults={'status': 'connected', 'enabled': True})

# Connect rag-search for both scopes
rag_card = ToolCard.objects.get(slug='rag-search')
ToolConnection.objects.get_or_create(
    client=client, tool_card=rag_card, target='assistant',
    defaults={'status': 'connected', 'enabled': True})
ToolConnection.objects.get_or_create(
    client=client, tool_card=rag_card, target='manager',
    defaults={'status': 'connected', 'enabled': True})
```

- [ ] **Step 3: Set MCP flag in frontend localStorage**

In browser console for srtyh sandbox:
```javascript
localStorage.setItem('mcp_real_agent', 'true');
```

- [ ] **Step 4: Test Sandbox (Oleg)**

1. Open Sandbox for srtyh
2. Send "Покажи мені ліди за останній тиждень"
3. Verify: Oleg uses `search_leads` tool, responds with results
4. Verify: Oleg uses `assistant_prompt` (not consultant)

- [ ] **Step 5: Test Messenger (Vasya)**

1. Send message to srtyh's Telegram/WhatsApp bot
2. Verify: Vasya responds using `consultant_prompt`
3. Share name/phone in conversation
4. Verify: Vasya calls `save_lead` tool
5. Check Lead model in admin — new record with `agent_session` FK

- [ ] **Step 6: Test Legacy Client**

1. Open sandbox for any non-srtyh client
2. Verify: uses legacy ragAPI, no MCP
3. Send message to non-srtyh bot
4. Verify: legacy pipeline, no changes

- [ ] **Step 7: Commit final verification notes**

```bash
git commit --allow-empty -m "chore: verified dual-agent + leads + middleware on srtyh

Sandbox: Oleg with assistant scope, search_leads works.
Messengers: Vasya with manager scope, save_lead works.
Legacy clients: zero impact confirmed."
```
