from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny
from django.db.models import Count, Sum
from django.utils.timezone import now, timedelta
from .serializers import RAGQuerySerializer, DocumentUploadSerializer
from MASTER.rag.response_generator import ResponseGenerator
from MASTER.clients.models import ClientAPIKey, Client, ClientDocument
from MASTER.branches.models import Branch
from MASTER.specializations.models import Specialization
from MASTER.EmbeddingModel.models import EmbeddingModel
from django.contrib.auth import get_user_model, authenticate
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import hashlib
from MASTER.accounts.models import User as AppUser
import requests


class RAGQueryView(APIView):
    def post(self, request):
        if not hasattr(request, 'client'):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = RAGQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        client = request.client
        
        return Response({
            'query': query,
            'client': client.user,  # CharField
            'specialization': client.specialization.name,
            'results': []
        })


class DocumentUploadView(APIView):
    def post(self, request):
        # Accept either API-key based client (middleware) or JWT-authenticated user
        client = getattr(request, 'client', None)
        if client is None and getattr(request, 'user', None) is not None and request.user.is_authenticated:
            client = getattr(request.user, 'client_profile', None)
        if client is None:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Persist document
        uploaded = serializer.validated_data['file']
        title = serializer.validated_data['title']
        # Derive file_type from extension
        import os
        _, ext = os.path.splitext(getattr(uploaded, 'name', '') or '')
        ext = (ext or '').lower().lstrip('.')
        allowed = {'pdf', 'txt', 'csv', 'json', 'docx'}
        file_type = ext if ext in allowed else 'txt'
        doc = ClientDocument(
            client=client,
            title=title,
            file=uploaded,
            file_type=file_type,
            file_size=getattr(uploaded, 'size', 0) or 0,
            metadata={'source': 'client'}
        )
        doc.save()
        
        return Response({
            'message': 'Document uploaded successfully',
            'document_id': getattr(doc, 'id', None),
            'title': getattr(doc, 'title', ''),
            'file': getattr(getattr(doc, 'file', None), 'url', ''),
            'file_type': getattr(doc, 'file_type', ''),
            'uploaded_at': getattr(doc, 'uploaded_at', None),
        }, status=status.HTTP_201_CREATED)


class APIDocsView(APIView):
    def get(self, request):
        if not hasattr(request, 'client'):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        client = request.client
        
        docs = {
            'client': client.user,  # CharField
            'specialization': client.specialization.name,
            'branch': client.specialization.branch.name,
            'endpoints': {
                'query': {
                    'url': '/api/rag/query/',
                    'method': 'POST',
                    'headers': {
                        'X-API-Key': 'your_api_key',
                        'Content-Type': 'application/json'
                    },
                    'body': {
                        'query': 'Your question here'
                    }
                },
                'upload': {
                    'url': '/api/rag/upload/',
                    'method': 'POST',
                    'headers': {
                        'X-API-Key': 'your_api_key'
                    },
                    'body': 'multipart/form-data with file'
                },
                'bootstrap': {
                    'url': '/api/rag/bootstrap/<branch_slug>/<specialization_slug>/<client_token>/',
                    'method': 'POST',
                    'auth': 'public (no API key)',
                    'path_params': {
                        'branch_slug': 'slug філії (наприклад, kyiv)',
                        'specialization_slug': 'slug спеціалізації (наприклад, restaurant)',
                        'client_token': 'унікальний токен клієнта (наприклад, acme-001)'
                    },
                    'response': {
                        'branch': {'id': 1, 'name': 'Kyiv', 'slug': 'kyiv'},
                        'specialization': {'id': 10, 'name': 'Restaurant', 'slug': 'restaurant', 'branch_id': 1},
                        'client': {'id': 100, 'user_id': 200, 'username': 'client_acme-001', 'email': 'client_acme-001@example.local', 'specialization_id': 10},
                        'api_key': {'key': 'acme-001', 'name': 'bootstrap:acme-001', 'is_active': True}
                    }
                }
            }
        }
        
        return Response(docs)


class PublicRAGChatView(APIView):
    """Public RAG chat endpoint - доступний для всіх клієнтів.

    Підтримує 3 типи авторизації:
    - JWT Bearer token (для клієнтського фронтенду)
    - X-Client-Token header (для публічного доступу з tag)
    - X-API-Key header (для зовнішніх API)

    Body: multipart/form-data or JSON
    - message (required): текст повідомлення
    - image (optional): файл зображення для аналізу
    
    Response: { "response": "...", "sources": [...], "num_chunks": N, "total_tokens": N }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Ідентифікація клієнта (підтримує X-Client-Token)
        from MASTER.clients.views import get_client_from_request
        client = get_client_from_request(request)
        
        if not client:
            return Response({'error': 'Authentication required (tag link, JWT, or API key)'}, status=status.HTTP_401_UNAUTHORIZED)

        # Підтримка і JSON і multipart/form-data
        message = request.data.get('message', '') or request.POST.get('message', '')
        image_file = request.FILES.get('image') or request.FILES.get('photo')
        
        if not message and not image_file:
            return Response({'error': 'message or image is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Мова: підтримуємо явний набір для UX: it, nl, de, en, fr + ru (тільки якщо справді вказана/прийшла)
        # 1) language з body (якщо є)
        language = ''
        try:
            if isinstance(request.data, dict):
                language = str(request.data.get('language') or '').strip().lower()
        except Exception:
            language = ''
        # 2) Якщо не передали явно — пробуємо з Accept-Language
        if not language:
            accept_lang = request.headers.get('Accept-Language') or ''
            if accept_lang:
                # Беремо першу мову з заголовка, без регіону (it-IT -> it)
                language = accept_lang.split(',')[0].split(';')[0].strip().split('-')[0].lower()
        # 3) Нормалізація до підтримуваного списку
        supported_langs = {'en', 'de', 'fr', 'it', 'nl', 'ru'}
        if not language:
            language = 'en'
        elif language not in supported_langs:
            # Якщо явно прийшла російська локаль — залишаємо 'ru'
            if language.startswith('ru'):
                language = 'ru'
            else:
                # Інші мови мапимо на англійську як дефолт
                language = 'en'

        # Якщо є зображення — аналізуємо його за допомогою vision моделі
        image_analysis = ''
        if image_file:
            try:
                image_analysis = self._analyze_image(image_file, message, language, client)
                # Якщо немає текстового повідомлення, використовуємо аналіз зображення як запит
                if not message:
                    message = image_analysis
                else:
                    # Якщо є і текст і зображення, об'єднуємо
                    message = f"{message}\n\n[Image analysis: {image_analysis}]"
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Image analysis error: {e}")
                # Якщо аналіз не вдався, але є текстове повідомлення, продовжуємо
                if not message:
                    return Response({'error': f'Image analysis failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Використовуємо клієнта для пошуку в його даних + даних бранча та спеціалізації
        generator = ResponseGenerator()

        # Отримуємо branch та specialization клієнта для багаторівневого пошуку
        specialization = getattr(client, 'specialization', None)
        branch = getattr(specialization, 'branch', None) if specialization else None

        # Передаємо client, specialization та branch для багаторівневого пошуку:
        # - Client embeddings (приватні дані клієнта)
        # - Specialization embeddings (спільні дані для всіх клієнтів цієї спеціалізації)
        # - Branch embeddings (спільні дані для всіх клієнтів цього бранча)
        rag_response = generator.generate(
            query=message,
            client=client,
            specialization=specialization,
            branch=branch,
            stream=False,
            language=language,
        )
        return Response({
            'response': getattr(rag_response, 'answer', ''),
            'sources': getattr(rag_response, 'sources', []),
            'num_chunks': getattr(rag_response, 'num_chunks', 0),
            'total_tokens': getattr(rag_response, 'total_tokens', 0),
            'language': language,
            'image_analysis': image_analysis if image_analysis else None,
        })
    
    def _analyze_image(self, image_file, message, language, client):
        """Аналізує зображення за допомогою vision моделі клієнта або OpenAI."""
        import base64
        from openai import OpenAI
        
        # Читаємо зображення і конвертуємо в base64
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Визначаємо MIME type
        content_type = getattr(image_file, 'content_type', 'image/jpeg')
        if not content_type.startswith('image/'):
            content_type = 'image/jpeg'
        
        # Використовуємо OpenAI Vision API
        # TODO: В майбутньому можна додати підтримку інших vision провайдерів
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Формуємо промпт залежно від мови
        vision_prompt = message if message else "Describe what you see in this image in detail."
        if language == 'ru':
            vision_prompt = message if message else "Опиши детально, что ты видишь на этом изображении."
        elif language == 'de':
            vision_prompt = message if message else "Beschreibe detailliert, was du auf diesem Bild siehst."
        elif language == 'fr':
            vision_prompt = message if message else "Décris en détail ce que tu vois sur cette image."
        elif language == 'it':
            vision_prompt = message if message else "Descrivi in dettaglio cosa vedi in questa immagine."
        elif language == 'nl':
            vision_prompt = message if message else "Beschrijf gedetailleerd wat je op deze afbeelding ziet."
        
        # Викликаємо vision API
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # gpt-4o підтримує vision
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content


class TokenByClientTokenView(APIView):
    """Issue JWT for client user by provided client_token (ClientAPIKey.key) or client tag.

    Request JSON: { client_token: string }
    Response: { access, refresh, client: { id, username, email } }
    
    Supports both:
    - ClientAPIKey.key (API key)
    - Client.tag (client tag)
    """
    def post(self, request):
        token = (request.data or {}).get('client_token')
        if not token:
            return Response({'error': 'client_token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        client = None
        
        # Спочатку шукаємо по API key
        try:
            api_key = ClientAPIKey.objects.select_related('client').get(key=token, is_active=True)
            client = api_key.client
        except ClientAPIKey.DoesNotExist:
            # Якщо не знайдено по API key, шукаємо по tag клієнта
            try:
                client = Client.objects.get(tag=token, is_active=True)
                # Перевіряємо, чи вже існує API key для цього клієнта
                # Якщо ні - створюємо новий (з випадковим ключем, не з tag)
                existing_api_key = ClientAPIKey.objects.filter(client=client, is_active=True).first()
                if not existing_api_key:
                    # Створюємо новий API key для клієнта
                    from MASTER.clients.models import generate_api_key
                    api_key = ClientAPIKey.objects.create(
                        client=client,
                        key=generate_api_key(),
                        name=f'auto-generated-for-tag-{token}',
                        is_active=True
                    )
            except Client.DoesNotExist:
                return Response({'error': 'Invalid client_token or tag'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        # Отримуємо існуючий user object для JWT (використовуємо того ж користувача, що був створений при bootstrap)
        from MASTER.accounts.models import User as AppUser

        # Client.user - це CharField з username, тому шукаємо User об'єкт за username
        client_username = getattr(client, 'user', None)
        if not client_username:
            # Fallback: якщо немає username, створюємо generic user
            client_username = f"client_{client.id}"

        user_obj, created = AppUser.objects.get_or_create(
            username=client_username,
            defaults={
                'email': f"{client_username[:40]}@system.local",
                'first_name': getattr(client, 'company_name', 'Client')[:30] or 'Client',
                'last_name': '',
                'role': 'client'
            }
        )

        refresh = RefreshToken.for_user(user_obj)
        return Response({
            'access': str(refresh.access_token),  # type: ignore
            'refresh': str(refresh),
            'client': {
                'id': client.id,
                'user': getattr(client, 'user', ''),
                'company_name': getattr(client, 'company_name', ''),
                'client_type': getattr(client, 'client_type', 'generic'),
            }
        })

class BootstrapProvisionView(APIView):
    """Idempotent endpoint to create/link Branch, Specialization, and Client by path.

    Path format: /api/rag/bootstrap/<branch_slug>/<specialization_slug>/<client_token>/
    - branch_slug: slug of Branch to create or reuse
    - specialization_slug: slug under Branch to create or reuse
    - client_token: unique token to identify Client's username/email namespace

    Behavior:
    - Ensures Branch(branch_slug) exists
    - Ensures Specialization(branch=..., slug=specialization_slug) exists
    - Ensures User(role=client) and Client linked to the specialization exist for client_token
      (creates a new User with generated email if necessary)
    - Returns stable IDs and minimal credentials for follow-up integration
    """

    def post(self, request, branch_slug: str, specialization_slug: str, client_token: str):
        User = AppUser

        # 1) Branch (idempotent by slug)
        branch, _ = Branch.objects.get_or_create(  # type: ignore
            slug=branch_slug,
            defaults={
                'name': branch_slug.replace('-', ' ').title(),
                'is_active': True,
            },
        )

        # 2) Specialization (idempotent by (branch, slug))
        specialization, _ = Specialization.objects.get_or_create(  # type: ignore
            branch=branch,
            slug=specialization_slug,
            defaults={
                'name': specialization_slug.replace('-', ' ').title(),
                'is_active': True,
            },
        )

        # 3) Client user (role=client), identified by client_token
        # FIRST: Check if client with this tag already exists (prevents duplicates)
        client = Client.objects.filter(tag=client_token).first()

        if client is None:
            # SECOND: Check if API key with this token already exists
            client_api = ClientAPIKey.objects.select_related('client').filter(key=client_token).first()
            client = getattr(client_api, 'client', None)

        if client is None:
            # Build a safe, deterministic base username within DB limits
            max_username_len = getattr(User._meta.get_field('username'), 'max_length', 150)  # type: ignore
            token_hash = hashlib.sha1(client_token.encode('utf-8')).hexdigest()[:8]
            token_slug = slugify(client_token)
            base_prefix = "client_"
            reserved = 1 + len(token_hash)  # '_' + hash
            max_base_len = max_username_len - len(base_prefix) - reserved
            safe_base = (token_slug[:max_base_len] if max_base_len > 0 else '')
            username = f"{base_prefix}{safe_base}_{token_hash}"

            # THIRD: Prefer existing client by username if still none
            client = Client.objects.filter(user=username).first()

            if client is None:
                # Create user with minimal required fields (without relying on manager-specific methods)
                email = f"{username[:40]}@example.local"
                user = User(
                    username=username,
                    email=email,
                    first_name=username[:30],  # Truncate to fit first_name field limit
                    last_name='Auto',
                )
                # Ensure uniqueness; if conflict, append a short numeric suffix trimming as needed
                counter = 1
                while User.objects.filter(username=user.username).exists():
                    suffix = f"-{counter}"
                    trim_len = max_username_len - len(suffix)
                    user.username = (username[:trim_len] + suffix) if trim_len > 0 else username
                    counter += 1
                    if counter > 99:
                        break
                user.set_password(get_random_string(12))
                user.save()
                # Ensure role is client if model has 'role'
                if hasattr(user, 'role'):
                    try:
                        user.role = 'client'  # type: ignore[attr-defined]
                        user.save(update_fields=['role'])
                    except Exception:
                        pass

                client = Client.objects.create(
                    user=user.username,  # Store username as string (CharField)
                    specialization=specialization,
                    company_name=f"{branch.name} / {specialization.name}",
                    is_active=True,
                    client_type=('restaurant' if 'rest' in (specialization.slug or '').lower() else 'generic'),
                    tag=client_token,
                    description=f"Auto-created for token {client_token}",
                )
        
        # Update specialization if differs (for existing clients)
        if getattr(client, 'specialization_id', None) != getattr(specialization, 'id', None):
            client.specialization = specialization
            client.save(update_fields=['specialization'])
        desired_type = 'restaurant' if 'rest' in (specialization.slug or '').lower() else 'generic'
        if getattr(client, 'client_type', None) != desired_type:
            try:
                client.client_type = desired_type  # type: ignore[attr-defined]
                client.save(update_fields=['client_type'])
            except Exception:
                pass

        branch_id = getattr(branch, 'id', None)
        specialization_id = getattr(specialization, 'id', None)
        client_id = getattr(client, 'id', None)

        # 4) Bind client_token to API key (rag_token)
        api_key_obj, _ = ClientAPIKey.objects.get_or_create(
            client=client,
            key=client_token,
            defaults={
                'name': f'bootstrap:{client_token}',
                'is_active': True,
            }
        )

        return Response({
            'branch': {
                'id': branch_id,
                'name': branch.name,
                'slug': branch.slug,
            },
            'specialization': {
                'id': specialization_id,
                'name': specialization.name,
                'slug': specialization.slug,
                'branch_id': branch_id,
            },
            'client': {
                'id': client_id,
                'user': client.user,  # This is a CharField now
                'company_name': getattr(client, 'company_name', ''),
                'specialization_id': getattr(client, 'specialization_id', None),
            },
            'api_key': {
                'key': api_key_obj.key,
                'name': api_key_obj.name,
                'is_active': api_key_obj.is_active,
            }
        }, status=status.HTTP_201_CREATED)


class ProvisionLinkView(APIView):
    """Create or ensure (branch, specialization, client) exist and return client portal URL.

    Request JSON: { branch: string, specialization: string, token: string }
    Response: { url, branch, specialization, client, api_key }
    """
    def post(self, request):
        data = request.data or {}
        branch_slug = data.get('branch')
        specialization_slug = data.get('specialization')
        client_token = data.get('token')
        if not branch_slug or not specialization_slug or not client_token:
            return Response({'error': 'branch, specialization, token are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Reuse bootstrap logic by calling the view method directly
        bootstrap_view = BootstrapProvisionView()
        bootstrap_response = bootstrap_view.post(request, branch_slug, specialization_slug, client_token)
        if bootstrap_response.status_code not in (200, 201):
            return bootstrap_response

        payload = bootstrap_response.data
        # Отримуємо client з відповіді bootstrap
        client_id = payload.get('client', {}).get('id')
        
        # Отримуємо tag клієнта
        from MASTER.clients.models import Client
        try:
            client = Client.objects.get(id=client_id)
            client_tag = client.tag
        except Client.DoesNotExist:
            # Fallback на client_token якщо клієнт не знайдено
            client_tag = slugify(client_token)
        
        # Get base URL from settings or use default
        base_url = getattr(settings, 'CLIENT_PORTAL_BASE_URL', 'https://app.nexelin.com').rstrip('/')
        # Новий формат: https://app.nexelin.com/l?tag={client_tag}
        url = f"{base_url}/l?tag={client_tag}"
        payload_out = dict(payload)
        payload_out['url'] = url
        return Response(payload_out, status=status.HTTP_201_CREATED)


class ClientFeaturesOverviewView(APIView):
    """Return a localized overview of client features/menu based on client type.

    Auth: JWT (client user) or X-API-Key (sets request.client).
    Optional: query param lang=uk|en|de|fr|ru (fallback to Accept-Language, then en).
    """
    def get(self, request):
        client = getattr(request, 'client', None)
        if client is None and getattr(request, 'user', None) is not None and request.user.is_authenticated:
            client = getattr(request.user, 'client_profile', None)
        if client is None:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        # Language detection
        lang = (request.query_params.get('lang') or '').lower()
        if not lang:
            lang = (request.headers.get('Accept-Language') or 'en').split(',')[0].split('-')[0].lower()
        if lang not in {'uk','en','de','fr','ru'}:
            lang = 'en'

        ct = getattr(client, 'client_type', 'generic')

        # Localized labels
        labels = {
            'uk': {
                'title': 'Можливості клієнтської панелі',
                'restaurant': {
                    'menu': {'title': 'Меню', 'desc': 'Керування категоріями, меню та позиціями'},
                    'orders': {'title': 'Замовлення', 'desc': 'Перегляд і оновлення статусів замовлень'},
                    'tables': {'title': 'Столи', 'desc': 'Столи, QR-коди та доступ по токену'},
                    'chat': {'title': 'AI-офіціант', 'desc': 'Чат з порадами та контекстом з меню'},
                },
                'generic': {
                    'documents': {'title': 'Документи', 'desc': 'Завантаження та обробка документів'},
                }
            },
            'en': {
                'title': 'Client Portal Features',
                'restaurant': {
                    'menu': {'title': 'Menu', 'desc': 'Manage categories, menus and items'},
                    'orders': {'title': 'Orders', 'desc': 'View and update order statuses'},
                    'tables': {'title': 'Tables', 'desc': 'Tables, QR codes and token access'},
                    'chat': {'title': 'AI Waiter', 'desc': 'Chat with menu-aware recommendations'},
                },
                'generic': {
                    'documents': {'title': 'Documents', 'desc': 'Upload and process documents'},
                }
            }
        }

        l = labels['uk' if lang == 'uk' else 'en']
        sections = []
        if ct == 'restaurant':
            sections = [
                {'key': 'menu', 'title': l['restaurant']['menu']['title'], 'description': l['restaurant']['menu']['desc'], 'endpoints': ['/api/restaurant/menu/', '/api/restaurant/menu-items/']},
                {'key': 'orders', 'title': l['restaurant']['orders']['title'], 'description': l['restaurant']['orders']['desc'], 'endpoints': ['/api/restaurant/orders/']},
                {'key': 'tables', 'title': l['restaurant']['tables']['title'], 'description': l['restaurant']['tables']['desc'], 'endpoints': ['/api/restaurant/tables/']},
                {'key': 'chat', 'title': l['restaurant']['chat']['title'], 'description': l['restaurant']['chat']['desc'], 'endpoints': ['/api/restaurant/chat/']},
            ]
        else:
            sections = [
                {'key': 'documents', 'title': l['generic']['documents']['title'], 'description': l['generic']['documents']['desc'], 'endpoints': ['/api/clients/documents/']},
            ]

        return Response({
            'language': lang,
            'client_type': ct,
            'title': l['title'],
            'sections': sections,
        })


class AIModelsListView(APIView):
    """Proxy endpoint for AI models from mg.nexelin.com.
    
    GET /api/ai-models/
    Response: List of AI models with pricing (pl, pc, ph)
    """
    def get(self, request):
        # Локальний список підтримуваних LLM-провайдерів і моделей
        return Response({
            'models': [
                {'provider': 'openai', 'label': 'OpenAI', 'models': ['gpt-4o-mini']},
                {'provider': 'ollama_main', 'label': 'Ollama Main', 'models': ['qwen2.5:7b']},
                {'provider': 'ollama_light', 'label': 'Ollama Light', 'models': ['qwen2.5:1.5b']},
                {'provider': 'kimi', 'label': 'Kimi (Moonshot AI)', 'models': ['moonshot-v1-8k']},
            ]
        })


class EmbeddingModelsListView(APIView):
    """Return list of available embedding models.
    
    Auth: JWT (client user) or X-API-Key (sets request.client).
    Response: List of active embedding models with their details.
    Now also includes AI models from mg.nexelin.com
    
    NOTE: pgvector has a maximum of 2000 dimensions, so we filter models accordingly.
    """
    permission_classes = [AllowAny]  # Дозволяємо публічний доступ до списку моделей
    
    def get(self, request):
        client = getattr(request, 'client', None)
        if client is None and getattr(request, 'user', None) is not None and request.user.is_authenticated:
            client = getattr(request.user, 'client_profile', None)
        
        # For unauthenticated requests, return public list
        # For authenticated clients, include their selected model
        
        # IMPORTANT: pgvector максимум 2000 вимірів! Фільтруємо моделі
        models_list = EmbeddingModel.objects.filter(is_active=True, dimensions__lte=2000).order_by('provider', 'name')
        
        selected_model_id = None
        if client:
            selected_model_id = getattr(client, 'embedding_model_id', None)
        
        default_model = EmbeddingModel.objects.filter(is_default=True, is_active=True).first()
        default_model_id = getattr(default_model, 'id', None) if default_model else None
        
        result = []
        for model in models_list:
            model_pk = getattr(model, 'pk', None) or getattr(model, 'id', None)
            result.append({
                'id': model_pk,
                'name': model.name,
                'slug': model.slug,
                'provider': model.provider,
                'model_name': model.model_name,
                'dimensions': model.dimensions,
                'cost_per_1k_tokens': float(model.cost_per_1k_tokens),
                'is_default': model.is_default,
                'is_selected': (model_pk == selected_model_id) if selected_model_id else False,
            })
        
        return Response({
            'models': result,
            'selected_model_id': selected_model_id,
            'default_model_id': default_model_id,
        })


class ClientEmbeddingModelSetView(APIView):
    """Set embedding or AI model for authenticated client.
    
    Auth: JWT (client user) or X-API-Key (sets request.client).
    Request JSON: { model_id: int, model_type: 'embedding'|'ai' } or { model_slug: str, model_type: 'embedding'|'ai' }
    Response: { success: bool, model: {...}, reindex_required: bool }
    """
    
    def post(self, request):
        # Import helper from clients.views
        from MASTER.clients.views import get_client_from_request
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        data = request.data or {}
        model_id = data.get('model_id')
        model_slug = data.get('model_slug')
        model_type = data.get('model_type', 'embedding')  # 'embedding' or 'ai'
        
        if not model_id and not model_slug:
            return Response({'error': 'model_id or model_slug is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Підтримка AI моделей вимкнена
        if model_type == 'ai':
            return Response({'error': 'AI models are disabled'}, status=status.HTTP_400_BAD_REQUEST)

        # Обробка лише embedding моделей
        
        # Обробка embedding моделей (оригінальна логіка)
        try:
            if model_id:
                model = EmbeddingModel.objects.get(id=model_id, is_active=True)
            else:
                model = EmbeddingModel.objects.get(slug=model_slug, is_active=True)
        except EmbeddingModel.DoesNotExist:
            return Response({'error': 'Embedding model not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
        
        # Валідація: pgvector підтримує максимум 2000 вимірів
        if model.dimensions > 2000:
            return Response({
                'error': f'Model dimensions ({model.dimensions}) exceed pgvector maximum (2000). Please select a different model.',
                'model_name': model.name,
                'model_dimensions': model.dimensions,
                'max_supported': 2000
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if client is changing model
        previous_model_id = getattr(client, 'embedding_model_id', None)
        model_pk = getattr(model, 'pk', None) or getattr(model, 'id', None)
        
        # Перевіряємо, чи існують embeddings для обраної моделі
        from MASTER.clients.models import ClientEmbedding
        existing_embeddings = ClientEmbedding.objects.filter(
            client=client,
            embedding_model=model
        ).exists()
        
        # reindex потрібен тільки якщо:
        # 1) змінюємо модель (previous != new)
        # 2) і embeddings для нової моделі ще не створені
        reindex_required = (
            previous_model_id != model_pk and 
            previous_model_id is not None and
            not existing_embeddings
        )
        
        # Update client's embedding model
        client.embedding_model = model
        client.save(update_fields=['embedding_model'])
        
        return Response({
            'success': True,
            'model': {
                'id': model_pk,
                'name': model.name,
                'slug': model.slug,
                'provider': model.provider,
                'model_name': model.model_name,
                'dimensions': model.dimensions,
                'cost_per_1k_tokens': float(model.cost_per_1k_tokens),
            },
            'model_type': 'embedding',
            'reindex_required': reindex_required,
            'message': 'Embedding model updated. Please reindex your documents.' if reindex_required else 'Embedding model updated successfully.'
        })


class ClientLLMSetView(APIView):
    """Set LLM provider/model for authenticated client.
    
    Auth: JWT (client user) or X-API-Key (sets request.client).
    Request JSON: { provider: str, model_name: str }
    Response: { success: bool, provider: str, model_name: str }
    """
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        data = request.data or {}
        provider = (data.get('provider') or '').strip().lower()
        model_name = (data.get('model_name') or '').strip()
        
        if not provider or not model_name:
            return Response({'error': 'provider and model_name are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate supported providers
        supported_providers = {'openai', 'ollama_main', 'ollama_light', 'kimi'}
        if provider not in supported_providers:
            return Response({'error': f'Unsupported provider: {provider}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Save settings
        client.llm_provider = provider
        client.llm_model_name = model_name
        client.save(update_fields=['llm_provider', 'llm_model_name'])
        
        return Response({
            'success': True,
            'provider': client.llm_provider,
            'model_name': client.llm_model_name,
        })

class EmbeddingModelsSyncToMGView(APIView):
    """POST: Синхронізувати наші embedding-моделі на MG (вихідний запит).

    Очікує, що в settings задано MG_EMBEDDINGS_SYNC_URL і (опційно) MG_SYNC_API_KEY.
    Повертає статус синку.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        sync_url = getattr(settings, 'MG_EMBEDDINGS_SYNC_URL', '').strip()
        if not sync_url:
            return Response({'error': 'MG_EMBEDDINGS_SYNC_URL is not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Готуємо список наших моделей
        models_list = EmbeddingModel.objects.filter(is_active=True).order_by('provider', 'name')
        payload = {
            'models': [
                {
                    'id': getattr(m, 'pk', None) or getattr(m, 'id', None),
                    'name': m.name,
                    'slug': m.slug,
                    'provider': m.provider,
                    'model_name': m.model_name,
                    'dimensions': m.dimensions,
                    'cost_per_1k_tokens': float(m.cost_per_1k_tokens),
                    'is_default': m.is_default,
                }
                for m in models_list
            ]
        }

        headers = {'Content-Type': 'application/json'}
        api_key = getattr(settings, 'MG_SYNC_API_KEY', '').strip()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        try:
            resp = requests.post(sync_url, json=payload, headers=headers, timeout=10)
            return Response({'status': 'ok', 'mg_status': resp.status_code, 'mg_response': resp.text[:500]})
        except requests.RequestException as e:
            return Response({'error': f'Sync failed: {e}'}, status=status.HTTP_502_BAD_GATEWAY)


class EmbeddingModelReindexView(APIView):
    """Trigger reindexing for all documents using a specific embedding model.
    
    Auth: Admin only (JWT with admin role) or staff user.
    Path: /api/embedding-models/<model_id>/reindex/
    Response: { success: bool, message: str, documents_count: int }
    """
    def post(self, request, model_id):
        # Check admin permissions
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not (hasattr(user, 'is_staff') and user.is_staff or hasattr(user, 'is_superuser') and user.is_superuser):
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            model = EmbeddingModel.objects.get(id=model_id)
        except EmbeddingModel.DoesNotExist:
            return Response({'error': 'Embedding model not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Mark model for reindexing and trigger Celery task
        model.reindex_required = True
        model.save(update_fields=['reindex_required'])
        
        # Count documents that need reindexing (for this model's clients)
        from MASTER.clients.models import ClientEmbedding, ClientDocument
        clients_with_model = Client.objects.filter(embedding_model=model)
        documents_count = ClientDocument.objects.filter(client__in=clients_with_model, is_processed=True).count()
        
        # Trigger reindexing task
        from MASTER.EmbeddingModel.tasks import reindex_documents_for_model
        model_pk = getattr(model, 'pk', None) or getattr(model, 'id', None)
        if model_pk is None:
            return Response({'error': 'Invalid model ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        task_result = reindex_documents_for_model.delay(int(model_pk))
        
        return Response({
            'success': True,
            'message': f'Reindexing started for model {model.name}. {documents_count} documents will be reindexed.',
            'model_id': model_pk,
            'model_name': model.name,
            'documents_count': documents_count,
            'task_id': task_result.id,
        })


class ClientAIUsageView(APIView):
    """Return AI usage statistics and pricing for the authenticated client."""
    def get(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.processing.models import UsageStats
        from MASTER.EmbeddingModel.models import EmbeddingModel
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        qs = UsageStats.objects.filter(client=client).select_related('embedding_model')
        
        totals = qs.aggregate(
            tokens_used=Sum('tokens_used'),
            cost=Sum('cost'),
            operations_count=Count('id'),
        )
        totals = {
            'tokens_used': int(totals['tokens_used'] or 0),
            'cost': float(totals['cost'] or 0.0),
            'operations_count': int(totals['operations_count'] or 0),
        }
        
        by_operation = list(
            qs.values('operation_type')
              .annotate(tokens_used=Sum('tokens_used'), cost=Sum('cost'), operations_count=Count('id'))
              .order_by('operation_type')
        )
        for row in by_operation:
            row['tokens_used'] = int(row['tokens_used'] or 0)
            row['cost'] = float(row['cost'] or 0.0)
            row['operations_count'] = int(row['operations_count'] or 0)
        
        by_model_rows = (
            qs.values('embedding_model')
              .annotate(tokens_used=Sum('tokens_used'), cost=Sum('cost'), operations_count=Count('id'))
              .order_by('embedding_model')
        )
        model_ids = [r['embedding_model'] for r in by_model_rows if r['embedding_model']]
        models = EmbeddingModel.objects.filter(id__in=model_ids)
        model_map = {
            int(getattr(m, 'id')): {
                'id': int(getattr(m, 'id')),
                'name': m.name,
                'provider': m.provider,
                'model_name': m.model_name,
                'dimensions': m.dimensions,
                'is_local': getattr(m, 'is_local', False),
                'server_type': getattr(m, 'server_type', ''),
                'cost_per_1k_tokens': float(m.cost_per_1k_tokens),
            } for m in models
        }
        by_model = []
        for r in by_model_rows:
            mid = r['embedding_model']
            by_model.append({
                'embedding_model': model_map.get(int(mid)) if mid else None,
                'tokens_used': int(r['tokens_used'] or 0),
                'cost': float(r['cost'] or 0.0),
                'operations_count': int(r['operations_count'] or 0),
            })
        
        since = now().date() - timedelta(days=30)
        daily = (
            qs.filter(date__gte=since)
              .values('date')
              .annotate(tokens_used=Sum('tokens_used'), cost=Sum('cost'), operations_count=Count('id'))
              .order_by('date')
        )
        daily_last_30d = [{
            'date': str(r['date']),
            'tokens_used': int(r['tokens_used'] or 0),
            'cost': float(r['cost'] or 0.0),
            'operations_count': int(r['operations_count'] or 0),
        } for r in daily]
        
        embedding_model_data = None
        if getattr(client, 'embedding_model_id', None):
            em = client.embedding_model
            embedding_model_data = {
                'id': int(getattr(em, 'id')),
                'name': em.name,
                'provider': em.provider,
                'model_name': em.model_name,
                'dimensions': em.dimensions,
                'is_local': getattr(em, 'is_local', False),
                'server_type': getattr(em, 'server_type', ''),
                'cost_per_1k_tokens': float(em.cost_per_1k_tokens),
            }
        
        payload = {
            'client': {
                'id': int(getattr(client, 'id')),
                'user': getattr(client, 'user'),
                'company_name': getattr(client, 'company_name', ''),
                'llm_provider': getattr(client, 'llm_provider', 'openai'),
                'llm_model_name': getattr(client, 'llm_model_name', ''),
                'embedding_model': embedding_model_data,
            },
            'totals': totals,
            'by_operation': by_operation,
            'by_model': by_model,
            'daily_last_30d': daily_last_30d,
        }
        return Response(payload)

class ClientIndexNewDocumentsView(APIView):
    """Index only new (unprocessed) documents of authenticated client.
    
    Auth: JWT (client user) or X-API-Key (sets request.client).
    Response: { success: bool, message: str, documents_count: int, task_id: str }
    
    This endpoint indexes only documents that haven't been processed yet (is_processed=False).
    It does NOT reindex existing documents or delete old embeddings.
    """
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Перевіряємо, чи є обрана модель
        if not client.embedding_model:
            return Response({
                'error': 'No embedding model selected. Please select a model first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Запускаємо таск для індексування тільки нових документів
        from MASTER.EmbeddingModel.tasks import index_new_client_documents_task
        client_pk = getattr(client, 'pk', None) or getattr(client, 'id', None)
        if client_pk is None:
            return Response({'error': 'Invalid client ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Підраховуємо необроблені документи для інформації
        documents_count = ClientDocument.objects.filter(client=client, is_processed=False).count()
        
        if documents_count == 0:
            return Response({
                'success': True,
                'message': 'No new documents to index. All documents are already processed.',
                'documents_count': 0,
                'task_id': None,
            })
        
        task_result = index_new_client_documents_task.delay(int(client_pk))
        
        return Response({
            'success': True,
            'message': f'Indexing started for {documents_count} new document(s).',
            'documents_count': documents_count,
            'task_id': task_result.id,
        })


class ClientReindexDocumentsView(APIView):
    """Trigger reindexing for all documents of authenticated client.
    
    Auth: JWT (client user) or X-API-Key (sets request.client).
    Response: { success: bool, message: str, documents_count: int, task_id: str }
    
    This endpoint reindexes ALL processed documents (marks them as unprocessed and reindexes).
    Use this when switching models or when you need to completely rebuild embeddings.
    """
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Перевіряємо, чи є обрана модель
        if not client.embedding_model:
            return Response({
                'error': 'No embedding model selected. Please select a model first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Запускаємо таск для реіндексації документів цього клієнта
        from MASTER.EmbeddingModel.tasks import reindex_client_documents_task
        client_pk = getattr(client, 'pk', None) or getattr(client, 'id', None)
        if client_pk is None:
            return Response({'error': 'Invalid client ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        task_result = reindex_client_documents_task.delay(int(client_pk))
        
        # Підраховуємо документи для інформації
        documents_count = ClientDocument.objects.filter(client=client, is_processed=True).count()
        
        return Response({
            'success': True,
            'message': f'Reindexing started for {documents_count} document(s).',
            'documents_count': documents_count,
            'task_id': task_result.id,
        })


class LLMProvidersListView(APIView):
    """Return list of available LLM providers."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.EmbeddingModel.models import LLMProvider
        
        client = get_client_from_request(request)
        providers_list = LLMProvider.objects.filter(is_active=True).order_by('provider_type', 'name')
        
        selected_provider_id = None
        if client:
            from MASTER.EmbeddingModel.models import LLMProvider as _LP
        selected_provider_id = _LP.objects.filter(is_active=True, provider_type=getattr(client,'llm_provider',None), model_name=getattr(client,'llm_model_name',None)).values_list('id', flat=True).first()
        
        default_provider = LLMProvider.objects.filter(is_default=True, is_active=True).first()
        default_provider_id = getattr(default_provider, 'id', None) if default_provider else None
        
        serialized = [
            {
                'id': getattr(p, 'id', None),
                'name': p.name,
                'slug': p.slug,
                'provider_type': p.provider_type,
                'model_name': p.model_name,
                'is_default': p.is_default,
            }
            for p in providers_list
        ]
        
        return Response({
            'providers': serialized,
            'selected_provider_id': selected_provider_id,
            'default_provider_id': default_provider_id,
        })


class ModelPairsView(APIView):
    """Return list of compatible LLM + Embedding model pairs.
    
    GET /api/model-pairs/
    Response: List of compatible pairs with metadata
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.EmbeddingModel.models import LLMProvider, EmbeddingModel
        
        # ВАЖЛИВО: тут працюємо тільки з client, знайденим через tag / X-Client-Token / X-API-Key.
        # JWT client_profile свідомо не використовуємо, щоб не змішувати admin/login потік з client-порталом.
        client = get_client_from_request(request)
        
        # Отримуємо активні LLM провайдери
        llm_providers = LLMProvider.objects.filter(is_active=True).order_by('provider_type', 'name')
        
        # Отримуємо активні embedding моделі (макс 2000 dimensions для pgvector)
        embedding_models = EmbeddingModel.objects.filter(is_active=True, dimensions__lte=2000).order_by('provider', 'name')
        
        # Поточні вибрані моделі
        selected_llm_id = getattr(client, 'llm_provider_model_id', None) if client else None
        selected_embedding_id = getattr(client, 'embedding_model_id', None) if client else None
        
        # Генеруємо сумісні пари
        pairs = []
        for llm in llm_providers:
            for emb in embedding_models:
                if self._check_compatibility(llm, emb):
                    is_selected = (
                        client and 
                        selected_llm_id == llm.id and 
                        selected_embedding_id == emb.id
                    )
                    
                    pairs.append({
                        'id': f"{llm.id}-{emb.id}",
                        'llm_id': llm.id,
                        'llm_name': llm.name,
                        'llm_provider_type': llm.provider_type,
                        'llm_model_name': llm.model_name,
                        'embedding_id': emb.id,
                        'embedding_name': emb.name,
                        'embedding_provider': emb.provider,
                        'embedding_model_name': emb.model_name,
                        'embedding_dimensions': emb.dimensions,
                        'embedding_server_type': emb.server_type or '',
                        'is_selected': is_selected,
                        'display_name': f"{llm.name} + {emb.name}",
                        'description': f"{llm.provider_type} ({llm.model_name}) + {emb.provider} ({emb.dimensions}D)",
                    })
        
        return Response({
            'pairs': pairs,
            'selected_llm_id': selected_llm_id,
            'selected_embedding_id': selected_embedding_id,
        })
    
    def _check_compatibility(self, llm, emb):
        """Перевірка сумісності LLM + Embedding"""
        llm_type = llm.provider_type
        emb_provider = emb.provider
        emb_server = getattr(emb, 'server_type', '') or ''
        
        # OpenAI LLM + OpenAI Embeddings
        if llm_type == 'openai' and emb_provider == 'openai':
            return True
        
        # Ollama LLM + Ollama Embeddings
        if llm_type in ['ollama_main', 'ollama_light']:
            if emb_provider == 'ollama':
                return True
            # HuggingFace на Ollama серверах
            if emb_provider == 'huggingface' and emb_server in ['main', 'light']:
                return True
        
        # Kimi працює з усіма
        if llm_type == 'kimi':
            return True
        
        # Custom працює з усіма
        if llm_type == 'custom':
            return True
        
        return False


class ClientLLMProviderSetView(APIView):
    """Set LLM provider for authenticated client."""
    
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.EmbeddingModel.models import LLMProvider
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        data = request.data or {}
        provider_id = data.get('provider_id')
        provider_slug = data.get('provider_slug')
        
        if not provider_id and not provider_slug:
            return Response({'error': 'provider_id or provider_slug is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if provider_id:
                provider = LLMProvider.objects.get(id=provider_id, is_active=True)
            else:
                provider = LLMProvider.objects.get(slug=provider_slug, is_active=True)
        except LLMProvider.DoesNotExist:
            return Response({'error': 'LLM provider not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
        
        client.llm_provider = provider.provider_type
        client.llm_model_name = provider.model_name
        client.save(update_fields=['llm_provider','llm_model_name'])
        
        provider_pk = getattr(provider, 'pk', None) or getattr(provider, 'id', None)
        
        return Response({
            'success': True,
            'provider': {
                'id': provider_pk,
                'name': provider.name,
                'slug': provider.slug,
                'provider_type': provider.provider_type,
                'model_name': provider.model_name,
                'api_endpoint': provider.api_endpoint,
                'max_tokens': provider.max_tokens,
                'temperature': provider.temperature,
            },
            'message': 'LLM provider updated successfully.'
        })


class SaveSandboxQAView(APIView):
    """Save Q&A pair from sandbox to knowledge base."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.clients.models import KnowledgeBlock, ClientDocument
        from django.core.files.base import ContentFile
        import os
        import hashlib
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        data = request.data or {}
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not question or not answer:
            return Response({'error': 'question and answer are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Знайти або створити knowledge block "Sandbox"
            knowledge_block, created = KnowledgeBlock.objects.get_or_create(
                client=client,
                name='Sandbox',
                defaults={
                    'description': 'Q&A pairs saved from sandbox chat',
                    'is_active': True,
                    'is_permanent': False,
                }
            )
            
            # Створити текстовий вміст Q&A
            qa_content = f"Question: {question}\n\nAnswer: {answer}\n"
            
            # Створити унікальну назву файлу на основі хешу питання
            question_hash = hashlib.md5(question.encode()).hexdigest()[:8]
            filename = f"sandbox_qa_{question_hash}.txt"
            title = f"Q&A: {question[:50]}..." if len(question) > 50 else f"Q&A: {question}"
            
            # Створити ContentFile
            content_file = ContentFile(qa_content.encode('utf-8'))
            content_file.name = filename
            
            # Створити ClientDocument
            document = ClientDocument.objects.create(
                client=client,
                knowledge_block=knowledge_block,
                title=title,
                file=content_file,
                file_type='txt',
                file_size=len(qa_content.encode('utf-8')),
                is_processed=False,
                metadata={
                    'source': 'sandbox',
                    'question': question,
                    'answer': answer,
                    'created_from': 'chat'
                }
            )
            
            # Запустити індексацію нових документів
            from MASTER.EmbeddingModel.tasks import index_new_client_documents_task
            client_pk = getattr(client, 'pk', None) or getattr(client, 'id', None)
            if client_pk:
                task_result = index_new_client_documents_task.delay(int(client_pk))
                task_id = task_result.id
            else:
                task_id = None
            
            return Response({
                'success': True,
                'message': 'Q&A saved to knowledge base',
                'knowledge_block': {
                    'id': knowledge_block.id,
                    'name': knowledge_block.name,
                    'created': created,
                },
                'document': {
                    'id': document.id,
                    'title': document.title,
                },
                'task_id': task_id,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving Q&A: {e}")
            return Response({'error': f'Failed to save Q&A: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
