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
    # HITL escalation fields
    requires_escalation: bool = False
    escalation_summary: str = ""


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
        
        # Track embedding tokens for query (will be combined with LLM tokens in single UsageStats)
        query_tokens = query_embedding_result.get('token_count', 0)

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
        
        # HITL: Detect escalation token in response OR refusal phrases OR [escalate] tag in query
        requires_escalation = False
        escalation_summary = ""
        
        # Check if client has HITL enabled for fallback detection
        hitl_enabled = client and getattr(client, 'hitl_enabled', False)
        manager_ids = client.get_manager_telegram_ids() if client and hasattr(client, 'get_manager_telegram_ids') else []
        hitl_available = hitl_enabled and len(manager_ids) > 0
        
        # Debug logging for HITL status
        logger.info(f"HITL status: enabled={hitl_enabled}, manager_ids={manager_ids}, available={hitl_available}")
        
        # Check for [escalate] tag in query (forced escalation from system prompt)
        # This allows users to add [escalate] markers in their prompts for specific questions
        forced_escalation = '[escalate]' in query.lower()
        if forced_escalation:
            logger.info(f"HITL: Forced escalation detected via [escalate] tag in query")
        
        # Fallback: detect refusal phrases even if LLM didn't output escalation token
        # This catches cases where LLM says "can't help" but didn't follow the escalation protocol
        refusal_phrases = [
            # English
            "can't help", "cannot help", "cannot assist", "can't assist",
            "unable to help", "unable to assist", "i don't have information",
            "i cannot provide", "i can't provide", "not able to",
            "beyond my capabilities", "outside my knowledge",
            # Ukrainian
            "не можу допомогти", "не маю інформації", "не можу відповісти",
            # Russian  
            "не могу помочь", "не могу ответить", "не располагаю информацией",
            # German
            "kann nicht helfen", "kann ich nicht", "keine informationen",
            # French
            "ne peux pas aider", "je ne peux pas", "pas d'information",
        ]
        
        answer_lower = answer.lower()
        is_refusal = any(phrase in answer_lower for phrase in refusal_phrases)
        
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
                answer = '\n'.join(customer_message_lines).strip()
                if not answer:
                    # Fallback: provide a waiting message
                    answer = "One moment, let me verify this information with my colleague to give you an accurate answer..."
            
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
        
        # Find model pair GUID for statistics and get LLMProvider for cost calculation
        model_pair_guid = None
        llm_provider_obj = None  # Will be reused for cost calculation
        if client and embedding_model:
            try:
                from MASTER.EmbeddingModel.models import ModelPair, LLMProvider
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
        
        # Create ONE combined UsageStats record with embedding + LLM tokens if we have usage info
        if client and embedding_model:
            try:
                from MASTER.processing.models import UsageStats
                from MASTER.processing.usage_sync import send_usage_to_mg_async_delay
                from decimal import Decimal
                
                # Calculate embedding cost
                emb_price = Decimal(str(embedding_model.cost_per_1k_tokens))
                embedding_cost = (Decimal(embedding_tokens) / Decimal('1000')) * emb_price if embedding_tokens > 0 else Decimal('0')
                
                # Calculate LLM cost and tokens
                llm_tokens = 0
                llm_cost = Decimal('0')
                prompt_tokens = 0
                completion_tokens = 0
                
                if llm_usage:
                    llm_tokens = int(llm_usage.get('total_tokens', 0))
                    if llm_tokens > 0:
                        prompt_tokens = int(llm_usage.get('prompt_tokens', 0))
                        completion_tokens = int(llm_usage.get('completion_tokens', 0))
                        
                        # Calculate cost using LLMProvider pricing
                        if llm_provider_obj:
                            # Use real pricing from LLMProvider (separate input and output costs)
                            in_price = Decimal(str(llm_provider_obj.cost_per_1k_input_tokens))
                            out_price = Decimal(str(llm_provider_obj.cost_per_1k_output_tokens))
                            llm_cost = (Decimal(prompt_tokens) / Decimal('1000') * in_price) + \
                                       (Decimal(completion_tokens) / Decimal('1000') * out_price)
                        else:
                            # Fallback: use default cost if provider not found
                            logger.warning(f"LLMProvider not found for client {client.id}, using default cost $0.002 per 1k tokens")
                            llm_cost = Decimal(str(llm_tokens)) / Decimal('1000') * Decimal('0.002')
                
                # Only create UsageStats if we have tokens (embedding or LLM)
                total_tokens_combined = embedding_tokens + llm_tokens
                if total_tokens_combined > 0:
                    # Create ONE combined UsageStats record with sum of embedding + LLM tokens
                    metadata = {
                        'query': query[:200],  # Store first 200 chars of query
                        'embedding_tokens': embedding_tokens,
                        'llm_tokens': llm_tokens,
                        'llm_model': llm_model,
                        'llm_provider': llm_provider,
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                    }
                    # Add model pair GUID if found (REQUIRED for API)
                    if model_pair_guid:
                        metadata['ai_model_guid'] = model_pair_guid
                    else:
                        logger.warning(f"ModelPair GUID not found for client {client.id}, LLM {llm_provider_obj}, Embedding {embedding_model.id}")
                    
                    combined_usage_stat = UsageStats.objects.create(
                        client=client,
                        embedding_model=embedding_model,
                        operation_type='rag_chat',
                        tokens_used=total_tokens_combined,  # Total tokens = embedding + LLM (sum)
                        cost=embedding_cost + llm_cost,  # Combined cost = embedding cost + LLM cost
                        metadata=metadata,
                    )
                    
                    # Send to MG asynchronously (non-blocking)
                    # API expects: tokens = sum(embedding + LLM), ai_model = ModelPair.external_guid
                    try:
                        send_usage_to_mg_async_delay(combined_usage_stat.id)
                    except Exception:
                        pass  # Best-effort sync
            except Exception as e:
                logger.warning(f"Failed to create combined UsageStats: {e}")
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            query=query,
            context_used=context if settings.DEBUG else "",  # Only in debug
            num_chunks=len(context_chunks),
            total_tokens=self.context_builder._count_tokens(context + answer),
            requires_escalation=requires_escalation,
            escalation_summary=escalation_summary,
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


