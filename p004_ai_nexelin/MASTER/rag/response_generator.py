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
        language: str | None = None,
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
        # Use local reference to avoid UnboundLocalError
        embedding_service = EmbeddingService
        query_embedding_result = embedding_service.create_embedding(query, embedding_model)
        query_vector = query_embedding_result['vector']
        
        # Track embedding tokens for query (optional, but useful for complete statistics)
        query_tokens = query_embedding_result.get('token_count', 0)
        if query_tokens > 0 and client:
            try:
                from MASTER.processing.models import UsageStats
                from MASTER.processing.usage_sync import send_usage_to_mg_async_delay
                from MASTER.EmbeddingModel.models import ModelPair, LLMProvider
                
                # Find model pair GUID for statistics
                model_pair_guid = None
                try:
                    # Get LLMProvider from client
                    llm_provider_obj = None
                    if hasattr(client, 'llm_provider_model') and client.llm_provider_model:
                        llm_provider_obj = client.llm_provider_model
                    else:
                        # Fallback: find LLMProvider by provider_type and model_name
                        llm_provider_type = getattr(client, 'llm_provider', None)
                        llm_model_name = getattr(client, 'llm_model_name', None)
                        if llm_provider_type and llm_model_name:
                            llm_provider_obj = LLMProvider.objects.filter(
                                provider_type=llm_provider_type,
                                model_name=llm_model_name,
                                is_active=True
                            ).first()
                    
                    # Find ModelPair by LLMProvider + EmbeddingModel
                    if llm_provider_obj:
                        model_pair = ModelPair.objects.filter(
                            llm_provider=llm_provider_obj,
                            embedding_model=embedding_model,
                            is_active=True
                        ).first()
                        if model_pair and model_pair.external_guid:
                            model_pair_guid = model_pair.external_guid
                except Exception:
                    pass  # Best-effort
                
                query_cost = embedding_service.calculate_cost(query_tokens, embedding_model)
                metadata = {
                    'query': query[:200],
                    'embedding_tokens': query_tokens,
                    'llm_tokens': 0,  # For embedding-only stats, LLM = 0
                }
                # Add model pair GUID if found
                if model_pair_guid:
                    metadata['ai_model_guid'] = model_pair_guid
                
                query_usage_stat = UsageStats.objects.create(
                    client=client,
                    embedding_model=embedding_model,
                    operation_type='query',
                    tokens_used=query_tokens,  # Total tokens (embedding + LLM) = embedding tokens + 0
                    cost=query_cost,
                    metadata=metadata,
                )
                # Send to MG asynchronously (best-effort, non-blocking)
                try:
                    send_usage_to_mg_async_delay(query_usage_stat.id)
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"Failed to track query embedding tokens: {e}")

        # Step 2: Vector search (передаємо embedding_model для фільтрації)
        search_results = self.vector_search.search(
            query_vector=query_vector,
            branch=branch,
            specialization=specialization,
            client=client,
            embedding_model=embedding_model,
        )
        
        if not search_results:
            logger.warning("No relevant context found for query - using LLM without context")
            # Продовжуємо без контексту - LLM відповість на основі своїх знань
            search_results = []
        
        if len(search_results) < self.config.get('min_chunks_for_answer', 1):
            logger.warning(f"Insufficient context: {len(search_results)} chunks")
            # Не повертаємо фолбек, а продовжуємо з тим контекстом що є
            # return self._insufficient_context_response(query, search_results, language)
        
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
        llm_result = self.llm_client.generate_response(
            user_query=query,
            context=context,
            client=client,
            specialization=specialization,
            branch=branch,
            stream=False,
        )
        
        # Handle new format (dict with content and usage) or old format (str)
        if isinstance(llm_result, dict):
            answer = cast(str, llm_result.get('content', ''))
            llm_usage = llm_result.get('usage', {})
            llm_model = llm_result.get('model', '')
            llm_provider = llm_result.get('provider', '')
        else:
            # Backward compatibility: old format (str)
            answer = cast(str, llm_result)
            llm_usage = {}
            llm_model = ''
            llm_provider = ''
        
        sources = self._format_sources(context_chunks)
        
        # Get embedding model for UsageStats
        embedding_model = self._get_embedding_model(client, specialization, branch)
        
        # Find model pair GUID for statistics
        model_pair_guid = None
        if client and embedding_model:
            try:
                from MASTER.EmbeddingModel.models import ModelPair, LLMProvider
                # Get LLMProvider from client
                llm_provider_obj = None
                if hasattr(client, 'llm_provider_model') and client.llm_provider_model:
                    llm_provider_obj = client.llm_provider_model
                else:
                    # Fallback: find LLMProvider by provider_type and model_name
                    llm_provider_type = getattr(client, 'llm_provider', None)
                    llm_model_name = getattr(client, 'llm_model_name', None)
                    if llm_provider_type and llm_model_name:
                        llm_provider_obj = LLMProvider.objects.filter(
                            provider_type=llm_provider_type,
                            model_name=llm_model_name,
                            is_active=True
                        ).first()
                
                # Find ModelPair by LLMProvider + EmbeddingModel
                if llm_provider_obj:
                    model_pair = ModelPair.objects.filter(
                        llm_provider=llm_provider_obj,
                        embedding_model=embedding_model,
                        is_active=True
                    ).first()
                    if model_pair and model_pair.external_guid:
                        model_pair_guid = model_pair.external_guid
            except Exception as e:
                logger.debug(f"Failed to find model pair GUID: {e}")
        
        # Create UsageStats for LLM tokens if we have usage info
        if llm_usage and client:
            try:
                from MASTER.processing.models import UsageStats
                from MASTER.processing.usage_sync import send_usage_to_mg_async_delay
                from decimal import Decimal
                
                total_tokens = int(llm_usage.get('total_tokens', 0))
                if total_tokens > 0:
                    # Calculate cost (simplified - can be enhanced with LLMProvider model)
                    # For now, use a default cost per 1k tokens
                    cost_per_1k = Decimal('0.002')  # Default $0.002 per 1k tokens
                    cost = Decimal(total_tokens) / Decimal(1000) * cost_per_1k
                    
                    # Create UsageStats for LLM (embedding tokens = 0, LLM tokens = total_tokens)
                    metadata = {
                        'llm_model': llm_model,
                        'llm_provider': llm_provider,
                        'prompt_tokens': llm_usage.get('prompt_tokens', 0),
                        'completion_tokens': llm_usage.get('completion_tokens', 0),
                        'query': query[:200],  # Store first 200 chars of query
                        'embedding_tokens': 0,  # For LLM-only stats, embedding = 0
                        'llm_tokens': total_tokens,
                    }
                    # Add model pair GUID if found
                    if model_pair_guid:
                        metadata['ai_model_guid'] = model_pair_guid
                    
                    llm_usage_stat = UsageStats.objects.create(
                        client=client,
                        embedding_model=embedding_model,  # Required field, but this is LLM usage
                        operation_type='rag_chat',
                        tokens_used=total_tokens,  # Total tokens (embedding + LLM) = 0 + LLM tokens
                        cost=cost,
                        metadata=metadata,
                    )
                    
                    # Send to MG asynchronously (non-blocking)
                    try:
                        send_usage_to_mg_async_delay(llm_usage_stat.id)
                    except Exception:
                        pass  # Best-effort sync
            except Exception as e:
                logger.warning(f"Failed to create LLM UsageStats: {e}")
        
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
        # Priority 1: client's explicitly selected model
        if client:
            model = getattr(client, 'embedding_model', None)
            if model is not None:
                return model
        # Priority 2: client specialization model
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
    
    def _no_context_response(self, query: str, language: str | None) -> RAGResponse:
        """Response when no relevant context found."""
        lang = (language or '').lower()
        # Відповіді локалізуємо для it, nl, de, en, fr.
        # Якщо мова інша — використовуємо англійський варіант, але сам lang не змінюємо.
        supported = {'en', 'de', 'fr', 'it', 'nl'}
        loc_lang = lang if lang in supported else 'en'
        localized = {
            'en': "I couldn't find enough relevant information to answer precisely. Please rephrase your question or add more details.",
            'de': "Ich konnte nicht genügend relevante Informationen finden. Bitte formulieren Sie die Frage um oder fügen Sie Details hinzu.",
            'fr': "Je n'ai pas trouvé suffisamment d'informations pertinentes pour répondre précisément. Veuillez reformuler votre question ou ajouter des détails.",
            'it': "Non ho trovato informazioni sufficientemente pertinenti per rispondere con precisione. Per favore riformula la domanda o aggiungi dettagli.",
            'nl': "Ik kon niet genoeg relevante informatie vinden om precies te antwoorden. Formuleer je vraag opnieuw of voeg meer details toe.",
        }
        return RAGResponse(
            answer=localized[loc_lang],
            sources=[],
            query=query,
            context_used="",
            num_chunks=0,
            total_tokens=0,
        )
    
    def _insufficient_context_response(self, query: str, search_results, language: str | None) -> RAGResponse:
        """Response when insufficient context found."""
        lang = (language or '').lower()
        supported = {'en', 'de', 'fr', 'it', 'nl'}
        loc_lang = lang if lang in supported else 'en'
        base = {
            'en': "I found some related information, but it may be insufficient for a complete answer.",
            'de': "Ich habe einige relevante Informationen gefunden, die jedoch möglicherweise nicht ausreichen.",
            'fr': "J'ai trouvé quelques informations liées, mais elles peuvent être insuffisantes pour une réponse complète.",
            'it': "Ho trovato alcune informazioni correlate, ma potrebbero non essere sufficienti per una risposta completa.",
            'nl': "Ik heb wat gerelateerde informatie gevonden, maar die is mogelijk niet voldoende voor een volledig antwoord.",
        }
        return RAGResponse(
            answer=f"{base[loc_lang]} ({len(search_results)} chunks)",
            sources=[],
            query=query,
            context_used="",
            num_chunks=len(search_results),
            total_tokens=0,
        )


