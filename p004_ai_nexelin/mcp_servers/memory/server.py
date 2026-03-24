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
from mcp.server.fastmcp import FastMCP  # noqa: E402

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
