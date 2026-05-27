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

from Jeeves.rag.vector_search import VectorSearchService
from Jeeves.rag.context_builder import ContextBuilder, ContextChunk
from Jeeves.rag.llm_client import LLMClient
from Jeeves.processing.embedding_service import EmbeddingService
from Jeeves.clients.models import Client
from Jeeves.EmbeddingModel.models import EmbeddingModel

# Qdrant + Cohere rerank (with pgvector fallback)
try:
    from Jeeves.rag.qdrant_search import QdrantSearchService
    _qdrant_available = True
except ImportError:
    _qdrant_available = False

if TYPE_CHECKING:
    from Jeeves.branches.models import Branch
    from Jeeves.specializations.models import Specialization

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
    # HITL escalation fields
    requires_escalation: bool = False
    escalation_summary: str = ""
    lead_data: dict | None = None


class ResponseGenerator:
    """Orchestrates full RAG pipeline."""
    
    def __init__(self):
        self.config = settings.RAG_CONFIG
        # Use Qdrant if available and enabled, fallback to pgvector
        use_qdrant = getattr(settings, 'USE_QDRANT', True) and _qdrant_available
        if use_qdrant:
            try:
                self.vector_search = QdrantSearchService()
                logger.info("Using Qdrant vector search with Cohere rerank")
            except Exception as e:
                logger.warning(f"Qdrant init failed, falling back to pgvector: {e}")
                self.vector_search = VectorSearchService()
        else:
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
        
        # Track embedding tokens for query (will be combined with LLM tokens in single UsageStats)
        query_tokens = query_embedding_result.get('token_count', 0)

        # Step 2: Vector search (Qdrant + Cohere rerank, or pgvector fallback)
        search_kwargs = dict(
            query_vector=query_vector,
            branch=branch,
            specialization=specialization,
            client=client,
            embedding_model=embedding_model,
        )
        # Pass query_text for Cohere reranking (QdrantSearchService only)
        if isinstance(self.vector_search, QdrantSearchService if _qdrant_available else type(None)):
            search_kwargs['query_text'] = query
        search_results = self.vector_search.search(**search_kwargs)
        
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
                embedding_model=embedding_model,
                embedding_tokens=query_tokens,
            )
        else:
            return self._generate_complete(
                query=query,
                context=context_string,
                context_chunks=context_chunks,
                client=client,
                specialization=specialization,
                branch=branch,
                embedding_model=embedding_model,
                embedding_tokens=query_tokens,
                language=language or 'en',
            )
    
    def _generate_complete(
        self,
        query: str,
        context: str,
        context_chunks: list[ContextChunk],
        client: Client | None,
        specialization: Specialization | None,
        branch: Branch | None,
        embedding_model: EmbeddingModel | None = None,
        embedding_tokens: int = 0,
        language: str = 'en',
    ) -> RAGResponse:
        """Generate complete (non-streaming) response."""
        llm_result = self.llm_client.generate_response(
            user_query=query,
            context=context,
            client=client,
            specialization=specialization,
            branch=branch,
            stream=False,
            language=language,
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
        
        # Lead extraction: parse lead data from LLM response
        lead_data_extracted = None
        if client and getattr(client, 'leads_enabled', False):
            try:
                from Jeeves.clients.services.lead_extraction import (
                    extract_lead_data_from_response,
                    clean_response,
                )
                lead_data_extracted = extract_lead_data_from_response(answer)
                if lead_data_extracted:
                    answer = clean_response(answer)
            except Exception as e:
                logger.warning(f"Lead extraction error: {e}")

        # HITL: Detect escalation token in response OR refusal phrases OR [escalate] tag in query
        requires_escalation = False
        escalation_summary = ""
        
        # Check if client has HITL enabled for fallback detection
        hitl_enabled = client and getattr(client, 'hitl_enabled', False)
        manager_ids = client.get_manager_telegram_ids() if client and hasattr(client, 'get_manager_telegram_ids') else []
        hitl_available = hitl_enabled and len(manager_ids) > 0

        # Debug logging for HITL status
        logger.info(f"HITL status: enabled={hitl_enabled}, telegram_mgrs={manager_ids}, available={hitl_available}")
        
        # Check for [escalate] tag in query (forced escalation from system prompt)
        # This allows users to add [escalate] markers in their prompts for specific questions
        forced_escalation = '[escalate]' in query.lower()
        print(f"HITL DEBUG: enabled={hitl_enabled}, available={hitl_available}, forced={forced_escalation}, query={query[:80]}", flush=True)
        if forced_escalation:
            logger.info(f"HITL: Forced escalation detected via [escalate] tag in query")

        # Fallback: detect refusal phrases even if LLM didn't output escalation token
        # This catches cases where LLM explicitly refuses to answer a business question
        # IMPORTANT: Only count as refusal if the phrase indicates inability to answer a SPECIFIC question
        refusal_phrases = [
            # English - specific inability phrases
            "i don't have that specific information",
            "i don't have information about that",
            "i cannot provide specific details",
            "i don't have access to that data",
            "i cannot answer that specific question",
            "that information is not available to me",
            # Ukrainian
            "не маю цієї конкретної інформації",
            "не маю інформації про це",
            "не можу надати конкретні деталі",
            # Russian  
            "у меня нет этой конкретной информации",
            "не располагаю этой информацией",
            # German
            "ich habe diese spezifischen informationen nicht",
            "diese information liegt mir nicht vor",
            # French
            "je n'ai pas cette information spécifique",
            "je ne dispose pas de cette information",
        ]
        
        answer_lower = answer.lower()
        # Only trigger refusal if it's a CLEAR refusal about specific information
        # AND the answer is relatively short (actual refusals are usually brief)
        is_refusal = any(phrase in answer_lower for phrase in refusal_phrases) and len(answer) < 500
        
        if '[[ESCALATE_TO_MANAGER]]' in answer:
            requires_escalation = True
            # Extract the summary after the token
            parts = answer.split('[[ESCALATE_TO_MANAGER]]', 1)
            if len(parts) > 1:
                summary_part = parts[1].strip()
                # Try to extract "Question summary: ..." line
                if 'Question summary:' in summary_part:
                    summary_lines = summary_part.split('\n')
                    for line in summary_lines:
                        if line.strip().startswith('Question summary:'):
                            escalation_summary = line.replace('Question summary:', '').strip()
                            break
                if not escalation_summary:
                    # Just take the first line after the token as summary
                    escalation_summary = summary_part.split('\n')[0].strip()[:200]
                if not escalation_summary:
                    escalation_summary = query[:200]  # Fallback to original query
            
            # Clean the answer: keep only the customer-facing message (after removing the token and summary)
            # Usually the message is after the summary line
            clean_parts = answer.split('[[ESCALATE_TO_MANAGER]]')
            if len(clean_parts) > 1:
                after_token = clean_parts[1]
                # Remove the "Question summary: ..." line from the response
                lines = after_token.strip().split('\n')
                customer_message_lines = []
                skip_next = False
                for line in lines:
                    if line.strip().startswith('Question summary:'):
                        skip_next = True
                        continue
                    if skip_next and not line.strip():
                        skip_next = False
                        continue
                    customer_message_lines.append(line)
                answer = self._get_hitl_waiting_message(language)
            
            logger.info(f"HITL escalation detected for query: {query[:100]}..., summary: {escalation_summary}")
        
        # Fallback: If HITL is available and LLM gave a refusal response, trigger escalation
        elif is_refusal and hitl_available:
            requires_escalation = True
            escalation_summary = query[:200]
            # Replace the refusal with a waiting message
            answer = self._get_hitl_waiting_message(language)
            logger.info(f"HITL escalation triggered by refusal detection for query: {query[:100]}...")
        
        # Forced escalation via [escalate] tag - always trigger if HITL is available
        elif forced_escalation and hitl_available:
            requires_escalation = True
            # Remove [escalate] tag from query for summary
            clean_query = query.lower().replace('[escalate]', '').strip()
            escalation_summary = clean_query[:200] if clean_query else query[:200]
            # Keep the original answer but add waiting notice
            answer = f"{answer}\n\n{self._get_hitl_waiting_message(language)}"
            logger.info(f"HITL escalation triggered by [escalate] tag for query: {query[:100]}...")
        
        sources = self._format_sources(context_chunks)
        
        # Get embedding model if not provided
        if not embedding_model:
            embedding_model = self._get_embedding_model(client, specialization, branch)
        
        # Get LLMProvider for cost calculation and statistics
        # Each model (embedding and LLM) has its own GUID from MG platform
        llm_provider_obj = None
        if client:
            try:
                from Jeeves.EmbeddingModel.models import LLMProvider
                # Get LLMProvider from client
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
            except Exception as e:
                logger.debug(f"Failed to find LLMProvider: {e}")
        
        # Create SEPARATE UsageStats records for embedding and LLM tokens
        if client:
            try:
                from Jeeves.processing.models import UsageStats
                from decimal import Decimal

                # Create embedding usage stats if we have embedding tokens
                if embedding_model and embedding_tokens > 0:
                    emb_price = Decimal(str(embedding_model.cost_per_1k_tokens))
                    embedding_cost = (Decimal(embedding_tokens) / Decimal('1000')) * emb_price

                    UsageStats.objects.create(
                        client=client,
                        embedding_model=embedding_model,
                        llm_provider=None,
                        operation_type='rag_chat_embedding',
                        tokens_used=embedding_tokens,
                        cost=embedding_cost,
                        metadata={
                            'query': query[:200],
                            'operation': 'rag_chat_embedding',
                            'embedding_tokens': embedding_tokens,
                        },
                    )

                # Create LLM usage stats if we have LLM tokens
                if llm_provider_obj and llm_usage:
                    llm_tokens = int(llm_usage.get('total_tokens', 0))
                    if llm_tokens > 0:
                        prompt_tokens = int(llm_usage.get('prompt_tokens', 0))
                        completion_tokens = int(llm_usage.get('completion_tokens', 0))

                        if llm_provider_obj:
                            in_price = Decimal(str(llm_provider_obj.cost_per_1k_input_tokens))
                            out_price = Decimal(str(llm_provider_obj.cost_per_1k_output_tokens))
                            llm_cost = (Decimal(prompt_tokens) / Decimal('1000') * in_price) + \
                                       (Decimal(completion_tokens) / Decimal('1000') * out_price)
                        else:
                            logger.warning(f"LLMProvider not found for client {client.id}, using default cost $0.002 per 1k tokens")
                            llm_cost = Decimal(str(llm_tokens)) / Decimal('1000') * Decimal('0.002')

                        UsageStats.objects.create(
                            client=client,
                            embedding_model=None,
                            llm_provider=llm_provider_obj,
                            operation_type='rag_chat_llm',
                            tokens_used=llm_tokens,
                            cost=llm_cost,
                            metadata={
                                'query': query[:200],
                                'operation': 'rag_chat_llm',
                                'llm_tokens': llm_tokens,
                                'llm_model': llm_model,
                                'llm_provider': llm_provider,
                                'prompt_tokens': prompt_tokens,
                                'completion_tokens': completion_tokens,
                            },
                        )
            except Exception as e:
                logger.warning(f"Failed to create separate UsageStats: {e}")
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            query=query,
            context_used=context if settings.DEBUG else "",  # Only in debug
            num_chunks=len(context_chunks),
            total_tokens=self.context_builder._count_tokens(context + answer),
            requires_escalation=requires_escalation,
            escalation_summary=escalation_summary,
            lead_data=lead_data_extracted,
        )
    
    def _generate_streaming(
        self,
        query: str,
        context: str,
        context_chunks: list[ContextChunk],
        client: Client | None,
        specialization: Specialization | None,
        branch: Branch | None,
        embedding_model: EmbeddingModel | None = None,
        embedding_tokens: int = 0,
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
    
    def _get_hitl_waiting_message(self, language: str = 'en') -> str:
        """Get localized waiting message for HITL escalation."""
        messages = {
            'en': "One moment, let me verify this information with my colleague to give you an accurate answer...",
            'de': "Einen Moment bitte, ich überprüfe diese Information mit meinem Kollegen, um Ihnen eine genaue Antwort zu geben...",
            'fr': "Un instant, je vérifie cette information avec mon collègue pour vous donner une réponse précise...",
            'es': "Un momento, permítame verificar esta información con mi colega para darle una respuesta precisa...",
            'it': "Un momento, verifico questa informazione con il mio collega per darle una risposta accurata...",
            'nl': "Een moment alstublieft, ik verifieer deze informatie met mijn collega om u een nauwkeurig antwoord te geven...",
            'da': "Et øjeblik, jeg bekræfter denne information med min kollega for at give dig et præcist svar...",
            'uk': "Зачекайте, я перевірю цю інформацію з колегою, щоб дати вам точну відповідь...",
            'ru': "Минуту, я уточню эту информацию у коллеги, чтобы дать вам точный ответ...",
        }
        return messages.get(language, messages['en'])
    
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
        supported = {'en', 'de', 'fr', 'it', 'nl', 'es', 'da', 'uk', 'ru'}
        loc_lang = lang if lang in supported else 'en'
        localized = {
            'en': "I couldn't find enough relevant information to answer precisely. Please rephrase your question or add more details.",
            'de': "Ich konnte nicht genügend relevante Informationen finden. Bitte formulieren Sie die Frage um oder fügen Sie Details hinzu.",
            'fr': "Je n'ai pas trouvé suffisamment d'informations pertinentes pour répondre précisément. Veuillez reformuler votre question ou ajouter des détails.",
            'it': "Non ho trovato informazioni sufficientemente pertinenti per rispondere con precisione. Per favore riformula la domanda o aggiungi dettagli.",
            'nl': "Ik kon niet genoeg relevante informatie vinden om precies te antwoorden. Formuleer je vraag opnieuw of voeg meer details toe.",
            'es': "No pude encontrar suficiente información relevante para responder con precisión. Reformule su pregunta o añada más detalles.",
            'da': "Jeg kunne ikke finde nok relevant information til at svare præcist. Omformuler venligst dit spørgsmål eller tilføj flere detaljer.",
            'uk': "Не вдалося знайти достатньо релевантної інформації для точної відповіді. Будь ласка, переформулюйте запитання або додайте більше деталей.",
            'ru': "Не удалось найти достаточно релевантной информации для точного ответа. Пожалуйста, переформулируйте вопрос или добавьте больше деталей.",
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
        supported = {'en', 'de', 'fr', 'it', 'nl', 'es', 'da', 'uk', 'ru'}
        loc_lang = lang if lang in supported else 'en'
        base = {
            'en': "I found some related information, but it may be insufficient for a complete answer.",
            'de': "Ich habe einige relevante Informationen gefunden, die jedoch möglicherweise nicht ausreichen.",
            'fr': "J'ai trouvé quelques informations liées, mais elles peuvent être insuffisantes pour une réponse complète.",
            'it': "Ho trovato alcune informazioni correlate, ma potrebbero non essere sufficienti per una risposta completa.",
            'nl': "Ik heb wat gerelateerde informatie gevonden, maar die is mogelijk niet voldoende voor een volledig antwoord.",
            'es': "Encontré información relacionada, pero puede ser insuficiente para una respuesta completa.",
            'da': "Jeg fandt noget relateret information, men det er muligvis ikke tilstrækkeligt til et fuldstændigt svar.",
            'uk': "Знайдено деяку пов'язану інформацію, але її може бути недостатньо для повної відповіді.",
            'ru': "Найдена некоторая связанная информация, но её может быть недостаточно для полного ответа.",
        }
        return RAGResponse(
            answer=f"{base[loc_lang]} ({len(search_results)} chunks)",
            sources=[],
            query=query,
            context_used="",
            num_chunks=len(search_results),
            total_tokens=0,
        )


