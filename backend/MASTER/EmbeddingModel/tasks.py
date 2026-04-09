from celery import shared_task
from MASTER.EmbeddingModel.models import EmbeddingModel
from MASTER.clients.models import Client, ClientDocument, ClientEmbedding
from MASTER.processing.tasks import process_client_document


@shared_task(bind=True, max_retries=3)
def reindex_client_documents_task(self, client_id: int):
    """Reindex all documents for a specific client.
    
    This task:
    1. Gets the client's selected embedding model
    2. Marks all processed documents as unprocessed
    3. Deletes old embeddings for this client
    4. Enqueues document processing tasks with the new model
    """
    try:
        client = Client.objects.get(id=client_id)
        
        # Перевіряємо, чи є обрана модель
        embedding_model = getattr(client, 'embedding_model', None)
        if not embedding_model:
            return {
                "status": "error",
                "message": "No embedding model selected for this client",
                "client_id": client_id
            }
        
        # Знаходимо всі оброблені документи клієнта
        documents = ClientDocument.objects.filter(client=client, is_processed=True)
        documents_count = documents.count()
        
        if documents_count == 0:
            return {
                "status": "success",
                "message": "No processed documents found for reindexing",
                "client_id": client_id,
                "documents_count": 0
            }
        
        embeddings_deleted = 0

        # Видаляємо тільки embeddings, створені з поточною моделлю клієнта
        # ВАЖЛИВО: Embeddings для інших моделей НЕ видаляються!
        # Це дозволяє при поверненні до старої моделі використовувати існуючі embeddings
        # без повторної індексації
        deleted, _ = ClientEmbedding.objects.filter(
            client=client,
            embedding_model=embedding_model
        ).delete()
        embeddings_deleted += deleted
        
        # Помічаємо всі документи для повторної обробки
        for doc in documents:
            doc.is_processed = False
            doc.processing_error = ""  # Очищаємо попередні помилки
            doc.save(update_fields=['is_processed', 'processing_error'])
            
            # Запускаємо обробку з новою моделлю
            process_client_document.delay(doc.id)
        
        return {
            "status": "success",
            "client_id": client_id,
            "model_id": embedding_model.id,
            "model_name": embedding_model.name,
            "documents_queued": documents_count,
            "embeddings_deleted": embeddings_deleted,
            "message": f"Reindexing queued for {documents_count} document(s)"
        }
        
    except Client.DoesNotExist:
        return {
            "status": "error",
            "message": f"Client with id={client_id} not found",
            "client_id": client_id
        }
    except Exception as e:  # noqa: BLE001
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def reindex_documents_for_model(self, model_id: int):
    """Reindex all documents for clients using a specific embedding model.
    
    This task:
    1. Finds all clients using the specified model
    2. Marks their documents as unprocessed
    3. Deletes old embeddings
    4. Enqueues document processing tasks with the new model
    """
    try:
        model = EmbeddingModel.objects.get(id=model_id)
        if not model.is_active:
            return {
                "status": "skipped",
                "reason": "Model is not active",
                "model_id": model_id
            }
        
        # Знаходимо всіх клієнтів, які використовують цю модель
        clients_with_model = Client.objects.filter(embedding_model=model)
        
        documents_count = 0
        embeddings_deleted = 0
        
        for client in clients_with_model:
            # Знаходимо всі документи клієнта
            documents = ClientDocument.objects.filter(client=client, is_processed=True)
            
            for doc in documents:
                # Видаляємо старі embeddings для цього документа
                deleted, _ = ClientEmbedding.objects.filter(
                    client=client,
                    document=doc,
                    embedding_model=model
                ).delete()
                embeddings_deleted += deleted
                
                # Помічаємо документ для повторної обробки
                doc.is_processed = False
                doc.processing_error = ""  # Очищаємо попередні помилки
                doc.save(update_fields=['is_processed', 'processing_error'])
                
                # Запускаємо обробку з новою моделлю
                process_client_document.delay(doc.id)
                documents_count += 1
        
        # Якщо модель має прапор reindex_required, скидаємо його після початку реіндексації
        if model.reindex_required:
            model.reindex_required = False
            model.save(update_fields=['reindex_required'])
        
        return {
            "status": "success",
            "model_id": model_id,
            "model_name": model.name,
            "clients_count": clients_with_model.count(),
            "documents_queued": documents_count,
            "embeddings_deleted": embeddings_deleted,
            "message": f"Reindexing queued for {documents_count} documents across {clients_with_model.count()} clients"
        }
        
    except EmbeddingModel.DoesNotExist:
        return {
            "status": "error",
            "message": f"EmbeddingModel with id={model_id} not found",
            "model_id": model_id
        }
    except Exception as e:  # noqa: BLE001
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def index_new_client_documents_task(self, client_id: int):
    """Index only new (unprocessed) documents for a specific client.
    
    This task:
    1. Gets the client's selected embedding model
    2. Finds all unprocessed documents (is_processed=False)
    3. Enqueues document processing tasks for new documents only
    4. Does NOT delete existing embeddings or mark processed documents as unprocessed
    """
    try:
        client = Client.objects.get(id=client_id)
        
        # Перевіряємо, чи є обрана модель
        embedding_model = getattr(client, 'embedding_model', None)
        if not embedding_model:
            return {
                "status": "error",
                "message": "No embedding model selected for this client",
                "client_id": client_id
            }
        
        # Знаходимо тільки необроблені документи клієнта
        documents = ClientDocument.objects.filter(client=client, is_processed=False)
        documents_count = documents.count()
        
        if documents_count == 0:
            return {
                "status": "success",
                "message": "No new documents found for indexing",
                "client_id": client_id,
                "documents_count": 0
            }
        
        # Запускаємо обробку тільки для нових документів
        for doc in documents:
            process_client_document.delay(doc.id)
        
        return {
            "status": "success",
            "client_id": client_id,
            "model_id": embedding_model.id,
            "model_name": embedding_model.name,
            "documents_queued": documents_count,
            "message": f"Indexing queued for {documents_count} new document(s)"
        }
        
    except Client.DoesNotExist:
        return {
            "status": "error",
            "message": f"Client with id={client_id} not found",
            "client_id": client_id
        }
    except Exception as e:  # noqa: BLE001
        raise self.retry(exc=e, countdown=60)

