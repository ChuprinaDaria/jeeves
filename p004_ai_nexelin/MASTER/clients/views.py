from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from MASTER.clients.models import Client, ClientDocument, ClientAPIKey, ClientAPIConfig, KnowledgeBlock, ClientQRCode, ClientWhatsAppConversation
from MASTER.clients.serializers import (
    ClientSerializer,
    ClientDocumentSerializer,
    ClientAPIKeySerializer,
    KnowledgeBlockSerializer,
    ClientQRCodeSerializer,
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
    Helper function to get client from request.
    Supports both:
    - request.user.client_profile (for regular users)
    - request.user.username = 'client_{id}' (for JWT tokens from TokenByClientTokenView)
    """
    # Спочатку пробуємо через client_profile
    client = getattr(request.user, 'client_profile', None)
    if client:
        return client
    
    # Якщо немає client_profile, перевіряємо username
    username = getattr(request.user, 'username', '')
    if username.startswith('client_'):
        try:
            client_id = int(username.replace('client_', ''))
            client = Client.objects.get(id=client_id, is_active=True)
            return client
        except (ValueError, Client.DoesNotExist):
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
    permission_classes = [IsClientOwner | IsAdminOrReadOnly]


class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = ClientAPIKey.objects.all()
    serializer_class = ClientAPIKeySerializer
    permission_classes = [IsAdminOrReadOnly]


class KnowledgeBlockViewSet(viewsets.ModelViewSet):
    """API для роботи з Knowledge Blocks."""
    serializer_class = KnowledgeBlockSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Повертає тільки блоки поточного клієнта."""
        client = get_client_from_request(self.request)
        if not client:
            return KnowledgeBlock.objects.none()
        return KnowledgeBlock.objects.filter(client=client)
    
    def perform_create(self, serializer):
        """Автоматично встановлює клієнта при створенні."""
        client = get_client_from_request(self.request)
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


class ClientQRCodeViewSet(viewsets.ModelViewSet):
    """API для роботи з QR кодами клієнтів (до 10 на клієнта)."""
    serializer_class = ClientQRCodeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Повертає тільки QR коди поточного клієнта."""
        client = get_client_from_request(self.request)
        if not client:
            return ClientQRCode.objects.none()
        return ClientQRCode.objects.filter(client=client)
    
    def perform_create(self, serializer):
        """Автоматично встановлює клієнта при створенні та перевіряє ліміт."""
        client = get_client_from_request(self.request)
        if not client:
            raise serializers.ValidationError("Client not found")
        
        # Перевіряємо ліміт 10 QR кодів
        existing_count = ClientQRCode.objects.filter(client=client).count()
        if existing_count >= 10:
            raise serializers.ValidationError("Maximum 10 QR codes allowed per client")
        
        qr_code = serializer.save(client=client)
        
        # Генеруємо QR код якщо не згенеровано
        if not qr_code.qr_code and not qr_code.qr_code_url:
            try:
                qr_code.generate_qr_code()
                qr_code.save(update_fields=['qr_code', 'qr_code_url'])
            except Exception as e:
                # Логуємо помилку, але не блокуємо створення
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to generate QR code for {qr_code}: {e}")
    
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
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'documents', ClientDocumentViewSet, basename='document')
router.register(r'api-keys', APIKeyViewSet, basename='api-key')
router.register(r'knowledge-blocks', KnowledgeBlockViewSet, basename='knowledge-block')
router.register(r'qr-codes', ClientQRCodeViewSet, basename='qr-code')


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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=404)
        data = ClientSerializer(client, context={'request': request}).data
        return Response(data)

    def patch(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=404)
        # Allow updating only specific fields from client cabinet
        allowed_fields = ['custom_system_prompt', 'features', 'company_name']
        payload = {k: v for k, v in (request.data or {}).items() if k in allowed_fields}
        if not payload:
            return Response({'error': 'No updatable fields provided'}, status=400)
        for k, v in payload.items():
            setattr(client, k, v)
        client.save(update_fields=list(payload.keys()))
        return Response(ClientSerializer(client, context={'request': request}).data)


class KnowledgeBlockDocumentsView(APIView):
    """API для додавання документів до Knowledge Block."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, block_id):
        """Додати документ до knowledge block."""
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=404)
        
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
        }
        return file_types.get(ext, 'txt')


class ClientLogoUploadView(APIView):
    """API endpoint для завантаження логотипу клієнта"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Отримуємо клієнта з токену
            client = get_client_from_request(request)
            
            if not client:
                return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
            
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
            client = get_client_from_request(request)
            
            if not client:
                return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
            
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
    permission_classes = [IsAuthenticated]
    
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
            
            # Форматуємо номер телефону як ім'я
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
                'source': 'whatsapp'
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
    permission_classes = [IsAuthenticated]
    
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
                'source': 'whatsapp'
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


class ClientTopQuestionsView(APIView):
    """
    API endpoint для отримання найчастіше запитуваних питань користувачів
    GET /api/clients/top-questions/
    """
    permission_classes = [IsAuthenticated]
    
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
    permission_classes = [IsAuthenticated]
    
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
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Отримати статистику клієнта з WhatsApp розмов"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=404)

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Перевірити статус моделі через тестовий запит"""
        client = get_client_from_request(request)
        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
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
            'username': client.user.username if client.user else None,
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
