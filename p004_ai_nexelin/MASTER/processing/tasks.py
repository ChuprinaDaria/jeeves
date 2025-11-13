from celery import shared_task

from MASTER.clients.models import ClientDocument, ClientEmbedding
from MASTER.branches.models import BranchDocument, BranchEmbedding
from MASTER.specializations.models import (
    SpecializationDocument,
    SpecializationEmbedding,
)

from .parsers import get_parser
from .chunker import chunk_text
from .embedding_service import EmbeddingService
from .models import UsageStats
from .metadata_extractor import extract_metadata
from .usage_sync import send_usage_to_mg


@shared_task(bind=True, max_retries=0)
def process_document(self, document_id: int, model_type: str):
    """Dispatcher task that enqueues the specific processing task based on model_type.

    model_type: one of {'client', 'branch', 'specialization'}
    Returns a short enqueue status with child task id.
    """
    model_key = (model_type or "").strip().lower()
    if model_key not in {"client", "branch", "specialization"}:
        raise ValueError(f"Unsupported model_type: {model_type}")

    if model_key == "client":
        res = process_client_document.delay(document_id)
    elif model_key == "branch":
        res = process_branch_document.delay(document_id)
    else:
        res = process_specialization_document.delay(document_id)

    return {
        "status": "queued",
        "task_id": res.id,
        "target": model_key,
        "document_id": int(document_id),
    }

@shared_task(bind=True, max_retries=3)
def process_client_document(self, document_id: int):
    try:
        document = ClientDocument.objects.select_related("client").get(id=document_id)

        file_path = document.file.path
        file_type = document.file_type

        parser = get_parser(file_type)
        parsed = parser.parse(file_path)
        if isinstance(parsed, dict):
            text = parsed.get("text", "")
            parser_metadata = parsed.get("metadata", {})
        else:
            text = str(parsed)
            parser_metadata = {}

        file_metadata = extract_metadata(file_path, file_type)

        # Зберігаємо базові метадані одразу після парсингу
        try:
            document.metadata = {"file": file_metadata, "parser": parser_metadata}
            document.save(update_fields=["metadata"])
        except Exception:
            pass

        chunks = chunk_text(text)

        client = document.client
        # Пріоритет: client.embedding_model > specialization.get_embedding_model()
        embedding_model = getattr(client, 'embedding_model', None)
        if embedding_model is None and client.specialization:
            embedding_model = client.specialization.get_embedding_model()
        if embedding_model is None:
            # Fallback to default model
            from MASTER.EmbeddingModel.models import EmbeddingModel
            embedding_model = EmbeddingModel.objects.filter(is_default=True, is_active=True).first()
            if embedding_model is None:
                embedding_model = EmbeddingModel.objects.filter(is_active=True).first()
                if embedding_model is None:
                    raise ValueError("No embedding model available")

        total_tokens = 0
        total_cost = 0.0

        for idx, chunk in enumerate(chunks):
            chunk_str = chunk.get("text", "")
            chunk_info = chunk.get("metadata", {})
            
            # Додаємо назву документа до контенту для кращого пошуку
            enhanced_content = f"Document: {document.title}\n\n{chunk_str}"
            result = EmbeddingService.create_embedding(enhanced_content, embedding_model)

            metadata = {
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "source_file": document.title,
                "file_type": file_type,
                "token_count": result["token_count"],
                "dimensions": result["dimensions"],
                "file": file_metadata,
                "parser": parser_metadata,
                "chunker": chunk_info,
            }

            ClientEmbedding.objects.create(
                client=client,
                document=document,
                embedding_model=embedding_model,
                vector=result["vector"],
                content=enhanced_content,  # Зберігаємо enhanced content
                metadata=metadata,
            )

            chunk_cost = EmbeddingService.calculate_cost(result["token_count"], embedding_model)
            total_tokens += result["token_count"]
            total_cost += chunk_cost

        document.is_processed = True
        document.chunks_count = len(chunks)
        # Очистити попередню помилку, якщо була
        document.processing_error = ""
        try:
            document.metadata = {"file": file_metadata, "parser": parser_metadata}
        except Exception:
            pass
        document.save()

        UsageStats.objects.create(
            client=client,
            embedding_model=embedding_model,
            operation_type="create_embedding",
            tokens_used=total_tokens,
            cost=total_cost,
            metadata={
                "document_id": int(document.pk),
                "document_title": document.title,
                "chunks_count": len(chunks),
            },
        )
        try:
            # Fire-and-forget sync (best-effort)
            latest = UsageStats.objects.filter(client=client).order_by('-id').first()
            if latest:
                send_usage_to_mg(latest)
        except Exception:
            pass

        return {
            "status": "success",
            "document_id": document_id,
            "chunks_count": len(chunks),
            "tokens_used": total_tokens,
            "cost": float(total_cost),
        }

    except Exception as e:  # noqa: BLE001
        document = ClientDocument.objects.get(id=document_id)
        document.processing_error = str(e)
        document.save()
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_branch_document(self, document_id: int):
    try:
        document = BranchDocument.objects.select_related("branch").get(id=document_id)

        file_path = document.file.path
        file_type = document.file_type

        parser = get_parser(file_type)
        parsed = parser.parse(file_path)
        if isinstance(parsed, dict):
            text = parsed.get("text", "")
            parser_metadata = parsed.get("metadata", {})
        else:
            text = str(parsed)
            parser_metadata = {}

        file_metadata = extract_metadata(file_path, file_type)

        chunks = chunk_text(text)

        # Зберігаємо метадані файлу/парсера в документі
        try:
            document.metadata = {"file": file_metadata, "parser": parser_metadata}
            document.save(update_fields=["metadata"])
        except Exception:
            pass

        branch = document.branch
        embedding_model = branch.get_embedding_model()
        if embedding_model is None:
            # Fallback to default model
            from MASTER.EmbeddingModel.models import EmbeddingModel
            embedding_model = EmbeddingModel.objects.filter(is_default=True, is_active=True).first()
            if embedding_model is None:
                embedding_model = EmbeddingModel.objects.filter(is_active=True).first()
                if embedding_model is None:
                    raise ValueError("No embedding model available")

        total_tokens = 0
        total_cost = 0.0

        for idx, chunk in enumerate(chunks):
            chunk_str = chunk.get("text", "")
            chunk_info = chunk.get("metadata", {})
            result = EmbeddingService.create_embedding(chunk_str, embedding_model)

            metadata = {
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "source_file": document.title,
                "file_type": file_type,
                "token_count": result["token_count"],
                "dimensions": result["dimensions"],
                "file": file_metadata,
                "parser": parser_metadata,
                "chunker": chunk_info,
            }

            BranchEmbedding.objects.create(
                branch=branch,
                document=document,
                embedding_model=embedding_model,
                vector=result["vector"],
                content=chunk_str,
                metadata=metadata,
            )

            chunk_cost = EmbeddingService.calculate_cost(result["token_count"], embedding_model)
            total_tokens += result["token_count"]
            total_cost += chunk_cost

        document.is_processed = True
        document.chunks_count = len(chunks)
        # Очистити попередню помилку, якщо була
        document.processing_error = ""
        document.save()

        UsageStats.objects.create(
            branch=branch,
            embedding_model=embedding_model,
            operation_type="create_embedding",
            tokens_used=total_tokens,
            cost=total_cost,
            metadata={
                "document_id": int(document.pk),
                "document_title": document.title,
                "chunks_count": len(chunks),
            },
        )
        try:
            latest = UsageStats.objects.filter(branch=branch).order_by('-id').first()
            if latest:
                send_usage_to_mg(latest)
        except Exception:
            pass

        return {
            "status": "success",
            "document_id": document_id,
            "chunks_count": len(chunks),
            "tokens_used": total_tokens,
            "cost": float(total_cost),
        }

    except Exception as e:  # noqa: BLE001
        document = BranchDocument.objects.get(id=document_id)
        document.processing_error = str(e)
        document.save()
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_specialization_document(self, document_id: int):
    try:
        document = SpecializationDocument.objects.select_related("specialization").get(
            id=document_id
        )

        file_path = document.file.path
        file_type = document.file_type

        parser = get_parser(file_type)
        parsed = parser.parse(file_path)
        if isinstance(parsed, dict):
            text = parsed.get("text", "")
            parser_metadata = parsed.get("metadata", {})
        else:
            text = str(parsed)
            parser_metadata = {}

        file_metadata = extract_metadata(file_path, file_type)

        chunks = chunk_text(text)

        # Зберігаємо метадані файлу/парсера в документі
        try:
            document.metadata = {"file": file_metadata, "parser": parser_metadata}
            document.save(update_fields=["metadata"])
        except Exception:
            pass

        specialization = document.specialization
        embedding_model = specialization.get_embedding_model()
        if embedding_model is None:
            # Fallback to default model
            from MASTER.EmbeddingModel.models import EmbeddingModel
            embedding_model = EmbeddingModel.objects.filter(is_default=True, is_active=True).first()
            if embedding_model is None:
                embedding_model = EmbeddingModel.objects.filter(is_active=True).first()
                if embedding_model is None:
                    raise ValueError("No embedding model available")

        total_tokens = 0
        total_cost = 0.0

        for idx, chunk in enumerate(chunks):
            chunk_str = chunk.get("text", "")
            chunk_info = chunk.get("metadata", {})
            result = EmbeddingService.create_embedding(chunk_str, embedding_model)

            metadata = {
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "source_file": document.title,
                "file_type": file_type,
                "token_count": result["token_count"],
                "dimensions": result["dimensions"],
                "file": file_metadata,
                "parser": parser_metadata,
                "chunker": chunk_info,
            }

            SpecializationEmbedding.objects.create(
                specialization=specialization,
                document=document,
                embedding_model=embedding_model,
                vector=result["vector"],
                content=chunk_str,
                metadata=metadata,
            )

            chunk_cost = EmbeddingService.calculate_cost(result["token_count"], embedding_model)
            total_tokens += result["token_count"]
            total_cost += chunk_cost

        document.is_processed = True
        document.chunks_count = len(chunks)
        # Очистити попередню помилку, якщо була
        document.processing_error = ""
        document.save()

        UsageStats.objects.create(
            specialization=specialization,
            embedding_model=embedding_model,
            operation_type="create_embedding",
            tokens_used=total_tokens,
            cost=total_cost,
            metadata={
                "document_id": int(document.pk),
                "document_title": document.title,
                "chunks_count": len(chunks),
            },
        )
        try:
            latest = UsageStats.objects.filter(specialization=specialization).order_by('-id').first()
            if latest:
                send_usage_to_mg(latest)
        except Exception:
            pass

        return {
            "status": "success",
            "document_id": document_id,
            "chunks_count": len(chunks),
            "tokens_used": total_tokens,
            "cost": float(total_cost),
        }

    except Exception as e:  # noqa: BLE001
        document = SpecializationDocument.objects.get(id=document_id)
        document.processing_error = str(e)
        document.save()
        raise self.retry(exc=e, countdown=60)


