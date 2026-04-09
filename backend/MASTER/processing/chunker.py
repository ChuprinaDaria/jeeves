from __future__ import annotations

from typing import Any, Dict, List

try:
    import tiktoken
except Exception:  # noqa: BLE001
    tiktoken = None  # type: ignore[assignment]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    encoding_name: str = "cl100k_base",
) -> List[Dict[str, Any]]:
    """Split text into token-based chunks with metadata.

    Returns list of dicts: { 'text': str, 'metadata': { chunk_index, start_pos, end_pos, token_count } }
    start_pos/end_pos are token indices in the original token sequence.
    """
    if not text:
        return []
    chunks: List[Dict[str, Any]] = []
    if tiktoken is None:
        # Fallback: approximate by characters if tiktoken is unavailable
        chunks = []
        start = 0
        text_length = len(text)
        idx = 0
        step = max(chunk_size - overlap, 1)
        while start < text_length:
            end = min(start + chunk_size, text_length)
            chunk_str = text[start:end]
            chunks.append(
                {
                    "text": chunk_str,
                    "metadata": {
                        "chunk_index": idx,
                        "start_pos": start,
                        "end_pos": end,
                        "token_count": len(chunk_str.split()),
                    },
                }
            )
            idx += 1
            start = end - min(overlap, end)
        return chunks

    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(text)
    num_tokens = len(tokens)
    if num_tokens == 0:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)
    start_tok = 0
    idx = 0
    while start_tok < num_tokens:
        end_tok = min(start_tok + chunk_size, num_tokens)
        token_slice = tokens[start_tok:end_tok]
        chunk_str = encoding.decode(token_slice)
        chunks.append(
            {
                "text": chunk_str,
                "metadata": {
                    "chunk_index": idx,
                    "start_pos": start_tok,
                    "end_pos": end_tok,
                    "token_count": len(token_slice),
                },
            }
        )
        idx += 1
        if end_tok >= num_tokens:
            break
        start_tok = max(end_tok - overlap, 0)

    return chunks

def split_text_into_chunks(text, chunk_size=800, overlap=100):
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        
        if end < text_length:
            last_period = text.rfind('.', start, end)
            last_newline = text.rfind('\n', start, end)
            last_space = text.rfind(' ', start, end)
            
            break_point = max(last_period, last_newline, last_space)
            
            if break_point > start:
                end = break_point + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
    
    return chunks

