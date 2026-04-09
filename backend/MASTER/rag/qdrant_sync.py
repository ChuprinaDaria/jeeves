"""
Dual-write sync: when ClientEmbedding is created/deleted in PostgreSQL,
automatically sync to Qdrant.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _get_qdrant_client():
    try:
        from qdrant_client import QdrantClient
        host = getattr(settings, 'QDRANT_HOST', 'ai_nexelin_qdrant')
        port = getattr(settings, 'QDRANT_PORT', 6333)
        return QdrantClient(host=host, port=port, timeout=5.0)
    except Exception as e:
        logger.warning(f"Qdrant client init failed: {e}")
        return None


def upsert_embedding_to_qdrant(embedding):
    """Upsert a single ClientEmbedding to Qdrant."""
    if not getattr(settings, 'USE_QDRANT', False):
        return

    client = _get_qdrant_client()
    if not client:
        return

    try:
        from qdrant_client.models import PointStruct
        collection = getattr(settings, 'QDRANT_COLLECTION', 'nexelin_embeddings')

        vec = embedding.vector
        if vec is None:
            return
        vector = vec.tolist() if hasattr(vec, 'tolist') else list(vec)
        if len(vector) != 1536:
            return

        point = PointStruct(
            id=embedding.id,
            vector=vector,
            payload={
                'client_id': embedding.client_id,
                'document_id': embedding.document_id,
                'embedding_model_id': embedding.embedding_model_id,
                'content': (embedding.content or '')[:2000],
                'metadata': embedding.metadata or {},
                'created_at': embedding.created_at.isoformat() if embedding.created_at else '',
            }
        )
        client.upsert(collection_name=collection, points=[point])
        logger.debug(f"Qdrant upsert: embedding {embedding.id}")
    except Exception as e:
        logger.warning(f"Qdrant upsert failed for embedding {embedding.id}: {e}")


def delete_embedding_from_qdrant(embedding_id):
    """Delete a single point from Qdrant by ID."""
    if not getattr(settings, 'USE_QDRANT', False):
        return

    client = _get_qdrant_client()
    if not client:
        return

    try:
        collection = getattr(settings, 'QDRANT_COLLECTION', 'nexelin_embeddings')
        client.delete(collection_name=collection, points_selector=[embedding_id])
        logger.debug(f"Qdrant delete: embedding {embedding_id}")
    except Exception as e:
        logger.warning(f"Qdrant delete failed for embedding {embedding_id}: {e}")


@receiver(post_save, sender='clients.ClientEmbedding')
def sync_embedding_to_qdrant(sender, instance, created, **kwargs):
    """Auto-sync new or updated embeddings to Qdrant."""
    if created:
        upsert_embedding_to_qdrant(instance)


@receiver(post_delete, sender='clients.ClientEmbedding')
def remove_embedding_from_qdrant(sender, instance, **kwargs):
    """Auto-remove deleted embeddings from Qdrant."""
    delete_embedding_from_qdrant(instance.id)
