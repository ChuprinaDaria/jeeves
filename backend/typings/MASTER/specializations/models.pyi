from typing import Any, Optional
from django.db import models
from django.contrib.auth.models import AbstractUser

class Specialization(models.Model):
    # Django automatically creates an 'id' field for all models
    id: int
    
    branch: Any  # Branch
    branch_id: int  # ForeignKey field automatically creates this attribute
    name: str
    slug: str
    description: str
    is_active: bool
    custom_system_prompt: str
    embedding_model: Optional[Any]  # EmbeddingModel
    owner: Optional[AbstractUser]
    created_by: Optional[AbstractUser]
    created_at: Any  # datetime
    updated_at: Any  # datetime
    
    def __str__(self) -> str: ...
    def get_embedding_model(self) -> Optional[Any]: ...
    

class SpecializationDocument(models.Model):
    id: int
    specialization: Specialization
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
    
    def __str__(self) -> str: ...
    def save(self, *args: Any, **kwargs: Any) -> None: ...
    def delete(self, *args: Any, **kwargs: Any) -> Any: ...
    def clean(self) -> None: ...

class SpecializationEmbedding(models.Model):
    id: int
    specialization: Specialization
    document: Optional[SpecializationDocument]
    embedding_model: Any  # EmbeddingModel
    vector: list[float]
    content: str
    metadata: dict
    created_at: Any  # datetime
    
    def __str__(self) -> str: ...
    def save(self, *args: Any, **kwargs: Any) -> None: ...
