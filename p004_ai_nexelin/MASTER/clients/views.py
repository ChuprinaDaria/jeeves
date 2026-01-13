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
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import JSONRenderer
from django.db.models import Q
from urllib.parse import urlparse
import logging
import hashlib
import re
from collections import defaultdict

logger = logging.getLogger(__name__)
from MASTER.clients.models import (
    Client,
    ClientDocument,
    ClientAPIKey,
    ClientAPIConfig,
    KnowledgeBlock,
    ClientQRCode,
    ClientWhatsAppConversation,
    WebParsingRequest,
    Prompt,
    PromptVote,
    News,
    ClientEmbedding,
    ExtensionPage,
    ExtensionEntity,
)
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
    ClientCustomPromptSerializer,
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


# --- Helpers for extension semantic analysis ---

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE_RE = re.compile(r'\+?\d[\d\s\-\(\)]{7,}\d')
ADDRESS_HINT_WORDS = [
    'street',
    'st.',
    'str.',
    'road',
    'rd',
    'avenue',
    'ave',
    'boulevard',
    'blvd',
    'площа',
    'проспект',
    'пр.',
    'вул.',
    'улица',
    'ул.',
]


def _extract_entities_from_text(text: str) -> dict:
    """Extract emails, phones, and address-like lines from raw text."""
    if not text:
        return {'emails': [], 'phones': [], 'addresses': []}

    emails = set(EMAIL_RE.findall(text))

    phones = set()
    for match in PHONE_RE.findall(text):
        # Remove all non-digit characters to count digits
        digits_only = re.sub(r'\D', '', match)
        digit_count = len(digits_only)
        
        # Filter out invalid phone numbers:
        # - Too short (less than 7 digits) - not a valid phone
        # - Too long (more than 15 digits) - likely IBAN, credit card, or other ID
        # - Exactly 16 digits - likely IBAN or credit card
        # - More than 12 digits without country code indicator - suspicious
        if digit_count < 7 or digit_count > 15:
            continue
        
        # Filter out numbers that look like IBANs, credit cards, or IDs
        # (usually 10+ digits without proper phone formatting)
        has_formatting = bool(re.search(r'[\s\-\(\)]', match))
        
        # If it's 10+ digits and doesn't have proper phone formatting (spaces, dashes, parentheses),
        # it's likely not a phone number (could be ID, account number, etc.)
        if digit_count >= 10 and not has_formatting:
            continue
        
        # Filter out numbers that are too long without country code
        # If it starts with +, it can be longer, but still max 15 digits
        if not match.startswith('+') and digit_count > 12:
            continue
        
        normalized = ' '.join(match.split())
        phones.add(normalized)

    addresses = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if any(hint in lower for hint in ADDRESS_HINT_WORDS):
            addresses.add(line)

    return {
        'emails': sorted(emails),
        'phones': sorted(phones),
        'addresses': sorted(addresses),
    }


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
    
    def create(self, request, *args, **kwargs):
        """
        Перевизначений create для підтримки Package API формату від mg.nexelin.
        Якщо payload містить поле 'action' - це Package API, інакше - стандартний формат.
        """
        data = request.data or {}
        
        # Перевірка чи це Package API формат (має поле 'action')
        if 'action' in data and data.get('action') in ['create', 'clone', 'update']:
            # Це Package API формат - делегуємо обробку PackageReceiveView
            from MASTER.api.views import PackageReceiveView
            package_view = PackageReceiveView()
            return package_view.post(request)
        
        # Стандартний формат створення клієнта
        return super().create(request, *args, **kwargs)
    
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
        """Повертає тільки активні блоки поточного клієнта."""
        client = self.get_client_from_request_or_api_key()
        if not client:
            return KnowledgeBlock.objects.none()
        return KnowledgeBlock.objects.filter(client=client, is_active=True)
    
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
        # Показуємо публічні промпти + власні промпти користувача
        if self.request.user and self.request.user.is_authenticated:
            queryset = Prompt.objects.filter(
                Q(is_public=True) | Q(created_by=self.request.user)
            )
        else:
            queryset = Prompt.objects.filter(is_public=True)
        
        # Фільтри
        category = self.request.query_params.get('category')
        industry = self.request.query_params.get('industry')
        search = self.request.query_params.get('search')
        my_prompts = self.request.query_params.get('my', '').lower() == 'true'
        
        # Фільтр "my" - показуємо тільки свої промпти
        if my_prompts and self.request.user and self.request.user.is_authenticated:
            queryset = queryset.filter(created_by=self.request.user)
        
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
        
        # Сортування: featured спочатку, потім за оцінками (likes_count), потім за датою
        return queryset.order_by('-is_featured', '-likes_count', '-created_at')
    
    def perform_create(self, serializer):
        """Автоматично встановлює created_by при створенні"""
        if self.request.user and self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()
    
    def perform_destroy(self, instance):
        """Дозволяє видаляти тільки свої промпти"""
        # Staff/superuser може видаляти будь-які промпти
        if self.request.user and self.request.user.is_authenticated:
            if self.request.user.is_staff or self.request.user.is_superuser:
                instance.delete()
                return
        
        # Перевіряємо, чи користувач є автором промпту
        if instance.created_by and self.request.user and self.request.user.is_authenticated:
            if instance.created_by == self.request.user:
                instance.delete()
                return
        
        # Якщо промпт без автора (created_by=None) - дозволяємо видалення тільки staff
        if not instance.created_by:
            if self.request.user and self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser):
                instance.delete()
                return
        
        # Якщо не пройшов перевірку - забороняємо
        raise PermissionDenied("Ви можете видаляти тільки свої власні промпти")
    
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
            # Для автентифікованих користувачів використовуємо user.id
            user_identifier = str(request.user.id)
            user = request.user
        else:
            # Для анонімних користувачів використовуємо комбінацію IP + User-Agent для унікальності
            # Це дозволяє різним користувачам з одного IP голосувати окремо
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR', 'unknown')
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')[:50]  # Обмежуємо довжину
            # Створюємо унікальний ідентифікатор для анонімного користувача
            unique_string = f"{ip_address}:{user_agent}"
            user_identifier = hashlib.md5(unique_string.encode()).hexdigest()
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


class ClientCustomPromptViewSet(viewsets.ModelViewSet):
    """Custom prompts management for clients"""
    serializer_class = ClientCustomPromptSerializer
    permission_classes = []
    
    def get_queryset(self):
        """Return custom prompts for the current client"""
        client = get_client_from_request(self.request)
        if not client:
            return ClientCustomPrompt.objects.none()
        return ClientCustomPrompt.objects.filter(client=client)
    
    def perform_create(self, serializer):
        """Set client automatically"""
        client = get_client_from_request(self.request)
        if not client:
            raise PermissionDenied("Client not found")
        serializer.save(client=client)
    
    def perform_update(self, serializer):
        """Ensure client can only update their own prompts"""
        instance = serializer.instance
        client = get_client_from_request(self.request)
        
        if not client:
            raise PermissionDenied("Client not found")
        
        if instance.client != client:
            raise PermissionDenied("You can only update your own prompts")
        
        # Ensure source_prompt is not changed (it's read-only)
        if 'source_prompt' in serializer.validated_data:
            if serializer.validated_data['source_prompt'] != instance.source_prompt:
                raise PermissionDenied("Cannot change source_prompt. This is a read-only field.")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Ensure client can only delete their own prompts"""
        client = get_client_from_request(self.request)
        
        if not client:
            raise PermissionDenied("Client not found")
        
        if instance.client != client:
            raise PermissionDenied("You can only delete your own prompts")
        
        # If this was the active prompt, clear it from client
        if client.active_custom_prompt == instance:
            client.active_custom_prompt = None
            client.save(update_fields=['active_custom_prompt'])
        
        # Delete only the ClientCustomPrompt, NOT the source Prompt from Prompt Book
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a custom prompt"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        custom_prompt = self.get_object()
        if custom_prompt.client != client:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Deactivate all other prompts
        ClientCustomPrompt.objects.filter(client=client).update(is_active=False)
        
        # Activate this prompt
        custom_prompt.is_active = True
        custom_prompt.save()
        
        # Update client's active_custom_prompt
        client.active_custom_prompt = custom_prompt
        client.save(update_fields=['active_custom_prompt'])
        
        return Response({
            'success': True,
            'message': f'Prompt "{custom_prompt.title}" activated',
            'prompt': ClientCustomPromptSerializer(custom_prompt).data
        })
    
    @action(detail=False, methods=['post'], url_path='add-from-library/(?P<prompt_id>[^/.]+)', url_name='add-from-library')
    def add_from_library(self, request, prompt_id=None):
        """Add a prompt from Prompt Book to client's custom prompts"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get prompt_id from URL or request data
        prompt_id = prompt_id or request.data.get('prompt_id')
        if not prompt_id:
            return Response(
                {'error': 'prompt_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            prompt_id = int(prompt_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid prompt_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            source_prompt = Prompt.objects.get(id=prompt_id, is_public=True)
        except Prompt.DoesNotExist:
            return Response(
                {'error': 'Prompt not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already exists
        existing = ClientCustomPrompt.objects.filter(
            client=client,
            source_prompt=source_prompt
        ).first()
        
        if existing:
            # Update existing LOCAL copy (not the original Prompt Book prompt)
            # This updates only the client's copy, not the global Prompt Book entry
            existing.prompt_text = source_prompt.prompt_template
            existing.title = source_prompt.title
            existing.description = source_prompt.description
            existing.save()
            
            return Response({
                'success': True,
                'message': 'Your local prompt copy updated from library (original Prompt Book entry unchanged)',
                'prompt': ClientCustomPromptSerializer(existing).data
            })
        
        # Create new LOCAL copy of the prompt
        # This creates a ClientCustomPrompt instance that references the source_prompt
        # but stores its own copy of the text. Editing this will NOT affect the original Prompt Book entry.
        custom_prompt = ClientCustomPrompt.objects.create(
            client=client,
            source_prompt=source_prompt,  # Reference to original (read-only)
            title=source_prompt.title,  # Copy of title
            prompt_text=source_prompt.prompt_template,  # Copy of prompt text
            description=source_prompt.description,  # Copy of description
            is_active=False,
            order=0
        )
        
        return Response({
            'success': True,
            'message': 'Prompt added from library',
            'prompt': ClientCustomPromptSerializer(custom_prompt).data
        }, status=status.HTTP_201_CREATED)


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
            # Для автентифікованих користувачів використовуємо user.id
            user_identifier = str(request.user.id)
            user = request.user
        else:
            # Для анонімних користувачів використовуємо комбінацію IP + User-Agent для унікальності
            # Це дозволяє різним користувачам з одного IP голосувати окремо
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR', 'unknown')
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')[:50]  # Обмежуємо довжину
            # Створюємо унікальний ідентифікатор для анонімного користувача
            unique_string = f"{ip_address}:{user_agent}"
            user_identifier = hashlib.md5(unique_string.encode()).hexdigest()
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
    
    def get_serializer_context(self):
        """Add request to serializer context for language detection"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class TopPromptsView(APIView):
    """Get top 5 prompts by client ratings (daily)"""
    permission_classes = [AllowAny]  # Public access
    
    def get(self, request):
        """Return top 5 prompts by like ratio and total votes"""
        from django.utils import timezone
        from django.db.models import F, Case, When, FloatField
        
        # Отримуємо промпти з мінімальною кількістю голосів (наприклад, 1+)
        # Якщо немає достатньої кількості голосів, показуємо просто найпопулярніші за лайками
        min_votes = 1
        base_qs = Prompt.objects.filter(
            is_public=True,
            likes_count__gte=0
        ).annotate(
            total_votes=F('likes_count') + F('dislikes_count'),
            like_ratio=Case(
                When(total_votes__gt=0, then=F('likes_count') * 1.0 / (F('likes_count') + F('dislikes_count'))),
                default=0.0,
                output_field=FloatField()
            )
        )

        # Спочатку пробуємо взяти промпти з достатньою кількістю голосів
        top_prompts = base_qs.filter(
            total_votes__gte=min_votes
        ).order_by(
            '-like_ratio',  # Спочатку за співвідношенням лайків
            '-likes_count',  # Потім за кількістю лайків
            '-total_votes',  # І нарешті за загальною кількістю голосів
            '-created_at',
        )[:5]

        # Якщо після фільтрації нічого немає, просто беремо топ-5 за лайками
        if not top_prompts:
            top_prompts = base_qs.order_by(
                '-likes_count',
                '-total_votes',
                '-created_at',
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
        """Override list to ensure it's available and update web QR codes location"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            response = super().list(request, *args, **kwargs)
            
            # Оновлюємо location для web QR кодів, щоб використовувати актуальний webchat_domain
            if response.status_code == 200 and response.data:
                client = self.get_client_from_request_or_api_key()
                if client:
                    # response.data може бути ReturnList (список) або OrderedDict (словник з пагінацією)
                    if isinstance(response.data, list):
                        qr_list = response.data
                    elif hasattr(response.data, 'get'):
                        qr_list = response.data.get('results', [])
                    else:
                        qr_list = []
                    
                    for qr_data in qr_list:
                        if isinstance(qr_data, dict) and qr_data.get('integration_type') == 'web':
                            try:
                                qr_code = ClientQRCode.objects.get(id=qr_data.get('id'))
                                new_link = qr_code.get_web_chat_link()
                                if qr_code.location != new_link:
                                    qr_code.location = new_link
                                    qr_code.save(update_fields=['location'])
                                    # Оновлюємо дані в відповіді
                                    qr_data['location'] = new_link
                            except (ClientQRCode.DoesNotExist, ValueError) as e:
                                logger.warning(f"Error updating web QR code {qr_data.get('id')}: {e}")
                            except Exception as e:
                                logger.error(f"Unexpected error updating web QR code {qr_data.get('id')}: {e}", exc_info=True)
            
            return response
        except Exception as e:
            logger.error(f"Error in ClientQRCodeViewSet.list(): {e}", exc_info=True)
            from rest_framework.response import Response
            return Response({'error': str(e)}, status=500)
    
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
        
        # Для web integration, встановлюємо location якщо не встановлено
        if qr_code.integration_type == 'web' and not qr_code.location:
            web_chat_link = qr_code.get_web_chat_link()
            qr_code.location = web_chat_link
            logger.info(f"Set location for web QR code {qr_code.id}: {web_chat_link[:50]}...")
            qr_code.save(update_fields=['location'])
        
        # Генеруємо QR код якщо не згенеровано
        if not qr_code.qr_code and not qr_code.qr_code_url:
            try:
                logger.info(f"Generating QR code image for QRCode {qr_code.id}, type: {qr_code.integration_type}")
                qr_code.generate_qr_code()
                qr_code.save(update_fields=['qr_code', 'qr_code_url', 'location'])
                logger.info(f"QR code image generated successfully for QRCode {qr_code.id}")
            except Exception as e:
                # Логуємо помилку з повним traceback
                logger.error(f"Failed to generate QR code for QRCode {qr_code.id}: {str(e)}", exc_info=True)
                # Не блокуємо створення, але повідомляємо про помилку
    
    def perform_update(self, serializer):
        """Оновлює QR код та регенерує його якщо потрібно."""
        instance = self.get_object()
        serializer.save()
        
        # Для web integration завжди оновлюємо location з актуальним webchat_domain
        if instance.integration_type == 'web':
            web_chat_link = instance.get_web_chat_link()
            if instance.location != web_chat_link:
                instance.location = web_chat_link
                instance.save(update_fields=['location'])
        
        # Регенеруємо QR код якщо змінили назву, локацію або для web integration (щоб використовувати актуальний домен)
        if 'name' in serializer.validated_data or 'location' in serializer.validated_data or instance.integration_type == 'web':
            try:
                instance.generate_qr_code()
                instance.save(update_fields=['qr_code', 'qr_code_url', 'location'])
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
# prompts та news зареєстровані явно в urls.py, щоб уникнути конфліктів


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
                # Формуємо webhook URL з унікальним tag клієнта
                base_url = getattr(settings, 'TELEGRAM_WEBHOOK_BASE_URL', request.build_absolute_uri('/').rstrip('/'))
                
                # Використовуємо client.tag для унікальної ідентифікації клієнта в webhook URL
                client_tag = client.tag if hasattr(client, 'tag') and client.tag else f"client-{client.id}"
                webhook_url = f"{base_url}/api/clients/telegram/webhook/?tag={client_tag}"
                
                # Використовуємо client.tag як secret_token для безпеки
                secret_token = client.tag if hasattr(client, 'tag') and client.tag else None
                
                if set_telegram_webhook(client.telegram_bot_token, webhook_url, secret_token=secret_token):
                    client.telegram_webhook_url = webhook_url
                    changed.append('telegram_webhook_url')
                else:
                    return Response({'error': 'Failed to set Telegram webhook'}, status=500)
        
        client.save(update_fields=changed)
        
        # Новіни про інтеграції створюються тільки через адмін-панель, не автоматично
        
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
            'email_report_enabled': getattr(client, 'email_report_enabled', False),
            'email_report_recipients': getattr(client, 'email_report_recipients', []),
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
            'email_report_enabled',
            'email_report_recipients',
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
                
                # Новіни про інтеграції створюються тільки через адмін-панель, не автоматично
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


class ClientExtensionPageView(APIView):
    """
    API endpoint for Google Chrome extension.

    POST /api/clients/extension/page/
    Headers:
        X-Client-Token: <client_tag or API key>

    Body (JSON):
        {
            "url": "...",
            "title": "...",
            "headings": [...],
            "lists": [...],
            "tables": [...],
            "quotes": [...],
            "full_text": "...",
            "mode": "scrap" | "collect" | "both"
        }
    """

    permission_classes = []  # Публічний, ідентифікація через tag / X-Client-Token / X-API-Key

    def post(self, request):
        # Force JSON response for Chrome Extension
        request.accepted_renderer = request.accepted_renderer or JSONRenderer()
        
        try:
            client = get_client_from_request(request)
            if not client:
                return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Error in ClientExtensionPageView.get_client_from_request: {e}", exc_info=True)
            return Response({'error': 'Failed to authenticate client'}, status=status.HTTP_401_UNAUTHORIZED)

        if not getattr(client, 'extension_enabled', False):
            return Response(
                {'error': 'Extension is not enabled for this client'},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data or {}
        url = data.get('url') or ''
        if not url:
            return Response({'error': 'url is required'}, status=status.HTTP_400_BAD_REQUEST)

        title = data.get('title') or ''
        headings = data.get('headings') or []
        lists_data = data.get('lists') or []
        tables = data.get('tables') or []
        quotes = data.get('quotes') or []
        full_text = data.get('full_text') or ''

        mode = (data.get('mode') or 'both').lower()
        if mode not in ('scrap', 'collect', 'both'):
            mode = 'both'

        parsed = urlparse(url)
        raw_site_name = data.get('site_name') or parsed.netloc or ''
        site_name = raw_site_name.lower().lstrip('www.') or 'unknown'

        # Create/get per-site knowledge block (named by site name)
        kb_name = site_name
        knowledge_block, _ = KnowledgeBlock.objects.get_or_create(
            client=client,
            name=kb_name,
            defaults={
                'description': f'Content from {site_name} collected via browser extension',
                'is_active': True,
                'is_permanent': False,
            },
        )

        page = ExtensionPage.objects.create(
            client=client,
            url=url,
            site_name=site_name,
            title=title,
            headings=headings,
            lists=lists_data,
            tables=tables,
            quotes=quotes,
            full_text=full_text,
            knowledge_block=knowledge_block,
        )

        entities_payload = {'emails': [], 'phones': [], 'addresses': []}

        # Create a text document for this page so it appears in Knowledge Blocks
        if mode in ('scrap', 'both') and full_text:
            try:
                from MASTER.clients.models import ClientDocument
                from django.core.files.base import ContentFile
                import io
                
                # Create a text file with the page content
                text_content = f"Title: {title}\nURL: {url}\n\n"
                
                # Add structured content
                if headings:
                    text_content += "\n## Headings\n"
                    for h in headings[:20]:  # Limit to first 20 headings
                        text_content += f"{h.get('level', 'h')}: {h.get('text', '')}\n"
                
                if lists_data:
                    text_content += "\n## Lists\n"
                    for lst in lists_data[:10]:  # Limit to first 10 lists
                        items = lst.get('items', [])[:10]  # First 10 items per list
                        text_content += f"{lst.get('type', 'ul')}: " + ", ".join(items) + "\n"
                
                if quotes:
                    text_content += "\n## Quotes\n"
                    for q in quotes[:10]:  # First 10 quotes
                        text_content += f"- {q}\n"
                
                # Add full text (truncated if too long)
                if full_text:
                    text_content += f"\n## Full Text\n{full_text[:50000]}"  # Limit to 50k chars
                
                # Create document
                document = ClientDocument.objects.create(
                    client=client,
                    knowledge_block=knowledge_block,
                    title=f"{title[:200]} - {site_name}" if title else f"Page from {site_name}",
                    file_type='txt',
                    file=ContentFile(text_content.encode('utf-8'), name=f"extension_page_{page.id}.txt"),
                    metadata={
                        'source': 'extension',
                        'site_name': site_name,
                        'url': url,
                        'extension_page_id': page.id,
                    },
                )
                logger.info(f"Created document {document.id} for extension page {page.id}")
                
                # Create embeddings for the document
                try:
                    from MASTER.EmbeddingModel.models import EmbeddingModel  # Local import to avoid circular deps

                    embedding_model = getattr(client, 'embedding_model', None)
                    if embedding_model is None:
                        embedding_model = EmbeddingModel.objects.filter(
                            is_default=True,
                            is_active=True,
                        ).first()

                    if embedding_model is not None:
                        ClientEmbedding.objects.create(
                            client=client,
                            document=document,  # Link embedding to document
                            embedding_model=embedding_model,
                            content=full_text,
                            metadata={
                                'source': 'extension',
                                'site_name': site_name,
                                'url': url,
                                'extension_page_id': page.id,
                            },
                        )
                except Exception as e:
                    logger.warning(f"Failed to create embedding for extension document {document.id}: {e}", exc_info=True)
                    
            except Exception as e:
                logger.warning(f"Failed to create document for extension page {page.id}: {e}", exc_info=True)
                # Fallback: create embeddings even if document creation failed
                if mode in ('scrap', 'both') and full_text:
                    try:
                        from MASTER.EmbeddingModel.models import EmbeddingModel
                        embedding_model = getattr(client, 'embedding_model', None)
                        if embedding_model is None:
                            embedding_model = EmbeddingModel.objects.filter(
                                is_default=True,
                                is_active=True,
                            ).first()
                        if embedding_model is not None:
                            ClientEmbedding.objects.create(
                                client=client,
                                document=None,
                                embedding_model=embedding_model,
                                content=full_text,
                                metadata={
                                    'source': 'extension',
                                    'site_name': site_name,
                                    'url': url,
                                    'extension_page_id': page.id,
                                },
                            )
                    except Exception as e2:
                        logger.warning(f"Failed to create fallback embedding for extension page {page.id}: {e2}", exc_info=True)

        # Semantic extraction of entities (emails/phones/addresses)
        if mode in ('collect', 'both') and full_text:
            try:
                entities = _extract_entities_from_text(full_text)
                emails = entities.get('emails') or []
                phones = entities.get('phones') or []
                addresses = entities.get('addresses') or []

                entities_payload = {
                    'emails': emails,
                    'phones': phones,
                    'addresses': addresses,
                }

                # Save only if we actually found something
                if emails or phones or addresses:
                    ExtensionEntity.objects.create(
                        client=client,
                        page=page,
                        site_name=site_name,
                        url=url,
                        emails=emails,
                        phones=phones,
                        addresses=addresses,
                    )
            except Exception as e:
                logger.warning(f"Failed to extract entities for extension page {page.id}: {e}", exc_info=True)

        try:
            return Response(
                {
                    'success': True,
                    'page_id': page.id,
                    'site_name': site_name,
                    'knowledge_block_id': knowledge_block.id if knowledge_block else None,
                    'entities': entities_payload,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.error(f"Error in ClientExtensionPageView.post: {e}", exc_info=True)
            return Response(
                {'error': f'Internal server error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClientExtensionDataView(APIView):
    """
    Aggregated semantic data from extension (emails/phones/addresses grouped by site).

    GET /api/clients/extension/data/
    """

    permission_classes = []  # Публічний, ідентифікація через tag / X-Client-Token / X-API-Key

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        if not getattr(client, 'extension_enabled', False):
            return Response(
                {
                    'enabled': False,
                    'sites': [],
                },
                status=status.HTTP_200_OK,
            )

        qs = ExtensionEntity.objects.filter(client=client)
        if not qs.exists():
            return Response(
                {
                    'enabled': True,
                    'sites': [],
                },
                status=status.HTTP_200_OK,
            )

        sites = {}
        for row in qs:
            key = row.site_name or 'unknown'
            if key not in sites:
                sites[key] = {
                    'site': key,
                    '_urls': set(),
                    '_emails': set(),
                    '_phones': set(),
                    '_addresses': set(),
                    'last_seen': row.created_at,
                }
            info = sites[key]
            if row.url:
                info['_urls'].add(row.url)

            for val in row.emails or []:
                info['_emails'].add(val)
            for val in row.phones or []:
                info['_phones'].add(val)
            for val in row.addresses or []:
                info['_addresses'].add(val)

            if row.created_at and row.created_at > info['last_seen']:
                info['last_seen'] = row.created_at

        result = []
        for _, info in sites.items():
            result.append(
                {
                    'site': info['site'],
                    'pages_count': len(info['_urls']),
                    'urls': sorted(info['_urls']),
                    'emails': sorted(info['_emails']),
                    'phones': sorted(info['_phones']),
                    'addresses': sorted(info['_addresses']),
                    'last_seen': info['last_seen'].isoformat() if info['last_seen'] else None,
                }
            )

        # Sort sites by most recently updated
        result.sort(key=lambda x: x['last_seen'] or '', reverse=True)

        return Response(
            {
                'enabled': True,
                'sites': result,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        """
        PATCH /api/clients/extension/data/

        Body:
        {
            "site": "lazysoft.pl",
            "emails": [...],
            "phones": [...],
            "addresses": [...]
        }

        Оновлює зібрані сутності для конкретного сайту (ручне очищення / редагування на фронті).
        """
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        if not getattr(client, 'extension_enabled', False):
            return Response({'error': 'Extension is not enabled for this client'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data or {}
        site = (data.get('site') or '').strip().lower()
        if not site:
            return Response({'error': 'site is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize lists
        def _normalize_list(value):
            if value is None:
                return []
            if isinstance(value, str):
                items = [v.strip() for v in value.split('\n')]
            elif isinstance(value, list):
                items = [str(v).strip() for v in value]
            else:
                return []
            # Remove empties and duplicates while preserving order
            seen = set()
            result = []
            for item in items:
                if not item:
                    continue
                if item in seen:
                    continue
                seen.add(item)
                result.append(item)
            return result

        emails = _normalize_list(data.get('emails'))
        phones = _normalize_list(data.get('phones'))
        addresses = _normalize_list(data.get('addresses'))

        qs = ExtensionEntity.objects.filter(client=client, site_name=site)
        if not qs.exists():
            return Response({'error': 'No extension entities found for this site'}, status=status.HTTP_404_NOT_FOUND)

        # Зберігаємо всі відредаговані значення в першому записі, інші зачищаємо
        primary = qs.order_by('id').first()
        primary.emails = emails
        primary.phones = phones
        primary.addresses = addresses
        primary.save(update_fields=['emails', 'phones', 'addresses'])

        # Для всіх інших записів цього сайту очищаємо сутності, щоб не дублювати
        qs.exclude(id=primary.id).update(emails=[], phones=[], addresses=[])

        # Повертаємо оновлений агрегований список сайтів
        return self.get(request)

    def delete(self, request):
        """
        DELETE /api/clients/extension/data/

        Body:
        {
            "site": "lazysoft.pl"
        }

        Повністю видаляє дані розширення для конкретного сайту.
        """
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        if not getattr(client, 'extension_enabled', False):
            return Response({'error': 'Extension is not enabled for this client'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data or {}
        site = (data.get('site') or '').strip().lower()
        if not site:
            return Response({'error': 'site is required'}, status=status.HTTP_400_BAD_REQUEST)

        qs = ExtensionEntity.objects.filter(client=client, site_name=site)
        deleted_count = qs.count()
        if deleted_count == 0:
            return Response({'error': 'No extension entities found for this site'}, status=status.HTTP_404_NOT_FOUND)

        qs.delete()
        return Response({'success': True, 'deleted': deleted_count}, status=status.HTTP_200_OK)


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
        
        # Підрахунок по типах
        web_convs = 0
        telegram_convs = 0
        whatsapp_convs = 0
        web_widget_convs = 0
        
        for conv in conversations:
            platform = None
            if conv.context_metadata:
                platform = conv.context_metadata.get('platform')
            
            if platform == 'telegram' or (conv.customer_phone and conv.customer_phone.startswith('telegram_')):
                telegram_convs += 1
            elif platform == 'web_widget' or platform == 'iframe' or platform == 'widget':
                web_widget_convs += 1
            elif platform == 'web' or (conv.customer_phone and conv.customer_phone.startswith('web_')):
                web_convs += 1
            else:
                whatsapp_convs += 1
        
        logger.info(f"📊 Conversations by type: Web={web_convs}, Telegram={telegram_convs}, WhatsApp={whatsapp_convs}, WebWidget={web_widget_convs}")
        
        # Також отримуємо RestaurantConversation для backward compatibility
        from MASTER.restaurant.models import RestaurantConversation
        restaurant_conversations = RestaurantConversation.objects.filter(client=client).order_by('-started_at')
        
        # Формуємо список розмов
        conversations_list = []
        
        # Додаємо ClientWhatsAppConversation
        for conv in conversations:
            # Автоматично оновлюємо context_metadata для старих conversations
            needs_update = False
            if not conv.context_metadata:
                conv.context_metadata = {}
                needs_update = True
            
            # Визначаємо source на основі context_metadata та customer_phone
            source = 'whatsapp'
            platform = conv.context_metadata.get('platform') if conv.context_metadata else None
            
            # Визначаємо source на основі platform або customer_phone prefix
            if platform == 'telegram' or (conv.customer_phone and conv.customer_phone.startswith('telegram_')):
                source = 'telegram'
                if platform != 'telegram':
                    conv.context_metadata['platform'] = 'telegram'
                    needs_update = True
            elif platform == 'web_widget' or platform == 'iframe' or platform == 'widget':
                source = 'web_widget'
                if platform not in ['web_widget', 'iframe', 'widget']:
                    conv.context_metadata['platform'] = 'web_widget'
                    needs_update = True
            elif platform == 'web' or (conv.customer_phone and conv.customer_phone.startswith('web_')):
                source = 'web'
                if platform != 'web':
                    conv.context_metadata['platform'] = 'web'
                    needs_update = True
            
            # Оновлюємо context_metadata якщо потрібно
            if needs_update:
                conv.save(update_fields=['context_metadata', 'updated_at'])
            
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
            
            # Форматуємо номер телефону як ім'я
            if source == 'web':
                customer_name = 'Web Chat'
            elif source == 'telegram':
                customer_name = 'Telegram'
            elif source == 'web_widget':
                customer_name = 'Web Widget'
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
                'source': source,
                'notes': conversation.notes or '',
                'user_rating': conversation.user_rating,
                'ai_rating': conversation.ai_rating,
                'summary': conversation.summary or ''
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
        
        now = timezone.now()
        conversation, created = ClientWhatsAppConversation.objects.get_or_create(
            session_id=session_id,
            client=client,
            is_active=True,
            defaults={
                'customer_phone': short_phone,
                'started_at': now,
                'messages': [],
                'context_metadata': {'platform': platform},
                'last_activity_at': now,
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
        
        now = timezone.now()
        conversation.messages.append({
            'role': 'user',
            'content': message,
            'timestamp': now.isoformat()
        })
        
        conversation.messages.append({
            'role': 'assistant',
            'content': response_text,
            'timestamp': now.isoformat()
        })
        
        conversation.total_messages = len(conversation.messages)
        conversation.last_activity_at = now
        conversation.save(update_fields=['messages', 'total_messages', 'updated_at', 'last_activity_at'])
        
        return Response({
            'success': True,
            'conversation_id': conversation.id,
            'total_messages': conversation.total_messages
        })


class ConversationRatingView(APIView):
    """
    API endpoint for rating conversations (thumbs up/down)
    POST /api/clients/conversations/{conversation_id}/rate/
    Body: { "rating": "positive" | "negative" }
    """
    permission_classes = []
    
    def post(self, request, conversation_id):
        from django.utils import timezone
        from MASTER.clients.models import ClientWhatsAppConversation
        
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            conversation = ClientWhatsAppConversation.objects.get(
                id=conversation_id,
                client=client
            )
        except ClientWhatsAppConversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        rating = request.data.get('rating', '').lower()
        if rating not in ['positive', 'negative']:
            return Response(
                {'error': 'Rating must be "positive" or "negative"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update rating
        conversation.user_rating = rating
        conversation.rating_timestamp = timezone.now()
        conversation.save(update_fields=['user_rating', 'rating_timestamp'])
        
        return Response({
            'success': True,
            'conversation_id': conversation.id,
            'rating': rating,
            'message': 'Rating saved successfully'
        })


class ConversationStatisticsView(APIView):
    """
    API endpoint for getting conversation statistics
    GET /api/clients/conversations/statistics/
    Query params: ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """
    permission_classes = []
    
    def get(self, request):
        from django.utils import timezone
        from datetime import datetime, timedelta
        from django.db.models import Count, Q, Avg
        from MASTER.clients.models import ClientWhatsAppConversation
        
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse date range
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        try:
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str).date()
            else:
                start_date = (timezone.now() - timedelta(days=30)).date()
            
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str).date()
            else:
                end_date = timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Filter conversations
        conversations = ClientWhatsAppConversation.objects.filter(
            client=client,
            started_at__date__gte=start_date,
            started_at__date__lte=end_date
        )
        
        # Calculate statistics
        total_conversations = conversations.count()
        active_conversations = conversations.filter(is_active=True).count()
        closed_conversations = total_conversations - active_conversations
        
        # Ratings
        positive_ratings = conversations.filter(
            Q(user_rating='positive') | Q(ai_rating='positive')
        ).count()
        negative_ratings = conversations.filter(
            Q(user_rating='negative') | Q(ai_rating='negative')
        ).count()
        unrated = conversations.filter(
            user_rating__isnull=True,
            ai_rating__isnull=True
        ).count()
        
        # Satisfaction rate
        total_rated = positive_ratings + negative_ratings
        satisfaction_rate = (positive_ratings / total_rated * 100) if total_rated > 0 else 0
        
        # Average messages per conversation
        avg_messages = conversations.aggregate(
            avg=Avg('total_messages')
        )['avg'] or 0
        
        # Email reports sent
        emails_sent = conversations.filter(email_sent=True).count()
        
        return Response({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'conversations': {
                'total': total_conversations,
                'active': active_conversations,
                'closed': closed_conversations
            },
            'ratings': {
                'positive': positive_ratings,
                'negative': negative_ratings,
                'unrated': unrated,
                'satisfaction_rate': round(satisfaction_rate, 2)
            },
            'average_messages_per_conversation': round(avg_messages, 2),
            'emails_sent': emails_sent
        })


class ManualReportView(APIView):
    """
    API endpoint for manual report generation (admin)
    POST /api/clients/conversations/{conversation_id}/generate-report/
    """
    permission_classes = []
    
    def post(self, request, conversation_id):
        from MASTER.clients.models import ClientWhatsAppConversation
        from MASTER.clients.tasks import generate_chat_summary, format_chat_as_text, send_chat_summary_email
        
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            conversation = ClientWhatsAppConversation.objects.get(
                id=conversation_id,
                client=client
            )
        except ClientWhatsAppConversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate summary if not exists
        if not conversation.summary:
            summary = generate_chat_summary(conversation)
            conversation.summary = summary
            conversation.save(update_fields=['summary'])
        
        # Format chat text
        chat_text = format_chat_as_text(conversation)
        
        # Send email if enabled
        email_result = None
        if conversation.client.email_report_enabled and conversation.client.email_report_recipients:
            email_result = send_chat_summary_email(conversation, chat_text)
        
        return Response({
            'success': True,
            'conversation_id': conversation.id,
            'summary': conversation.summary,
            'chat_text': chat_text,
            'email_sent': email_result.get('success', False) if email_result else False,
            'email_result': email_result
        })


class ConversationNotesView(APIView):
    """
    API endpoint for adding/updating notes for a conversation
    POST /api/clients/conversations/{conversation_id}/notes/
    Body: { "notes": "text" }
    """
    permission_classes = []
    
    def post(self, request, conversation_id):
        from MASTER.clients.models import ClientWhatsAppConversation
        
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            conversation = ClientWhatsAppConversation.objects.get(
                id=conversation_id,
                client=client
            )
        except ClientWhatsAppConversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        notes = request.data.get('notes', '')
        
        # Update notes
        conversation.notes = notes
        conversation.save(update_fields=['notes'])
        
        return Response({
            'success': True,
            'conversation_id': conversation.id,
            'notes': conversation.notes,
            'message': 'Notes saved successfully'
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
