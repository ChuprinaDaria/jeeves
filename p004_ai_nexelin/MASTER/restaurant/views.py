from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, F, FloatField
from django.db.models.functions import Cast
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import Any, cast
import base64
from django.http import HttpResponse
from django.conf import settings
import logging
import requests
import json
import secrets

from .models import (
    MenuCategory, Menu, MenuItem, MenuItemEmbedding, RestaurantTable,
    Order, OrderItem, RestaurantConversation
)
from .serializers import (
    MenuCategorySerializer, MenuSerializer, MenuItemSerializer, MenuItemCompactSerializer,
    RestaurantTableSerializer, OrderSerializer, OrderCreateSerializer,
    OrderStatusUpdateSerializer, RestaurantChatSerializer,
    RestaurantChatRequestSerializer, RestaurantChatResponseSerializer,
    MenuSearchSerializer, WebhookConfigSerializer
)
from MASTER.clients.models import Client, ClientAPIKey
from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
from MASTER.rag.vector_search import VectorSearchService
from MASTER.rag.llm_client import LLMClient
from pgvector.django import CosineDistance  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class RestaurantPermission(IsAuthenticated):
    """Custom permission for restaurant endpoints"""
    def has_permission(self, request, view):
        # Allow public access to menu and chat endpoints with valid API key
        action = getattr(view, 'action', None)
        if action in ['menu', 'menu_item', 'chat', 'create_order']:
            api_key = request.headers.get('X-API-Key')
            if api_key:
                try:
                    key_obj = ClientAPIKey.objects.get(key=api_key, is_active=True)
                    if key_obj.is_valid():
                        req_any = cast(Any, request)
                        req_any.client = key_obj.client
                        return True
                except ClientAPIKey.DoesNotExist:
                    pass
        
        # Otherwise require authentication
        return super().has_permission(request, view)
    
    def has_object_permission(self, request, view, obj):
        # Check if user has access to this client's data
        if hasattr(request, 'client'):
            return obj.client == request.client
        
        if bool(getattr(request.user, 'is_superuser', False)):
            return True
        
        if hasattr(obj, 'client'):
            return obj.client.user == request.user
        
        return False


class MenuCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = MenuCategorySerializer
    permission_classes = [RestaurantPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name']
    ordering = ['sort_order']
    
    def get_queryset(self):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            return MenuCategory.objects.none()
        
        return MenuCategory.objects.filter(
            client=client
        ).annotate(
            items_count=Count('items')
        )
    
    def perform_create(self, serializer):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            raise ValidationError('No client associated with this request')
        serializer.save(client=client)


class MenuViewSet(viewsets.ModelViewSet):
    serializer_class = MenuSerializer
    permission_classes = [RestaurantPermission]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ['name', 'description_text']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            return Menu.objects.none()
        return Menu.objects.filter(client=client)

    def perform_create(self, serializer):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            raise ValidationError('No client associated with this request')
        serializer.save(client=client)


class MenuItemViewSet(viewsets.ModelViewSet):
    serializer_class = MenuItemSerializer
    permission_classes = [RestaurantPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'ingredients']
    ordering_fields = ['sort_order', 'name', 'price']
    ordering = ['category', 'sort_order']
    
    def get_queryset(self):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            return MenuItem.objects.none()
        
        queryset = MenuItem.objects.filter(client=client)
        
        # Filter by menu and category if provided
        menu_id = self.request.query_params.get('menu')
        if menu_id:
            queryset = queryset.filter(menu_id=menu_id)
        # Filter by category if provided
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by dietary labels
        dietary = self.request.query_params.get('dietary')
        if dietary:
            queryset = queryset.filter(dietary_labels__contains=[dietary])
        
        # Filter by availability
        available_only = self.request.query_params.get('available', 'true').lower() == 'true'
        if available_only:
            queryset = queryset.filter(is_available=True)
        
        return queryset.select_related('category')

    def perform_create(self, serializer):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            raise PermissionDenied("Client not found")
    
        serializer.save(client=client)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MenuItemCompactSerializer
        return MenuItemSerializer
    
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """Semantic search for menu items"""
        serializer = MenuSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if hasattr(request, 'client'):
            client = request.client
        elif request.user.is_authenticated and hasattr(request.user, 'client_profile'):
            client = cast(Any, request.user).client_profile
        else:
            return Response(
                {'error': 'No client associated with this request'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        query = serializer.validated_data['query']
        language = serializer.validated_data.get('language', 'uk')
        
        # Start with base queryset
        queryset = MenuItem.objects.filter(
            client=client,
            is_available=True
        )
        
        # Apply filters
        if 'category_id' in serializer.validated_data:
            queryset = queryset.filter(category_id=serializer.validated_data['category_id'])
        
        if 'dietary_filters' in serializer.validated_data:
            for dietary in serializer.validated_data['dietary_filters']:
                queryset = queryset.filter(dietary_labels__contains=[dietary])
        
        if 'allergen_exclude' in serializer.validated_data:
            for allergen in serializer.validated_data['allergen_exclude']:
                queryset = queryset.exclude(allergens__contains=[allergen])
        
        if 'max_price' in serializer.validated_data:
            queryset = queryset.filter(price__lte=serializer.validated_data['max_price'])
        
        if 'min_calories' in serializer.validated_data:
            queryset = queryset.filter(calories__gte=serializer.validated_data['min_calories'])
        
        if 'max_calories' in serializer.validated_data:
            queryset = queryset.filter(calories__lte=serializer.validated_data['max_calories'])
        
        # Perform semantic search if we have embeddings
        # This would use the MenuItemEmbedding model
        # For now, fall back to text search
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(ingredients__icontains=query)
        )
        
        items = queryset[:20]  # Limit results
        serializer = MenuItemCompactSerializer(items, many=True)
        
        return Response({
            'query': query,
            'results': serializer.data,
            'count': len(serializer.data)
        })


class RestaurantTableViewSet(viewsets.ModelViewSet):
    serializer_class = RestaurantTableSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['table_number']
    ordering = ['table_number']
    
    def get_queryset(self):
        if self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            return RestaurantTable.objects.filter(
                client=cast(Any, self.request.user).client_profile
            )
        return RestaurantTable.objects.none()
    
    def perform_create(self, serializer):
        if self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            serializer.save(client=cast(Any, self.request.user).client_profile)
        else:
            raise ValidationError('No client associated with this request')
    
    @action(detail=True, methods=['post'])
    def regenerate_qr(self, request, pk=None):
        """Regenerate QR code for a table"""
        table = self.get_object()
        table.generate_qr_code()
        table.save()
        
        serializer = self.get_serializer(table)
        return Response(serializer.data)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [RestaurantPermission]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if hasattr(self.request, 'client'):
            client = self.request.client
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'client_profile'):
            client = cast(Any, self.request.user).client_profile
        else:
            return Order.objects.none()
        
        queryset = Order.objects.filter(client=client)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by table
        table_id = self.request.query_params.get('table')
        if table_id:
            queryset = queryset.filter(table_id=table_id)
        
        # Filter by date
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.select_related('table').prefetch_related('items__menu_item')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'update_status':
            return OrderStatusUpdateSerializer
        return OrderSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if hasattr(request, 'client'):
            client = request.client
        elif request.user.is_authenticated and hasattr(request.user, 'client_profile'):
            client = cast(Any, request.user).client_profile
        else:
            return Response(
                {'error': 'No client associated with this request'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.context['client'] = client
        order = serializer.save()
        
        # Send webhook if configured
        self._send_webhook(order, 'order_created')
        
        # Return full order details
        response_serializer = OrderSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status"""
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        
        # Send webhook if configured
        self._send_webhook(order, 'status_updated')
        
        response_serializer = OrderSerializer(order)
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_items(self, request, pk=None):
        """Add items to existing order"""
        order = self.get_object()
        
        if order.status not in [Order.STATUS_PENDING, Order.STATUS_CONFIRMED]:
            return Response(
                {'error': 'Cannot add items to order with this status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        items_data = request.data.get('items', [])
        for item_data in items_data:
            OrderItem.objects.create(
                order=order,
                menu_item_id=item_data['menu_item'],
                quantity=item_data.get('quantity', 1),
                notes=item_data.get('notes', ''),
                modifiers=item_data.get('modifiers', [])
            )
        
        order.calculate_total()
        
        # Send webhook if configured
        self._send_webhook(order, 'items_added')
        
        serializer = OrderSerializer(order)
        return Response(serializer.data)
    
    def _send_webhook(self, order, event_type):
        """Send webhook to POS system if configured"""
        client = order.client
        webhook_url = client.get_feature_config('pos_webhook')
        
        if not webhook_url or not client.has_feature('pos_webhook_enabled'):
            return
        
        # Prepare webhook data
        data = {
            'event': event_type,
            'order': OrderSerializer(order).data,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=data,
                headers={
                    'Content-Type': 'application/json',
                    'X-Restaurant-ID': str(client.id)
                },
                timeout=5
            )
            
            order.webhook_sent = True
            order.webhook_response = {
                'status_code': response.status_code,
                'response': response.text[:500]  # Limit response size
            }
            order.save()
            
        except Exception as e:
            logger.error(f"Webhook failed for order {order.id}: {str(e)}")
            order.webhook_response = {'error': str(e)}
            order.save()


class RestaurantChatViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]  # Will check API key in the view
    
    @action(detail=False, methods=['post'])
    def chat(self, request):
        """Chat endpoint for restaurant AI waiter - доступний для всіх клієнтів.
        
        Headers: X-API-Key (валідний API ключ будь-якого клієнта для валідації)
        Body JSON: { "message": "...", "session_id": "...", ... }
        """
        # Валідація API ключа (для rate limiting), але не прив'язка до конкретного клієнта
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return Response(
                {'error': 'API key required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            key_obj = ClientAPIKey.objects.get(key=api_key, is_active=True)
            if not key_obj.is_valid():
                return Response(
                    {'error': 'Invalid API key'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # Отримуємо клієнта для контексту, але не обмежуємо доступ до ресторанних функцій
            client = key_obj.client
        except ClientAPIKey.DoesNotExist:
            return Response(
                {'error': 'Invalid API key'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Прибираємо перевірку client_type та features - ресторанний чат доступний для всіх клієнтів
        # Якщо client_type не 'restaurant', використовуємо загальний контекст
        
        # Validate request
        serializer = RestaurantChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message = serializer.validated_data['message']
        session_id = serializer.validated_data['session_id']
        language = serializer.validated_data.get('language', 'uk')
        table_id = serializer.validated_data.get('table_id')
        order_id = serializer.validated_data.get('order_id')
        
        # Get table if provided
        table = None
        if table_id:
            try:
                table = RestaurantTable.objects.get(id=table_id, client=client)
            except RestaurantTable.DoesNotExist:
                pass
        
        # Get order if provided
        order = None
        if order_id:
            try:
                order = Order.objects.get(id=order_id, client=client)
            except Order.DoesNotExist:
                pass
        
        # Find or create RestaurantConversation for this session
        # Generate a customer phone if not provided (use session-based identifier)
        customer_phone = serializer.validated_data.get('customer_phone') or f"+000{session_id[:7]}"
        
        # Try to find existing active conversation for this session and client
        conversation = RestaurantConversation.objects.filter(
            client=client,
            session_id=session_id,
            is_active=True
        ).order_by('-started_at').first()
        
        if not conversation:
            # Create new conversation
            conversation = RestaurantConversation.objects.create(
                client=client,
                customer_phone=customer_phone,
                session_id=session_id,
                table=table,
                language=language,
            )
        else:
            # Update existing conversation if needed
            if table and not conversation.table:
                conversation.table = table
            if language and conversation.language != language:
                conversation.language = language
            if conversation.customer_phone.startswith('+000') and customer_phone != conversation.customer_phone:
                conversation.customer_phone = customer_phone
            conversation.save()
        
        # Save user message
        conversation.add_message('user', message)
        
        # Build context from menu items using vector search (fallback to text search)
        context = self._build_menu_context_vector_first(client, message, language)
        
        # Generate response using LLM with restaurant-specific system prompt and menu context
        try:
            system_prompt = self._get_restaurant_system_prompt(client, language)
            # Temporarily inject prompt for this call
            old_prompt = getattr(client, 'custom_system_prompt', '')
            try:
                client.custom_system_prompt = system_prompt
                llm = LLMClient()
                # Include last few messages for conversational continuity
                history_messages = conversation.get_last_messages(5)
                history_text = "\n\n".join([
                    f"{msg['role'].upper()}: {msg['content']}" for msg in history_messages
                ])
                full_context = (context + "\n\n" + history_text).strip()
                response_text = cast(str, llm.generate_response(
                    user_query=message,
                    context=full_context,
                    client=client,
                    stream=False,
                ))
            finally:
                client.custom_system_prompt = old_prompt
        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            response_text = self._get_fallback_response(language)
        
        # Save assistant response
        conversation.add_message('assistant', response_text)
        
        # Update context metadata
        if not conversation.context_metadata:
            conversation.context_metadata = {}
        conversation.context_metadata['menu_context'] = len(context)
        conversation.save(update_fields=['context_metadata'])
        
        # Optional TTS generation
        tts_payload: dict[str, Any] | None = None
        try:
            speak = bool(serializer.initial_data.get('speak'))
        except Exception:
            speak = False
        if speak:
            try:
                from openai import OpenAI
                tts_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                tts_model = getattr(settings, 'TTS_MODEL', 'gpt-4o-mini-tts')
                voice_in = cast(str, serializer.initial_data.get('voice') or 'alloy')
                # Constrain to known literals to satisfy type checker
                allowed_voices = {'alloy','echo','fable','onyx','nova','shimmer'}
                voice = cast(str, voice_in if voice_in in allowed_voices else 'alloy')
                # Bypass strict typing by using kwargs dict
                tts_kwargs: dict[str, Any] = {"model": tts_model, "voice": voice, "input": response_text}
                result = tts_client.audio.speech.create(**tts_kwargs)
                audio_bytes = result.read() if hasattr(result, 'read') else result
                if isinstance(audio_bytes, (bytes, bytearray)):
                    tts_payload = {
                        'mime': 'audio/mpeg',
                        'audio_base64': base64.b64encode(audio_bytes).decode('ascii')
                    }
            except Exception as e:
                logger.error(f"TTS generation failed: {e}")
                tts_payload = None

        # Find suggested items from the response
        suggested_items = self._extract_suggested_items(response_text, client)
        
        # Prepare response
        response_data = {
            'response': response_text,
            'session_id': session_id,
            'suggested_items': MenuItemCompactSerializer(suggested_items, many=True).data,
            'context': {
                'table_id': table_id,
                'order_id': order_id,
                'language': language
            },
            'tts': tts_payload
        }
        
        return Response(response_data)
    
    def _build_menu_context_vector_first(self, client, query, language):
        """Build context from menu items for RAG. Prefer vector search if embeddings exist."""
        try:
            # Try vector search against menu item embeddings
            from MASTER.processing.embedding_service import EmbeddingService
            # Пріоритет: client.embedding_model > specialization.get_embedding_model()
            embedding_model = getattr(client, 'embedding_model', None)
            if not embedding_model and client and client.specialization:
                embedding_model = client.specialization.get_embedding_model()
            model_name = embedding_model.model_name if embedding_model else getattr(settings, 'EMBEDDINGS_MODEL_NAME', 'text-embedding-3-small')
            q = EmbeddingService.embed_text(query, model_name)
            qvec = q.get('vector') or []
            if qvec:
                emb_qs = (
                    MenuItemEmbedding.objects
                    .filter(menu_item__client=client, language=language)
                )
                # Фільтруємо embeddings тільки по поточній моделі клієнта
                if embedding_model:
                    emb_qs = emb_qs.filter(embedding_model=embedding_model)
                
                emb_qs = (
                    emb_qs
                    .select_related('menu_item', 'menu_item__category')
                    .annotate(similarity=1 - Cast(CosineDistance(F('vector'), qvec), output_field=FloatField()))
                    .order_by('-similarity')[:10]
                )
                items = [e.menu_item for e in emb_qs]
                if items:
                    context_parts = []
                    for item in items:
                        item_info = f"**{item.name}**"
                        if item.category:
                            item_info += f" ({item.category.name})"
                        item_info += f"\n{item.description}"
                        item_info += f"\nЦіна: {item.get_display_price()} {item.currency}"
                        if item.allergens:
                            item_info += f"\nАлергени: {', '.join(item.allergens)}"
                        if item.dietary_labels:
                            item_info += f"\nДієтичні мітки: {', '.join(item.dietary_labels)}"
                        if item.calories:
                            item_info += f"\nКалорії: {item.calories}"
                        if item.wine_pairing:
                            item_info += f"\nРекомендоване вино: {item.wine_pairing}"
                        context_parts.append(item_info)
                    return "\n\n".join(context_parts)
        except Exception:
            # If embeddings or OpenAI not available — fallback silently
            pass

        # Get relevant menu items by text filter as reliable base
        menu_items = MenuItem.objects.filter(
            client=client,
            is_available=True
        ).select_related('category')
        
        # Simple text search for now (should use vector search)
        relevant_items = menu_items.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(ingredients__icontains=query) |
            Q(wine_pairing__icontains=query)
        )[:10]

        # Fallback for generic queries: show chef_recommendation/popular_item
        if not relevant_items.exists():
            fallback = menu_items.filter(Q(chef_recommendation=True) | Q(popular_item=True)).order_by('-chef_recommendation', '-popular_item', 'sort_order')[:5]
            relevant_items = fallback
        
        # Build context string
        context_parts = []
        for item in relevant_items:
            item_info = f"**{item.name}**"
            if item.category:
                item_info += f" ({item.category.name})"
            item_info += f"\n{item.description}"
            item_info += f"\nЦіна: {item.get_display_price()} {item.currency}"
            
            if item.allergens:
                item_info += f"\nАлергени: {', '.join(item.allergens)}"
            
            if item.dietary_labels:
                item_info += f"\nДієтичні мітки: {', '.join(item.dietary_labels)}"
            
            if item.calories:
                item_info += f"\nКалорії: {item.calories}"
            
            if item.wine_pairing:
                item_info += f"\nРекомендоване вино: {item.wine_pairing}"
            
            context_parts.append(item_info)
        
        return "\n\n".join(context_parts)
    
    def _get_restaurant_system_prompt(self, client, language):
        """Get system prompt for restaurant AI waiter"""
        base_prompt = client.custom_system_prompt or ""
        
        restaurant_prompt = f"""
        You are an AI waiter for {client.company_name} restaurant.
        Your role is to help guests with menu questions, recommendations, and orders.
        
        Guidelines:
        - Be friendly and professional
        - Provide detailed information about dishes when asked
        - Mention allergens and dietary information when relevant
        - Suggest wine pairings when appropriate
        - Help with special dietary needs
        - Answer in {language} language
        - If asked about something not on the menu, politely explain what's available
        
        {base_prompt}
        """
        
        return restaurant_prompt.strip()
    
    def _get_fallback_response(self, language):
        """Fallback response if RAG fails"""
        responses = {
            'uk': "Вибачте, сталася помилка. Будь ласка, спробуйте ще раз або зверніться до офіціанта.",
            'en': "Sorry, an error occurred. Please try again or ask a waiter for assistance.",
            'de': "Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut oder fragen Sie einen Kellner um Hilfe.",
            'ru': "Извините, произошла ошибка. Пожалуйста, попробуйте еще раз или обратитесь к официанту."
        }
        return responses.get(language, responses['uk'])
    
    def _extract_suggested_items(self, response_text, client):
        """Extract menu items mentioned in the response"""
        # Simple extraction - look for menu item names in response
        menu_items = MenuItem.objects.filter(
            client=client,
            is_available=True
        )
        
        suggested = []
        for item in menu_items:
            if item.name.lower() in response_text.lower():
                suggested.append(item)
                if len(suggested) >= 3:  # Limit suggestions
                    break
        
        return suggested


@api_view(['GET'])
@permission_classes([AllowAny])
def public_table_access(request, client_slug: str, token: str):
    """Public entry from QR: issue a session id for a valid table token.

    URL example: /restaurant/{client_slug}/table/{token}/
    """
    try:
        client = Client.objects.select_related('user').get(user__username=client_slug)
    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
    try:
        table = RestaurantTable.objects.get(client=client, access_token=token, is_active=True)
    except RestaurantTable.DoesNotExist:
        return Response({'error': 'Invalid or inactive table token'}, status=status.HTTP_404_NOT_FOUND)
    # Issue ephemeral session id
    session_id = secrets.token_urlsafe(16)
    return Response({
        'session_id': session_id,
        'client': {
            'id': client.pk,
            'name': client.company_name,
            'slug': client_slug,
        },
        'table': {
            'id': table.pk,
            'number': table.table_number,
            'display_name': table.display_name,
            'capacity': table.capacity,
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def tts_demo(request):
    """Text-to-speech demo endpoint - доступний для всіх клієнтів.

    Підтримує 2 типи авторизації:
    - JWT Bearer token (для клієнтського фронтенду)
    - X-API-Key header (для зовнішніх API)

    Body JSON: { "text": "...", "voice": "alloy" }
    Returns: audio/mpeg
    """
    # Перевіряємо чи є JWT авторизація
    client = None
    if request.user and request.user.is_authenticated:
        # Якщо користувач авторизований через JWT, отримуємо його клієнта
        try:
            from MASTER.clients.views import get_client_from_request
            client = get_client_from_request(request)
        except Exception:
            pass

    # Якщо немає JWT, перевіряємо X-API-Key
    if not client:
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return Response({'error': 'Authentication required (JWT or API key)'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            key_obj = ClientAPIKey.objects.get(key=api_key, is_active=True)
            if not key_obj.is_valid():
                return Response({'error': 'Invalid API key'}, status=status.HTTP_401_UNAUTHORIZED)
            client = key_obj.client
        except ClientAPIKey.DoesNotExist:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data if isinstance(request.data, dict) else {}
    text = data.get('text', '')
    voice = data.get('voice', 'alloy')
    if not text:
        return Response({'error': 'text is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # Model names may vary; use a safe default
        tts_model = getattr(settings, 'TTS_MODEL', 'gpt-4o-mini-tts')
        result = client.audio.speech.create(
            model=tts_model,
            voice=voice,
            input=text,
        )
        audio_bytes = result.read() if hasattr(result, 'read') else result
        resp = HttpResponse(audio_bytes, content_type='audio/mpeg')
        resp['Content-Disposition'] = 'inline; filename="speech.mp3"'
        return resp
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return Response({'error': 'TTS failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def stt_demo(request):
    """Speech-to-text demo endpoint - доступний для всіх клієнтів.

    Підтримує 2 типи авторизації:
    - JWT Bearer token (для клієнтського фронтенду)
    - X-API-Key header (для зовнішніх API)

    Multipart form: file=<audio>
    Returns: { text }
    """
    # Перевіряємо чи є JWT авторизація
    client = None
    if request.user and request.user.is_authenticated:
        # Якщо користувач авторизований через JWT, отримуємо його клієнта
        try:
            from MASTER.clients.views import get_client_from_request
            client = get_client_from_request(request)
        except Exception:
            pass

    # Якщо немає JWT, перевіряємо X-API-Key
    if not client:
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return Response({'error': 'Authentication required (JWT or API key)'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            key_obj = ClientAPIKey.objects.get(key=api_key, is_active=True)
            if not key_obj.is_valid():
                return Response({'error': 'Invalid API key'}, status=status.HTTP_401_UNAUTHORIZED)
            client = key_obj.client
        except ClientAPIKey.DoesNotExist:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_401_UNAUTHORIZED)

    audio = request.FILES.get('file')
    if not audio:
        return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        stt_model = getattr(settings, 'STT_MODEL', 'gpt-4o-transcribe')
        result = client.audio.transcriptions.create(
            model=stt_model,
            file=audio,
        )
        text = getattr(result, 'text', None) or result
        return Response({'text': text})
    except Exception as e:
        logger.error(f"STT error: {e}")
        return Response({'error': 'STT failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
