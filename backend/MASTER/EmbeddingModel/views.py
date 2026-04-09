from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.text import slugify
from .models import EmbeddingModel
from MASTER.clients.models import Client
from MASTER.processing.tasks import process_client_document
import json


def health(_request):
    return JsonResponse({"module": "embeddingmodel", "status": "ok"})


@require_GET
def get_models(request):
    """Return list of available embedding models."""
    models = EmbeddingModel.objects.filter(is_active=True).order_by('provider', 'name')
    return JsonResponse({
        "status": "ok",
        "models": [
            {
                "id": getattr(m, 'pk', None) or getattr(m, 'id', None),
                "name": m.name,
                "slug": m.slug,
                "description": f"{m.provider} - {m.model_name}",
                "dimensions": m.dimensions,
                "cost_per_1k_tokens": float(m.cost_per_1k_tokens),
                "is_default": m.is_default,
            }
            for m in models
        ]
    })


@csrf_exempt
@require_POST
def select_model(request):
    """Select embedding model for a client and trigger reindexing if needed."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)
    
    uid = data.get('uid')
    ai_model = data.get('ai_model')
    
    if not uid or not ai_model:
        return JsonResponse({"status": "error", "message": "uid and ai_model are required."}, status=400)

    try:
        model = EmbeddingModel.objects.get(slug=ai_model, is_active=True)
    except EmbeddingModel.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Invalid model."}, status=400)

    try:
        # uid може бути client.id або client tag/api_key
        # Спробуємо знайти клієнта за id
        try:
            client_id = int(uid)
            client = Client.objects.get(id=client_id)
        except (ValueError, Client.DoesNotExist):
            # Якщо не число, спробуємо знайти за tag або api_key
            client = Client.objects.filter(tag=uid).first() or Client.objects.filter(api_key=uid).first()
            if not client:
                return JsonResponse({"status": "error", "message": "Client not found."}, status=404)
        
        # Перевіряємо, чи змінилась модель
        previous_model_id = getattr(client, 'embedding_model_id', None)
        model_pk = getattr(model, 'pk', None) or getattr(model, 'id', None)
        reindex_needed = (previous_model_id != model_pk and previous_model_id is not None)
        
        # Оновлюємо модель клієнта
        client.embedding_model = model
        client.save(update_fields=['embedding_model'])
        
        # Не запускаємо реіндексацію автоматично - клієнт сам має натиснути кнопку
        # Тільки повідомляємо, що потрібна реіндексація
        
        return JsonResponse({
            "status": "ok", 
            "selected_model": model.slug,
            "reindex_required": reindex_needed,
            "message": "Model updated. Please reindex your documents." if reindex_needed else "Model updated successfully."
        })
        
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@require_POST
def reindex_client_documents(request):
    """Reindex all documents for a specific client.
    
    Request JSON: { uid: string }
    Response: { status: "ok", message: string, documents_count: int, task_id: string }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)
    
    uid = data.get('uid')
    if not uid:
        return JsonResponse({"status": "error", "message": "uid is required."}, status=400)

    try:
        # Знаходимо клієнта
        try:
            client_id = int(uid)
            client = Client.objects.get(id=client_id)
        except (ValueError, Client.DoesNotExist):
            # Якщо не число, спробуємо знайти за tag або api_key
            client = Client.objects.filter(tag=uid).first() or Client.objects.filter(api_key=uid).first()
            if not client:
                return JsonResponse({"status": "error", "message": "Client not found."}, status=404)
        
        # Перевіряємо, чи є обрана модель
        if not client.embedding_model:
            return JsonResponse({
                "status": "error", 
                "message": "No embedding model selected. Please select a model first."
            }, status=400)
        
        # Запускаємо таск для реіндексації документів цього клієнта
        from MASTER.EmbeddingModel.tasks import reindex_client_documents_task
        task_result = reindex_client_documents_task.delay(int(getattr(client, 'pk', None) or getattr(client, 'id', None)))
        
        # Підраховуємо документи для інформації
        from MASTER.clients.models import ClientDocument
        documents_count = ClientDocument.objects.filter(client=client, is_processed=True).count()
        
        return JsonResponse({
            "status": "ok",
            "message": f"Reindexing started for {documents_count} document(s).",
            "documents_count": documents_count,
            "task_id": task_result.id,
        })
        
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
