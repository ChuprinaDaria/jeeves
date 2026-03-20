# Real MCP Architecture for Nexelin — Design Spec

## Summary

Migrate Nexelin from hardcoded RAG pipeline to real MCP architecture with FastMCP servers and LLM tool calling. Dual-mode: enabled only for test client `srtyh` via FeatureFlag, all other clients use existing pipeline unchanged.

## Goals

1. Two standalone FastMCP servers: `mcp-rag` and `mcp-escalation`
2. `AgentOrchestrator` in Django that connects to MCP servers and uses LLM tool calling
3. FeatureFlag `mcp_real_agent` gating — `selected` mode, only client `srtyh`
4. Zero changes to existing pipeline for non-flagged clients
5. Separate Docker containers for each MCP server (scalability)

## Non-Goals

- Communication channel MCP servers (WhatsApp, Telegram, Email) — phase 2
- Migration of all clients — only `srtyh` for now
- Changes to frontend Flow Builder
- Changes to webhook handlers beyond adding dual-mode routing

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Docker Compose (nexelin_network)                     │
│                                                       │
│  ┌────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │  mcp-rag   │  │ mcp-escalation │  │ web (Django) │ │
│  │  :8010     │  │  :8011         │  │  :8000       │ │
│  │  FastMCP   │  │  FastMCP       │  │              │ │
│  │  streamable│  │  streamable    │  │  AgentOrch.  │ │
│  │  _http     │  │  _http         │  │  ↕ MCP Client│ │
│  └─────┬──────┘  └──────┬─────────┘  └──────┬──────┘ │
│        │                │                    │        │
│        └────────────────┴────────────────────┘        │
│              internal Docker network                  │
│                                                       │
│  ┌──────────┐  ┌────────┐  ┌────────┐                │
│  │ postgres │  │ qdrant │  │ redis  │                │
│  └──────────┘  └────────┘  └────────┘                │
└──────────────────────────────────────────────────────┘
```

---

## Component 1: `mcp-rag` Server

**Port:** 8010
**Transport:** streamable_http
**Base image:** python:3.12-slim
**Dependencies:** fastmcp>=2.0, qdrant-client, cohere, psycopg, Django (for ORM access)

### Tools

#### `search`
```python
@mcp.tool()
async def search(query: str, client_id: int, top_k: int = 10) -> dict:
    """Search the knowledge base using vector similarity + Cohere reranking.

    Args:
        query: User's question or search query
        client_id: Client ID for data isolation
        top_k: Maximum number of results to return

    Returns:
        dict with 'chunks' list (content, similarity, level, document_title)
    """
```

Wraps existing `VectorSearchService.search()` + `QdrantSearchService` with Cohere reranking. Multi-level search (branch → specialization → client) preserved.

#### `index_document`
```python
@mcp.tool()
async def index_document(client_id: int, title: str, content: str, metadata: dict = {}) -> dict:
    """Index a new document into the client's knowledge base.

    Args:
        client_id: Client ID for data isolation
        title: Document title
        content: Full document text (will be chunked automatically)
        metadata: Optional metadata dict

    Returns:
        dict with 'chunks_created' count and 'document_id'
    """
```

Wraps existing `EmbeddingService.create_embedding()` + chunk storage.

### Resources

#### `knowledge://documents`
```python
@mcp.resource("knowledge://documents/{client_id}")
async def list_documents(client_id: int) -> str:
    """List all documents in client's knowledge base with stats."""
```

#### `knowledge://stats`
```python
@mcp.resource("knowledge://stats/{client_id}")
async def knowledge_stats(client_id: int) -> str:
    """Knowledge base statistics: total docs, chunks, last indexed date."""
```

### Database Access

The RAG server needs read access to PostgreSQL (embeddings, clients) and Qdrant. It imports Django models directly — shares the same `MASTER/` codebase via volume mount or COPY in Dockerfile. `DJANGO_SETTINGS_MODULE=MASTER.settings` set in env.

---

## Component 2: `mcp-escalation` Server

**Port:** 8011
**Transport:** streamable_http
**Base image:** python:3.12-slim
**Dependencies:** fastmcp>=2.0, matrix-nio (for Matrix notifications), psycopg, Django

### Tools

#### `escalate_to_manager`
```python
@mcp.tool()
async def escalate_to_manager(
    client_id: int,
    conversation_id: str,
    reason: str,
    customer_name: str = "",
    channel: str = "unknown",
    summary: str = "",
) -> dict:
    """Escalate a conversation to a live manager (Vasya).

    The AI assistant should call this when:
    - Customer explicitly asks for a human
    - Question is outside the knowledge base scope
    - Customer is frustrated or the situation is sensitive
    - Complex issue requiring human judgment

    Args:
        client_id: Client ID
        conversation_id: WhatsApp/Telegram conversation ID
        reason: Why escalation is needed
        customer_name: Customer name if known
        channel: Source channel (whatsapp, telegram, web, etc.)
        summary: Brief summary of conversation so far

    Returns:
        dict with 'escalation_id', 'manager_notified' bool, 'estimated_wait'
    """
```

Implementation:
1. Creates escalation record in DB
2. Notifies manager(s) via Matrix (using existing HITL Matrix bridge) or Telegram
3. Updates conversation status to `escalated`
4. Returns escalation metadata

#### `resolve_escalation`
```python
@mcp.tool()
async def resolve_escalation(escalation_id: str, resolution_note: str = "") -> dict:
    """Mark an escalation as resolved.

    Args:
        escalation_id: ID from escalate_to_manager result
        resolution_note: Optional note about how it was resolved

    Returns:
        dict with 'status': 'resolved', 'resolved_at' timestamp
    """
```

#### `check_manager_availability`
```python
@mcp.tool()
async def check_manager_availability(client_id: int) -> dict:
    """Check if a live manager is currently available.

    Returns:
        dict with 'available' bool, 'online_managers' count, 'avg_response_time'
    """
```

Checks Matrix presence or last activity timestamp of configured managers.

### Resources

#### `escalations://active`
```python
@mcp.resource("escalations://active/{client_id}")
async def active_escalations(client_id: int) -> str:
    """List currently active (unresolved) escalations for this client."""
```

---

## Component 3: `AgentOrchestrator`

**Location:** `MASTER/agents/orchestrator.py`
**Role:** Connects to MCP servers, manages LLM tool calling loop, replaces hardcoded pipeline for flagged clients.

### Class Design

```python
class AgentOrchestrator:
    """MCP-native agent orchestrator with LLM tool calling.

    Connects to registered MCP servers, discovers tools/resources,
    and lets the LLM decide which tools to call.
    """

    def __init__(self, client: Client, agent_config: AgentConfig):
        self.client = client
        self.agent_config = agent_config
        self.mcp_clients = {}       # server_name → ClientSession
        self.available_tools = []    # merged from all servers
        self.conversation_history = []

    async def connect(self):
        """Connect to all MCP servers configured for this client."""
        # Read MCP server URLs from settings or ToolCard records
        servers = self._get_mcp_servers()
        for name, url in servers.items():
            session = await self._connect_server(name, url)
            tools = await session.list_tools()
            self.available_tools.extend(tools)
            self.mcp_clients[name] = session

    async def process(self, message: str, session: AgentSession,
                      conversation: list = None) -> str:
        """Process a user message through the MCP agent loop.

        1. Build messages with system prompt + history + user message
        2. Send to LLM with tool definitions
        3. If LLM returns tool_calls → execute via MCP → feed results back
        4. Repeat until LLM returns final text response
        5. Log everything to AgentLog
        """

    async def _execute_tool_call(self, tool_call) -> dict:
        """Route a tool call to the correct MCP server and execute it."""

    async def disconnect(self):
        """Cleanly disconnect from all MCP servers."""
```

### Tool Calling Loop

```
User message
    ↓
Build messages array:
  [system_prompt, ...history, {role: "user", content: message}]
    ↓
LLM.generate(messages, tools=self.available_tools)
    ↓
┌─ If response has tool_calls:
│    For each tool_call:
│      → Find which MCP server owns this tool
│      → Execute via MCP client session
│      → Collect result
│    Append tool results to messages
│    → Loop back to LLM.generate()
│
└─ If response is text (no tool_calls):
     → Return as final answer
     → Log to AgentLog
```

### System Prompt Enhancement

The orchestrator builds an enhanced system prompt that includes:
1. Base system prompt from `AgentConfig.system_prompt` or client defaults
2. Available tools description (auto-generated from MCP tool schemas)
3. Client context (name, language, channel)
4. Instructions for when to use each tool

### LLM Provider Requirements

Tool calling requires providers that support function/tool calling:
- OpenAI (gpt-4o, gpt-4o-mini) — native support
- Anthropic (Claude 3.5+) — native support
- Ollama — depends on model (qwen2.5 supports it)

The orchestrator converts MCP tool schemas to the LLM provider's tool format.

### MCP Server Discovery

Two sources for server URLs:
1. **Settings-based** (phase 1): `MCP_SERVERS` dict in `settings.py`
2. **ToolCard-based** (phase 2): `ToolCard` records with `transport_type='streamable_http'` and `mcp_server_url` filled

Phase 1 config:
```python
# settings.py
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

---

## Component 4: Dual-Mode Routing

### FeatureFlag

```python
FeatureFlag(
    name='mcp_real_agent',
    mode='selected',
    enabled_clients=[Client.objects.get(tag='srtyh')],
)
```

### Webhook Handler Changes

Each webhook handler gets a single branch point. Example for WhatsApp:

```python
# In views_meta_whatsapp.py, after message extraction:

if FeatureFlag.is_enabled('mcp_real_agent', client):
    # New MCP agent path
    orchestrator = AgentOrchestrator(client, agent_config)
    await orchestrator.connect()
    try:
        response_text = await orchestrator.process(
            message=text,
            session=session,
            conversation=conversation.messages,
        )
    finally:
        await orchestrator.disconnect()
else:
    # Existing pipeline — unchanged
    response_text = generate_response(text, client)
```

Same pattern for Telegram, Web Chat, and any other entry point.

### What Stays Unchanged

- All webhook URL routing
- Message parsing and validation
- Signature verification
- Conversation storage (ClientWhatsAppConversation)
- Response sending (Meta API, Telegram API, SSE)
- AgentLog creation (orchestrator creates logs internally)
- All clients except `srtyh`

---

## Component 5: Docker Configuration

### New Services in docker-compose.yml

```yaml
  mcp-rag:
    build:
      context: .
      dockerfile: mcp_servers/rag/Dockerfile
    container_name: ai_nexelin_mcp_rag
    restart: unless-stopped
    ports:
      - "8010:8010"
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

  mcp-escalation:
    build:
      context: .
      dockerfile: mcp_servers/escalation/Dockerfile
    container_name: ai_nexelin_mcp_escalation
    restart: unless-stopped
    ports:
      - "8011:8011"
    environment:
      - DJANGO_SETTINGS_MODULE=MASTER.settings
      - DATABASE_URL=${DATABASE_URL}
      - MATRIX_HOMESERVER_URL=${MATRIX_HOMESERVER_URL}
      - MCP_SERVER_PORT=8011
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - nexelin_network
```

### Dockerfile Template (shared pattern)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY mcp_servers/rag/requirements.txt /app/mcp_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r mcp_requirements.txt

COPY . /app

EXPOSE 8010
CMD ["python", "-m", "mcp_servers.rag.server"]
```

Each MCP server shares the main codebase (for Django ORM access) but has its own `requirements.txt` for server-specific deps.

---

## File Structure

```
p004_ai_nexelin/
├── mcp_servers/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   └── django_setup.py      # Django ORM bootstrap for standalone servers
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt     # fastmcp>=2.0, qdrant-client, cohere
│   │   └── server.py            # FastMCP server with @mcp.tool decorators
│   └── escalation/
│       ├── __init__.py
│       ├── Dockerfile
│       ├── requirements.txt     # fastmcp>=2.0, matrix-nio
│       └── server.py            # FastMCP server with @mcp.tool decorators
├── MASTER/
│   ├── agents/
│   │   ├── orchestrator.py      # NEW: AgentOrchestrator
│   │   └── models.py            # existing (AgentConfig, AgentSession, AgentLog)
│   ├── mcp_hub/
│   │   └── executor.py          # updated: delegates to orchestrator when flagged
│   ├── settings.py              # + MCP_SERVERS config
│   └── ...
└── docker-compose.yml           # + mcp-rag, mcp-escalation services
```

---

## Data Flow Diagram

```
WhatsApp/Telegram/Web message
         │
         ▼
   Webhook Handler
         │
         ▼
  FeatureFlag check ──── False ──→ Existing pipeline (unchanged)
         │                              │
        True                            ▼
         │                       generate_response()
         ▼                       (RAG → LLM → response)
  AgentOrchestrator
         │
         ▼
  Connect to MCP servers
  (mcp-rag:8010, mcp-escalation:8011)
         │
         ▼
  Discover available tools
  (search, index_document, escalate_to_manager, ...)
         │
         ▼
  Build system prompt + tool definitions
         │
         ▼
  ┌─────────────────────────┐
  │  LLM Tool Calling Loop  │
  │                         │
  │  LLM decides:           │
  │  → search(query=...)    │──→ MCP call to mcp-rag:8010
  │  → escalate(reason=...) │──→ MCP call to mcp-escalation:8011
  │  → final text response  │──→ Return to user
  │                         │
  │  (loops until text)     │
  └─────────────────────────┘
         │
         ▼
  AgentLog records all steps
         │
         ▼
  Send response to user
  (Meta API / Telegram API / SSE)
```

---

## Testing Strategy

### Unit Tests
- MCP server tools in isolation (mock DB/Qdrant)
- AgentOrchestrator with mock MCP servers
- FeatureFlag routing (ensure old pipeline untouched)

### Integration Tests
- MCP server → real Qdrant (test container)
- AgentOrchestrator → real MCP servers → real DB
- End-to-end: webhook → orchestrator → MCP → LLM → response

### Manual Testing
- Client `srtyh`: send messages via Web Chat, verify tool calling works
- Other clients: verify zero behavioral change
- Escalation: trigger escalation, verify Vasya gets notified

---

## Migration Path

### Phase 1 (this spec)
- `mcp-rag` + `mcp-escalation` servers
- `AgentOrchestrator` with LLM tool calling
- FeatureFlag for `srtyh` only

### Phase 2 (future)
- `mcp-whatsapp` server (send_message, send_template)
- `mcp-telegram` server (send_message, send_photo)
- `mcp-email` server (send_email, send_report)
- `mcp-webchat` server (widget config, sessions)

### Phase 3 (future)
- Gradual rollout: `mcp_real_agent` flag → `all`
- Remove old pipeline code
- Remove compat.py layer

---

## Requirements Update

```
# requirements.txt additions:
mcp>=1.9.0
fastmcp>=2.0.0
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| MCP server crashes affect all clients | FeatureFlag: only srtyh affected. Other clients use old pipeline. |
| LLM tool calling costs more tokens | Accepted: user confirmed tokens are not a concern |
| MCP server latency adds to response time | FastMCP streamable_http is low-overhead. Monitor via AgentLog.latency_ms |
| Django ORM in standalone process | Shared codebase with DJANGO_SETTINGS_MODULE. Tested pattern. |
| LLM hallucinates tool calls | Robust error handling in orchestrator. Invalid tool calls logged and skipped. |
