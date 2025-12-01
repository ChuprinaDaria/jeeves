from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)
from MASTER.clients.models import Client, ClientDocument, ClientAPIKey, ClientAPIConfig, KnowledgeBlock, ClientQRCode, ClientWhatsAppConversation, WebParsingRequest, Prompt, PromptVote, News
from MASTER.clients.serializers import (
    ClientSerializer,
    ClientDocumentSerializer,
    ClientAPIKeySerializer,
    KnowledgeBlockSerializer,
    ClientQRCodeSerializer,
    WebParsingRequestSerializer,
    PromptSerializer,
    NewsSerializer,
    PromptVoteSerializer,
)
from MASTER.clients.permissions import IsAdminOrReadOnly, IsClientOwner
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from MASTER.rag.response_generator import ResponseGenerator
from MASTER.branches.models import Branch
from MASTER.specializations.models import Specialization
import json


# Create your views here.


def get_client_from_request(request):
    """
    Helper function to get client from request without JWT.
    Priority:
    - request.client (set by ClientAPIKeyMiddleware via X-API-Key)
    - X-Client-Token header (client tag)
    - ?tag= or ?client_token= query params
    - tag/client_token in request body
    """
    # 0) Клієнт, встановлений middleware через X-API-Key
    client = getattr(request, 'client', None)
    if client:
        return client
    
    # 1) Заголовок X-Client-Token
    try:
        token = request.headers.get('X-Client-Token') or request.META.get('HTTP_X_CLIENT_TOKEN')
        if token:
            try:
                client = Client.objects.get(tag=token, is_active=True)
                return client
            except Client.DoesNotExist:
                # Якщо це не tag клієнта, пробуємо інтерпретувати як API key
                try:
                    key_obj = ClientAPIKey.objects.select_related('client').get(
                        key=token,
                        is_active=True
                    )
                    if key_obj.is_valid():
                        return key_obj.client
                except ClientAPIKey.DoesNotExist:
                    pass
        # 2) Параметри запиту ?tag= або ?client_token=
        params = getattr(request, 'query_params', None) or getattr(request, 'GET', None)
        tag = None
        if params:
            tag = params.get('tag') or params.get('client_token')
        # 3) Тіло запиту (multipart/form / json)
        if not tag and hasattr(request, 'data'):
            try:
                tag = request.data.get('tag') or request.data.get('client_token')
            except Exception:
                tag = None
        if tag:
            try:
                client = Client.objects.get(tag=tag, is_active=True)
                return client
            except Client.DoesNotExist:
                # Якщо це не tag клієнта, пробуємо інтерпретувати як API key
                try:
                    key_obj = ClientAPIKey.objects.select_related('client').get(
                        key=tag,
                        is_active=True
                    )
                    if key_obj.is_valid():
                        return key_obj.client
                except ClientAPIKey.DoesNotExist:
                    pass
    except Exception:
        # Не ламаємо потік при будь-яких помилках
        pass

    return None


def health(_request):
    return JsonResponse({"module": "clients", "status": "ok"})


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = []  # Публічний доступ для створення клієнта
    def get_queryset(self):
        qs = super().get_queryset()
        specialization_id = self.request.query_params.get('specialization_id')
        branch_id = self.request.query_params.get('branch_id')
        if specialization_id:
            qs = qs.filter(specialization_id=specialization_id)
        if branch_id:
            qs = qs.filter(specialization__branch_id=branch_id)
        return qs
    
    def perform_create(self, serializer):
        """Встановлюємо created_by при створенні клієнта через API"""
        # Якщо користувач авторизований, встановлюємо created_by
        if self.request.user and self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            # Якщо не авторизований, залишаємо created_by = None
            serializer.save()


class ClientDocumentViewSet(viewsets.ModelViewSet):
    queryset = ClientDocument.objects.all()
    serializer_class = ClientDocumentSerializer
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методах
    
    def get_client_from_request_or_api_key(self):
        """Отримати клієнта з JWT або API ключа."""
        client = get_client_from_request(self.request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in self.request.META:
            api_key = self.request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
        
        return client
    
    def get_queryset(self):
        """Filter documents by authenticated client"""
        client = self.get_client_from_request_or_api_key()
        if client:
            return ClientDocument.objects.filter(client=client).order_by('-uploaded_at')
        # Admin/staff can see all
        user = self.request.user
        if user and user.is_authenticated and (user.is_superuser or getattr(user, 'is_staff', False)):
            return ClientDocument.objects.all().order_by('-uploaded_at')
        return ClientDocument.objects.none()
    
    def list(self, request, *args, **kwargs):
        """Override list to ensure it's available"""
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """Override create to ensure it's available"""
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Automatically set client from request"""
        client = self.get_client_from_request_or_api_key()
        if not client:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Client authentication required')
        serializer.save(client=client)


class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = ClientAPIKey.objects.all()
    serializer_class = ClientAPIKeySerializer
    permission_classes = [IsAdminOrReadOnly]


class KnowledgeBlockViewSet(viewsets.ModelViewSet):
    """API для роботи з Knowledge Blocks."""
    serializer_class = KnowledgeBlockSerializer
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методах
    
    def get_client_from_request_or_api_key(self):
        """Отримати клієнта з JWT або API ключа."""
        client = get_client_from_request(self.request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in self.request.META:
            api_key = self.request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
        
        return client
    
    def get_queryset(self):
        """Повертає тільки блоки поточного клієнта."""
        client = self.get_client_from_request_or_api_key()
        if not client:
            return KnowledgeBlock.objects.none()
        return KnowledgeBlock.objects.filter(client=client)
    
    def create(self, request, *args, **kwargs):
        """Override create to ensure it's available"""
        return super().create(request, *args, **kwargs)
    
    def list(self, request, *args, **kwargs):
        """Override list to ensure it's available"""
        return super().list(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Автоматично встановлює клієнта при створенні."""
        client = self.get_client_from_request_or_api_key()
        if not client:
            raise serializers.ValidationError("Client not found")
        serializer.save(client=client)
    
    def perform_update(self, serializer):
        """Перевіряє що блок не permanent перед оновленням."""
        instance = self.get_object()
        if instance.is_permanent:
            raise serializers.ValidationError("Cannot edit permanent knowledge blocks")
        serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        """Перевіряє що блок не permanent перед видаленням."""
        instance = self.get_object()
        if instance.is_permanent:
            return Response(
                {'error': 'Cannot delete permanent knowledge blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


class PromptViewSet(viewsets.ModelViewSet):
    """Public Prompt Library - доступний для всіх користувачів"""
    serializer_class = PromptSerializer
    permission_classes = [AllowAny]  # Публічний доступ
    
    def get_queryset(self):
        """Фільтрація промптів по категорії, індустрії та пошуку"""
        queryset = Prompt.objects.filter(is_public=True)
        
        # Фільтри
        category = self.request.query_params.get('category')
        industry = self.request.query_params.get('industry')
        search = self.request.query_params.get('search')
        
        if category and category != 'all':
            queryset = queryset.filter(category=category)
        
        if industry and industry != 'all':
            queryset = queryset.filter(industry=industry)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(prompt_template__icontains=search) |
                Q(tags__contains=[search])
            )
        
        return queryset.order_by('-is_featured', '-created_at')
    
    def perform_create(self, serializer):
        """Автоматично встановлює created_by при створенні"""
        if self.request.user and self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Оцінити промпт (like/dislike)"""
        prompt = self.get_object()
        vote_type = request.data.get('vote')
        
        if vote_type not in ['like', 'dislike']:
            return Response(
                {'error': 'Invalid vote type. Use "like" or "dislike"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Отримуємо user_identifier
        if request.user and request.user.is_authenticated:
            user_identifier = str(request.user.id)
            user = request.user
        else:
            # Для анонімних користувачів використовуємо IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                user_identifier = x_forwarded_for.split(',')[0]
            else:
                user_identifier = request.META.get('REMOTE_ADDR', 'anonymous')
            user = None
        
        # Перевіряємо чи вже є голос
        existing_vote = PromptVote.objects.filter(
            prompt=prompt,
            user_identifier=user_identifier
        ).first()
        
        if existing_vote:
            # Якщо той самий голос - видаляємо
            if existing_vote.vote == vote_type:
                if existing_vote.vote == 'like':
                    prompt.likes_count = max(0, prompt.likes_count - 1)
                else:
                    prompt.dislikes_count = max(0, prompt.dislikes_count - 1)
                existing_vote.delete()
            else:
                # Якщо інший голос - змінюємо
                old_vote = existing_vote.vote
                existing_vote.vote = vote_type
                existing_vote.save()
                
                # Оновлюємо лічильники
                if old_vote == 'like':
                    prompt.likes_count = max(0, prompt.likes_count - 1)
                else:
                    prompt.dislikes_count = max(0, prompt.dislikes_count - 1)
                
                if vote_type == 'like':
                    prompt.likes_count += 1
                else:
                    prompt.dislikes_count += 1
        else:
            # Створюємо новий голос
            PromptVote.objects.create(
                prompt=prompt,
                user=user,
                user_identifier=user_identifier,
                vote=vote_type
            )
            
            # Оновлюємо лічильники
            if vote_type == 'like':
                prompt.likes_count += 1
            else:
                prompt.dislikes_count += 1
        
        prompt.save(update_fields=['likes_count', 'dislikes_count'])
        
        return Response({
            'likes_count': prompt.likes_count,
            'dislikes_count': prompt.dislikes_count,
            'like_ratio': prompt.get_like_ratio(),
        })


class PromptVoteView(APIView):
    """Окремий view для vote action, щоб гарантувати доступність через явний маршрут"""
    permission_classes = [AllowAny]
    
    def post(self, request, pk):
        """Оцінити промпт (like/dislike)"""
        try:
            prompt = Prompt.objects.get(pk=pk, is_public=True)
        except Prompt.DoesNotExist:
            return Response(
                {'error': 'Prompt not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        vote_type = request.data.get('vote')
        
        if vote_type not in ['like', 'dislike']:
            return Response(
                {'error': 'Invalid vote type. Use "like" or "dislike"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Отримуємо user_identifier
        if request.user and request.user.is_authenticated:
            user_identifier = str(request.user.id)
            user = request.user
        else:
            # Для анонімних користувачів використовуємо IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                user_identifier = x_forwarded_for.split(',')[0]
            else:
                user_identifier = request.META.get('REMOTE_ADDR', 'anonymous')
            user = None
        
        # Перевіряємо чи вже є голос
        existing_vote = PromptVote.objects.filter(
            prompt=prompt,
            user_identifier=user_identifier
        ).first()
        
        if existing_vote:
            # Якщо той самий голос - видаляємо
            if existing_vote.vote == vote_type:
                if existing_vote.vote == 'like':
                    prompt.likes_count = max(0, prompt.likes_count - 1)
                else:
                    prompt.dislikes_count = max(0, prompt.dislikes_count - 1)
                existing_vote.delete()
            else:
                # Якщо інший голос - змінюємо
                old_vote = existing_vote.vote
                existing_vote.vote = vote_type
                existing_vote.save()
                
                # Оновлюємо лічильники
                if old_vote == 'like':
                    prompt.likes_count = max(0, prompt.likes_count - 1)
                else:
                    prompt.dislikes_count = max(0, prompt.dislikes_count - 1)
                
                if vote_type == 'like':
                    prompt.likes_count += 1
                else:
                    prompt.dislikes_count += 1
        else:
            # Створюємо новий голос
            PromptVote.objects.create(
                prompt=prompt,
                user=user,
                user_identifier=user_identifier,
                vote=vote_type
            )
            
            # Оновлюємо лічильники
            if vote_type == 'like':
                prompt.likes_count += 1
            else:
                prompt.dislikes_count += 1
        
        prompt.save(update_fields=['likes_count', 'dislikes_count'])
        
        return Response({
            'likes_count': prompt.likes_count,
            'dislikes_count': prompt.dislikes_count,
            'like_ratio': prompt.get_like_ratio(),
        })


class NewsViewSet(viewsets.ReadOnlyModelViewSet):
    """System news and updates - read-only for clients"""
    serializer_class = NewsSerializer
    permission_classes = [AllowAny]  # Public access
    
    def get_queryset(self):
        """Return only active news, ordered by featured and date"""
        return News.objects.filter(is_active=True).order_by('-is_featured', '-created_at')


class TopPromptsView(APIView):
    """Get top 5 prompts by client ratings (daily)"""
    permission_classes = [AllowAny]  # Public access
    
    def get(self, request):
        """Return top 5 prompts by like ratio and total votes"""
        from django.utils import timezone
        from django.db.models import F, Case, When, FloatField
        
        # Отримуємо промпти з мінімальною кількістю голосів (наприклад, 3+)
        min_votes = 3
        top_prompts = Prompt.objects.filter(
            is_public=True,
            likes_count__gte=0
        ).annotate(
            total_votes=F('likes_count') + F('dislikes_count'),
            calculated_ratio=Case(
                When(total_votes__gt=0, then=F('likes_count') * 1.0 / (F('likes_count') + F('dislikes_count'))),
                default=0.0,
                output_field=FloatField()
            )
        ).filter(
            total_votes__gte=min_votes
        ).order_by(
            '-calculated_ratio',  # Спочатку за співвідношенням лайків
            '-likes_count',  # Потім за кількістю лайків
            '-total_votes'  # І нарешті за загальною кількістю голосів
        )[:5]
        
        serializer = PromptSerializer(top_prompts, many=True, context={'request': request})
        
        return Response({
            'top_prompts': serializer.data,
            'updated_at': timezone.now().isoformat()
        })


class ClientQRCodeViewSet(viewsets.ModelViewSet):
    """API для роботи з QR кодами клієнтів (до 10 на клієнта)."""
    serializer_class = ClientQRCodeSerializer
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методах
    
    def get_client_from_request_or_api_key(self):
        """Отримати клієнта з JWT або API ключа."""
        client = get_client_from_request(self.request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in self.request.META:
            api_key = self.request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
        
        return client
    
    def get_queryset(self):
        """Повертає тільки QR коди поточного клієнта."""
        client = self.get_client_from_request_or_api_key()
        if not client:
            return ClientQRCode.objects.none()
        return ClientQRCode.objects.filter(client=client)
    
    def list(self, request, *args, **kwargs):
        """Override list to ensure it's available"""
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """Override create to ensure it's available"""
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Автоматично встановлює клієнта при створенні та перевіряє ліміт."""
        import logging
        logger = logging.getLogger(__name__)
        
        client = self.get_client_from_request_or_api_key()
        if not client:
            logger.error("Client not found in request")
            raise serializers.ValidationError("Client not found")
        
        logger.info(f"Creating QR code for client {client.id}")
        
        # Перевіряємо ліміт 10 QR кодів
        existing_count = ClientQRCode.objects.filter(client=client).count()
        if existing_count >= 10:
            logger.warning(f"Client {client.id} reached QR code limit (10)")
            raise serializers.ValidationError("Maximum 10 QR codes allowed per client")
        
        qr_code = serializer.save(client=client)
        logger.info(f"QR code created with id {qr_code.id}")
        
        # Генеруємо QR код якщо не згенеровано
        if not qr_code.qr_code and not qr_code.qr_code_url:
            try:
                logger.info(f"Generating QR code image for QRCode {qr_code.id}")
                qr_code.generate_qr_code()
                qr_code.save(update_fields=['qr_code', 'qr_code_url'])
                logger.info(f"QR code image generated successfully for QRCode {qr_code.id}")
            except Exception as e:
                # Логуємо помилку з повним traceback
                logger.error(f"Failed to generate QR code for QRCode {qr_code.id}: {str(e)}", exc_info=True)
                # Не блокуємо створення, але повідомляємо про помилку
    
    def perform_update(self, serializer):
        """Оновлює QR код та регенерує його якщо потрібно."""
        instance = self.get_object()
        serializer.save()
        
        # Регенеруємо QR код якщо змінили назву або локацію (може змінитися prefill)
        if 'name' in serializer.validated_data or 'location' in serializer.validated_data:
            try:
                instance.generate_qr_code()
                instance.save(update_fields=['qr_code', 'qr_code_url'])
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to regenerate QR code for {instance}: {e}")


router = DefaultRouter()
router.register(r'', ClientViewSet, basename='client')  # Видаляємо префікс 'clients', бо він вже є в основному urls.py
router.register(r'documents', ClientDocumentViewSet, basename='document')
router.register(r'api-keys', APIKeyViewSet, basename='api-key')
router.register(r'knowledge-blocks', KnowledgeBlockViewSet, basename='knowledge-block')
router.register(r'qr-codes', ClientQRCodeViewSet, basename='qr-code')
# prompts зареєстрований явно в urls.py, щоб уникнути конфліктів
router.register(r'news', NewsViewSet, basename='news')


def generate_api_docs(request, client_id: int):
    client = get_object_or_404(Client, pk=client_id)
    api_key_obj = ClientAPIKey.objects.filter(client=client, is_active=True).order_by('-created_at').first()
    api_key = api_key_obj.key if api_key_obj else ''
    config = getattr(client, 'api_config', None)
    language = (config.language if config else 'python')
    integration_type = (config.integration_type if config else 'web')

    template_map = {
        ('python', 'telegram'): 'api_docs/python_telegram.md',
        ('python', 'web'): 'api_docs/python_web.md',
        ('nodejs', 'telegram'): 'api_docs/nodejs_telegram.md',
        ('nodejs', 'web'): 'api_docs/nodejs_web.md',
        ('php', 'web'): 'api_docs/php_web.md',
        ('curl', 'web'): 'api_docs/curl_generic.md',
        ('curl', 'telegram'): 'api_docs/curl_generic.md',
    }
    template_name = template_map.get((language, integration_type), 'api_docs/curl_generic.md')

    context = {
        'api_key': api_key,
        'base_url': settings.CLIENT_PORTAL_BASE_URL.rstrip('/') + '/',
        'specialization': str(client.specialization),
        'client': client,
    }

    content = render_to_string(template_name, context)
    return HttpResponse(content, content_type='text/markdown')


@require_POST
@staff_member_required
def rag_test_query(request):
    """AJAX endpoint для мінімального RAG тестера в адмінці.
    Приймає POST з полями: query, client_id, branch_id (optional), specialization_id (optional)
    Повертає JSON: {answer, sources: [{title, level, similarity}]}
    """
    if request.headers.get('Content-Type', '').startswith('application/json'):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        query = (payload.get('query') or '').strip()
        client_id = payload.get('client_id')
        branch_id = payload.get('branch_id')
        specialization_id = payload.get('specialization_id')
    else:
        query = (request.POST.get('query') or '').strip()
        client_id = request.POST.get('client_id')
        branch_id = request.POST.get('branch_id')
        specialization_id = request.POST.get('specialization_id')

    if not query:
        return JsonResponse({"error": "Query is required"}, status=400)
    if not client_id:
        return JsonResponse({"error": "client_id is required"}, status=400)

    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)
    client = get_object_or_404(Client, pk=client_id)
    branch = None
    specialization = None

    if branch_id:
        try:
            branch = Branch.objects.get(pk=branch_id)
        except Branch.DoesNotExist:
            return JsonResponse({"error": "Branch not found"}, status=404)

    if specialization_id:
        try:
            specialization = Specialization.objects.get(pk=specialization_id)
        except Specialization.DoesNotExist:
            return JsonResponse({"error": "Specialization not found"}, status=404)

    client_specialization_id = getattr(client, 'specialization_id', None)
    specialization_id_val = getattr(specialization, 'id', None) if specialization else None
    if specialization and client_specialization_id != specialization_id_val:
        return JsonResponse({"error": "Client does not belong to the selected specialization"}, status=400)

    client_branch_id = getattr(getattr(client, 'specialization', None), 'branch_id', None)
    branch_id_val = getattr(branch, 'id', None) if branch else None
    if branch and client_branch_id != branch_id_val:
        return JsonResponse({"error": "Client does not belong to the selected branch"}, status=400)

    generator = ResponseGenerator()
    rag_response = generator.generate(
        query=query,
        client=client,
        specialization=specialization,
        branch=branch,
        stream=False,
    )

    return JsonResponse({
        "answer": getattr(rag_response, 'answer', ''),
        "sources": getattr(rag_response, 'sources', []),
        "num_chunks": getattr(rag_response, 'num_chunks', 0),
        "total_tokens": getattr(rag_response, 'total_tokens', 0),
    })


class ClientMeView(APIView):
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методі

    def get(self, request):
        client = get_client_from_request(request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
                
        if not client:
            return Response({'error': 'Client not found or invalid API key'}, status=401)
            
        data = ClientSerializer(client, context={'request': request}).data
        return Response(data)

    def patch(self, request):
        client = get_client_from_request(request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
                
        if not client:
            return Response({'error': 'Client not found or invalid API key'}, status=401)
        # Allow updating only specific fields from client cabinet
        allowed_fields = ['custom_system_prompt', 'features', 'company_name']
        payload = {k: v for k, v in (request.data or {}).items() if k in allowed_fields}
        if not payload:
            return Response({'error': 'No updatable fields provided'}, status=400)
        for k, v in payload.items():
            setattr(client, k, v)
        client.save(update_fields=list(payload.keys()))
        return Response(ClientSerializer(client, context={'request': request}).data)


class ClientWhatsAppConfigView(APIView):
    """Get/Update per-client Meta WhatsApp configuration."""
    permission_classes = []  # Публічний, ідентифікація через middleware/api_key/tag

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        data = {
            'whatsapp_meta_enabled': getattr(client, 'whatsapp_meta_enabled', False),
            'meta_waba_id': getattr(client, 'meta_waba_id', ''),
            'meta_app_id': getattr(client, 'meta_app_id', ''),
            'meta_phone_number': getattr(client, 'meta_phone_number', ''),
            'meta_phone_number_id': getattr(client, 'meta_phone_number_id', ''),
            'meta_verify_token': getattr(client, 'meta_verify_token', ''),
        }
        return Response(data)

    def post(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        data = request.data or {}
        updatable = {
            'whatsapp_meta_enabled',
            'meta_waba_id',
            'meta_app_id',
            'meta_phone_number',
            'meta_phone_number_id',
            'meta_verify_token',
            'meta_app_secret',
            'meta_access_token',
        }
        changed = []
        for key, val in data.items():
            if key in updatable:
                setattr(client, key, val)
                changed.append(key)
        if not changed:
            return Response({'error': 'No fields to update'}, status=400)
        client.save(update_fields=changed)
        return Response({'success': True})


class ClientTelegramConfigView(APIView):
    """Get/Update per-client Telegram Bot configuration."""
    permission_classes = []  # Публічний, ідентифікація через middleware/api_key/tag

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        data = {
            'telegram_enabled': getattr(client, 'telegram_enabled', False),
            'telegram_bot_token': getattr(client, 'telegram_bot_token', ''),
            'telegram_webhook_url': getattr(client, 'telegram_webhook_url', ''),
        }
        return Response(data)

    def post(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        from .views_telegram import set_telegram_webhook, delete_telegram_webhook
        from django.conf import settings
        
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        
        data = request.data or {}
        updatable = {
            'telegram_enabled',
            'telegram_bot_token',
        }
        
        old_token = client.telegram_bot_token
        old_enabled = client.telegram_enabled
        
        changed = []
        for key, val in data.items():
            if key in updatable:
                setattr(client, key, val)
                changed.append(key)
        
        if not changed:
            return Response({'error': 'No fields to update'}, status=400)
        
        # Якщо змінився токен або статус, оновлюємо webhook
        token_changed = 'telegram_bot_token' in changed
        enabled_changed = 'telegram_enabled' in changed
        
        if token_changed or enabled_changed:
            # Видаляємо старий webhook якщо був токен
            if old_token and (token_changed or (enabled_changed and not client.telegram_enabled)):
                try:
                    delete_telegram_webhook(old_token)
                except Exception as e:
                    logger.warning(f"Failed to delete old Telegram webhook: {e}")
            
            # Встановлюємо новий webhook якщо увімкнено і є токен
            if client.telegram_enabled and client.telegram_bot_token:
                # Формуємо webhook URL
                base_url = getattr(settings, 'TELEGRAM_WEBHOOK_BASE_URL', request.build_absolute_uri('/').rstrip('/'))
                webhook_url = f"{base_url}/api/clients/telegram/webhook/"
                
                if set_telegram_webhook(client.telegram_bot_token, webhook_url):
                    client.telegram_webhook_url = webhook_url
                    changed.append('telegram_webhook_url')
                else:
                    return Response({'error': 'Failed to set Telegram webhook'}, status=500)
        
        client.save(update_fields=changed)
        
        # Створюємо новину про нову інтеграцію Telegram
        if token_changed and client.telegram_enabled and client.telegram_bot_token:
            try:
                from MASTER.clients.news_utils import create_integration_news
                create_integration_news('Telegram', 'Telegram Bot integration is now available! Connect your AI assistant to Telegram and reach your customers on their favorite messaging platform.')
            except Exception as e:
                logger.warning(f"Failed to create Telegram integration news: {e}")
        
        return Response({
            'success': True,
            'telegram_enabled': client.telegram_enabled,
            'telegram_webhook_url': client.telegram_webhook_url,
        })


class ClientEmailSMTPConfigView(APIView):
    """Get/Update per-client SMTP Email configuration."""
    permission_classes = []  # Публічний, ідентифікація через middleware/api_key/tag

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        data = {
            'email_smtp_enabled': getattr(client, 'email_smtp_enabled', False),
            'email_smtp_host': getattr(client, 'email_smtp_host', ''),
            'email_smtp_port': getattr(client, 'email_smtp_port', 587),
            'email_smtp_use_tls': getattr(client, 'email_smtp_use_tls', True),
            'email_smtp_username': getattr(client, 'email_smtp_username', ''),
            'email_smtp_password': '',  # Не повертаємо пароль
            'email_from_address': getattr(client, 'email_from_address', ''),
            'email_from_name': getattr(client, 'email_from_name', ''),
        }
        return Response(data)

    def post(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        
        data = request.data or {}
        updatable = {
            'email_smtp_enabled',
            'email_smtp_host',
            'email_smtp_port',
            'email_smtp_use_tls',
            'email_smtp_username',
            'email_smtp_password',
            'email_from_address',
            'email_from_name',
        }
        
        changed = []
        test_connection = data.get('test_connection', False)
        
        for key, val in data.items():
            if key in updatable and key != 'test_connection':
                setattr(client, key, val)
                changed.append(key)
        
        if not changed:
            return Response({'error': 'No fields to update'}, status=400)
        
        # Тестуємо з'єднання якщо потрібно
        if test_connection and client.email_smtp_enabled and client.email_smtp_host and client.email_smtp_username and client.email_smtp_password:
            try:
                # Тестуємо SMTP з'єднання
                if client.email_smtp_use_tls:
                    server = smtplib.SMTP(client.email_smtp_host, client.email_smtp_port)
                    server.starttls()
                else:
                    server = smtplib.SMTP_SSL(client.email_smtp_host, client.email_smtp_port)
                
                server.login(client.email_smtp_username, client.email_smtp_password)
                server.quit()
                
                # Створюємо новину про нову інтеграцію Email
                try:
                    from MASTER.clients.news_utils import create_integration_news
                    create_integration_news('Email SMTP', 'Email SMTP integration is now available! Send and receive emails through your AI assistant.')
                except Exception as e:
                    logger.warning(f"Failed to create Email SMTP integration news: {e}")
            except Exception as e:
                return Response({
                    'error': f'SMTP connection test failed: {str(e)}',
                    'test_passed': False
                }, status=400)
        
        client.save(update_fields=changed)
        
        return Response({
            'success': True,
            'email_smtp_enabled': client.email_smtp_enabled,
            'test_passed': test_connection if 'test_connection' in data else None,
        })


class KnowledgeBlockDocumentsView(APIView):
    """API для додавання документів до Knowledge Block."""
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методі
    
    def post(self, request, block_id):
        """Додати документ до knowledge block."""
        client = get_client_from_request(request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
                
        if not client:
            return Response({'error': 'Client not found or invalid API key'}, status=401)
        
        try:
            block = KnowledgeBlock.objects.get(id=block_id, client=client)
        except KnowledgeBlock.DoesNotExist:
            return Response({'error': 'Knowledge block not found'}, status=404)
        
        if block.is_permanent:
            return Response(
                {'error': 'Cannot add documents to permanent blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Отримуємо файл та title
        file = request.FILES.get('file')
        title = request.data.get('title', file.name if file else 'Untitled')
        
        if not file:
            return Response({'error': 'File is required'}, status=400)
        
        # Створюємо документ
        document = ClientDocument.objects.create(
            client=client,
            knowledge_block=block,
            title=title,
            file=file,
            file_type=self._get_file_type(file.name),
            file_size=file.size,
            metadata={'source': 'knowledge_block', 'block_name': block.name}
        )
        
        return Response(
            ClientDocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    def _get_file_type(self, filename):
        """Визначити тип файлу з розширення."""
        ext = filename.split('.')[-1].lower()
        file_types = {
            'pdf': 'pdf',
            'txt': 'txt',
            'csv': 'csv',
            'json': 'json',
            'doc': 'docx',
            'docx': 'docx',
            # Додаємо підтримку JSON файлів (вже є в списку)
        }
        return file_types.get(ext, 'txt')


class ClientLogoUploadView(APIView):
    """API endpoint для завантаження логотипу клієнта"""
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методі
    
    def post(self, request):
        try:
            # Отримуємо клієнта з токену або API ключа
            client = get_client_from_request(request)
            
            # Якщо немає клієнта через JWT, пробуємо через API ключ
            if not client and 'HTTP_X_API_KEY' in request.META:
                api_key = request.META['HTTP_X_API_KEY']
                try:
                    key_obj = ClientAPIKey.objects.select_related('client').get(
                        key=api_key,
                        is_active=True
                    )
                    if key_obj.is_valid():
                        client = key_obj.client
                except ClientAPIKey.DoesNotExist:
                    pass
            
            if not client:
                return Response({'error': 'Client not found or invalid API key'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Перевіряємо чи є файл
            if 'logo' not in request.FILES:
                return Response({'error': 'No logo file provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            logo_file = request.FILES['logo']
            
            # Валідація файлу
            if not logo_file.content_type.startswith('image/'):
                return Response({'error': 'File must be an image'}, status=status.HTTP_400_BAD_REQUEST)
            
            if logo_file.size > 5 * 1024 * 1024:  # 5MB limit
                return Response({'error': 'File size must be less than 5MB'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Зберігаємо логотип
            client.logo = logo_file
            client.save(update_fields=['logo'])
            
            # Регенеруємо QR-коди ClientQRCode для всіх клієнтів
            qr_codes = ClientQRCode.objects.filter(client=client)
            for qr_code in qr_codes:
                try:
                    qr_code.generate_qr_code()
                    qr_code.save(update_fields=['qr_code', 'qr_code_url'])
                except Exception as e:
                    print(f"Помилка регенерації QR-коду {qr_code.name}: {e}")
            
            # Backward compatibility: регенеруємо RestaurantTable QR-коди
            if client.client_type == 'restaurant':
                from MASTER.restaurant.models import RestaurantTable
                tables = RestaurantTable.objects.filter(client=client)
                for table in tables:
                    try:
                        table.generate_qr_code()
                        table.save(update_fields=['qr_code', 'qr_code_url'])
                    except Exception as e:
                        print(f"Помилка регенерації QR-коду для столика {table.table_number}: {e}")
            
            # Отримуємо повний URL логотипу
            logo_url = None
            if client.logo:
                request_temp = request  # Для доступу до request в serializer
                serializer = ClientSerializer(client, context={'request': request_temp})
                logo_url = serializer.data.get('logo_url')
            
            return Response({
                'message': 'Logo uploaded successfully',
                'logo_url': logo_url,
                'client': ClientSerializer(client, context={'request': request}).data
            })
            
        except Exception as e:
            return Response(
                {'error': f'Error uploading logo: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request):
        """Видалити логотип клієнта"""
        try:
            # Отримуємо клієнта з токену або API ключа
            client = get_client_from_request(request)
            
            # Якщо немає клієнта через JWT, пробуємо через API ключ
            if not client and 'HTTP_X_API_KEY' in request.META:
                api_key = request.META['HTTP_X_API_KEY']
                try:
                    key_obj = ClientAPIKey.objects.select_related('client').get(
                        key=api_key,
                        is_active=True
                    )
                    if key_obj.is_valid():
                        client = key_obj.client
                except ClientAPIKey.DoesNotExist:
                    pass
            
            if not client:
                return Response({'error': 'Client not found or invalid API key'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if client.logo:
                client.logo.delete()
                client.logo = None
                client.save(update_fields=['logo'])
                
                # Регенеруємо QR-коди без логотипу (ClientQRCode для всіх клієнтів)
                qr_codes = ClientQRCode.objects.filter(client=client)
                for qr_code in qr_codes:
                    try:
                        qr_code.generate_qr_code()
                        qr_code.save(update_fields=['qr_code', 'qr_code_url'])
                    except Exception as e:
                        print(f"Помилка регенерації QR-коду {qr_code.name}: {e}")
                
                # Backward compatibility: регенеруємо RestaurantTable QR-коди
                if client.client_type == 'restaurant':
                    from MASTER.restaurant.models import RestaurantTable
                    tables = RestaurantTable.objects.filter(client=client)
                    for table in tables:
                        try:
                            table.generate_qr_code()
                            table.save(update_fields=['qr_code', 'qr_code_url'])
                        except Exception as e:
                            print(f"Помилка регенерації QR-коду для столика {table.table_number}: {e}")
            
            return Response({'message': 'Logo deleted successfully'})
            
        except Exception as e:
            return Response(
                {'error': f'Error deleting logo: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClientRegenerateQRsView(APIView):
    """
    API endpoint для форсова регенерації всіх QR-кодів клієнта (ClientQRCode та RestaurantTable)
    POST /api/clients/{id}/regenerate-qrs/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            # Отримуємо клієнта
            client = get_object_or_404(Client, pk=pk)
            
            # Перевіряємо права доступу
            request_client = get_client_from_request(request)
            if not (request.user.is_staff or request_client == client):
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            regenerated_count = 0
            errors = []
            
            # Регенеруємо ClientQRCode (для всіх клієнтів)
            qr_codes = ClientQRCode.objects.filter(client=client)
            for qr_code in qr_codes:
                try:
                    qr_code.generate_qr_code()
                    qr_code.save(update_fields=['qr_code', 'qr_code_url'])
                    regenerated_count += 1
                except Exception as e:
                    errors.append(f"QR code {qr_code.name}: {str(e)}")
            
            # Регенеруємо RestaurantTable QR-коди (backward compatibility)
            from MASTER.restaurant.models import RestaurantTable
            tables = RestaurantTable.objects.filter(client=client)
            for table in tables:
                try:
                    table.generate_qr_code()
                    table.save(update_fields=['qr_code', 'qr_code_url'])
                    regenerated_count += 1
                except Exception as e:
                    errors.append(f"Table {table.table_number}: {str(e)}")
            
            response_data = {
                'message': f'Successfully regenerated {regenerated_count} QR code(s)',
                'regenerated_count': regenerated_count,
                'total_qr_codes': qr_codes.count(),
                'total_tables': tables.count(),
            }
            
            if errors:
                response_data['errors'] = errors
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error regenerating QR codes: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClientConversationsView(APIView):
    """
    API endpoint для отримання всіх розмов WhatsApp клієнта
    GET /api/clients/conversations/
    """
    permission_classes = []
    
    def get(self, request):
        """Отримати список всіх розмов WhatsApp клієнта"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Отримуємо всі розмови клієнта (ClientWhatsAppConversation)
        conversations = ClientWhatsAppConversation.objects.filter(client=client).order_by('-started_at')
        
        # Логування для діагностики
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📊 Client {client.id} ({client.company_name}) requested conversations")
        logger.info(f"📊 Total conversations: {conversations.count()}")
        web_convs = conversations.filter(context_metadata__platform='web').count()
        whatsapp_convs = conversations.exclude(context_metadata__platform='web').count()
        logger.info(f"📊 Web conversations: {web_convs}, WhatsApp: {whatsapp_convs}")
        
        # Також отримуємо RestaurantConversation для backward compatibility
        from MASTER.restaurant.models import RestaurantConversation
        restaurant_conversations = RestaurantConversation.objects.filter(client=client).order_by('-started_at')
        
        # Формуємо список розмов
        conversations_list = []
        
        # Додаємо ClientWhatsAppConversation
        for conv in conversations:
            # Отримуємо останнє повідомлення
            last_message = conv.messages[-1] if conv.messages else None
            last_message_text = last_message.get('content', '') if last_message else ''
            
            # Форматуємо timestamp
            from django.utils import timezone
            from datetime import timedelta
            now = timezone.now()
            time_diff = now - conv.started_at
            
            if time_diff < timedelta(hours=1):
                timestamp = f"{int(time_diff.seconds / 60)} minutes ago"
            elif time_diff < timedelta(hours=24):
                timestamp = f"{int(time_diff.seconds / 3600)} hours ago"
            elif time_diff < timedelta(days=7):
                timestamp = f"{time_diff.days} days ago"
            else:
                timestamp = conv.started_at.strftime('%Y-%m-%d')
            
            # Визначаємо source на основі context_metadata
            source = 'whatsapp'
            if conv.context_metadata and conv.context_metadata.get('platform') == 'web':
                source = 'web'
            
            # Форматуємо номер телефону як ім'я
            if source == 'web':
                customer_name = 'Web Chat'
            else:
                customer_name = conv.customer_phone
                if len(customer_name) > 10:
                    # Спрощуємо номер для відображення
                    customer_name = f"+{customer_name[-9:]}" if customer_name.startswith('+') else customer_name[-9:]
            
            conversations_list.append({
                'id': conv.id,
                'conversation_id': conv.id,
                'customerName': customer_name,
                'customer_phone': conv.customer_phone,
                'lastMessage': last_message_text,
                'timestamp': timestamp,
                'started_at': conv.started_at.isoformat(),
                'unread': 0,  # Можна додати логіку підрахунку непрочитаних
                'is_active': conv.is_active,
                'total_messages': conv.total_messages,
                'qr_code_name': conv.qr_code.name if conv.qr_code else None,
                'source': source
            })
        
        # Додаємо RestaurantConversation (backward compatibility)
        for conv in restaurant_conversations:
            # Перевіряємо, чи вже є ця розмова в списку (може бути дублікат)
            if not any(c['customer_phone'] == conv.customer_phone and c['source'] == 'restaurant' for c in conversations_list):
                last_message = conv.messages[-1] if conv.messages else None
                last_message_text = last_message.get('content', '') if last_message else ''
                
                time_diff = now - conv.started_at
                if time_diff < timedelta(hours=1):
                    timestamp = f"{int(time_diff.seconds / 60)} minutes ago"
                elif time_diff < timedelta(hours=24):
                    timestamp = f"{int(time_diff.seconds / 3600)} hours ago"
                elif time_diff < timedelta(days=7):
                    timestamp = f"{time_diff.days} days ago"
                else:
                    timestamp = conv.started_at.strftime('%Y-%m-%d')
                
                customer_name = conv.customer_phone
                if len(customer_name) > 10:
                    customer_name = f"+{customer_name[-9:]}" if customer_name.startswith('+') else customer_name[-9:]
                
                conversations_list.append({
                    'id': f"rest_{conv.id}",
                    'conversation_id': conv.id,
                    'customerName': customer_name,
                    'customer_phone': conv.customer_phone,
                    'lastMessage': last_message_text,
                    'timestamp': timestamp,
                    'started_at': conv.started_at.isoformat(),
                    'unread': 0,
                    'is_active': conv.is_active,
                    'total_messages': conv.total_messages,
                    'table_number': conv.table.table_number if conv.table else None,
                    'source': 'restaurant'
                })
        
        # Сортуємо за датою створення (найновіші перші)
        conversations_list.sort(key=lambda x: x['started_at'], reverse=True)
        
        return Response({
            'conversations': conversations_list,
            'total': len(conversations_list)
        })


class ClientConversationDetailView(APIView):
    """
    API endpoint для отримання деталей конкретної розмови
    GET /api/clients/conversations/{id}/
    """
    permission_classes = []
    
    def get(self, request, conversation_id):
        """Отримати деталі розмови"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Перевіряємо чи це ClientWhatsAppConversation
        try:
            conversation = ClientWhatsAppConversation.objects.get(id=conversation_id, client=client)
            
            # Форматуємо повідомлення для фронтенду
            messages = []
            for idx, msg in enumerate(conversation.messages or []):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                timestamp_str = msg.get('timestamp', '')
                
                # Конвертуємо timestamp
                try:
                    from datetime import datetime
                    if timestamp_str:
                        timestamp_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        timestamp = timestamp_dt.strftime('%I:%M %p')
                    else:
                        timestamp = ''
                except Exception:
                    timestamp = ''
                
                messages.append({
                    'id': idx + 1,
                    'text': content,
                    'sender': 'customer' if role == 'user' else 'ai',
                    'timestamp': timestamp,
                    'photo': None,  # WhatsApp не підтримує фото в нашій поточній реалізації
                })
            
            # Форматуємо timestamp для відображення
            from django.utils import timezone
            from datetime import timedelta
            now = timezone.now()
            time_diff = now - conversation.started_at
            
            if time_diff < timedelta(hours=1):
                timestamp_display = f"{int(time_diff.seconds / 60)} minutes ago"
            elif time_diff < timedelta(hours=24):
                timestamp_display = f"{int(time_diff.seconds / 3600)} hours ago"
            elif time_diff < timedelta(days=7):
                timestamp_display = f"{time_diff.days} days ago"
            else:
                timestamp_display = conversation.started_at.strftime('%Y-%m-%d')
            
            # Визначаємо source на основі context_metadata
            source = 'whatsapp'
            if conversation.context_metadata and conversation.context_metadata.get('platform') == 'web':
                source = 'web'
            
            # Форматуємо ім'я клієнта
            if source == 'web':
                customer_name = 'Web Chat'
            else:
                customer_name = conversation.customer_phone
                if len(customer_name) > 10:
                    customer_name = f"+{customer_name[-9:]}" if customer_name.startswith('+') else customer_name[-9:]
            
            return Response({
                'id': conversation.id,
                'conversation_id': conversation.id,
                'customerName': customer_name,
                'customer_phone': conversation.customer_phone,
                'timestamp': timestamp_display,
                'started_at': conversation.started_at.isoformat(),
                'is_active': conversation.is_active,
                'total_messages': conversation.total_messages,
                'qr_code_name': conversation.qr_code.name if conversation.qr_code else None,
                'messages': messages,
                'source': source
            })
            
        except ClientWhatsAppConversation.DoesNotExist:
            # Backward compatibility: перевіряємо RestaurantConversation
            from MASTER.restaurant.models import RestaurantConversation
            try:
                conversation = RestaurantConversation.objects.get(id=conversation_id, client=client)
                
                messages = []
                for idx, msg in enumerate(conversation.messages or []):
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    timestamp_str = msg.get('timestamp', '')
                    
                    try:
                        from datetime import datetime
                        if timestamp_str:
                            timestamp_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            timestamp = timestamp_dt.strftime('%I:%M %p')
                        else:
                            timestamp = ''
                    except Exception:
                        timestamp = ''
                    
                    messages.append({
                        'id': idx + 1,
                        'text': content,
                        'sender': 'customer' if role == 'user' else 'ai',
                        'timestamp': timestamp,
                        'photo': None,
                    })
                
                now = timezone.now()
                time_diff = now - conversation.started_at
                
                if time_diff < timedelta(hours=1):
                    timestamp_display = f"{int(time_diff.seconds / 60)} minutes ago"
                elif time_diff < timedelta(hours=24):
                    timestamp_display = f"{int(time_diff.seconds / 3600)} hours ago"
                elif time_diff < timedelta(days=7):
                    timestamp_display = f"{time_diff.days} days ago"
                else:
                    timestamp_display = conversation.started_at.strftime('%Y-%m-%d')
                
                customer_name = conversation.customer_phone
                if len(customer_name) > 10:
                    customer_name = f"+{customer_name[-9:]}" if customer_name.startswith('+') else customer_name[-9:]
                
                return Response({
                    'id': f"rest_{conversation.id}",
                    'conversation_id': conversation.id,
                    'customerName': customer_name,
                    'customer_phone': conversation.customer_phone,
                    'timestamp': timestamp_display,
                    'started_at': conversation.started_at.isoformat(),
                    'is_active': conversation.is_active,
                    'total_messages': conversation.total_messages,
                    'table_number': conversation.table.table_number if conversation.table else None,
                    'messages': messages,
                    'source': 'restaurant'
                })
            except RestaurantConversation.DoesNotExist:
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )


class ClientWebConversationView(APIView):
    """
    API endpoint для збереження web розмов
    POST /api/clients/web-conversations/
    Body: { "session_id": "...", "message": "...", "response": "...", "platform": "web" }
    """
    permission_classes = []
    
    def post(self, request):
        """Зберегти повідомлення web розмови"""
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)
        
        client = get_client_from_request(request)
        if not client:
            logger.error("❌ Web conversation: Client not found")
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        session_id = request.data.get('session_id', '')
        message = request.data.get('message', '')
        response_text = request.data.get('response', '')
        platform = request.data.get('platform', 'web')
        
        logger.info(f"💬 Web conversation POST: client={client.id}, session={session_id[:20]}...")
        
        if not session_id:
            logger.error("❌ Web conversation: session_id is required")
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Створюємо або оновлюємо розмову
        # Використовуємо session_id для пошуку, але коротку версію для customer_phone (макс 20 символів)
        # customer_phone для веб: "web_" + останні 16 символів session_id = 20 символів макс
        short_phone = f"web_{session_id[-16:]}" if len(session_id) > 16 else f"web_{session_id}"
        short_phone = short_phone[:20]  # Гарантуємо макс 20 символів
        
        conversation, created = ClientWhatsAppConversation.objects.get_or_create(
            session_id=session_id,
            client=client,
            is_active=True,
            defaults={
                'customer_phone': short_phone,
                'started_at': timezone.now(),
                'messages': [],
                'context_metadata': {'platform': platform},
            }
        )
        
        logger.info(f"💬 Web conversation {'CREATED' if created else 'UPDATED'}: id={conversation.id}")
        
        # Оновлюємо platform в context_metadata якщо не створено
        if not created:
            if not conversation.context_metadata:
                conversation.context_metadata = {}
            conversation.context_metadata['platform'] = platform
            conversation.save(update_fields=['context_metadata', 'updated_at'])
        
        # Додаємо повідомлення користувача та відповідь
        if not conversation.messages:
            conversation.messages = []
        
        conversation.messages.append({
            'role': 'user',
            'content': message,
            'timestamp': timezone.now().isoformat()
        })
        
        conversation.messages.append({
            'role': 'assistant',
            'content': response_text,
            'timestamp': timezone.now().isoformat()
        })
        
        conversation.total_messages = len(conversation.messages)
        conversation.save(update_fields=['messages', 'total_messages', 'updated_at'])
        
        return Response({
            'success': True,
            'conversation_id': conversation.id,
            'total_messages': conversation.total_messages
        })


class ClientWebKnowledgeView(APIView):
    """
    Legacy API endpoint для створення запитів на парсинг веб-сайтів.
    POST /api/clients/web-knowledge/
    Body: { "url": "...", "description": "..." }
    Проксі до WebParsingRequest (новий функціонал).
    """
    permission_classes = []  # Ідентифікація через tag / X-Client-Token / X-API-Key

    def post(self, request):
        from MASTER.clients.models import WebParsingRequest

        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        url = request.data.get('url') or request.data.get('website_url')
        description = request.data.get('description', '') or ''

        if not url:
            return Response(
                {'error': 'url is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        request_obj = WebParsingRequest.objects.create(
            client=client,
            website_url=url,
            description=description.strip()
        )

        return Response({
            'id': request_obj.id,
            'website_url': request_obj.website_url,
            'description': request_obj.description,
            'status': request_obj.status,
            'created_at': request_obj.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class ClientTopQuestionsView(APIView):
    """
    API endpoint для отримання найчастіше запитуваних питань користувачів
    GET /api/clients/top-questions/
    """
    permission_classes = []  # Дозволяємо доступ без JWT – ідентифікація за tag/API key
    
    def get(self, request):
        """Отримати топ питань з розмов WhatsApp"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Отримуємо всі розмови клієнта
        conversations = ClientWhatsAppConversation.objects.filter(client=client)
        
        # Також отримуємо RestaurantConversation для backward compatibility
        from MASTER.restaurant.models import RestaurantConversation
        restaurant_conversations = RestaurantConversation.objects.filter(client=client)
        
        # Збираємо всі повідомлення користувачів
        user_messages = []
        
        for conv in conversations:
            if conv.messages:
                for msg in conv.messages:
                    if msg.get('role') == 'user':
                        content = msg.get('content', '').strip()
                        if content and len(content) > 10:  # Мінімальна довжина питання
                            user_messages.append(content)
        
        # Backward compatibility
        for conv in restaurant_conversations:
            if conv.messages:
                for msg in conv.messages:
                    if msg.get('role') == 'user':
                        content = msg.get('content', '').strip()
                        if content and len(content) > 10:
                            user_messages.append(content)
        
        # Підраховуємо частоти (простий підхід - по першому реченню)
        import re
        from collections import Counter
        
        # Нормалізуємо питання (беремо перші 100 символів, видаляємо зайві пробіли)
        normalized_questions = []
        for msg in user_messages:
            # Беремо перше речення (до крапки, знаку питання або перші 100 символів)
            first_sentence = re.split(r'[.!?]\s+', msg)[0] if re.search(r'[.!?]', msg) else msg[:100]
            first_sentence = first_sentence.strip()[:100]  # Обмежуємо до 100 символів
            if len(first_sentence) > 10:  # Мінімальна довжина
                normalized_questions.append(first_sentence)
        
        # Підраховуємо частоти
        question_counts = Counter(normalized_questions)
        
        # Отримуємо топ 4 найчастіші питання
        top_questions = question_counts.most_common(4)
        
        # Форматуємо для відповіді
        result = []
        for i, (question, count) in enumerate(top_questions):
            result.append({
                'question': question,
                'count': count,
                'rank': i + 1
            })
        
        # Якщо питань менше 4, додаємо порожні місця
        while len(result) < 4:
            result.append({
                'question': '',
                'count': 0,
                'rank': len(result) + 1
            })
        
        return Response({
            'top_questions': result,
            'total': len(user_messages)
        })


class ClientRecentActivityView(APIView):
    """
    API endpoint для отримання останніх активностей клієнта
    GET /api/clients/recent-activity/
    """
    permission_classes = []  # Дозволяємо доступ без JWT – ідентифікація за tag/API key
    
    def get(self, request):
        """Отримати останні активності з розмов WhatsApp"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = []
        
        # Отримуємо останні розмови (ClientWhatsAppConversation)
        conversations = ClientWhatsAppConversation.objects.filter(
            client=client
        ).order_by('-started_at', '-updated_at')[:20]
        
        # Також отримуємо RestaurantConversation для backward compatibility
        from MASTER.restaurant.models import RestaurantConversation
        restaurant_conversations = RestaurantConversation.objects.filter(
            client=client
        ).order_by('-started_at', '-updated_at')[:20]
        
        # Формуємо список активностей
        for conv in conversations:
            # Активність: нова розмова
            if conv.started_at:
                from django.utils import timezone
                from datetime import timedelta
                now = timezone.now()
                time_diff = now - conv.started_at
                
                if time_diff < timedelta(minutes=1):
                    time_ago = "just now"
                elif time_diff < timedelta(hours=1):
                    minutes = int(time_diff.seconds / 60)
                    time_ago = f"{minutes} min ago"
                elif time_diff < timedelta(days=1):
                    hours = int(time_diff.seconds / 3600)
                    time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
                elif time_diff < timedelta(days=7):
                    days = time_diff.days
                    time_ago = f"{days} day{'s' if days > 1 else ''} ago"
                else:
                    time_ago = conv.started_at.strftime('%Y-%m-%d')
                
                # Форматуємо номер телефону
                customer_name = conv.customer_phone
                if len(customer_name) > 10:
                    customer_name = f"+{customer_name[-9:]}" if customer_name.startswith('+') else customer_name[-9:]
                    # Додаємо ініціал з номера
                    customer_display = f"{customer_name.split('+')[-1][0].upper()}. {customer_name[-8:]}"
                else:
                    customer_display = customer_name
                
                activities.append({
                    'type': 'new_chat',
                    'text': f"New chat from {customer_display}",
                    'time': time_ago,
                    'timestamp': conv.started_at.isoformat(),
                    'conversation_id': conv.id,
                })
        
        # Backward compatibility: RestaurantConversation
        for conv in restaurant_conversations:
            # Перевіряємо чи не дублікат (за номером телефону)
            if not any(a.get('type') == 'new_chat' and conv.customer_phone in a.get('text', '') for a in activities):
                if conv.started_at:
                    from django.utils import timezone
                    from datetime import timedelta
                    now = timezone.now()
                    time_diff = now - conv.started_at
                    
                    if time_diff < timedelta(minutes=1):
                        time_ago = "just now"
                    elif time_diff < timedelta(hours=1):
                        minutes = int(time_diff.seconds / 60)
                        time_ago = f"{minutes} min ago"
                    elif time_diff < timedelta(days=1):
                        hours = int(time_diff.seconds / 3600)
                        time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    elif time_diff < timedelta(days=7):
                        days = time_diff.days
                        time_ago = f"{days} day{'s' if days > 1 else ''} ago"
                    else:
                        time_ago = conv.started_at.strftime('%Y-%m-%d')
                    
                    customer_name = conv.customer_phone
                    if len(customer_name) > 10:
                        customer_name = f"+{customer_name[-9:]}" if customer_name.startswith('+') else customer_name[-9:]
                        customer_display = f"{customer_name.split('+')[-1][0].upper()}. {customer_name[-8:]}"
                    else:
                        customer_display = customer_name
                    
                    activities.append({
                        'type': 'new_chat',
                        'text': f"New chat from {customer_display}",
                        'time': time_ago,
                        'timestamp': conv.started_at.isoformat(),
                        'conversation_id': conv.id,
                    })
        
        # Сортуємо за timestamp (найновіші перші)
        activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Беремо тільки останні 10 активностей
        activities = activities[:10]
        
        return Response({
            'activities': activities,
            'total': len(activities)
        })


class ClientStatsView(APIView):
    """
    API endpoint для отримання статистики клієнта
    GET /api/clients/stats/
    """
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методі
    
    def get(self, request):
        """Отримати статистику клієнта з WhatsApp розмов"""
        client = get_client_from_request(request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
                
        if not client:
            return Response(
                {'error': 'Client not found or invalid API key'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        last_month = now - timedelta(days=30)
        
        # Отримуємо всі розмови клієнта
        all_conversations = ClientWhatsAppConversation.objects.filter(client=client)
        conversations_last_month = all_conversations.filter(started_at__gte=last_month)
        
        # Backward compatibility: RestaurantConversation
        from MASTER.restaurant.models import RestaurantConversation
        all_restaurant_conversations = RestaurantConversation.objects.filter(client=client)
        restaurant_conversations_last_month = all_restaurant_conversations.filter(started_at__gte=last_month)
        
        # Total Chats - загальна кількість розмов
        total_chats = all_conversations.count() + all_restaurant_conversations.count()
        total_chats_last_month = conversations_last_month.count() + restaurant_conversations_last_month.count()
        
        # Активні користувачі - унікальні номери телефонів
        active_phones = set()
        for conv in all_conversations:
            if conv.customer_phone:
                active_phones.add(conv.customer_phone)
        for conv in all_restaurant_conversations:
            if conv.customer_phone:
                active_phones.add(conv.customer_phone)
        
        active_users = len(active_phones)
        
        # Активні користувачі за минулий місяць
        active_phones_last_month = set()
        for conv in conversations_last_month:
            if conv.customer_phone:
                active_phones_last_month.add(conv.customer_phone)
        for conv in restaurant_conversations_last_month:
            if conv.customer_phone:
                active_phones_last_month.add(conv.customer_phone)
        
        active_users_last_month = len(active_phones_last_month)
        
        # Загальна кількість повідомлень (Messages instead of Bookings)
        total_messages = 0
        for conv in all_conversations:
            if conv.messages:
                total_messages += len(conv.messages)
        for conv in all_restaurant_conversations:
            if conv.messages:
                total_messages += len(conv.messages)
        
        # Повідомлення за минулий місяць
        messages_last_month = 0
        for conv in conversations_last_month:
            if conv.messages:
                messages_last_month += len(conv.messages)
        for conv in restaurant_conversations_last_month:
            if conv.messages:
                messages_last_month += len(conv.messages)
        
        # Conversion Rate - відсоток активних розмов (з повідомленнями > 1)
        active_conversations = 0
        for conv in all_conversations:
            if conv.messages and len(conv.messages) > 1:
                active_conversations += 1
        for conv in all_restaurant_conversations:
            if conv.messages and len(conv.messages) > 1:
                active_conversations += 1
        
        conversion_rate = 0
        if total_chats > 0:
            conversion_rate = round((active_conversations / total_chats) * 100)
        
        # Активні розмови за минулий місяць
        active_conversations_last_month = 0
        for conv in conversations_last_month:
            if conv.messages and len(conv.messages) > 1:
                active_conversations_last_month += 1
        for conv in restaurant_conversations_last_month:
            if conv.messages and len(conv.messages) > 1:
                active_conversations_last_month += 1
        
        conversion_rate_last_month = 0
        if total_chats_last_month > 0:
            conversion_rate_last_month = round((active_conversations_last_month / total_chats_last_month) * 100)
        
        # Розраховуємо зміни в процентах
        # Для Total Chats
        chats_change = 0
        if total_chats_last_month > 0:
            # Порівнюємо з попереднім місяцем (приблизно)
            prev_month_start = last_month - timedelta(days=30)
            prev_month_conversations = all_conversations.filter(
                started_at__gte=prev_month_start,
                started_at__lt=last_month
            ).count()
            prev_month_restaurant = all_restaurant_conversations.filter(
                started_at__gte=prev_month_start,
                started_at__lt=last_month
            ).count()
            prev_month_total = prev_month_conversations + prev_month_restaurant
            
            if prev_month_total > 0:
                chats_change = round(((total_chats_last_month - prev_month_total) / prev_month_total) * 100)
        
        # Для Active Users
        users_change = 0
        if active_users_last_month > 0:
            # Приблизна зміна
            prev_month_phones = set()
            prev_conv = all_conversations.filter(
                started_at__gte=prev_month_start,
                started_at__lt=last_month
            )
            for conv in prev_conv:
                if conv.customer_phone:
                    prev_month_phones.add(conv.customer_phone)
            
            prev_rest_conv = all_restaurant_conversations.filter(
                started_at__gte=prev_month_start,
                started_at__lt=last_month
            )
            for conv in prev_rest_conv:
                if conv.customer_phone:
                    prev_month_phones.add(conv.customer_phone)
            
            prev_month_users = len(prev_month_phones)
            if prev_month_users > 0:
                users_change = round(((active_users_last_month - prev_month_users) / prev_month_users) * 100)
        
        # Для Messages
        messages_change = 0
        if messages_last_month > 0:
            prev_month_messages = 0
            prev_conv = all_conversations.filter(
                started_at__gte=prev_month_start,
                started_at__lt=last_month
            )
            for conv in prev_conv:
                if conv.messages:
                    prev_month_messages += len(conv.messages)
            
            prev_rest_conv = all_restaurant_conversations.filter(
                started_at__gte=prev_month_start,
                started_at__lt=last_month
            )
            for conv in prev_rest_conv:
                if conv.messages:
                    prev_month_messages += len(conv.messages)
            
            if prev_month_messages > 0:
                messages_change = round(((messages_last_month - prev_month_messages) / prev_month_messages) * 100)
        
        # Для Conversion
        conversion_change = 0
        if conversion_rate_last_month > 0 and conversion_rate > 0:
            conversion_change = conversion_rate - conversion_rate_last_month
        
        return Response({
            'total_chats': total_chats,
            'chats_change': chats_change,
            'active_users': active_users,
            'users_change': users_change,
            'total_messages': total_messages,
            'messages_change': messages_change,
            'conversion_rate': conversion_rate,
            'conversion_change': conversion_change,
        })


class ClientEmbeddingsStatsView(APIView):
    """Get embeddings statistics for the authenticated client.

    Shows:
    - Selected embedding model
    - Count of embeddings per model
    - Total embeddings count
    - Models with existing embeddings
    """
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методі

    def get(self, request):
        client = get_client_from_request(request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
                
        if not client:
            return Response({'error': 'Client not found or invalid API key'}, status=401)

        from django.db.models import Count
        from MASTER.clients.models import ClientEmbedding
        from MASTER.EmbeddingModel.models import EmbeddingModel

        # Отримуємо статистику embeddings по моделям
        embeddings_by_model = ClientEmbedding.objects.filter(
            client=client
        ).values(
            'embedding_model__id',
            'embedding_model__name',
            'embedding_model__slug',
            'embedding_model__provider'
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # Поточна модель клієнта
        current_model = client.embedding_model
        current_model_data = None
        if current_model:
            current_model_data = {
                'id': current_model.id,
                'name': current_model.name,
                'slug': current_model.slug,
                'provider': current_model.provider,
                'dimensions': current_model.dimensions,
            }

        # Загальна кількість embeddings
        total_embeddings = ClientEmbedding.objects.filter(client=client).count()

        # Кількість необроблених документів
        from MASTER.clients.models import ClientDocument
        unprocessed_docs = ClientDocument.objects.filter(
            client=client,
            is_processed=False
        ).count()

        return Response({
            'current_model': current_model_data,
            'total_embeddings': total_embeddings,
            'embeddings_by_model': list(embeddings_by_model),
            'unprocessed_documents': unprocessed_docs,
            'has_multiple_models': len(embeddings_by_model) > 1,
        })


class ClientModelStatusView(APIView):
    """
    API endpoint для перевірки статусу моделі (health check)
    GET /api/clients/model-status/
    """
    permission_classes = []  # Дозволяємо доступ без автентифікації, перевірка буде в методі

    def get(self, request):
        """Перевірити статус моделі через тестовий запит"""
        client = get_client_from_request(request)
        
        # Якщо немає клієнта через JWT, пробуємо через API ключ
        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
                
        if not client:
            return Response(
                {'error': 'Client not found or invalid API key'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            # Отримуємо інформацію про клієнта та моделі
            from MASTER.rag.response_generator import ResponseGenerator
            
            # Перевіряємо чи є embedding моделі у клієнта
            has_embeddings = False
            try:
                embeddings = client.embeddings.filter(is_processed=True)
                has_embeddings = embeddings.exists()
            except Exception:
                pass
            
            # Перевіряємо чи є документи
            has_documents = False
            try:
                documents = client.documents.filter(is_processed=True)
                has_documents = documents.exists()
            except Exception:
                pass
            
            # Перевіряємо knowledge blocks
            knowledge_blocks_count = 0
            try:
                from MASTER.clients.models import KnowledgeBlock
                knowledge_blocks = KnowledgeBlock.objects.filter(client=client, is_active=True)
                knowledge_blocks_count = knowledge_blocks.count()
            except Exception:
                pass
            
            # Пробуємо зробити тестовий запит до RAG
            model_status = "Active"
            model_error = None
            last_updated = None
            
            try:
                generator = ResponseGenerator()
                # Простий тестовий запит
                test_query = "test"
                rag_response = generator.generate(
                    query=test_query,
                    client=client,
                    stream=False
                )
                
                # Якщо відповідь отримано, модель працює
                if rag_response and hasattr(rag_response, 'answer'):
                    model_status = "Active"
                else:
                    model_status = "Inactive"
                    model_error = "Model returned empty response"
            except Exception as e:
                model_status = "Inactive"
                model_error = str(e)
            
            # Отримуємо інформацію про останнє оновлення
            try:
                # Останній документ
                last_doc = client.documents.filter(is_processed=True).order_by('-updated_at').first()
                if last_doc:
                    from django.utils import timezone
                    from datetime import timedelta
                    now = timezone.now()
                    time_diff = now - last_doc.updated_at
                    
                    if time_diff < timedelta(days=1):
                        last_updated = f"{int(time_diff.seconds / 3600)} hours ago"
                    elif time_diff < timedelta(days=7):
                        last_updated = f"{time_diff.days} days ago"
                    else:
                        last_updated = last_doc.updated_at.strftime('%Y-%m-%d')
                else:
                    last_updated = "Never"
            except Exception:
                last_updated = "Unknown"
            
            # Отримуємо поточну модель
            current_model = None
            try:
                # AI модель
                if hasattr(client, 'features') and client.features and isinstance(client.features, dict):
                    ai_model = client.features.get('ai_model')
                    if ai_model:
                        current_model = {
                            'id': ai_model.get('id'),
                            'name': ai_model.get('name'),
                            'type': 'ai'
                        }
                
                # Embedding модель
                if not current_model and hasattr(client, 'embedding_model') and client.embedding_model:
                    current_model = {
                        'id': client.embedding_model.id,
                        'name': client.embedding_model.name,
                        'type': 'embedding'
                    }
            except Exception:
                pass
            
            return Response({
                'status': model_status,
                'error': model_error,
                'last_updated': last_updated,
                'has_embeddings': has_embeddings,
                'has_documents': has_documents,
                'knowledge_blocks_count': knowledge_blocks_count,
                'current_model': current_model,
                'data_sources': client.documents.filter(is_processed=True).count() if hasattr(client, 'documents') else 0,
            })
            
        except Exception as e:
            return Response({
                'status': 'Error',
                'error': str(e),
                'last_updated': 'Unknown',
                'has_embeddings': False,
                'has_documents': False,
                'knowledge_blocks_count': 0,
                'current_model': None,
                'data_sources': 0,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.decorators import api_view, permission_classes


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_api_key_for_client(request, client_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    client = get_object_or_404(Client, id=client_id)
    data = request.data
    
    api_key = ClientAPIKey.objects.create(
        client=client,
        name=data.get('name', 'API Key'),
        rate_limit_per_minute=data.get('rate_limit_per_minute', 60),
        rate_limit_per_day=data.get('rate_limit_per_day', 10000)
    )
    
    return Response({
        'key': api_key.key,
        'name': api_key.name,
        'is_active': api_key.is_active,
        'rate_limit_per_minute': api_key.rate_limit_per_minute,
        'rate_limit_per_day': api_key.rate_limit_per_day,
        'created_at': api_key.created_at.isoformat()
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_stats(request, client_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    client = get_object_or_404(Client, id=client_id)
    api_keys = ClientAPIKey.objects.filter(client=client)
    
    total_usage = sum(key.usage_count for key in api_keys)
    
    return Response({
        'client_id': client.id,
        'company_name': client.company_name,
        'client_type': client.client_type,
        'is_active': client.is_active,
        'specialization': {
            'id': client.specialization.id,
            'name': client.specialization.name,
            'branch_name': client.specialization.branch.name
        } if client.specialization else None,
        'total_usage': total_usage,
        'api_keys': [
            {
                'key_preview': f"{key.key[:15]}...{key.key[-8:]}",
                'name': key.name,
                'is_active': key.is_active,
                'usage_count': key.usage_count,
                'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                'created_at': key.created_at.isoformat()
            }
            for key in api_keys
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_clients_extended(request):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    queryset = Client.objects.select_related('specialization', 'specialization__branch', 'user').all()
    
    branch_id = request.query_params.get('branch_id')
    specialization_id = request.query_params.get('specialization_id')
    client_type = request.query_params.get('client_type')
    
    if branch_id:
        queryset = queryset.filter(specialization__branch_id=branch_id)
    if specialization_id:
        queryset = queryset.filter(specialization_id=specialization_id)
    if client_type:
        queryset = queryset.filter(client_type=client_type)
    
    results = []
    for client in queryset[:100]:
        api_keys_count = getattr(client, 'api_keys', ClientAPIKey.objects.none()).filter(is_active=True).count()
        results.append({
            'id': client.id,
            'company_name': client.company_name,
            'client_type': client.client_type,
            'is_active': client.is_active,
            'username': client.user if client.user else None,  # client.user is CharField
            'specialization': {
                'id': client.specialization.id,
                'name': client.specialization.name,
                'branch_id': client.specialization.branch_id,
                'branch_name': client.specialization.branch.name
            } if client.specialization else None,
            'api_keys_count': api_keys_count,
            'created_at': client.created_at.isoformat()
        })
    
    return Response({'results': results})


class WebParsingRequestViewSet(viewsets.ModelViewSet):
    """API for web parsing requests"""
    serializer_class = WebParsingRequestSerializer
    permission_classes = []  # Allow access without JWT, check in methods
    
    def get_client_from_request_or_api_key(self):
        """Get client from JWT or API key"""
        client = get_client_from_request(self.request)
        
        if not client and 'HTTP_X_API_KEY' in self.request.META:
            api_key = self.request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass
        
        return client
    
    def get_queryset(self):
        """Return only requests for current client"""
        client = self.get_client_from_request_or_api_key()
        if not client:
            return WebParsingRequest.objects.none()
        return WebParsingRequest.objects.filter(client=client).order_by('-created_at')
    
    def perform_create(self, serializer):
        """Automatically set client from request"""
        client = self.get_client_from_request_or_api_key()
        if not client:
            raise serializers.ValidationError("Client not found")
        serializer.save(client=client)
