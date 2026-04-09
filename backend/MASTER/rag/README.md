# RAG Module (Retrieval-Augmented Generation)

This directory contains the end-to-end RAG pipeline used to answer user queries using semantically similar documents stored with pgvector.

## Components

- `vector_search.py`: Executes semantic search across three levels:
  - Branch-level embeddings
  - Specialization-level embeddings
  - Client-level embeddings
  Results are merged with configurable weights and thresholds.

- `context_builder.py`: Converts the top-N results into a compact context string while optionally including neighbor chunks to preserve continuity. Also tracks token counts.

- `llm_client.py`: Thin wrapper around the LLM provider (OpenAI). Supports:
  - Domain/system prompts with priority: Client > Specialization > Branch > Default
  - Streaming and non-streaming responses
  - Retry and timeout policies

- `response_generator.py`: Orchestrates the whole flow:
  1. Creates a query embedding
  2. Runs vector search (multi-level)
  3. Builds the context
  4. Calls the LLM to produce the final answer
  Returns full answers or a streaming generator, including formatted sources.

## Configuration

All critical settings live in `MASTER/settings.py`:

- `VECTOR_SEARCH_CONFIG` — index parameters, thresholds, result caps, diagnostics
- `RAG_CONFIG` — number of chunks, max tokens, streaming, safety rules
- `LLM_CONFIG` — model, temperature, decoding, retries
- `SYSTEM_PROMPTS` — default and domain-specific system prompts

## Operational Notes (pgvector)

When indexes may not be used (and that's OK):
- Collections < ~1000 vectors
- Highly selective WHERE clauses
- Very small partitions after filtering

When indexes should be used:
- ~10k+ vectors in table/partition
- Global similarity search without strong filters
- Reasonable `ivfflat.probes` / `hnsw.ef_search` settings

Parameters:
- `ivfflat.probes`: 1..lists (higher = more accurate, slower)
- `hnsw.ef_search`: ~40..1000 (higher = more accurate, slower)

Diagnostics:
- Enable `VECTOR_SEARCH_CONFIG.explain_queries` for EXPLAIN ANALYZE
- Consider `force_index_usage` only for diagnostics

## Type-Safety and Stability

- `response_generator.py`: Ensures a non-null `EmbeddingModel` is selected with a clear fallback chain; uses strict typing to avoid `None` and union type leaks.
- `llm_client.py`: Simplified type signatures; returns `str` for non-streaming and `Generator[str, None, None]` for streaming; internal retries and timeouts.

## Example (non-streaming)

```python
from MASTER.rag.response_generator import ResponseGenerator

rg = ResponseGenerator()
res = rg.generate("What are my policy terms?", client=my_client, stream=False)
print(res.answer)
for s in res.sources:
    print(s["title"], s["similarity"]) 
```

