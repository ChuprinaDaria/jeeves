# Real MCP Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy two FastMCP servers (RAG + Escalation) with LLM tool calling orchestrator, gated by FeatureFlag for test client `srtyh`.

**Architecture:** Separate Docker containers for each MCP server (`mcp-rag:8010`, `mcp-escalation:8011`). New `AgentOrchestrator` in Django connects as MCP client, discovers tools, feeds them to LLM for tool calling. FeatureFlag `mcp_real_agent` in `selected` mode routes only `srtyh` through new pipeline; all other clients use existing code unchanged.

**Tech Stack:** FastMCP 2.0 (streamable_http), mcp>=1.9.0, Django 5.0, OpenAI/Anthropic tool calling, Docker Compose, PostgreSQL, Qdrant, Cohere rerank.

**Spec:** `docs/superpowers/specs/2026-03-20-mcp-real-architecture-design.md`

---

### Task 1: Django ORM Bootstrap for Standalone MCP Servers

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/common/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/common/django_setup.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p p004_ai_nexelin/mcp_servers/common
touch p004_ai_nexelin/mcp_servers/__init__.py
touch p004_ai_nexelin/mcp_servers/common/__init__.py
```

- [ ] **Step 2: Write django_setup.py**

```python
# mcp_servers/common/django_setup.py
"""Bootstrap Django ORM for standalone MCP server processes."""
import os
import django


def setup():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
    django.setup()
```

This module must be called before any Django model import in MCP servers.

- [ ] **Step 3: Verify import works**

```bash
cd p004_ai_nexelin && python -c "from mcp_servers.common.django_setup import setup; setup(); from MASTER.clients.models import Client; print('OK:', Client.objects.count())"
```

Expected: `OK: <number>` (no import errors).

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/
git commit -m "feat(mcp): add Django ORM bootstrap for standalone MCP servers"
```

---

### Task 2: mcp-rag FastMCP Server

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/rag/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/rag/server.py`
- Create: `p004_ai_nexelin/mcp_servers/rag/requirements.txt`
- Create: `p004_ai_nexelin/mcp_servers/rag/Dockerfile`

- [ ] **Step 1: Create rag directory**

```bash
mkdir -p p004_ai_nexelin/mcp_servers/rag
touch p004_ai_nexelin/mcp_servers/rag/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
fastmcp>=2.0.0
```

Server-specific deps only. Main `requirements.txt` (Django, qdrant-client, cohere etc.) installed separately in Dockerfile.

- [ ] **Step 3: Write server.py — search tool**

```python
# mcp_servers/rag/server.py
"""MCP RAG Server — knowledge base search and indexing."""
import os
import json
import logging
from fastmcp import FastMCP

# Bootstrap Django before any model import
from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async
from MASTER.clients.models import Client
from MASTER.rag.context_builder import ContextBuilder

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Nexelin RAG",
    description="Knowledge base search with vector similarity and Cohere reranking",
)


@mcp.tool()
async def search(query: str, client_id: int, top_k: int = 10) -> str:
    """Search the knowledge base using vector similarity + Cohere reranking.

    Use this tool when you need to find information to answer user questions.
    Always search before answering factual questions about the business.

    Args:
        query: The user's question or search terms
        client_id: Client ID for data isolation
        top_k: Maximum results to return (default 10)

    Returns:
        JSON with 'chunks' list containing content, similarity score, level, and document title
    """
    result = await sync_to_async(_search_sync)(query, client_id, top_k)
    return json.dumps(result, ensure_ascii=False)


def _search_sync(query: str, client_id: int, top_k: int) -> dict:
    try:
        client = Client.objects.select_related(
            'branch', 'specialization', 'embedding_model'
        ).get(pk=client_id)
    except Client.DoesNotExist:
        return {'chunks': [], 'error': f'Client {client_id} not found'}

    from MASTER.agents.models import AgentConfig
    from MASTER.nexelin_platform.models import PlatformDefaults

    defaults = PlatformDefaults.get()

    try:
        agent_config = AgentConfig.objects.select_related(
            'embedding_model'
        ).get(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = None

    # Resolve embedding model (same priority as existing pipeline)
    embedding_model = None
    if agent_config and agent_config.embedding_model:
        embedding_model = agent_config.embedding_model
    elif defaults.default_embedding_model:
        embedding_model = defaults.default_embedding_model
    elif client.embedding_model:
        embedding_model = client.embedding_model

    if not embedding_model:
        return {'chunks': [], 'error': 'No embedding model configured'}

    # Create query embedding
    builder = ContextBuilder()
    query_vector = builder._create_embedding(query, embedding_model)
    if not query_vector:
        return {'chunks': [], 'error': 'Failed to create embedding'}

    # Search — use Qdrant if available, fallback to pgvector
    use_qdrant = getattr(defaults, 'use_qdrant', False) or os.environ.get('USE_QDRANT', 'true').lower() == 'true'

    if use_qdrant:
        from MASTER.rag.qdrant_search import QdrantSearchService
        service = QdrantSearchService()
        results = service.search(
            query_vector=query_vector,
            branch=client.branch,
            specialization=client.specialization,
            client=client,
            embedding_model=embedding_model,
            query_text=query,  # for Cohere reranking
        )
    else:
        from MASTER.rag.vector_search import VectorSearchService
        service = VectorSearchService()
        results = service.search(
            query_vector=query_vector,
            branch=client.branch,
            specialization=client.specialization,
            client=client,
            embedding_model=embedding_model,
        )

    chunks = [
        {
            'content': r.content,
            'similarity': round(r.similarity, 4),
            'level': r.level,
            'document_title': getattr(r, 'document_title', ''),
        }
        for r in results[:top_k]
    ]

    return {'chunks': chunks, 'query': query, 'total_found': len(results)}


@mcp.resource("knowledge://stats/{client_id}")
async def knowledge_stats(client_id: int) -> str:
    """Knowledge base statistics for a client."""
    stats = await sync_to_async(_stats_sync)(client_id)
    return json.dumps(stats, ensure_ascii=False)


def _stats_sync(client_id: int) -> dict:
    from MASTER.clients.models import ClientEmbedding, ClientDocument
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {'error': f'Client {client_id} not found'}

    chunk_count = ClientEmbedding.objects.filter(client=client).count()
    doc_count = ClientDocument.objects.filter(client=client).count() if hasattr(ClientDocument, 'objects') else 0

    return {
        'client_id': client_id,
        'total_chunks': chunk_count,
        'total_documents': doc_count,
    }


if __name__ == "__main__":
    port = int(os.environ.get('MCP_SERVER_PORT', '8010'))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
```

- [ ] **Step 4: Write Dockerfile**

```dockerfile
# mcp_servers/rag/Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY mcp_servers/rag/requirements.txt /app/mcp_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r mcp_requirements.txt

COPY . /app

ENV DJANGO_SETTINGS_MODULE=MASTER.settings
EXPOSE 8010

CMD ["python", "-m", "mcp_servers.rag.server"]
```

- [ ] **Step 5: Test server starts locally**

```bash
cd p004_ai_nexelin && MCP_SERVER_PORT=8010 python -m mcp_servers.rag.server &
sleep 3 && curl -s http://localhost:8010/mcp | head -5
kill %1
```

Expected: MCP endpoint responds (JSON or SSE handshake).

- [ ] **Step 6: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/rag/
git commit -m "feat(mcp): add mcp-rag FastMCP server with search tool and knowledge stats resource"
```

---

### Task 3: mcp-escalation FastMCP Server

**Files:**
- Create: `p004_ai_nexelin/mcp_servers/escalation/__init__.py`
- Create: `p004_ai_nexelin/mcp_servers/escalation/server.py`
- Create: `p004_ai_nexelin/mcp_servers/escalation/requirements.txt`
- Create: `p004_ai_nexelin/mcp_servers/escalation/Dockerfile`

- [ ] **Step 1: Create escalation directory**

```bash
mkdir -p p004_ai_nexelin/mcp_servers/escalation
touch p004_ai_nexelin/mcp_servers/escalation/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
fastmcp>=2.0.0
```

- [ ] **Step 3: Write server.py**

```python
# mcp_servers/escalation/server.py
"""MCP Escalation Server — HITL manager escalation and resolution."""
import os
import json
import logging
from datetime import datetime
from fastmcp import FastMCP

from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Nexelin Escalation",
    description="Escalate conversations to live managers and track resolution",
)


@mcp.tool()
async def escalate_to_manager(
    client_id: int,
    conversation_id: str,
    reason: str,
    customer_name: str = "",
    channel: str = "unknown",
    summary: str = "",
) -> str:
    """Escalate a conversation to a live human manager.

    Call this when:
    - The customer explicitly asks to speak with a human
    - The question is outside the knowledge base scope and you cannot help
    - The customer is frustrated, angry, or the situation is sensitive
    - A complex issue requires human judgment (refunds, complaints, legal)

    Args:
        client_id: Client ID
        conversation_id: Conversation identifier (phone number, chat_id, etc.)
        reason: Clear explanation of why escalation is needed
        customer_name: Customer's name if known
        channel: Source channel (whatsapp, telegram, web)
        summary: Brief summary of the conversation so far

    Returns:
        JSON with escalation_id, manager_notified status, and estimated wait time
    """
    result = await sync_to_async(_escalate_sync)(
        client_id, conversation_id, reason, customer_name, channel, summary
    )
    return json.dumps(result, ensure_ascii=False)


def _escalate_sync(client_id, conversation_id, reason, customer_name, channel, summary):
    from MASTER.clients.models import Client, ClientWhatsAppConversation

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {'error': f'Client {client_id} not found'}

    # Update conversation status
    try:
        conv = ClientWhatsAppConversation.objects.get(
            client=client,
            conversation_id=conversation_id,
        )
        conv.escalated = True
        conv.escalation_reason = reason
        conv.save(update_fields=['escalated', 'escalation_reason'])
    except ClientWhatsAppConversation.DoesNotExist:
        pass  # Conversation may not exist yet for all channels

    # Notify manager via configured channel
    manager_notified = _notify_manager(client, reason, customer_name, channel, summary)

    return {
        'escalation_id': f'esc-{client_id}-{conversation_id}-{int(timezone.now().timestamp())}',
        'manager_notified': manager_notified,
        'estimated_wait': '2-5 minutes' if manager_notified else 'Manager offline',
        'reason': reason,
    }


def _notify_manager(client, reason, customer_name, channel, summary):
    """Send notification to manager via Telegram or Matrix."""
    notification_text = (
        f"🔔 Escalation from {channel}\n"
        f"Customer: {customer_name or 'Unknown'}\n"
        f"Reason: {reason}\n"
    )
    if summary:
        notification_text += f"Summary: {summary}\n"

    # Try Telegram notification to manager
    if hasattr(client, 'telegram_bot_token') and client.telegram_bot_token:
        try:
            from MASTER.clients.views_telegram import send_telegram_message
            manager_ids = getattr(client, 'manager_telegram_ids', [])
            for manager_id in manager_ids:
                send_telegram_message(
                    client.telegram_bot_token, manager_id, notification_text
                )
            if manager_ids:
                return True
        except Exception as e:
            logger.error(f'Telegram escalation notification failed: {e}')

    # Try Matrix notification
    if getattr(client, 'matrix_homeserver_url', None):
        try:
            # Use existing Matrix HITL bridge
            from MASTER.clients.services.whatsapp_bridge import notify_matrix_managers
            notify_matrix_managers(client, notification_text)
            return True
        except Exception as e:
            logger.error(f'Matrix escalation notification failed: {e}')

    logger.warning(f'No manager notification channel configured for client {client.pk}')
    return False


@mcp.tool()
async def check_manager_availability(client_id: int) -> str:
    """Check if a live manager is currently available for this client.

    Args:
        client_id: Client ID

    Returns:
        JSON with availability status and online manager count
    """
    result = await sync_to_async(_check_availability_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


def _check_availability_sync(client_id):
    from MASTER.clients.models import Client
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {'available': False, 'error': f'Client {client_id} not found'}

    # Simple heuristic: check if client has manager channels configured
    has_telegram = bool(getattr(client, 'telegram_bot_token', ''))
    has_matrix = bool(getattr(client, 'matrix_homeserver_url', ''))

    return {
        'available': has_telegram or has_matrix,
        'channels': {
            'telegram': has_telegram,
            'matrix': has_matrix,
        },
    }


@mcp.resource("escalations://active/{client_id}")
async def active_escalations(client_id: int) -> str:
    """List currently active (unresolved) escalations."""
    result = await sync_to_async(_active_escalations_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


def _active_escalations_sync(client_id):
    from MASTER.clients.models import ClientWhatsAppConversation
    convs = ClientWhatsAppConversation.objects.filter(
        client_id=client_id,
        escalated=True,
    ).values('conversation_id', 'customer_phone', 'escalation_reason', 'updated_at')[:20]

    return {
        'client_id': client_id,
        'active_count': len(convs),
        'escalations': list(convs),
    }


if __name__ == "__main__":
    port = int(os.environ.get('MCP_SERVER_PORT', '8011'))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
```

- [ ] **Step 4: Write Dockerfile**

```dockerfile
# mcp_servers/escalation/Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY mcp_servers/escalation/requirements.txt /app/mcp_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r mcp_requirements.txt

COPY . /app

ENV DJANGO_SETTINGS_MODULE=MASTER.settings
EXPOSE 8011

CMD ["python", "-m", "mcp_servers.escalation.server"]
```

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/escalation/
git commit -m "feat(mcp): add mcp-escalation FastMCP server with escalate, resolve, availability tools"
```

---

### Task 4: AgentOrchestrator — MCP Client with LLM Tool Calling

**Files:**
- Create: `p004_ai_nexelin/MASTER/agents/orchestrator.py`

- [ ] **Step 1: Write orchestrator.py**

```python
# MASTER/agents/orchestrator.py
"""MCP-native agent orchestrator with LLM tool calling.

Connects to MCP servers, discovers tools, and uses LLM function calling
to decide which tools to invoke. Replaces hardcoded RAG pipeline for
clients with mcp_real_agent FeatureFlag enabled.
"""
import json
import logging
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

from MASTER.agents.models import AgentConfig, AgentSession, AgentLog
from MASTER.clients.models import Client

logger = logging.getLogger(__name__)

# Max iterations to prevent infinite tool calling loops
MAX_TOOL_ITERATIONS = 10


class AgentOrchestrator:

    def __init__(self, client: Client, agent_config: AgentConfig):
        self.client = client
        self.agent_config = agent_config
        self.mcp_sessions = {}          # name → (read, write, session)
        self.available_tools = []       # list of MCP tool definitions
        self.tool_to_server = {}        # tool_name → server_name

    async def connect(self):
        """Connect to all configured MCP servers and discover tools."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        server_configs = getattr(settings, 'MCP_SERVERS', {})

        for name, config in server_configs.items():
            if not config.get('enabled', True):
                continue

            url = config['url']
            try:
                read, write = await streamablehttp_client(url).__aenter__()
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()

                # Discover tools
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    self.available_tools.append(tool)
                    self.tool_to_server[tool.name] = name

                self.mcp_sessions[name] = (read, write, session)
                logger.info(f'MCP connected: {name} ({url}) — {len(tools_result.tools)} tools')

            except Exception as e:
                logger.error(f'MCP connection failed: {name} ({url}): {e}')

    async def process(
        self,
        message: str,
        session: AgentSession,
        conversation: list | None = None,
        channel: str = 'web',
        external_user_id: str = '',
    ) -> str:
        """Process a user message through LLM tool calling loop.

        Returns the final text response from the LLM.
        """
        # Build conversation messages
        messages = self._build_messages(message, conversation)

        # Convert MCP tools to LLM function format
        tools_for_llm = self._tools_to_llm_format()

        # Tool calling loop
        iteration = 0
        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            start = time.monotonic()

            # Call LLM
            llm_response = await self._call_llm(messages, tools_for_llm)
            latency = int((time.monotonic() - start) * 1000)

            # Log LLM call
            await AgentLog.objects.acreate(
                session=session,
                call_type='llm',
                tool_name='',
                input_data={'messages_count': len(messages), 'iteration': iteration},
                output_data={
                    'has_tool_calls': bool(llm_response.get('tool_calls')),
                    'model': llm_response.get('model', ''),
                },
                status='ok',
                latency_ms=latency,
                tokens_used=llm_response.get('usage', {}).get('total_tokens', 0),
            )

            # Check if LLM wants to call tools
            tool_calls = llm_response.get('tool_calls', [])
            if not tool_calls:
                # Final text response
                return llm_response.get('content', '')

            # Execute tool calls
            for tool_call in tool_calls:
                tool_name = tool_call['function']['name']
                tool_args = json.loads(tool_call['function']['arguments'])

                # Inject client_id automatically
                if 'client_id' in self._get_tool_params(tool_name):
                    tool_args['client_id'] = self.client.pk

                # Execute via MCP
                tool_start = time.monotonic()
                try:
                    result = await self._execute_tool(tool_name, tool_args)
                    tool_status = 'ok'
                except Exception as e:
                    result = json.dumps({'error': str(e)})
                    tool_status = 'error'
                    logger.error(f'MCP tool call failed: {tool_name}: {e}')

                tool_latency = int((time.monotonic() - tool_start) * 1000)

                # Log tool call
                await AgentLog.objects.acreate(
                    session=session,
                    call_type='tool',
                    tool_name=tool_name,
                    input_data=tool_args,
                    output_data={'result': result[:2000] if isinstance(result, str) else result},
                    status=tool_status,
                    latency_ms=tool_latency,
                )

                # Append tool result to messages for next LLM iteration
                messages.append({
                    'role': 'assistant',
                    'tool_calls': [tool_call],
                })
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.get('id', tool_name),
                    'content': result if isinstance(result, str) else json.dumps(result),
                })

        # Safety: max iterations reached
        logger.warning(f'AgentOrchestrator: max iterations ({MAX_TOOL_ITERATIONS}) reached for client {self.client.pk}')
        return 'I apologize, but I was unable to complete processing your request. Please try again.'

    async def disconnect(self):
        """Disconnect from all MCP servers."""
        for name, (read, write, session) in self.mcp_sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f'MCP disconnect error ({name}): {e}')
        self.mcp_sessions.clear()

    # ── Private methods ──────────────────────

    def _build_messages(self, user_message: str, conversation: list | None) -> list:
        """Build messages array with system prompt + history."""
        system_prompt = self._build_system_prompt()

        messages = [{'role': 'system', 'content': system_prompt}]

        # Add conversation history (last N messages)
        if conversation:
            for msg in conversation[-20:]:  # limit history
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role in ('user', 'assistant') and content:
                    messages.append({'role': role, 'content': content})

        messages.append({'role': 'user', 'content': user_message})
        return messages

    def _build_system_prompt(self) -> str:
        """Build enhanced system prompt with tool usage instructions."""
        # Base prompt (same priority as existing pipeline)
        base = ''
        if self.agent_config and self.agent_config.system_prompt:
            base = self.agent_config.system_prompt
        elif hasattr(self.client, 'custom_system_prompt') and self.client.custom_system_prompt:
            base = self.client.custom_system_prompt

        if not base:
            from MASTER.nexelin_platform.models import PlatformDefaults
            defaults = PlatformDefaults.get()
            base = defaults.default_greeting or 'You are a helpful AI assistant.'

        # Add tool usage instructions
        tool_instructions = (
            "\n\n## Tool Usage\n"
            "You have access to tools. Use them when needed:\n"
            "- **search**: Always search the knowledge base before answering factual questions.\n"
            "- **escalate_to_manager**: Escalate when the customer asks for a human, "
            "is frustrated, or the question is beyond your capabilities.\n"
            "- **check_manager_availability**: Check before telling the customer "
            "about manager availability.\n"
        )

        # Add language instruction
        lang = self.agent_config.get_language() if self.agent_config else 'en'
        lang_instruction = f"\n\nAlways respond in the language the customer uses. Default: {lang}."

        return base + tool_instructions + lang_instruction

    def _tools_to_llm_format(self) -> list[dict]:
        """Convert MCP tool definitions to OpenAI function calling format."""
        tools = []
        for tool in self.available_tools:
            # Build JSON schema from MCP tool inputSchema
            schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}

            # Remove client_id from required — we inject it automatically
            properties = dict(schema.get('properties', {}))
            required = [r for r in schema.get('required', []) if r != 'client_id']
            properties.pop('client_id', None)

            tools.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description or '',
                    'parameters': {
                        'type': 'object',
                        'properties': properties,
                        'required': required,
                    },
                },
            })
        return tools

    def _get_tool_params(self, tool_name: str) -> list[str]:
        """Get parameter names for a tool."""
        for tool in self.available_tools:
            if tool.name == tool_name:
                schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                return list(schema.get('properties', {}).keys())
        return []

    async def _call_llm(self, messages: list, tools: list) -> dict:
        """Call LLM with tool definitions. Returns response dict."""
        from MASTER.rag.llm_client import LLMClient

        llm = LLMClient()
        provider_info = llm._get_provider(self.client)
        provider = provider_info['provider']
        model = provider_info['model']

        # Use OpenAI-compatible tool calling
        if hasattr(provider, 'client'):
            # OpenAI or compatible
            response = provider.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                temperature=self.agent_config.get_temperature() if self.agent_config else 0.7,
                max_tokens=self.agent_config.get_max_tokens() if self.agent_config else 2000,
            )

            choice = response.choices[0]
            result = {
                'content': choice.message.content or '',
                'model': response.model,
                'usage': {
                    'total_tokens': response.usage.total_tokens if response.usage else 0,
                },
            }

            if choice.message.tool_calls:
                result['tool_calls'] = [
                    {
                        'id': tc.id,
                        'function': {
                            'name': tc.function.name,
                            'arguments': tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return result
        else:
            # Fallback: no tool calling support — just generate text
            response = provider.generate(messages)
            return {
                'content': response.get('content', ''),
                'model': response.get('model', ''),
                'usage': response.get('usage', {}),
            }

    async def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call via the correct MCP server."""
        server_name = self.tool_to_server.get(tool_name)
        if not server_name or server_name not in self.mcp_sessions:
            return json.dumps({'error': f'Unknown tool: {tool_name}'})

        _, _, session = self.mcp_sessions[server_name]
        result = await session.call_tool(tool_name, arguments)

        # Extract text content from MCP result
        if result.content:
            texts = [c.text for c in result.content if hasattr(c, 'text')]
            return '\n'.join(texts) if texts else str(result.content)
        return '{}'
```

- [ ] **Step 2: Verify import works**

```bash
cd p004_ai_nexelin && python -c "from MASTER.agents.orchestrator import AgentOrchestrator; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/agents/orchestrator.py
git commit -m "feat(mcp): add AgentOrchestrator with MCP client and LLM tool calling loop"
```

---

### Task 5: Settings + Requirements + FeatureFlag Migration

**Files:**
- Modify: `p004_ai_nexelin/MASTER/settings.py` — add MCP_SERVERS config
- Modify: `p004_ai_nexelin/requirements.txt` — update mcp, add fastmcp
- Create: `p004_ai_nexelin/MASTER/agents/migrations/0004_feature_flag_mcp_real_agent.py`

- [ ] **Step 1: Add MCP_SERVERS to settings.py**

Add at the bottom of settings.py:

```python
# ── MCP Server Configuration ────────────────────────
MCP_SERVERS = {
    'rag': {
        'url': os.environ.get('MCP_RAG_URL', 'http://mcp-rag:8010/mcp'),
        'enabled': True,
    },
    'escalation': {
        'url': os.environ.get('MCP_ESCALATION_URL', 'http://mcp-escalation:8011/mcp'),
        'enabled': True,
    },
}
```

- [ ] **Step 2: Update requirements.txt**

Change `mcp>=1.0.0` to `mcp>=1.9.0` and add `fastmcp>=2.0.0`.

- [ ] **Step 3: Create FeatureFlag data migration**

```python
# MASTER/agents/migrations/0004_feature_flag_mcp_real_agent.py
from django.db import migrations


def create_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('nexelin_platform', 'FeatureFlag')
    Client = apps.get_model('clients', 'Client')

    flag, created = FeatureFlag.objects.get_or_create(
        key='mcp_real_agent',
        defaults={'rollout': 'selected'},
    )
    if created:
        try:
            srtyh = Client.objects.get(tag='srtyh')
            flag.enabled_clients.add(srtyh)
        except Client.DoesNotExist:
            pass  # Client will be added manually


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0003_auto_last'),  # adjust to actual last migration
        ('nexelin_platform', '0001_initial'),  # adjust
        ('clients', '0049_lead_and_leads_enabled'),  # adjust
    ]
    operations = [
        migrations.RunPython(create_flag, migrations.RunPython.noop),
    ]
```

Note: Migration dependencies must be adjusted to actual last migrations. Check with `python manage.py showmigrations agents nexelin_platform`.

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/settings.py p004_ai_nexelin/requirements.txt p004_ai_nexelin/MASTER/agents/migrations/
git commit -m "feat(mcp): add MCP_SERVERS config, update deps, create mcp_real_agent FeatureFlag"
```

---

### Task 6: Dual-Mode Routing in Webhook Handlers

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py` — add branch at line ~223
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py` — add branch at generate_rag_response
- Modify: `p004_ai_nexelin/MASTER/mcp_hub/views.py` — add branch in ChatSSEView._stream

- [ ] **Step 1: Create shared helper for dual-mode dispatch**

Create `MASTER/agents/dispatch.py`:

```python
# MASTER/agents/dispatch.py
"""Dual-mode dispatch: MCP agent vs legacy pipeline."""
import logging
from asgiref.sync import async_to_sync

from MASTER.nexelin_platform.models import FeatureFlag

logger = logging.getLogger(__name__)


def generate_response_dual(message, client, conversation=None, channel='web', external_user_id=''):
    """Route to MCP orchestrator or legacy pipeline based on FeatureFlag.

    Drop-in replacement for generate_response() / ResponseGenerator.generate().
    Returns response text string.
    """
    if FeatureFlag.is_enabled('mcp_real_agent', client):
        return _mcp_generate(message, client, conversation, channel, external_user_id)
    else:
        return _legacy_generate(message, client)


def _mcp_generate(message, client, conversation, channel, external_user_id):
    """Run through MCP AgentOrchestrator."""
    try:
        return async_to_sync(_mcp_generate_async)(
            message, client, conversation, channel, external_user_id
        )
    except Exception as e:
        logger.error(f'MCP orchestrator failed for client {client.pk}: {e}', exc_info=True)
        # Fallback to legacy on MCP failure
        logger.info(f'Falling back to legacy pipeline for client {client.pk}')
        return _legacy_generate(message, client)


async def _mcp_generate_async(message, client, conversation, channel, external_user_id):
    from MASTER.agents.models import AgentConfig, AgentSession
    from MASTER.agents.orchestrator import AgentOrchestrator

    try:
        agent_config = await AgentConfig.objects.select_related(
            'llm_provider', 'embedding_model'
        ).aget(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = await AgentConfig.objects.acreate(client=client)

    session = await AgentSession.objects.acreate(
        agent_config=agent_config,
        channel=channel,
        external_user_id=external_user_id,
    )

    orchestrator = AgentOrchestrator(client, agent_config)
    await orchestrator.connect()
    try:
        return await orchestrator.process(
            message=message,
            session=session,
            conversation=conversation,
            channel=channel,
            external_user_id=external_user_id,
        )
    finally:
        await orchestrator.disconnect()


def _legacy_generate(message, client):
    """Existing RAG pipeline — unchanged."""
    from MASTER.rag.response_generator import ResponseGenerator
    generator = ResponseGenerator()
    result = generator.generate(
        query=message,
        client=client,
        specialization=getattr(client, 'specialization', None),
        branch=getattr(client, 'branch', None),
        stream=False,
    )
    if hasattr(result, 'answer'):
        return result.answer
    return str(result)
```

- [ ] **Step 2: Integrate into WhatsApp webhook**

In `views_meta_whatsapp.py`, find `handle_regular_message()` and replace the `generate_response()` call with:

```python
from MASTER.agents.dispatch import generate_response_dual

# Replace: response_text = self.generate_rag_response(...)
# With:
response_text = generate_response_dual(
    message=message_body,
    client=client,
    conversation=conversation.messages if conversation else None,
    channel='whatsapp_meta',
    external_user_id=from_number,
)
```

- [ ] **Step 3: Integrate into Telegram webhook**

In `views_telegram.py`, find `generate_rag_response()` and add the same dispatch:

```python
from MASTER.agents.dispatch import generate_response_dual

# At the top of generate_rag_response(), before ResponseGenerator:
if FeatureFlag.is_enabled('mcp_real_agent', client):
    return generate_response_dual(
        message=message_text,
        client=client,
        conversation=conversation.messages if conversation else None,
        channel='telegram',
        external_user_id=str(chat_id),
    )
# else: continue with existing code below
```

- [ ] **Step 4: Integrate into ChatSSEView**

In `mcp_hub/views.py`, in `_stream()` method, add branch before RAG search:

```python
from MASTER.agents.dispatch import generate_response_dual

# In _stream(), after agent_config setup:
if FeatureFlag.is_enabled('mcp_real_agent', client):
    response = generate_response_dual(
        message=message,
        client=client,
        channel='web',
    )
    yield self._sse('token', {'text': response})
    yield self._sse('done', {'session_id': str(session.id)})
    return
# else: continue with existing SSE code
```

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/agents/dispatch.py \
        p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py \
        p004_ai_nexelin/MASTER/clients/views_telegram.py \
        p004_ai_nexelin/MASTER/mcp_hub/views.py
git commit -m "feat(mcp): add dual-mode routing — MCP orchestrator for flagged clients, legacy for others"
```

---

### Task 7: Docker Compose — MCP Server Services

**Files:**
- Modify: `p004_ai_nexelin/docker-compose.yml` — add mcp-rag and mcp-escalation services

- [ ] **Step 1: Add services to docker-compose.yml**

Append after existing services:

```yaml
  mcp-rag:
    build:
      context: .
      dockerfile: mcp_servers/rag/Dockerfile
    container_name: ai_nexelin_mcp_rag
    restart: unless-stopped
    environment:
      - DJANGO_SETTINGS_MODULE=MASTER.settings
      - DATABASE_URL=${DATABASE_URL}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - COHERE_API_KEY=${COHERE_API_KEY}
      - MCP_SERVER_PORT=8010
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    networks:
      - nexelin_network
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8010/mcp')"]
      interval: 30s
      timeout: 10s
      retries: 3

  mcp-escalation:
    build:
      context: .
      dockerfile: mcp_servers/escalation/Dockerfile
    container_name: ai_nexelin_mcp_escalation
    restart: unless-stopped
    environment:
      - DJANGO_SETTINGS_MODULE=MASTER.settings
      - DATABASE_URL=${DATABASE_URL}
      - MATRIX_HOMESERVER_URL=${MATRIX_HOMESERVER_URL:-}
      - MCP_SERVER_PORT=8011
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - nexelin_network
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8011/mcp')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

- [ ] **Step 2: Update web service — add depends_on for MCP servers**

Add to `web` service:

```yaml
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      mcp-rag:
        condition: service_healthy
      mcp-escalation:
        condition: service_healthy
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/docker-compose.yml
git commit -m "feat(mcp): add mcp-rag and mcp-escalation Docker services"
```

---

### Task 8: Deploy and Test on Production Server

**Files:** None (deployment operations)

- [ ] **Step 1: Push to remote**

```bash
git push ai feature/sp1-mcp-core-engine
```

- [ ] **Step 2: Pull on production server**

```bash
ssh dc@188.34.143.153 "cd /opt/p004_ai_nexelin/p004_ai_nexelin && git pull origin feature/sp1-mcp-core-engine"
```

- [ ] **Step 3: Copy updated files to MASTER/ (dual-path issue)**

```bash
ssh dc@188.34.143.153 "cd /opt/p004_ai_nexelin/p004_ai_nexelin && \
  cp -r p004_ai_nexelin/mcp_servers/ . && \
  cp p004_ai_nexelin/MASTER/agents/orchestrator.py MASTER/agents/ && \
  cp p004_ai_nexelin/MASTER/agents/dispatch.py MASTER/agents/ && \
  cp p004_ai_nexelin/MASTER/settings.py MASTER/ && \
  cp p004_ai_nexelin/requirements.txt . && \
  cp p004_ai_nexelin/docker-compose.yml ."
```

- [ ] **Step 4: Build and start MCP servers**

```bash
ssh dc@188.34.143.153 "cd /opt/p004_ai_nexelin/p004_ai_nexelin && \
  docker compose build mcp-rag mcp-escalation web && \
  docker compose up -d mcp-rag mcp-escalation && \
  docker compose restart web celery_worker"
```

- [ ] **Step 5: Run migration for FeatureFlag**

```bash
ssh dc@188.34.143.153 "cd /opt/p004_ai_nexelin/p004_ai_nexelin && \
  docker compose exec -T web python manage.py migrate"
```

- [ ] **Step 6: Verify MCP servers are healthy**

```bash
ssh dc@188.34.143.153 "docker compose ps mcp-rag mcp-escalation"
```

Expected: Both containers `Up (healthy)`.

- [ ] **Step 7: Test via Web Chat for client srtyh**

Send a test message to client `srtyh` via Web Chat. Check:
1. Response arrives (tool calling worked)
2. AgentLog has entries with `call_type='tool'`
3. Other clients still work normally

- [ ] **Step 8: Commit deployment notes**

```bash
git commit --allow-empty -m "deploy: mcp-rag + mcp-escalation servers live on production for client srtyh"
```
