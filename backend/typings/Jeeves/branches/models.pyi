from typing import Any, Optional
from django.db import models
from django.contrib.auth.models import AbstractUser

class Branch(models.Model):
    id: int
    name: str
    slug: str
    description: str
    is_active: bool
    embedding_model: Optional[Any]  # EmbeddingModel
    owner: Optional[AbstractUser]
    created_by: Optional[AbstractUser]
    created_at: Any  # datetime
    updated_at: Any  # datetime
    
    def get_embedding_model(self) -> Any: ...

class BranchDocument(models.Model):
    id: int
    branch: Branch
    title: str
    file: Any  # FileField
    file_type: str
    file_size: int
    metadata: dict
    uploaded_by: Optional[AbstractUser]
    uploaded_at: Any  # datetime
    is_processed: bool
    processing_error: str
    chunks_count: int
    
    def clean(self) -> None: ...

class BranchEmbedding(models.Model):
    id: int
    branch: Branch
    document: Optional[BranchDocument]
    embedding_model: Any  # EmbeddingModel
    vector: Optional[list[float]]
    content: str
    metadata: dict
    created_at: Any  # datetime
