from django.http import JsonResponse
from django.utils import timezone
from .models import ClientAPIKey


class ClientAPIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        # Тимчасово робимо всі /api/* публічними:
        # - не блокуємо 401/403
        # - якщо є api_key або client tag — ідентифікуємо клієнта
        # - інакше просто пропускаємо запит далі (AllowAny у DRF)
        try:
            # API key: only from headers (never from URL params — they leak in logs)
            api_key = request.headers.get('X-API-Key')
            if api_key:
                try:
                    key_obj = ClientAPIKey.objects.select_related('client').get(
                        key=api_key,
                        is_active=True
                    )
                    if key_obj.is_valid():
                        key_obj.usage_count += 1
                        key_obj.last_used_at = timezone.now()
                        key_obj.save(update_fields=['usage_count', 'last_used_at'])
                        request.client = key_obj.client
                        request.api_key = key_obj
                except ClientAPIKey.DoesNotExist:
                    pass
            if not getattr(request, 'client', None):
                # Client tag: headers first, URL ?tag= allowed (public identifier, not a secret)
                client_tag = (
                    request.headers.get('X-Client-Token')
                    or request.GET.get('tag')
                )
                if client_tag:
                    from .models import Client
                    try:
                        client = Client.objects.get(tag=client_tag, is_active=True)
                        request.client = client
                    except Client.DoesNotExist:
                        pass
        except Exception:
            pass
        return self.get_response(request)

