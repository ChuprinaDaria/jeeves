"""Builtin RAG search tool — wraps existing vector search pipeline."""
import logging

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


async def rag_search(connection, tool_name, query, **kwargs):
    """Search knowledge base via existing VectorSearchService.
    Wraps existing code — does not rewrite anything."""
    from Jeeves.agents.models import AgentConfig
    from Jeeves.concierge_platform.models import PlatformDefaults
    from Jeeves.clients.models import Client

    client = connection.client
    defaults = PlatformDefaults.get()

    try:
        agent_config = await AgentConfig.objects.select_related(
            'embedding_model'
        ).aget(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = None

    # Use existing response_generator which handles embedding + search + rerank
    results = await sync_to_async(_search_sync)(client, query, agent_config, defaults)
    return results


def _search_sync(client, query, agent_config, defaults):
    """Sync search wrapper — calls existing pipeline."""
    try:
        from Jeeves.rag.vector_search import VectorSearchService, SearchResult
        from Jeeves.rag.context_builder import ContextBuilder

        # Get embedding model
        embedding_model = None
        if agent_config and agent_config.embedding_model:
            embedding_model = agent_config.embedding_model
        elif defaults.default_embedding_model:
            embedding_model = defaults.default_embedding_model
        elif client.embedding_model:
            embedding_model = client.embedding_model

        if not embedding_model:
            return {'chunks': [], 'error': 'No embedding model configured'}

        # Create embedding for query
        from Jeeves.rag.context_builder import ContextBuilder
        builder = ContextBuilder()
        query_vector = builder._create_embedding(query, embedding_model)

        if not query_vector:
            return {'chunks': [], 'error': 'Failed to create embedding'}

        # Search
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
                'similarity': r.similarity,
                'level': r.level,
                'document_title': r.document_title,
            }
            for r in results
        ]

        return {'chunks': chunks, 'query': query}

    except Exception as e:
        logger.error(f'RAG search error for client {client.pk}: {e}')
        return {'chunks': [], 'error': str(e)}
