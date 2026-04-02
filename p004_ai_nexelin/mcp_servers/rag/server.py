"""
mcp-rag — FastMCP server exposing the Nexelin RAG pipeline as MCP tools.

Provides:
- search(query, client_id, top_k) tool for semantic search over client knowledge base
- knowledge://stats/{client_id} resource for document/chunk statistics
"""

from __future__ import annotations

import json
import logging
import os

from mcp_servers.common.django_setup import setup

setup()

from asgiref.sync import sync_to_async  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-rag",
    description="Nexelin RAG knowledge-base search. "
    "Use the `search` tool to find relevant documents for a client.",
)


# ---------------------------------------------------------------------------
# Sync helpers (Django ORM is synchronous)
# ---------------------------------------------------------------------------

def _resolve_embedding_model(client, agent_config, defaults):
    """Priority chain: AgentConfig -> Client -> PlatformDefaults."""
    if agent_config and agent_config.embedding_model:
        return agent_config.embedding_model
    if client.embedding_model:
        return client.embedding_model
    if defaults.default_embedding_model:
        return defaults.default_embedding_model
    return None


def _search_sync(query: str, client_id: int, top_k: int = 10, requesting_agent: str = 'assistant') -> dict:
    """Run the full RAG search pipeline synchronously."""
    from MASTER.agents.models import AgentConfig
    from MASTER.clients.models import Client, ClientDocument
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

    # Post-filter by scope when requesting_agent is 'manager':
    # Manager (Vasya) must NOT see 'assistant'-only knowledge blocks.
    if requesting_agent == 'manager':
        document_ids = [r.document_id for r in results if r.document_id is not None]
        if document_ids:
            assistant_only_doc_ids = set(
                ClientDocument.objects.filter(
                    id__in=document_ids,
                    knowledge_block__target_scope='assistant',
                ).values_list('id', flat=True)
            )
            results = [r for r in results if r.document_id not in assistant_only_doc_ids]

    # Trim to top_k
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


def _stats_sync(client_id: int) -> dict:
    """Return document and chunk counts for a client."""
    from MASTER.clients.models import Client, ClientDocument, ClientEmbedding

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"error": f"Client {client_id} not found"}

    document_count = ClientDocument.objects.filter(client=client).count()
    chunk_count = ClientEmbedding.objects.filter(client=client).count()

    return {
        "client_id": client_id,
        "document_count": document_count,
        "chunk_count": chunk_count,
    }


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MCP resource
# ---------------------------------------------------------------------------

@mcp.resource("knowledge://stats/{client_id}")
async def knowledge_stats(client_id: int) -> str:
    """Document and chunk statistics for a client's knowledge base."""
    result = await sync_to_async(_stats_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
