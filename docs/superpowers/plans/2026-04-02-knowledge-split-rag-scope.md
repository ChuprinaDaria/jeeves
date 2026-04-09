# Knowledge Split — RAG Scope Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Vasya (Manager) searches the knowledge base, results are filtered by `target_scope` — he only sees `all` + `manager` scoped blocks. Oleg (Assistant) sees everything.

**Architecture:** The MCP RAG `search` tool gets a new `requesting_agent` parameter (`assistant` | `manager`). After Qdrant returns results, we post-filter by matching document → KnowledgeBlock → `target_scope`. The orchestrator passes the agent role from `AgentConfig.role` through to the search call.

**Tech Stack:** Django ORM, FastMCP, Qdrant, Python

---

## Current State

Everything below is ALREADY implemented and should NOT be changed:
- `KnowledgeBlock.target_scope` field with choices `all`, `assistant`, `manager` (model + migration 0050)
- `KnowledgeBlockSerializer` includes `target_scope`
- `KnowledgeBlockViewSet.get_queryset()` filters by scope behind `mcp_knowledge_split` feature flag
- Frontend scope selector in KnowledgeBlockAddModal
- Sidebar rename (Sandbox → Assistant) behind feature flag

---

### Task 1: Add scope filtering to `_search_sync`

**Files:**
- Modify: `p004_ai_nexelin/mcp_servers/rag/server.py:46-118`

- [ ] **Step 1: Add `requesting_agent` param and post-filter logic to `_search_sync`**

The function currently returns all results regardless of scope. Add filtering after Qdrant search:

```python
def _search_sync(query: str, client_id: int, top_k: int = 10, requesting_agent: str = 'assistant') -> dict:
    """Run the full RAG search pipeline synchronously."""
    from MASTER.agents.models import AgentConfig
    from MASTER.clients.models import Client, KnowledgeBlock
    from MASTER.nexelin_platform.models import PlatformDefaults

    try:
        client = Client.objects.select_related(
            "branch", "specialization", "embedding_model",
        ).get(pk=client_id)
    except Client.DoesNotExist:
        return {"chunks": [], "error": f"Client {client_id} not found"}

    defaults = PlatformDefaults.get()

    try:
        agent_config = AgentConfig.objects.select_related(
            "embedding_model",
        ).get(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = None

    embedding_model = _resolve_embedding_model(client, agent_config, defaults)
    if not embedding_model:
        return {"chunks": [], "error": "No embedding model configured"}

    # Create query embedding
    from MASTER.processing.embedding_service import EmbeddingService

    embed_result = EmbeddingService.create_embedding(query, embedding_model)
    query_vector = embed_result.get("vector", [])
    if not query_vector:
        return {"chunks": [], "error": "Failed to create query embedding"}

    # Choose search backend
    use_qdrant = os.environ.get("USE_QDRANT", "true").lower() in ("true", "1", "yes")

    if use_qdrant:
        from MASTER.rag.qdrant_search import QdrantSearchService

        service = QdrantSearchService()
        results = service.search(
            query_vector=query_vector,
            client=client,
            embedding_model=embedding_model,
            query_text=query,
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

    # --- Scope filtering for manager agent ---
    if requesting_agent == 'manager':
        # Collect document IDs from results
        doc_ids = {r.document_id for r in results if r.document_id}
        if doc_ids:
            # Find documents whose KnowledgeBlock is assistant-only
            from MASTER.clients.models import ClientDocument
            excluded_doc_ids = set(
                ClientDocument.objects.filter(
                    id__in=doc_ids,
                    knowledge_block__target_scope='assistant',
                ).values_list('id', flat=True)
            )
            if excluded_doc_ids:
                results = [r for r in results if r.document_id not in excluded_doc_ids]

    # Trim to top_k and serialise
    results = results[:top_k]

    chunks = [
        {
            "content": r.content,
            "similarity": round(r.similarity, 4),
            "level": r.level,
            "document_title": r.document_title,
        }
        for r in results
    ]

    return {"chunks": chunks, "query": query, "client_id": client_id}
```

- [ ] **Step 2: Update MCP `search` tool to accept `requesting_agent`**

In the same file, update the `search` tool:

```python
@mcp.tool()
async def search(query: str, client_id: int, top_k: int = 10, requesting_agent: str = 'assistant') -> str:
    """Search the client knowledge base using semantic vector similarity.

    Use this tool when you need to find relevant information from
    the client's uploaded documents, branch knowledge, or specialization data.
    Returns the most similar text chunks ranked by relevance.

    Args:
        query: Natural-language search query describing what information is needed.
        client_id: Numeric ID of the Nexelin client whose knowledge base to search.
        top_k: Maximum number of result chunks to return (default 10).
        requesting_agent: Role of the agent making the request ('assistant' or 'manager').
            Manager only sees 'all' and 'manager' scoped knowledge blocks.
    """
    result = await sync_to_async(_search_sync)(query, client_id, top_k, requesting_agent)
    return json.dumps(result, ensure_ascii=False)
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/mcp_servers/rag/server.py
git commit -m "feat(rag): add requesting_agent scope filtering to MCP search tool"
```

---

### Task 2: Pass agent role from orchestrator to RAG search

**Files:**
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py`

The orchestrator calls MCP tools. When calling the `search` tool, it should inject `requesting_agent` based on the agent's role. Check `AgentConfig` model for a `role` field.

- [ ] **Step 1: Investigate how orchestrator calls MCP tools**

Read `p004_ai_nexelin/MASTER/agents/orchestrator.py` lines 280-360 to understand the tool call flow. The orchestrator likely passes arguments from LLM tool_use responses directly to MCP. The LLM should include `requesting_agent` in its tool call if the system prompt tells it to.

- [ ] **Step 2: Inject requesting_agent into search tool calls**

In the orchestrator's tool execution loop, when the tool being called is `search` (RAG), inject `requesting_agent` from the agent config:

```python
# In the tool call execution section of process():
if tool_name == 'search' and hasattr(self, 'agent_config') and self.agent_config:
    role = getattr(self.agent_config, 'role', 'assistant')
    if isinstance(raw_args, dict):
        raw_args.setdefault('requesting_agent', role)
```

This ensures scope filtering happens even if the LLM doesn't explicitly include the parameter.

- [ ] **Step 3: Verify AgentConfig has a role field**

Check `p004_ai_nexelin/MASTER/agents/models.py` for `AgentConfig.role` or equivalent. If no role field exists, use the agent's name/type to determine scope:
- Agent named "Vasya" or type "manager" → `requesting_agent='manager'`
- Everything else → `requesting_agent='assistant'`

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/agents/orchestrator.py
git commit -m "feat(orchestrator): inject requesting_agent scope into RAG search calls"
```

---

### Task 3: Manual integration test

- [ ] **Step 1: Verify scope filtering works**

1. Create a KnowledgeBlock with `target_scope='assistant'` and upload a document
2. Create a KnowledgeBlock with `target_scope='manager'` and upload a document
3. Search via MCP with `requesting_agent='assistant'` — should see both
4. Search via MCP with `requesting_agent='manager'` — should NOT see assistant-only block

- [ ] **Step 2: Commit any fixes**

```bash
git add -u
git commit -m "fix(rag): scope filtering adjustments after integration test"
```
