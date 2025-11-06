from django.http import JsonResponse
from django.utils import timezone
from .models import ClientAPIKey


class ClientAPIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith('/api/rag/') or path.startswith('/api/query') or path.startswith('/api/upload') or path.startswith('/api/docs'):
            # Allow JWT-auth flows and public bootstrap/auth endpoints
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                return self.get_response(request)
            # Дозволяємо публічний доступ до деяких endpoints
            if ('/api/rag/auth/' in path or 
                '/api/rag/bootstrap/' in path or 
                '/api/rag/embedding-models/' in path or
                '/api/rag/ai-models/' in path):
                return self.get_response(request)

            api_key = request.headers.get('X-API-Key')
            if not api_key:
                return JsonResponse({'error': 'API key required'}, status=401)

            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )

                if not key_obj.is_valid():
                    return JsonResponse({'error': 'Invalid or expired API key'}, status=401)

                key_obj.usage_count += 1
                key_obj.last_used_at = timezone.now()
                key_obj.save(update_fields=['usage_count', 'last_used_at'])

                request.client = key_obj.client
                request.api_key = key_obj

            except ClientAPIKey.DoesNotExist:
                return JsonResponse({'error': 'Invalid API key'}, status=401)
        
        return self.get_response(request)

