"""
Response Generator - orchestrates RAG pipeline.

Combines:
- Vector search
- Context building
- LLM generation
- Source citations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Generator, Any, cast
from dataclasses import dataclass

from django.conf import settings

from MASTER.rag.vector_search import VectorSearchService
from MASTER.rag.context_builder import ContextBuilder, ContextChunk
from MASTER.rag.llm_client import LLMClient
from MASTER.processing.embedding_service import EmbeddingService
from MASTER.clients.models import Client
from MASTER.EmbeddingModel.models import EmbeddingModel

if TYPE_CHECKING:
    from MASTER.branches.models import Branch
    from MASTER.specializations.models import Specialization

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Complete RAG response with metadata."""
    answer: str
    sources: list[dict[str, Any]]
    query: str
    context_used: str
    num_chunks: int
    total_tokens: int


class ResponseGenerator:
    """Orchestrates full RAG pipeline."""
    
    def __init__(self):
        self.config = settings.RAG_CONFIG
        self.vector_search = VectorSearchService()
        self.context_builder = ContextBuilder()
        self.llm_client = LLMClient()
    
    def generate(
        self,
        query: str,
        client: Client | None = None,
        specialization: Specialization | None = None,
        branch: Branch | None = None,
        stream: bool = False,
    ) -> RAGResponse | Generator[str, None, None]:
        """
        Generate response using full RAG pipeline.
        
        Args:
            query: User's question
            client: Client context
            specialization: Specialization context
            branch: Branch context
            stream: Whether to stream response
            
        Returns:
            RAGResponse object or generator of response chunks if streaming
        """
        logger.info(f"RAG query: '{query[:100]}...' for client={client}, spec={specialization}, branch={branch}")
        
        # Step 1: Create query embedding
        embedding_model = self._get_embedding_model(client, specialization, branch)
        query_embedding_result = EmbeddingService.create_embedding(query, embedding_model)
        query_vector = query_embedding_result['vector']

        # Step 2: Vector search (передаємо embedding_model для фільтрації)
        search_results = self.vector_search.search(
            query_vector=query_vector,
            branch=branch,
            specialization=specialization,
            client=client,
            embedding_model=embedding_model,
        )
        
        if not search_results:
            logger.warning("No relevant context found for query")
            return self._no_context_response(query)
        
        if len(search_results) < self.config['min_chunks_for_answer']:
            logger.warning(f"Insufficient context: {len(search_results)} chunks")
            return self._insufficient_context_response(query, search_results)
        
        # Step 3: Build context
        context_string, context_chunks = self.context_builder.build_context(
            search_results=search_results,
            include_neighbors=True,
        )
        
        # Step 4: Generate response
        if stream:
            return self._generate_streaming(
                query=query,
                context=context_string,
                context_chunks=context_chunks,
                client=client,
                specialization=specialization,
                branch=branch,
            )
        else:
            return self._generate_complete(
                query=query,
                context=context_string,
                context_chunks=context_chunks,
                client=client,
                specialization=specialization,
                branch=branch,
            )
    
    def _generate_complete(
        self,
        query: str,
        context: str,
        context_chunks: list[ContextChunk],
        client: Client | None,
        specialization: Specialization | None,
        branch: Branch | None,
    ) -> RAGResponse:
        """Generate complete (non-streaming) response."""
        answer = cast(str, self.llm_client.generate_response(
            user_query=query,
            context=context,
            client=client,
            specialization=specialization,
            branch=branch,
            stream=False,
        ))
        
        sources = self._format_sources(context_chunks)
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            query=query,
            context_used=context if settings.DEBUG else "",  # Only in debug
            num_chunks=len(context_chunks),
            total_tokens=self.context_builder._count_tokens(context + answer),
        )
    
    def _generate_streaming(
        self,
        query: str,
        context: str,
        context_chunks: list[ContextChunk],
        client: Client | None,
        specialization: Specialization | None,
        branch: Branch | None,
    ) -> Generator[str, None, None]:
        """Generate streaming response."""
        # First, yield sources metadata
        sources = self._format_sources(context_chunks)
        sources_json = {
            "type": "sources",
            "sources": sources,
            "num_chunks": len(context_chunks),
        }
        yield f"data: {sources_json}\n\n"
        
        # Then stream answer chunks
        response_stream = self.llm_client.generate_response(
            user_query=query,
            context=context,
            client=client,
            specialization=specialization,
            branch=branch,
            stream=True,
        )
        
        for chunk in response_stream:
            yield f"data: {chunk}\n\n"
        
        # Final event
        yield "data: [DONE]\n\n"
    
    def _format_sources(self, chunks: list[ContextChunk]) -> list[dict[str, Any]]:
        """Format context chunks as source citations."""
        sources = []
        seen_sources = set()
        
        for chunk in chunks:
            source_key = (chunk.source_title, chunk.source_level)
            if source_key not in seen_sources:
                sources.append({
                    "title": chunk.source_title,
                    "level": chunk.source_level,
                    "similarity": chunk.similarity,
                })
                seen_sources.add(source_key)
        
        return sources
    
    def _get_embedding_model(
        self,
        client: Client | None,
        specialization: Specialization | None,
        branch: Branch | None,
    ) -> EmbeddingModel:
        """Get appropriate embedding model ensuring non-None return."""
        # Try client specialization model
        if client and client.specialization:
            model = client.specialization.get_embedding_model()
            if model is not None:
                return model
        # Try explicit specialization
        if specialization:
            model = specialization.get_embedding_model()
            if model is not None:
                return model
        # Try branch-level model
        if branch:
            model = branch.get_embedding_model()
            if model is not None:
                return model
        # Fallback to default active model
        default_model = EmbeddingModel.objects.filter(is_default=True, is_active=True).first()
        if default_model is not None:
            return default_model
        # As a last resort, pick any active model
        any_active = EmbeddingModel.objects.filter(is_active=True).first()
        if any_active is not None:
            return any_active
        # If no models exist, fail fast with a clear error
        raise ValueError("No EmbeddingModel configured. Create a default active embedding model in admin.")
    
    def _no_context_response(self, query: str) -> RAGResponse:
        """Response when no relevant context found."""
        return RAGResponse(
            answer="I couldn't find any relevant information to answer your question. Please try rephrasing or ask about a different topic.",
            sources=[],
            query=query,
            context_used="",
            num_chunks=0,
            total_tokens=0,
        )
    
    def _insufficient_context_response(self, query: str, search_results) -> RAGResponse:
        """Response when insufficient context found."""
        return RAGResponse(
            answer=f"I found some related information but it may not fully answer your question. I have {len(search_results)} relevant chunks which might be below the confidence threshold.",
            sources=[],
            query=query,
            context_used="",
            num_chunks=len(search_results),
            total_tokens=0,
        )


