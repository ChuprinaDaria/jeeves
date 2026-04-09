from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

class TfidfVectorizer:
    def __init__(
        self,
        *,
        max_features: Optional[int] = ..., 
        ngram_range: Sequence[int] = ..., 
    ) -> None: ...

    def fit_transform(self, raw_documents: Iterable[str], y: Optional[Iterable[object]] = ...) -> "_SparseMatrix": ...

class _SparseMatrix:
    def toarray(self) -> List[List[float]]: ...


