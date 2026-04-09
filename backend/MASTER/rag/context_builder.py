"""
Context assembly service for RAG pipeline.

Takes search results and builds optimized context for LLM with:
- Chunk neighbor loading (context window)
- Token counting and limiting
- Source citation metadata
- Deduplication
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from collections import defaultdict

from django.conf import settings

from MASTER.rag.vector_search import SearchResult
from MASTER.branches.models import BranchEmbedding, BranchDocument
from MASTER.specializations.models import SpecializationEmbedding, SpecializationDocument
from MASTER.clients.models import ClientEmbedding, ClientDocument

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

try:
    import tiktoken
except ImportError:
    tiktoken = None
    logger.warning("tiktoken not available, using approximate token counting")


class ContextChunk:
    """Single chunk of context with metadata for LLM."""
    
    def __init__(
        self,
        content: str,
        source_title: str,
        source_level: str,
        chunk_index: int,
        similarity: float,
    ):
        self.content = content
        self.source_title = source_title
        self.source_level = source_level
        self.chunk_index = chunk_index
        self.similarity = similarity
    
    def to_citation(self) -> str:
        """Format as citation for LLM context."""
        return f"[Source: {self.source_title} - {self.source_level.upper()} - chunk {self.chunk_index}]"
    
    def __repr__(self) -> str:
        return f"<ContextChunk from={self.source_title} similarity={self.similarity:.3f}>"


class ContextBuilder:
    """Builds optimized context for LLM from search results."""
    
    def __init__(self):
        self.config = settings.RAG_CONFIG
        self.context_window = self.config['chunk_context_window']
        self.max_chunks = self.config['max_context_chunks']
        self.max_tokens = self.config['max_context_tokens']
        
        if tiktoken:
            self.encoding = tiktoken.encoding_for_model("gpt-4")
        else:
            self.encoding = None
    
    def build_context(
        self,
        search_results: list[SearchResult],
        include_neighbors: bool = True,
    ) -> tuple[str, list[ContextChunk]]:
        """
        Build context string for LLM from search results.
        
        Args:
            search_results: Sorted list of search results
            include_neighbors: Whether to load neighboring chunks for better context
            
        Returns:
            Tuple of (context_string, list_of_chunks)
            context_string: Formatted string ready for LLM
            list_of_chunks: Metadata about included chunks for citations
        """
        # Group results by document to load neighbors efficiently
        chunks_by_doc = self._group_by_document(search_results)
        
        # Load neighbor chunks if requested
        if include_neighbors and self.context_window > 0:
            chunks_by_doc = self._load_neighbor_chunks(chunks_by_doc)
        
        # Flatten, deduplicate, and limit by tokens
        context_chunks = self._assemble_chunks(chunks_by_doc, search_results)
        
        # Build final context string
        context_string = self._format_context(context_chunks)
        
        logger.info(f"Built context: {len(context_chunks)} chunks, ~{self._count_tokens(context_string)} tokens")
        
        return context_string, context_chunks
    
    def _group_by_document(
        self,
        search_results: list[SearchResult],
    ) -> dict[tuple[str, int | None], list[SearchResult]]:
        """Group search results by (level, document_id)."""
        grouped: dict[tuple[str, int | None], list[SearchResult]] = defaultdict(list)
        
        for result in search_results:
            key = (result.level, result.document_id)
            grouped[key].append(result)
        
        return grouped
    
    def _load_neighbor_chunks(
        self,
        chunks_by_doc: dict[tuple[str, int | None], list[SearchResult]],
    ) -> dict[tuple[str, int | None], list[SearchResult]]:
        """Load neighboring chunks for better context continuity."""
        enhanced_results: dict[tuple[str, int | None], list[SearchResult]] = {}
        
        for (level, doc_id), results in chunks_by_doc.items():
            if not doc_id:
                enhanced_results[(level, doc_id)] = results
                continue
            
            # Get all chunk indices we need
            chunk_indices = set()
            for result in results:
                idx = result.chunk_index
                # Add neighbors: idx-window, idx-window+1, ..., idx, ..., idx+window
                for offset in range(-self.context_window, self.context_window + 1):
                    chunk_indices.add(idx + offset)
            
            # Load chunks from database
            neighbor_results = self._load_chunks_from_db(level, doc_id, chunk_indices)
            
            # Merge with original results (keep original similarity scores)
            all_results = {r.chunk_index: r for r in neighbor_results}
            for result in results:
                all_results[result.chunk_index] = result  # Original takes precedence
            
            enhanced_results[(level, doc_id)] = sorted(
                all_results.values(),
                key=lambda r: r.chunk_index
            )
        
        return enhanced_results
    
    def _load_chunks_from_db(
        self,
        level: str,
        doc_id: int,
        chunk_indices: set[int],
    ) -> list[SearchResult]:
        """Load specific chunks from database by indices."""
        results = []
        
        if level == 'branch':
            embeddings = BranchEmbedding.objects.filter(
                document_id=doc_id
            ).select_related('document')
            
            for emb in embeddings:
                chunk_idx = emb.metadata.get('chunk_index', 0) if emb.metadata else 0
                if chunk_idx in chunk_indices:
                    results.append(SearchResult(
                        content=emb.content,
                        similarity=0.0,  # Neighbor, not from search
                        level='branch',
                        document_id=doc_id,
                        document_title=emb.document.title if emb.document else None,
                        metadata=emb.metadata or {},
                        chunk_index=chunk_idx,
                    ))
        
        elif level == 'specialization':
            embeddings = SpecializationEmbedding.objects.filter(
                document_id=doc_id
            ).select_related('document')
            
            for emb in embeddings:
                chunk_idx = emb.metadata.get('chunk_index', 0) if emb.metadata else 0
                if chunk_idx in chunk_indices:
                    results.append(SearchResult(
                        content=emb.content,
                        similarity=0.0,
                        level='specialization',
                        document_id=doc_id,
                        document_title=emb.document.title if emb.document else None,
                        metadata=emb.metadata or {},
                        chunk_index=chunk_idx,
                    ))
        
        elif level == 'client':
            embeddings = ClientEmbedding.objects.filter(
                document_id=doc_id
            ).select_related('document')
            
            for emb in embeddings:
                chunk_idx = emb.metadata.get('chunk_index', 0) if emb.metadata else 0
                if chunk_idx in chunk_indices:
                    results.append(SearchResult(
                        content=emb.content,
                        similarity=0.0,
                        level='client',
                        document_id=doc_id,
                        document_title=emb.document.title if emb.document else None,
                        metadata=emb.metadata or {},
                        chunk_index=chunk_idx,
                    ))
        
        return results
    
    def _assemble_chunks(
        self,
        chunks_by_doc: dict[tuple[str, int | None], list[SearchResult]],
        original_results: list[SearchResult],
    ) -> list[ContextChunk]:
        """Assemble final list of chunks within token limit."""
        context_chunks: list[ContextChunk] = []
        total_tokens = 0
        seen_content = set()  # Deduplication
        
        # Process in order of original similarity scores
        for result in original_results:
            if len(context_chunks) >= self.max_chunks:
                break
            
            key = (result.level, result.document_id)
            doc_chunks = chunks_by_doc.get(key, [])
            
            for doc_result in doc_chunks:
                # Deduplicate
                if doc_result.content in seen_content:
                    continue
                
                # Count tokens
                chunk_tokens = self._count_tokens(doc_result.content)
                if total_tokens + chunk_tokens > self.max_tokens:
                    logger.warning(f"Token limit reached: {total_tokens}/{self.max_tokens}")
                    break
                
                # Add chunk
                context_chunks.append(ContextChunk(
                    content=doc_result.content,
                    source_title=doc_result.document_title or "Unknown",
                    source_level=doc_result.level,
                    chunk_index=doc_result.chunk_index,
                    similarity=doc_result.similarity,
                ))
                
                seen_content.add(doc_result.content)
                total_tokens += chunk_tokens
                
                if len(context_chunks) >= self.max_chunks:
                    break
            
            if len(context_chunks) >= self.max_chunks:
                break
        
        return context_chunks
    
    def _format_context(self, chunks: list[ContextChunk]) -> str:
        """Format chunks into context string for LLM."""
        if not chunks:
            return ""
        
        parts = ["=== RELEVANT CONTEXT ===\n"]
        
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"\n--- Context {i} ---")
            parts.append(f"{chunk.to_citation()}")
            parts.append(chunk.content)
            parts.append("")
        
        parts.append("=== END CONTEXT ===")
        
        return "\n".join(parts)
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Approximate: 1 token ≈ 4 characters
            return len(text) // 4


