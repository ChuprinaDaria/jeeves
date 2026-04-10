"""
Qdrant vector search service with multi-level support and Cohere reranking.

Drop-in replacement for pgvector VectorSearchService.
Uses the same SearchResult class and search() interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .vector_search import SearchResult, SearchLevel

if TYPE_CHECKING:
    from Jeeves.branches.models import Branch
    from Jeeves.specializations.models import Specialization
    from Jeeves.clients.models import Client
    from Jeeves.EmbeddingModel.models import EmbeddingModel

logger = logging.getLogger(__name__)

QDRANT_HOST = getattr(settings, 'QDRANT_HOST', 'concierge_qdrant')
QDRANT_PORT = getattr(settings, 'QDRANT_PORT', 6333)
QDRANT_COLLECTION = getattr(settings, 'QDRANT_COLLECTION', 'concierge_embeddings')
COHERE_API_KEY = getattr(settings, 'COHERE_API_KEY', '')
COHERE_RERANK_MODEL = getattr(settings, 'COHERE_RERANK_MODEL', 'rerank-multilingual-v3.0')


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10.0)


def _cohere_rerank(query: str, results: list[SearchResult], top_n: int = 5) -> list[SearchResult]:
    """Rerank search results using Cohere Rerank API."""
    if not COHERE_API_KEY or not results:
        return results[:top_n]

    try:
        import cohere
        co = cohere.ClientV2(api_key=COHERE_API_KEY)

        documents = [r.content for r in results]
        response = co.rerank(
            model=COHERE_RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )

        reranked = []
        for item in response.results:
            original = results[item.index]
            original.similarity = item.relevance_score
            original.metadata['rerank_score'] = item.relevance_score
            original.metadata['original_rank'] = item.index
            reranked.append(original)

        logger.info(f"Cohere rerank: {len(results)} → {len(reranked)} results")
        return reranked

    except Exception as e:
        logger.warning(f"Cohere rerank failed, returning original order: {e}")
        return results[:top_n]


class QdrantSearchService:
    """Qdrant vector search with multi-level support. Same interface as VectorSearchService."""

    def __init__(self):
        self.config = settings.VECTOR_SEARCH_CONFIG
        self.similarity_threshold = self.config['similarity_threshold']
        self.max_results_per_level = self.config['max_results_per_level']
        self.weights = self.config['weights']
        self._client = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = _get_qdrant_client()
        return self._client

    def search(
        self,
        query_vector: list[float],
        branch: Branch | None = None,
        specialization: Specialization | None = None,
        client: Client | None = None,
        embedding_model: EmbeddingModel | None = None,
        query_text: str = '',
    ) -> list[SearchResult]:
        """
        Multi-level vector search via Qdrant with optional Cohere reranking.

        Same interface as VectorSearchService.search() with added query_text
        param for reranking (pass the original user question).
        """
        results: list[SearchResult] = []

        if client:
            results.extend(self._search_qdrant(
                query_vector=query_vector,
                client_id=client.id,
                embedding_model_id=getattr(client.embedding_model, 'id', None) if hasattr(client, 'embedding_model') and client.embedding_model else None,
                level='client',
                weight=self.weights['client'],
            ))

        # Rerank with Cohere if query_text provided
        if query_text and results:
            results = _cohere_rerank(query_text, results, top_n=self.max_results_per_level)
        else:
            results.sort(key=lambda r: r.similarity, reverse=True)
            results = results[:self.max_results_per_level]

        return results

    def _search_qdrant(
        self,
        query_vector: list[float],
        client_id: int | None = None,
        embedding_model_id: int | None = None,
        level: SearchLevel = 'client',
        weight: float = 1.0,
    ) -> list[SearchResult]:
        """Search Qdrant collection with payload filtering."""
        must_conditions = []

        if client_id is not None:
            must_conditions.append(
                FieldCondition(key='client_id', match=MatchValue(value=client_id))
            )
        if embedding_model_id is not None:
            must_conditions.append(
                FieldCondition(key='embedding_model_id', match=MatchValue(value=embedding_model_id))
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        # Retrieve more candidates for reranking (20 instead of 5)
        retrieve_limit = 20 if COHERE_API_KEY else self.max_results_per_level

        try:
            hits = self.client.query_points(
                collection_name=QDRANT_COLLECTION,
                query=query_vector,
                query_filter=query_filter,
                limit=retrieve_limit,
                score_threshold=self.similarity_threshold,
                with_payload=True,
            ).points
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []

        results = []
        for hit in hits:
            payload = hit.payload or {}
            metadata = payload.get('metadata', {})
            similarity = (hit.score or 0.0) * weight

            results.append(SearchResult(
                content=payload.get('content', ''),
                similarity=similarity,
                level=level,
                document_id=payload.get('document_id'),
                document_title=metadata.get('source_file', ''),
                metadata=metadata,
                chunk_index=metadata.get('chunk_index', 0),
            ))

        logger.info(f"Qdrant search: {len(results)} results for client_id={client_id}")
        return results
