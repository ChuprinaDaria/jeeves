"""
Vector similarity search service with multi-level support.

Performs pgvector similarity search across Branch, Specialization, and Client embeddings
with configurable weights and ANN index parameters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, cast

from django.conf import settings
from django.db import connection
from django.db.models import QuerySet, F, Value, FloatField
from django.db.models.functions import Cast
from pgvector.django import CosineDistance  # type: ignore[attr-defined]

from MASTER.branches.models import BranchEmbedding
from MASTER.specializations.models import SpecializationEmbedding
from MASTER.clients.models import ClientEmbedding
from MASTER.restaurant.models import MenuItemEmbedding
from MASTER.EmbeddingModel.models import EmbeddingModel

if TYPE_CHECKING:
    from MASTER.branches.models import Branch
    from MASTER.specializations.models import Specialization
    from MASTER.clients.models import Client

logger = logging.getLogger(__name__)

SearchLevel = Literal['branch', 'specialization', 'client', 'menu']


class SearchResult:
    """Single search result with metadata."""
    
    def __init__(
        self,
        content: str,
        similarity: float,
        level: SearchLevel,
        document_id: int | None,
        document_title: str | None,
        metadata: dict[str, Any],
        chunk_index: int,
    ):
        self.content = content
        self.similarity = similarity
        self.level = level
        self.document_id = document_id
        self.document_title = document_title
        self.metadata = metadata
        self.chunk_index = chunk_index
    
    def __repr__(self) -> str:
        return f"<SearchResult level={self.level} similarity={self.similarity:.3f}>"


class VectorSearchService:
    """Vector similarity search with multi-level support and ANN optimization."""
    
    def __init__(self):
        self.config = settings.VECTOR_SEARCH_CONFIG
        self.similarity_threshold = self.config['similarity_threshold']
        self.max_results_per_level = self.config['max_results_per_level']
        self.weights = self.config['weights']
    
    def search(
        self,
        query_vector: list[float],
        branch: Branch | None = None,
        specialization: Specialization | None = None,
        client: Client | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> list[SearchResult]:
        """
        Multi-level vector similarity search.

        Searches across Branch, Specialization, and Client embeddings with configured weights.
        Automatically sets pgvector ANN parameters for better performance.

        Args:
            query_vector: Embedding vector of the search query
            branch: Optional Branch to filter results
            specialization: Optional Specialization to filter results
            client: Optional Client to filter results
            embedding_model: Embedding model to filter results by (ensures consistency)

        Returns:
            List of SearchResult objects sorted by weighted similarity
        """
        self._set_pgvector_parameters()

        results: list[SearchResult] = []

        # Визначаємо модель для фільтрації (щоб використовувати тільки сумісні embeddings)
        filter_model = embedding_model
        if not filter_model and client:
            filter_model = getattr(client, 'embedding_model', None)
        if not filter_model and specialization:
            filter_model = specialization.get_embedding_model()
        if not filter_model and branch:
            filter_model = branch.get_embedding_model()

        # Пошук завжди з фільтрами - дані клієнта ізольовані та приватні
        # Якщо client переданий - шукаємо ТІЛЬКИ в його даних
        if branch:
            results.extend(self._search_branch_level(query_vector, branch, filter_model))

        if specialization:
            results.extend(self._search_specialization_level(query_vector, specialization, filter_model))

        if client:
            # Пошук ТІЛЬКИ в даних цього клієнта (ізольований, приватний)
            results.extend(self._search_client_level(query_vector, client))
            # Також шукаємо в меню ресторану для клієнтів ресторанного типу
            if client.client_type == 'restaurant':
                results.extend(self._search_menu_level(query_vector, client))

        # Sort by weighted similarity and limit results
        results.sort(key=lambda r: r.similarity, reverse=True)

        return results
    
    def _search_branch_level(
        self,
        query_vector: list[float],
        branch: Branch,
        embedding_model: EmbeddingModel | None = None,
    ) -> list[SearchResult]:
        """Search Branch embeddings using specified embedding model."""
        weight = self.weights['branch']

        queryset = BranchEmbedding.objects.filter(
            branch=branch
        )

        # Фільтруємо по моделі embedding, якщо вона передана
        if embedding_model:
            queryset = queryset.filter(embedding_model=embedding_model)

        queryset = queryset.annotate(
            similarity=1 - Cast(
                CosineDistance(F('vector'), query_vector),
                output_field=FloatField()
            )
        ).filter(
            similarity__gte=self.similarity_threshold
        ).order_by('-similarity')[:self.max_results_per_level]
        
        if self.config['explain_queries']:
            self._explain_query(queryset)
        
        results = []
        for emb in queryset:
            weighted_similarity = self._get_similarity(emb) * weight
            results.append(SearchResult(
                content=emb.content,
                similarity=weighted_similarity,
                level='branch',
                document_id=cast(int | None, getattr(emb, 'document_id', None)) if emb.document else None,
                document_title=emb.document.title if emb.document else None,
                metadata=emb.metadata or {},
                chunk_index=emb.metadata.get('chunk_index', 0) if emb.metadata else 0,
            ))
        
        logger.info(f"Branch search: found {len(results)} results for branch '{branch.name}'")
        return results
    
    def _search_specialization_level(
        self,
        query_vector: list[float],
        specialization: Specialization,
        embedding_model: EmbeddingModel | None = None,
    ) -> list[SearchResult]:
        """Search Specialization embeddings using specified embedding model."""
        weight = self.weights['specialization']

        queryset = SpecializationEmbedding.objects.filter(
            specialization=specialization
        )

        # Фільтруємо по моделі embedding, якщо вона передана
        if embedding_model:
            queryset = queryset.filter(embedding_model=embedding_model)

        queryset = queryset.annotate(
            similarity=1 - Cast(
                CosineDistance(F('vector'), query_vector),
                output_field=FloatField()
            )
        ).filter(
            similarity__gte=self.similarity_threshold
        ).order_by('-similarity')[:self.max_results_per_level]
        
        if self.config['explain_queries']:
            self._explain_query(queryset)
        
        results = []
        for emb in queryset:
            weighted_similarity = self._get_similarity(emb) * weight
            results.append(SearchResult(
                content=emb.content,
                similarity=weighted_similarity,
                level='specialization',
                document_id=cast(int | None, getattr(emb, 'document_id', None)) if emb.document else None,
                document_title=emb.document.title if emb.document else None,
                metadata=emb.metadata or {},
                chunk_index=emb.metadata.get('chunk_index', 0) if emb.metadata else 0,
            ))
        
        logger.info(f"Specialization search: found {len(results)} results for '{specialization.name}'")
        return results
    
    def _search_client_level(
        self,
        query_vector: list[float],
        client: Client,
    ) -> list[SearchResult]:
        """Search Client embeddings using only the client's current embedding model."""
        weight = self.weights['client']
        
        # Фільтруємо embeddings тільки по поточній моделі клієнта
        # щоб не змішувати embeddings різних моделей
        embedding_model = getattr(client, 'embedding_model', None)
        
        queryset = ClientEmbedding.objects.filter(
            client=client
        )
        
        # Якщо клієнт має обрану модель, використовуємо тільки її embeddings
        if embedding_model:
            queryset = queryset.filter(embedding_model=embedding_model)
        
        queryset = queryset.annotate(
            similarity=1 - Cast(
                CosineDistance(F('vector'), query_vector),
                output_field=FloatField()
            )
        ).filter(
            similarity__gte=self.similarity_threshold
        ).order_by('-similarity')[:self.max_results_per_level]
        
        if self.config['explain_queries']:
            self._explain_query(queryset)
        
        results = []
        for emb in queryset:
            weighted_similarity = self._get_similarity(emb) * weight
            results.append(SearchResult(
                content=emb.content,
                similarity=weighted_similarity,
                level='client',
                document_id=cast(int | None, getattr(emb, 'document_id', None)) if emb.document else None,
                document_title=emb.document.title if emb.document else None,
                metadata=emb.metadata or {},
                chunk_index=emb.metadata.get('chunk_index', 0) if emb.metadata else 0,
            ))
        
        logger.info(f"Client search: found {len(results)} results for client '{client.user.username}'")
        return results
    
    def _search_menu_level(
        self,
        query_vector: list[float],
        client: Client,
    ) -> list[SearchResult]:
        """Search MenuItem embeddings for restaurant clients using only the client's current embedding model."""
        weight = self.weights.get('menu', 0.8)  # Використовуємо вагу для меню
        
        # Фільтруємо embeddings тільки по поточній моделі клієнта
        embedding_model = getattr(client, 'embedding_model', None)
        
        queryset = MenuItemEmbedding.objects.filter(
            menu_item__client=client
        )
        
        # Якщо клієнт має обрану модель, використовуємо тільки її embeddings
        if embedding_model:
            queryset = queryset.filter(embedding_model=embedding_model)
        
        queryset = queryset.annotate(
            similarity=1 - Cast(
                CosineDistance(F('vector'), query_vector),
                output_field=FloatField()
            )
        ).filter(
            similarity__gte=self.similarity_threshold
        ).order_by('-similarity')[:self.max_results_per_level]
        
        if self.config['explain_queries']:
            self._explain_query(queryset)
        
        results = []
        for emb in queryset:
            weighted_similarity = self._get_similarity(emb) * weight
            results.append(SearchResult(
                content=emb.content,
                similarity=weighted_similarity,
                level='menu',
                document_id=emb.menu_item.id,
                document_title=emb.menu_item.name,
                metadata={
                    'menu_item_id': emb.menu_item.id,
                    'menu_item_name': emb.menu_item.name,
                    'category': emb.menu_item.category.name if emb.menu_item.category else None,
                    'price': float(emb.menu_item.get_display_price()),
                    'language': emb.language,
                },
                chunk_index=0,  # Menu items are single chunks
            ))
        
        logger.info(f"Menu search: found {len(results)} results for client '{client.user.username}'")
        return results
    
    def _set_pgvector_parameters(self) -> None:
        """Set pgvector ANN index parameters for better search quality."""
        with connection.cursor() as cursor:
            # IVFFlat parameters
            ivfflat_probes = self.config['ivfflat_probes']
            cursor.execute(f"SET ivfflat.probes = {ivfflat_probes}")
            
            # HNSW parameters
            hnsw_ef_search = self.config['hnsw_ef_search']
            cursor.execute(f"SET hnsw.ef_search = {hnsw_ef_search}")
            
            # Optionally disable seq scan for debugging
            if self.config['force_index_usage']:
                cursor.execute("SET enable_seqscan = off")
                logger.warning("⚠️ Seq scan disabled - for diagnostics only!")
            
            logger.debug(f"pgvector parameters set: probes={ivfflat_probes}, ef_search={hnsw_ef_search}")
    
    def _explain_query(self, queryset: QuerySet) -> None:
        """Log EXPLAIN ANALYZE for query diagnostics."""
        if not self.config.get('log_query_plans', False):
            return
        
        sql, params = queryset.query.sql_with_params()
        explain_sql = f"EXPLAIN ANALYZE {sql}"
        
        with connection.cursor() as cursor:
            cursor.execute(explain_sql, params)
            plan = cursor.fetchall()
            
            logger.debug("=== QUERY PLAN ===")
            for row in plan:
                logger.debug(row[0])
            logger.debug("==================")

    def _get_similarity(self, obj: Any) -> float:
        """Safely read annotated similarity added via queryset.annotate for static type checkers."""
        sim = getattr(obj, 'similarity', None)
        try:
            return float(sim) if sim is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

