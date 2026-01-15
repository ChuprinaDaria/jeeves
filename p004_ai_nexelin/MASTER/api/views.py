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
import logging

logger = logging.getLogger(__name__)


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
        allowed = {'pdf', 'txt', 'csv', 'json', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'webp'}
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
    - context (optional): локальна історія діалогу з фронтенду (для sandbox)
    - session_id (optional): ID сесії для завантаження історії з бази (НЕ використовується sandbox)
    
    Response: { "response": "...", "sources": [...], "num_chunks": N, "total_tokens": N }
    
    CRITICAL SECURITY NOTES:
    - Sandbox chats use ONLY 'context' parameter (localStorage history), NEVER 'session_id'
    - Sandbox conversations are NEVER saved to ClientWhatsAppConversation database
    - Sandbox history stays ONLY in browser localStorage, never leaks to Telegram/WhatsApp/Web Chat
    - This endpoint does NOT save conversations - only WebChatPage calls /clients/web-conversations/ for that
    """
    permission_classes = [AllowAny]
    # Простий кеш для результатів класифікації email-інтентів (у межах процесу)
    _email_intent_cache: dict[str, dict] = {}
    # Константи для промпту класифікації email-інтенту
    EMAIL_INTENT_JSON_SCHEMA: str = (
        "{\n"
        '  "intent": "send" | "analyze" | "find" | "recent" | "none",\n'
        "  \"confidence\": float between 0.0 and 1.0,\n"
        "  \"extracted_data\": {\n"
        "    # for 'send':\n"
        "    \"to_address\": string | null,\n"
        "    \"cc\": list of strings (email) or null,\n"
        "    \"bcc\": list of strings (email) or null,\n"
        "    \"subject\": string or null,\n"
        "    \"body\": string or null,\n"
        "    \"is_html\": boolean or null,\n"
        "    # optional aliases for send:\n"
        "    \"to\": string | null,\n"
        "    \"recipient\": string | null,\n"
        "    \"recipient_email\": string | null,\n"
        "    \"email\": string | null,\n"
        "    \"title\": string | null,\n"
        "    \"topic\": string | null,\n"
        "    \"text\": string | null,\n"
        "    \"content\": string | null,\n"
        "    \"message_body\": string | null,\n"
        "    # for 'analyze':\n"
        "    \"days\": integer or null,\n"
        "    # optional aliases for days:\n"
        "    \"days_back\": integer | null,\n"
        "    \"period_days\": integer | null,\n"
        "    \"timeframe_days\": integer | null,\n"
        "    # for 'find':\n"
        "    \"from_address\": string or null,\n"
        "    \"subject_filter\": string or null,\n"
        "    \"days\": integer or null,\n"
        "    \"limit\": integer or null,\n"
        "    # optional aliases for find:\n"
        "    \"sender\": string | null,\n"
        "    # for 'recent':\n"
        "    \"days\": integer or null,\n"
        "    \"limit\": integer or null,\n"
        "    # optional aliases for limit:\n"
        "    \"max_results\": integer | null,\n"
        "    \"count\": integer | null\n"
        "  }\n"
        "}\n"
    )
    EMAIL_INTENT_SYSTEM_PROMPT: str = (
        "You are an intent classifier for email-related commands.\n"
        "User messages can be in: English, German, French, Spanish, "
        "Italian, Dutch, Danish, or other languages.\n\n"
        "Your task:\n"
        "1) Decide if the user EXPLICITLY wants to work with EMAIL.\n"
        "2) Classify the intent into one of:\n"
        "   - 'send'   : user EXPLICITLY wants to send a new email (must contain email address)\n"
        "   - 'analyze': user EXPLICITLY asks for email analysis/summary (must mention 'email', 'mail', 'мейл', 'лист')\n"
        "   - 'find'   : user EXPLICITLY wants to search emails (must mention 'email', 'mail', 'мейл', 'лист')\n"
        "   - 'recent' : user EXPLICITLY asks for list of recent emails (must mention 'email', 'mail', 'мейл', 'лист')\n"
        "   - 'none'   : message is NOT about email actions OR is unclear\n\n"
        "3) Extract structured data into 'extracted_data'.\n\n"
        "CRITICAL: Return 'none' with confidence < 0.5 for:\n"
        "- General conversation (\"як справи\", \"hello\", \"how are you\")\n"
        "- Questions about anything else (games, weather, code, etc.)\n"
        "- Messages that don't explicitly mention email/mail/мейл/лист\n"
        "- Ambiguous requests without clear email keywords\n\n"
        "Return email intent ONLY if user EXPLICITLY mentions email/mail/мейл/лист in their request!\n\n"
        "JSON schema (single JSON object):\n"
        "{JSON_SCHEMA}\n\n"
        "IMPORTANT RULES:\n"
        "- Always return a SINGLE valid JSON object.\n"
        "- Do NOT wrap JSON in markdown or any extra text.\n"
        "- If message doesn't mention email/mail/мейл/лист, use 'intent': 'none' and confidence < 0.3.\n"
        "- Use confidence >= 0.75 ONLY when email intent is EXPLICIT and CLEAR.\n"
    )

    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
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

            # Language detection: support explicit language from body or Accept-Language header
            # Default to 'en' if not provided
            # LLM will automatically respond in user's language based on their question
            language = ''
            try:
                if isinstance(request.data, dict):
                    language = str(request.data.get('language') or '').strip().lower()
            except Exception:
                language = ''
            # If not provided explicitly, try Accept-Language header
            if not language:
                accept_lang = request.headers.get('Accept-Language') or ''
                if accept_lang:
                    # Take first language from header, without region (it-IT -> it)
                    language = accept_lang.split(',')[0].split(';')[0].strip().split('-')[0].lower()
            # Normalize to supported languages
            supported_langs = {'en', 'de', 'fr', 'it', 'nl', 'da', 'es'}
            if not language:
                language = 'en'
            elif language not in supported_langs:
                # Map unsupported languages to English as fallback
                # LLM will still respond in user's actual language automatically
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
                    logger.error(f"Image analysis error: {e}")
                    # Якщо аналіз не вдався, але є текстове повідомлення, продовжуємо
                    if not message:
                        return Response({'error': f'Image analysis failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Додаємо контекст діалогу (якщо переданий) до запиту
            # MAX_HISTORY_MESSAGES визначає глибину контексту (20-30 повідомлень)
            MAX_HISTORY_MESSAGES = 30
            history_lines: list[str] = []

            # 1) Контекст з фронтенду (optional)
            # context може прийти:
            # - як масив [{role, content}, ...] у JSON
            # - або як JSON-рядок у multipart/form-data
            raw_context = request.data.get('context')
            if raw_context:
                import json
                try:
                    if isinstance(raw_context, str):
                        ctx_list = json.loads(raw_context)
                    else:
                        ctx_list = raw_context
                    if isinstance(ctx_list, list):
                        for msg in ctx_list[-MAX_HISTORY_MESSAGES:]:
                            role = str(msg.get('role', 'user')).upper()
                            content = str(msg.get('content', '')).strip()
                            if content:
                                history_lines.append(f"{role}: {content}")
                except Exception:
                    # Не ламаємо запит, якщо контекст некоректний
                    pass

            # 2) Контекст із бекенду по session_id (web-client chat)
            # CRITICAL: Sandbox chats don't use session_id, so they won't load conversation history
            # This ensures sandbox conversations stay private and don't leak to Telegram/WhatsApp
            # Sandbox only uses 'context' parameter (localStorage history), never session_id
            session_id = request.data.get('session_id') or request.data.get('conversation_id')
            # CRITICAL SECURITY: Only load conversation history if session_id is provided AND not empty
            # Sandbox never provides session_id, so it will never load or save conversations to database
            if session_id and str(session_id).strip() and not str(session_id).startswith('sandbox_'):
                try:
                    from MASTER.clients.models import ClientWhatsAppConversation
                    # CRITICAL: Always filter by client for security - sandbox chats must not leak
                    conv = ClientWhatsAppConversation.objects.filter(
                        client=client,
                        session_id=session_id,
                    ).first()
                    if conv and conv.messages:
                        for msg in conv.messages[-MAX_HISTORY_MESSAGES:]:
                            role = str(msg.get('role', 'user')).upper()
                            content = str(msg.get('content', '')).strip()
                            if content:
                                history_lines.append(f"{role}: {content}")
                except Exception:
                    # Не блокуємо запит, якщо щось пішло не так з загрузкою історії
                    pass

            # Уникаємо дублювання рядків в історії (якщо і фронт, і бекенд дають те саме)
            if history_lines:
                # Зберігаємо порядок, видаляючи дублікати
                seen = set()
                unique_lines: list[str] = []
                for line in history_lines:
                    if line not in seen:
                        seen.add(line)
                        unique_lines.append(line)
                history_text = "Conversation history:\n" + "\n".join(unique_lines)
            else:
                history_text = ''

            # Перевіряємо чи є email команди та обробляємо їх
            email_result = None
            if client:
                email_enabled = getattr(client, 'email_smtp_enabled', False)
                logger.info(f"Client {client.id} email_smtp_enabled: {email_enabled}")
                
                if email_enabled:
                    logger.info(f"Processing email command for message: '{message[:100]}'")
                    email_result = self._process_email_command(message, client, language)
                    logger.info(f"Email command result: {email_result}")
                    
                    if email_result and email_result.get('action_taken'):
                        command_type = email_result.get('command_type')
                        # Для аналітики та пошуку мейлів повертаємо відповідь без виклику RAG,
                        # щоб уникнути "жартів" та зайвого контексту від LLM
                        if command_type in {'analyze', 'find', 'recent'}:
                            logger.info(f"Returning email {command_type} result directly")
                            return Response(
                                {
                                    'response': email_result.get('message', ''),
                                    'email_action': email_result,
                                    'language': language,
                                }
                            )
                        # Для send email — додаємо результат в контекст, але все одно викликаємо RAG
                        elif command_type == 'send':
                            email_context = f"\n\n[Email Service Result: {email_result.get('message', '')}]\n"
                            message = message + email_context
                else:
                    logger.warning(f"Client {client.id} has email_smtp_enabled=False, skipping email command processing")

            # Формуємо фінальний запит для RAG:
            # додаємо історію діалогу перед останнім повідомленням користувача
            rag_query = message
            if history_text:
                rag_query = f"{history_text}\n\nLast user message:\n{message}"

            # Використовуємо клієнта для пошуку в його даних + даних бранча та спеціалізації
            generator = ResponseGenerator()

            # Отримуємо branch та specialization клієнта для багаторівневого пошуку
            specialization = getattr(client, 'specialization', None)
            branch = getattr(specialization, 'branch', None) if specialization else None

            # HITL: Check if conversation is waiting for manager response (only for session-based chats)
            if session_id and str(session_id).strip() and not str(session_id).startswith('sandbox_'):
                try:
                    from MASTER.clients.models import ClientWhatsAppConversation
                    conv = ClientWhatsAppConversation.objects.filter(
                        client=client,
                        session_id=session_id,
                    ).first()
                    if conv and getattr(conv, 'is_waiting_for_manager', False):
                        waiting_messages = {
                            'en': "I'm still waiting for confirmation from my colleague. Please hold on, I'll get back to you shortly.",
                            'de': "Ich warte noch auf die Bestätigung von meinem Kollegen. Bitte warten Sie einen Moment.",
                            'fr': "J'attends toujours la confirmation de mon collègue. Veuillez patienter.",
                            'es': "Todavía estoy esperando la confirmación de mi colega. Por favor espere un momento.",
                            'it': "Sto ancora aspettando la conferma dal mio collega. Attenda un momento per favore.",
                            'nl': "Ik wacht nog op bevestiging van mijn collega. Even geduld alstublieft.",
                            'da': "Jeg venter stadig på bekræftelse fra min kollega. Vent venligst et øjeblik.",
                        }
                        return Response({
                            'response': waiting_messages.get(language, waiting_messages['en']),
                            'sources': [],
                            'num_chunks': 0,
                            'total_tokens': 0,
                            'language': language,
                            'waiting_for_manager': True,
                        })
                except Exception:
                    pass  # Continue if error checking HITL status

            # Передаємо client, specialization та branch для багаторівневого пошуку:
            # - Client embeddings (приватні дані клієнта)
            # - Specialization embeddings (спільні дані для всіх клієнтів цієї спеціалізації)
            # - Branch embeddings (спільні дані для всіх клієнтів цього бранча)
            rag_response = generator.generate(
                query=rag_query,
                client=client,
                specialization=specialization,
                branch=branch,
                stream=False,
                language=language,
            )
            
            # HITL: Check if escalation is required (only for session-based chats, not sandbox)
            if getattr(rag_response, 'requires_escalation', False) and getattr(client, 'hitl_enabled', False):
                if session_id and str(session_id).strip() and not str(session_id).startswith('sandbox_'):
                    manager_ids = client.get_manager_telegram_ids() if hasattr(client, 'get_manager_telegram_ids') else []
                    if manager_ids:
                        try:
                            from MASTER.clients.models import ClientWhatsAppConversation
                            conv = ClientWhatsAppConversation.objects.filter(
                                client=client,
                                session_id=session_id,
                            ).first()
                            if conv:
                                from MASTER.clients.tasks import notify_manager_of_escalation
                                escalation_summary = getattr(rag_response, 'escalation_summary', '') or message[:200]
                                notify_manager_of_escalation.delay(conv.id, escalation_summary)
                                logger.info(f"HITL escalation triggered for web conversation {conv.id}")
                        except Exception as e:
                            logger.warning(f"Failed to trigger HITL escalation: {e}")
            
            response_data = {
                'response': getattr(rag_response, 'answer', ''),
                'sources': getattr(rag_response, 'sources', []),
                'num_chunks': getattr(rag_response, 'num_chunks', 0),
                'total_tokens': getattr(rag_response, 'total_tokens', 0),
                'language': language,
                'image_analysis': image_analysis if image_analysis else None,
            }
            
            # Додаємо email результат якщо є
            if email_result:
                response_data['email_action'] = email_result
            
            return Response(response_data)
        except Exception as e:
            logger.error(f"Error in PublicRAGChatView.post(): {e}", exc_info=True)
            return Response(
                {'error': f'Internal server error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _classify_email_intent(self, message: str, language: str = 'en', client=None) -> dict:
        """
        Використовує LLM (з урахуванням вибраного клієнтом провайдера) для класифікації email-інтенту.
        
        Повертає dict:
        {
            "intent": "send" | "analyze" | "find" | "recent" | "none",
            "confidence": float,
            "extracted_data": {...}
        }
        """
        import json
        import hashlib
        import logging
        from django.conf import settings
        from MASTER.rag.llm_client import LLMClient

        logger = logging.getLogger(__name__)

        text = (message or '').strip()
        if not text:
            return {
                'intent': 'none',
                'confidence': 0.0,
                'extracted_data': {},
            }

        lang = (language or 'en').strip().lower()

        # Ключ для кешу (уникаємо збереження сирого тексту в ключі)
        cache_key_src = f"{lang}:{text}"
        cache_key = hashlib.sha256(cache_key_src.encode('utf-8')).hexdigest()
        cache = getattr(PublicRAGChatView, '_email_intent_cache', {})
        if cache_key in cache:
            logger.info(f"Email intent cache hit for key={cache_key}")
            return cache[cache_key]

        # System-промпт: мультимовний, тільки JSON, описаний у константі класу
        system_prompt = self.EMAIL_INTENT_SYSTEM_PROMPT.replace(
            "{JSON_SCHEMA}", self.EMAIL_INTENT_JSON_SCHEMA
        )

        user_content = (
            f"language: {lang}\n"
            f"message: {text}\n\n"
            "Return ONLY the JSON object described above."
        )

        raw_response_text = ""

        try:
            # Визначаємо бажаного провайдера: спочатку з клієнта, потім з LLM_CONFIG
            provider_name = None
            model_name = None
            if client is not None:
                provider_name = (getattr(client, 'llm_provider', None) or '').strip().lower() or None
                model_name = (getattr(client, 'llm_model_name', None) or '').strip() or None
            if not provider_name:
                provider_name = settings.LLM_CONFIG.get('provider', 'openai').lower()
            if not model_name:
                model_name = settings.LLM_CONFIG.get('model', 'gpt-4o-mini')

            logger.info(
                f"Classifying email intent via LLM: provider={provider_name}, model={model_name}, lang={lang}"
            )

            # 1) Якщо провайдер OpenAI і модель OpenAI — пробуємо прямий виклик з response_format=json_object
            used_direct_openai = False
            # Перевіряємо, що це дійсно OpenAI модель (не Claude, не інші)
            is_openai_model = (
                provider_name == 'openai' 
                and model_name 
                and ('gpt' in model_name.lower() or 'o1' in model_name.lower())
            )
            
            if is_openai_model:
                try:
                    from openai import OpenAI  # type: ignore[import-not-found]

                    api_key = getattr(settings, 'OPENAI_API_KEY', '').strip()
                    if api_key:
                        openai_client = OpenAI(api_key=api_key)
                        response = openai_client.chat.completions.create(
                            model=model_name or 'gpt-4o-mini',
                            response_format={"type": "json_object"},
                            temperature=0,
                            max_tokens=300,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content},
                            ],
                        )
                        raw_response_text = response.choices[0].message.content or ""
                        used_direct_openai = True
                        logger.info(
                            f"Email intent classified via direct OpenAI model={model_name}"
                        )
                    else:
                        logger.warning(
                            "OPENAI_API_KEY not configured for email intent classification; "
                            "falling back to generic LLMClient provider."
                        )
                except Exception as e:
                    logger.error(
                        f"Direct OpenAI email intent classification failed: {e}",
                        exc_info=True,
                    )
                    raw_response_text = ""

            # 2) Fallback: використовуємо універсальний LLMClient (OpenAI/Ollama/Kimi/Anthropic)
            if not raw_response_text:
                try:
                    llm_client = LLMClient()
                    provider = llm_client._get_provider(client)  # type: ignore[attr-defined]
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ]
                    llm_result = provider.generate(
                        messages=messages,
                        temperature=0.0,
                        max_tokens=300,
                    )
                    raw_response_text = str(llm_result.get('content', '') or '')
                    logger.info(
                        f"Email intent classified via generic provider={getattr(provider, 'model_name', '')}"
                    )
                except Exception as e:
                    logger.error(
                        f"Generic LLM email intent classification failed: {e}",
                        exc_info=True,
                    )
                    return {
                        'intent': 'none',
                        'confidence': 0.0,
                        'extracted_data': {},
                    }

            logger.debug(
                f"Email intent LLM raw response (first 500 chars): "
                f"{raw_response_text[:500]}"
            )

            # Парсимо JSON-відповідь
            parsed = json.loads(raw_response_text)

            intent = str(parsed.get('intent', 'none')).lower()
            if intent not in {'send', 'analyze', 'find', 'recent', 'none'}:
                intent = 'none'

            conf_raw = parsed.get('confidence', 0.0)
            try:
                confidence = float(conf_raw)
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))

            extracted_data = parsed.get('extracted_data') or {}
            if not isinstance(extracted_data, dict):
                extracted_data = {}

            result = {
                'intent': intent,
                'confidence': confidence,
                'extracted_data': extracted_data,
            }

            # Зберігаємо в кеш
            cache = getattr(PublicRAGChatView, '_email_intent_cache', {})
            cache[cache_key] = result
            setattr(PublicRAGChatView, '_email_intent_cache', cache)

            logger.info(
                f"Email intent result: intent={intent}, confidence={confidence}, "
                f"keys={list(extracted_data.keys())}"
            )
            return result
        except Exception as e:
            logger.error(f"Email intent classification unexpected error: {e}", exc_info=True)
            return {
                'intent': 'none',
                'confidence': 0.0,
                'extracted_data': {},
            }

    def _process_email_command(self, message: str, client, language: str = 'en') -> dict:
        """
        Process email-related commands from user message.
        Detects commands like:
        - "створи мейл", "send email", "напиши email"
        - "дай аналіз останніх мейлів", "analyze recent emails"
        - "знайди мейли від", "find emails from"
        """
        from MASTER.clients.email_service import EmailService
        import re
        import logging
        
        logger = logging.getLogger(__name__)
        message_lower = message.lower()
        logger.info(f"Processing email command from message: '{message_lower[:100]}'")
        
        email_service = EmailService(client)
        # Base result structure
        result: dict = {
            'action_taken': False,
            'message': '',
            'command_type': None,  # 'send', 'analyze', 'find', 'recent'
        }
        
        try:
            # Локальний хелпер для формування зрозумілого тексту з останніх мейлів
            def _format_recent_emails_message(emails, limit_value=None, days_value=None) -> str:
                total = len(emails)
                if total == 0:
                    if days_value:
                        return f"No recent emails found for the last {days_value} days."
                    return "No recent emails found."
                
                shown = total if limit_value is None else min(total, int(limit_value))
                header_parts = []
                if days_value:
                    header_parts.append(f"last {days_value} days")
                header_text = ""
                if header_parts:
                    header_text = f" from the {', '.join(header_parts)}"
                
                lines: list[str] = []
                for idx, email in enumerate(emails[:shown], start=1):
                    subject = (email.get('subject') or '(No Subject)').strip()
                    sender = (email.get('from') or email.get('from_name') or '').strip()
                    date_raw = (email.get('date') or '').strip()
                    # Робимо дату трохи читабельнішою, якщо це ISO-рядок
                    date_short = ""
                    if date_raw:
                        try:
                            # 2025-12-02T09:51:47+00:00 -> 2025-12-02 09:51
                            date_short = date_raw.split('.')[0].replace('T', ' ')[:16]
                        except Exception:
                            date_short = date_raw
                    
                    parts: list[str] = []
                    if date_short:
                        parts.append(f"[{date_short}]")
                    if sender:
                        parts.append(f"from {sender}")
                    
                    # Обрізаємо дуже довгу тему
                    subj_short = subject[:120] + ("…" if len(subject) > 120 else "")
                    main_text = " ".join(parts).strip()
                    if main_text:
                        line = f"{idx}. {main_text}: {subj_short}"
                    else:
                        line = f"{idx}. {subj_short}"
                    lines.append(line)
                
                return f"Here are your last {shown} emails{header_text}:\n" + "\n".join(lines)

            # 1) Спочатку пробуємо класифікацію інтенту через LLM
            llm_intent = None
            try:
                llm_intent = self._classify_email_intent(message, language, client)
            except Exception as e:
                logger.error(
                    f"Error in _classify_email_intent: {e}",
                    exc_info=True,
                )
                llm_intent = None

            if llm_intent:
                intent = (llm_intent.get('intent') or 'none').lower()
                confidence = float(llm_intent.get('confidence') or 0.0)
                extracted = llm_intent.get('extracted_data') or {}

                logger.info(
                    f"LLM email intent: intent={intent}, confidence={confidence}, "
                    f"keys={list(extracted.keys())}"
                )

                if intent != 'none' and confidence >= 0.75:
                    # Intent: SEND
                    if intent == 'send':
                        to_address = (
                            extracted.get('to_address')
                            or extracted.get('to')
                            or extracted.get('recipient')
                            or extracted.get('recipient_email')
                            or extracted.get('email')
                            or extracted.get('email_address')
                        )
                        subject = (
                            extracted.get('subject')
                            or extracted.get('title')
                            or extracted.get('topic')
                            or 'Email from AI Assistant'
                        )
                        body = (
                            extracted.get('body')
                            or extracted.get('text')
                            or extracted.get('content')
                            or extracted.get('message_body')
                            or 'This email was sent by AI Assistant.'
                        )
                        is_html = bool(extracted.get('is_html') or False)
                        cc = extracted.get('cc') or None
                        bcc = extracted.get('bcc') or None

                        if to_address:
                            logger.info(
                                f"Sending email via LLM intent to={to_address}, "
                                f"subject='{str(subject)[:80]}'"
                            )
                            send_result = email_service.send_email(
                                to_address, subject, body, is_html=is_html, cc=cc, bcc=bcc
                            )
                            result['action_taken'] = True
                            result['command_type'] = 'send'
                            
                            # Формуємо детальну відповідь з повним текстом листа
                            if send_result.get('success'):
                                detailed_message = f"✉️ Email sent successfully:\n\n"
                                detailed_message += f"📧 To: {to_address}\n"
                                detailed_message += f"📝 Subject: {subject}\n\n"
                                detailed_message += f"💬 Content:\n{send_result.get('body', body)}"
                                result['message'] = detailed_message
                            else:
                                result['message'] = send_result.get('message', 'Email sending failed')
                            
                            result['email_sent'] = send_result.get('success', False)
                            result['intent_confidence'] = confidence
                            result['intent_source'] = 'llm'
                            result['intent_extracted_data'] = extracted
                            return result
                        else:
                            logger.warning(
                                "LLM classified email intent as 'send' but no to_address found "
                                "in extracted_data; falling back to regex parser."
                            )

                    # Intent: ANALYZE
                    elif intent == 'analyze':
                        days_raw = (
                            extracted.get('days')
                            or extracted.get('days_back')
                            or extracted.get('period_days')
                            or extracted.get('timeframe_days')
                            or 7
                        )
                        try:
                            days = int(days_raw)
                        except (TypeError, ValueError):
                            days = 7

                        logger.info(f"Analyzing emails via LLM intent for last {days} days (language: {language})")
                        analysis = email_service.analyze_recent_emails(days_back=days, language=language)
                        result['action_taken'] = True
                        result['command_type'] = 'analyze'
                        
                        # Показуємо LLM summary замість статистичного
                        llm_summary = analysis.get('llm_summary', '')
                        statistical_summary = analysis.get('statistical_summary', '')
                        
                        if llm_summary:
                            result['message'] = llm_summary
                        elif statistical_summary:
                            result['message'] = statistical_summary
                        else:
                            result['message'] = analysis.get('message', 'Email analysis completed')
                        
                        result['analysis'] = analysis
                        result['intent_confidence'] = confidence
                        result['intent_source'] = 'llm'
                        result['intent_extracted_data'] = extracted
                        return result

                    # Intent: FIND
                    elif intent == 'find':
                        from_address = (
                            extracted.get('from_address')
                            or extracted.get('sender')
                            or extracted.get('email')
                            or extracted.get('email_address')
                        )
                        subject_filter = extracted.get('subject_filter') or extracted.get(
                            'subject'
                        )
                        days_raw = (
                            extracted.get('days')
                            or extracted.get('days_back')
                            or extracted.get('period_days')
                            or extracted.get('timeframe_days')
                            or 30
                        )
                        limit_raw = (
                            extracted.get('limit')
                            or extracted.get('max_results')
                            or extracted.get('count')
                            or 20
                        )
                        try:
                            days = int(days_raw)
                        except (TypeError, ValueError):
                            days = 30
                        try:
                            limit = int(limit_raw)
                        except (TypeError, ValueError):
                            limit = 20

                        logger.info(
                            f"Finding emails via LLM intent from={from_address}, "
                            f"subject_filter='{str(subject_filter)[:80]}', days={days}, limit={limit}"
                        )
                        emails = email_service.search_emails(
                            from_address=from_address,
                            subject=subject_filter,
                            days_back=days,
                            limit=limit,
                        )
                        result['action_taken'] = True
                        result['command_type'] = 'find'
                        if from_address:
                            result['message'] = (
                                f"Found {len(emails)} emails from {from_address}"
                            )
                        else:
                            result['message'] = (
                                f"Found {len(emails)} emails matching search criteria"
                            )
                        result['emails'] = emails
                        result['intent_confidence'] = confidence
                        result['intent_source'] = 'llm'
                        result['intent_extracted_data'] = extracted
                        return result

                    # Intent: RECENT
                    elif intent == 'recent':
                        days_raw = (
                            extracted.get('days')
                            or extracted.get('days_back')
                            or extracted.get('period_days')
                            or extracted.get('timeframe_days')
                            or 7
                        )
                        limit_raw = (
                            extracted.get('limit')
                            or extracted.get('max_results')
                            or extracted.get('count')
                            or 10
                        )
                        try:
                            days = int(days_raw)
                        except (TypeError, ValueError):
                            days = 7
                        try:
                            limit = int(limit_raw)
                        except (TypeError, ValueError):
                            limit = 10

                        logger.info(
                            f"Getting recent emails via LLM intent: days={days}, limit={limit}"
                        )
                        emails = email_service.get_recent_emails(
                            limit=limit,
                            days_back=days,
                        )
                        result['action_taken'] = True
                        result['command_type'] = 'recent'
                        result['message'] = _format_recent_emails_message(
                            emails, limit_value=limit, days_value=days
                        )
                        result['emails'] = emails
                        result['intent_confidence'] = confidence
                        result['intent_source'] = 'llm'
                        result['intent_extracted_data'] = extracted
                        return result

                else:
                    logger.info(
                        f"LLM email intent has low confidence or 'none': {llm_intent}"
                    )

            # Command: Send/Create email
            send_patterns = [
                # Класичні команди: "створи мейл", "send email", "напиши лист"
                r'(?:створи|напиши|відправ|send|create|write)\s+(?:мейл|email|лист)',
                # Email з прийменниками: "email to", "email для"
                r'email\s+(?:to|для)\s+([\w\.-]+@[\w\.-]+\.\w+)',
                # НАТУРАЛЬНА МОВА: будь-який текст + "на/to/для" + email адреса
                # Приклади: "test test на user@example.com", "hello на email@test.com", "привіт на test@gmail.com"
                r'.+\s+(?:на|to|для|до)\s+([\w\.-]+@[\w\.-]+\.\w+)',
                # Просто email адреса в повідомленні (без прийменників, але тоді має бути коротке повідомлення)
                # Приклад: "test test user@example.com" - якщо повідомлення коротке (< 200 символів)
                r'^.{1,200}([\w\.-]+@[\w\.-]+\.\w+)',
            ]
            
            for pattern in send_patterns:
                if re.search(pattern, message_lower):
                    # Extract email address and subject/body
                    email_match = re.search(r'([\w\.-]+@[\w\.-]+\.\w+)', message)
                    if email_match:
                        to_address = email_match.group(1)
                        
                        # Try to extract subject and body
                        # 1) Спочатку шукаємо явні поля "subject:" або "тема:"
                        subject_match = re.search(r'(?:subject|тема)[:\s]+(.+?)(?:\n|body|тіло|$)', message, re.IGNORECASE)
                        body_match = re.search(r'(?:body|тіло|message|повідомлення)[:\s]+(.+?)$', message, re.IGNORECASE | re.DOTALL)
                        
                        if subject_match:
                            subject = subject_match.group(1).strip()
                        else:
                            # 2) НАТУРАЛЬНА МОВА: витягуємо текст перед email адресою (та прийменником)
                            # Приклад: "test test на user@example.com" -> subject та body = "test test"
                            text_before_email = re.search(
                                r'^(.+?)\s+(?:на|to|для|до)\s+[\w\.-]+@[\w\.-]+\.\w+',
                                message,
                                re.IGNORECASE
                            )
                            if text_before_email:
                                content = text_before_email.group(1).strip()
                                # Видаляємо ключові слова типу "send", "створи" з початку
                                content = re.sub(r'^(?:send|create|write|створи|напиши|відправ)\s+(?:email|мейл|лист)\s*', '', content, flags=re.IGNORECASE).strip()
                                subject = content if content else 'Email from AI Assistant'
                            else:
                                # 3) Якщо не знайшли текст перед email, просто беремо перше речення
                                first_sentence = message.split('.')[0].strip()
                                # Видаляємо email адресу з subject
                                subject = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', first_sentence).strip()
                                subject = subject if subject else 'Email from AI Assistant'
                        
                        if body_match:
                            body = body_match.group(1).strip()
                        else:
                            # 2) НАТУРАЛЬНА МОВА: використовуємо той самий текст що і для subject
                            # Якщо користувач написав коротке повідомлення, використовуємо його як тіло листа
                            text_before_email = re.search(
                                r'^(.+?)\s+(?:на|to|для|до)\s+[\w\.-]+@[\w\.-]+\.\w+',
                                message,
                                re.IGNORECASE
                            )
                            if text_before_email:
                                content = text_before_email.group(1).strip()
                                # Видаляємо ключові слова
                                content = re.sub(r'^(?:send|create|write|створи|напиши|відправ)\s+(?:email|мейл|лист)\s*', '', content, flags=re.IGNORECASE).strip()
                                body = content if content else 'This email was sent by AI Assistant.'
                            else:
                                body = message.replace(to_address, '').strip()
                                body = body if body else 'This email was sent by AI Assistant.'
                        
                        logger.info(f"Sending email to {to_address}, subject: '{subject}', body: '{body[:50]}...'")
                        send_result = email_service.send_email(to_address, subject, body)
                        result['action_taken'] = True
                        result['command_type'] = 'send'
                        
                        # Формуємо детальну відповідь з повним текстом листа
                        if send_result.get('success'):
                            detailed_message = f"✉️ Email sent successfully:\n\n"
                            detailed_message += f"📧 To: {to_address}\n"
                            detailed_message += f"📝 Subject: {subject}\n\n"
                            detailed_message += f"💬 Content:\n{send_result.get('body', body)}"
                            result['message'] = detailed_message
                        else:
                            result['message'] = send_result.get('message', 'Email sending failed')
                        
                        result['email_sent'] = send_result.get('success', False)
                        return result
            
            # Command: Analyze recent emails or get summary
            # Більш гнучкі патерни, враховуємо всі мови додатку (uk, en, de, es, fr, it, nl, da)
            analyze_patterns = [
                # НАЙПРОСТІШІ КОМАНДИ (одне слово): "summary", "саммаріі", "анализ"
                r'^(?:summary|саммаріі|саммарі|анализ|analysis|analyse|resumen|résumé|riepilogo|samenvatting|resumé)$',
                
                # Приклади:
                # - "дай аналіз останніх мейлів", "покажи саммарі останнії мейлів"
                # - "show analysis of recent emails", "give summary of last emails"
                # - "analysiere die letzten E-Mails", "zeige Zusammenfassung der letzten Mails"
                # - "analiza los últimos correos", "muestra resumen de correos recientes"
                # - "analyse les derniers emails", "donne un résumé des derniers courriels"
                # - "analizza le ultime email", "mostra riepilogo delle ultime mail"
                # - "analyseer de laatste e-mails", "toon samenvatting van recente mails"
                # - "vis analyse af de seneste mails", "giv resumé af sidste emails"
                r'(?:дай|покажи|vis|zeige|muestra|mostrar|show|give|get|donne|mostra|dammi|toon|geef|analyze|analyse|analysiere|analizar|analiza|analizza|analyseer)?'
                r'\s*'
                r'(?:аналіз|analysis|analyse|análisis|analisi|analise|analyseer|анализ)\s+'
                r'(?:останні\w*|recent|last|latest|letzten|neueste\w*|últim\w*|derni\w*|ultim\w*|laatste\w*|seneste\w*)\s+'
                r'(?:мейлів|emails?|e-mails?|mail\w*|mails?|correos(?:\s+electrónicos)?|courriels?)',

                # "що в останніх мейлах", "what is in recent emails", "was ist in den letzten Emails"
                r'(?:що|what|was)\s+(?:в|in)\s+(?:останні\w*|recent|letzten|últim\w*|derni\w*|ultim\w*|laatste\w*|seneste\w*)\s+(?:мейлах|emails?|e-mails?|mails?|correos|courriels?)',

                # "дай саммарі останніх мейлів", "show summary recent emails", "gib Zusammenfassung der letzten Emails"
                r'(?:дай|покажи|vis|zeige|muestra|mostrar|show|give|get|donne|mostra|dammi|toon|geef)\s+'
                r'(?:саммарі|summary|zusammenfassung|resumen|résumé|riepilogo|samenvatting|resumé)\s+'
                r'(?:останні\w*|recent|last|latest|letzten|últim\w*|derni\w*|ultim\w*|laatste\w*|seneste\w*)?\s*'
                r'(?:мейлів|emails?|e-mails?|mail\w*|mails?|correos(?:\s+electrónicos)?|courriels?)',

                # "саммарі останніх мейлів", "summary of recent emails", "summary of last email from my mail box"
                r'(?:саммарі|summary|zusammenfassung|resumen|résumé|riepilogo|samenvatting|resumé)\s+'
                r'(?:of\s+)?(?:останні\w*|recent|last|latest|letzten|últim\w*|derni\w*|ultim\w*|laatste\w*|seneste\w*)?\s*'
                r'(?:мейлів|emails?|e-mails?|mail\w*|mails?|correos(?:\s+electrónicos)?|courriels?)'
                r'(?:\s+from\s+(?:my\s+)?(?:mail\s*box|inbox))?',
                
                # Загальні email запити: "analyze my emails", "check my mailbox", "read my inbox"
                r'(?:analyze|check|read|show|get|аналізуй|перевір|читай|покажи)\s+(?:my\s+)?(?:email|mail\s*box|inbox|мейли|пошту|мейл)',
                
                # "what's in my mailbox", "що в моїй пошті"
                r'(?:what|що).{0,20}(?:in\s+my\s+|в\s+мої\w*\s+)(?:mail\s*box|inbox|email|пошті|мейлі)',
            ]
            
            for pattern in analyze_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    logger.info(f"Email analyze pattern matched: '{pattern}' in '{message_lower}'")
                    days_match = re.search(r'(\d+)\s+(?:днів|days)', message_lower)
                    days = int(days_match.group(1)) if days_match else 7
                    
                    logger.info(f"Analyzing emails for last {days} days (language: {language})")
                    analysis = email_service.analyze_recent_emails(days_back=days, language=language)
                    result['action_taken'] = True
                    result['command_type'] = 'analyze'
                    
                    # Показуємо LLM summary замість статистичного
                    llm_summary = analysis.get('llm_summary', '')
                    statistical_summary = analysis.get('statistical_summary', '')
                    
                    if llm_summary:
                        result['message'] = llm_summary
                    elif statistical_summary:
                        result['message'] = statistical_summary
                    else:
                        result['message'] = analysis.get('message', 'Email analysis completed')
                    
                    result['analysis'] = analysis
                    logger.info(f"Email analysis completed: {len(analysis.get('emails', []))} emails found, message: {result['message'][:100] if result['message'] else 'no message'}")
                    return result
            
            logger.info("No analyze pattern matched")
            
            # Command: Find emails from sender (by email address)
            find_patterns = [
                # "знайди мейли від X", "find emails from X", "suche emails von X",
                # "buscar correos de X", "rechercher emails de X", "trova email da X", "zoek e-mails van X"
                r'(?:знайди|find|search|шукай|suche|buscar|rechercher|trova|cerca|zoek)\s+'
                r'(?:мейли|emails?|e-mails?|mails?|correos|courriels?)\s+'
                r'(?:від|from|von|de)\s+([\w\.-]+@[\w\.-]+\.\w+)',

                # "emails from X", "mails von X", "correos de X"
                r'(?:мейли|emails?|e-mails?|mails?|correos|courriels?)\s+'
                r'(?:від|from|von|de)\s+([\w\.-]+@[\w\.-]+\.\w+)',
            ]
            
            for pattern in find_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    from_address = match.group(1)
                    emails = email_service.search_emails(from_address=from_address, limit=10)
                    result['action_taken'] = True
                    result['command_type'] = 'find'
                    result['message'] = f'Found {len(emails)} emails from {from_address}'
                    result['emails'] = emails
                    return result
            
            # Command: Get recent emails (list without analysis) 
            # Це для простого отримання списку листів без детального аналізу
            recent_patterns = [
                # "покажи останні мейли", "дай останнії мейли"
                r'(?:покажи|дай|get|show|list|read)\s+(?:останні\w*|нові|recent|last|latest)\s+(?:мейли|emails?|e-mails?|mails?)',

                # "show recent emails", "get latest emails", "any new emails"
                r'(?:show|get|list|read|display)\s+(?:recent|last|latest|new)\s+(?:emails?|e-mails?|mails?)',
                r'(?:any|are there)\s+(?:new|recent)\s+(?:emails?|e-mails?|mails?)',

                # German: "zeige letzte Emails", "neue E-Mails anzeigen"
                r'(?:zeige|zeig|list)\s+(?:letzte\w*|neue\w*|aktuelle\w*)\s+(?:emails?|e-mails?|mails?)',

                # Spanish: "muestra últimos correos", "ver correos recientes"
                r'(?:muestra|mostrar|ver)\s+(?:últim\w*|recient\w*)\s+(?:correos(?:\s+electrónicos)?|emails?|mails?)',

                # French: "montre les derniers emails", "affiche les nouveaux courriels"
                r'(?:montre|montrer|affiche|afficher)\s+(?:les\s+)?(?:derni\w*|nouveaux)\s+(?:emails?|courriels?)',

                # Italian: "mostra le ultime email", "fammi vedere le email recenti"
                r'(?:mostra|fammi\s+vedere|vedi)\s+(?:le\s+)?(?:ultim\w*|recent\w*)\s+(?:email|mail|emails?)',

                # Dutch: "toon laatste e-mails", "laat recente mails zien"
                r'(?:toon|laat\s+zien)\s+(?:laatste\w*|recente\w*)\s+(?:e-mails?|emails?|mails?)',

                # Danish: "vis seneste mails"
                r'(?:vis)\s+(?:seneste\w*|sidste\w*)\s+(?:mails?|emails?|e-mails?)',

                # Generic "what's new in email", "read my emails"
                r'(?:що|what).{0,10}(?:нового|new)\s+(?:в|in)\s+(?:мейлі|email|mail)',
                r'(?:read|show|check)\s+(?:my\s+)?(?:inbox|mailbox|emails?)',
            ]
            
            for pattern in recent_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    logger.info(f"Email recent pattern matched: '{pattern}' in '{message_lower}'")
                    limit_match = re.search(r'(\d+)\s+(?:мейлів|emails)', message_lower)
                    limit = int(limit_match.group(1)) if limit_match else 10
                    
                    logger.info(f"Getting {limit} recent emails")
                    emails = email_service.get_recent_emails(limit=limit)
                    result['action_taken'] = True
                    result['command_type'] = 'recent'
                    result['message'] = _format_recent_emails_message(
                        emails, limit_value=limit, days_value=None
                    )
                    result['emails'] = emails
                    logger.info(f"Retrieved {len(emails)} recent emails")
                    return result
            
            logger.info("No recent pattern matched")
                    
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Email command processing error: {e}")
            result['action_taken'] = False
            result['error'] = str(e)
        
        return result
    
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
        
        # Vision prompt: use English as base, LLM will respond in user's language automatically
        # based on the context and user's question language
        vision_prompt = message if message else "Describe what you see in this image in detail."
        
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
    Request JSON: { provider: str, model_name: str } or { provider_id: int }
    Response: { success: bool, provider: str, model_name: str }
    """
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.EmbeddingModel.models import LLMProvider
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        data = request.data or {}
        provider_id = data.get('provider_id')
        
        # Якщо передано provider_id, використовуємо LLMProvider
        if provider_id:
            try:
                provider_obj = LLMProvider.objects.get(id=provider_id, is_active=True)
                client.llm_provider_model = provider_obj
                client.llm_provider = provider_obj.provider_type
                client.llm_model_name = provider_obj.model_name
                client.save(update_fields=['llm_provider_model', 'llm_provider', 'llm_model_name'])
                
                return Response({
                    'success': True,
                    'provider': client.llm_provider,
                    'model_name': client.llm_model_name,
                    'provider_id': provider_obj.id,
                })
            except LLMProvider.DoesNotExist:
                return Response({'error': 'LLM provider not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Legacy: використовуємо provider та model_name
        provider = (data.get('provider') or '').strip().lower()
        model_name = (data.get('model_name') or '').strip()
        
        if not provider or not model_name:
            return Response({'error': 'provider and model_name are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate supported providers
        supported_providers = {'openai', 'ollama_main', 'ollama_light', 'kimi'}
        if provider not in supported_providers:
            return Response({'error': f'Unsupported provider: {provider}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Спробуємо знайти LLMProvider за provider_type та model_name
        llm_provider_obj = LLMProvider.objects.filter(
            provider_type=provider,
            model_name=model_name,
            is_active=True
        ).first()
        
        # Save settings
        if llm_provider_obj:
            client.llm_provider_model = llm_provider_obj
        client.llm_provider = provider
        client.llm_model_name = model_name
        update_fields = ['llm_provider', 'llm_model_name']
        if llm_provider_obj:
            update_fields.append('llm_provider_model')
        client.save(update_fields=update_fields)
        
        return Response({
            'success': True,
            'provider': client.llm_provider,
            'model_name': client.llm_model_name,
            'provider_id': llm_provider_obj.id if llm_provider_obj else None,
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
        # Для LLM: спочатку перевіряємо ForeignKey, потім fallback на старі поля
        selected_llm_id = None
        if client:
            if hasattr(client, 'llm_provider_model') and client.llm_provider_model:
                selected_llm_id = client.llm_provider_model.id
            else:
                # Fallback: шукаємо LLMProvider за provider_type та model_name
                llm_provider_type = getattr(client, 'llm_provider', None)
                llm_model_name = getattr(client, 'llm_model_name', None)
                if llm_provider_type and llm_model_name:
                    matching_llm = LLMProvider.objects.filter(
                        provider_type=llm_provider_type,
                        model_name=llm_model_name,
                        is_active=True
                    ).first()
                    if matching_llm:
                        selected_llm_id = matching_llm.id
        
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
        
        # Anthropic LLM працює з OpenAI embeddings (оскільки Anthropic не має embedding моделей)
        if llm_type == 'anthropic':
            # Дозволяємо використовувати OpenAI embeddings з Claude
            if emb_provider == 'openai':
                return True
            # Також дозволяємо Anthropic embeddings (коли з'являться)
            if emb_provider == 'anthropic':
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
        
        # Зберігаємо як ForeignKey (новий спосіб) та CharField (для сумісності)
        old_provider = client.llm_provider_model
        client.llm_provider_model = provider
        client.llm_provider = provider.provider_type
        client.llm_model_name = provider.model_name
        client.save(update_fields=['llm_provider_model', 'llm_provider', 'llm_model_name'])
        
        # Новіни про моделі створюються тільки через адмін-панель, не автоматично
        
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


class EmailSendView(APIView):
    """Send email via SMTP"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.clients.email_service import EmailService
        
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not getattr(client, 'email_smtp_enabled', False):
            return Response({'error': 'Email SMTP is not enabled for this client'}, status=status.HTTP_400_BAD_REQUEST)
        
        to_address = request.data.get('to')
        subject = request.data.get('subject', '')
        body = request.data.get('body', '')
        is_html = request.data.get('is_html', False)
        cc = request.data.get('cc', [])
        bcc = request.data.get('bcc', [])
        
        if not to_address:
            return Response({'error': 'Recipient email address is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        email_service = EmailService(client)
        result = email_service.send_email(to_address, subject, body, is_html, cc, bcc)
        
        if result.get('success'):
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class EmailRecentView(APIView):
    """Get recent emails"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.clients.email_service import EmailService
        
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not getattr(client, 'email_smtp_enabled', False):
            return Response({'error': 'Email SMTP is not enabled for this client'}, status=status.HTTP_400_BAD_REQUEST)
        
        limit = int(request.query_params.get('limit', 10))
        days_back = int(request.query_params.get('days_back', 7))
        
        email_service = EmailService(client)
        emails = email_service.get_recent_emails(limit=limit, days_back=days_back)
        
        return Response({
            'emails': emails,
            'count': len(emails)
        })


class EmailSearchView(APIView):
    """Search emails by criteria"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.clients.email_service import EmailService
        
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not getattr(client, 'email_smtp_enabled', False):
            return Response({'error': 'Email SMTP is not enabled for this client'}, status=status.HTTP_400_BAD_REQUEST)
        
        from_address = request.query_params.get('from')
        subject = request.query_params.get('subject')
        days_back = int(request.query_params.get('days_back', 30))
        limit = int(request.query_params.get('limit', 20))
        
        email_service = EmailService(client)
        emails = email_service.search_emails(
            from_address=from_address,
            subject=subject,
            days_back=days_back,
            limit=limit
        )
        
        return Response({
            'emails': emails,
            'count': len(emails)
        })


class EmailAnalyzeView(APIView):
    """Analyze recent emails"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.clients.email_service import EmailService
        
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not getattr(client, 'email_smtp_enabled', False):
            return Response({'error': 'Email SMTP is not enabled for this client'}, status=status.HTTP_400_BAD_REQUEST)
        
        days_back = int(request.query_params.get('days_back', 7))
        
        # Отримуємо мову з запиту (за замовчуванням 'en')
        language = request.query_params.get('language', 'en')
        
        email_service = EmailService(client)
        analysis = email_service.analyze_recent_emails(days_back=days_back, language=language)
        
        return Response(analysis)


class WebChatManifestView(APIView):
    """Generate dynamic PWA manifest for webchat based on tag."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        tag = request.GET.get('tag', '')
        
        if not tag:
            return Response({'error': 'tag parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        manifest = {
            "name": "AI Chat Assistant",
            "short_name": "AI Chat",
            "description": "Chat with your AI assistant",
            "start_url": f"/client?tag={tag}",
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#4F46E5",
            "orientation": "portrait-primary",
            "icons": [
                {
                    "src": "/logo/logo.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable"
                },
                {
                    "src": "/icon.svg",
                    "sizes": "512x512",
                    "type": "image/svg+xml",
                    "purpose": "any maskable"
                }
            ],
            "categories": ["productivity", "social"],
            "lang": "en"
        }
        
        return Response(manifest, content_type='application/manifest+json')


class SaveSandboxPhotoView(APIView):
    """Save photo with AI analysis from sandbox to knowledge base."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        from MASTER.clients.views import get_client_from_request
        from MASTER.clients.models import KnowledgeBlock, ClientDocument
        import hashlib
        import logging
        
        logger = logging.getLogger(__name__)
        
        client = get_client_from_request(request)
        if client is None:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Отримуємо файл та опис від AI
        photo = request.FILES.get('photo')
        description = request.data.get('description', '').strip()
        is_clean = request.data.get('is_clean', 'false').lower() == 'true'
        
        if not photo:
            return Response({'error': 'photo is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Якщо опис не передано, викликаємо vision API для розшифровки фото
        if not description:
            try:
                # Якщо потрібен чистий опис, використовуємо спеціальний промпт
                prompt = 'Describe what you see in this image in detail. Focus only on the visual content, objects, people, text, and any other relevant information. Do not add any game-related context or references.' if is_clean else ''
                description = self._analyze_image(photo, prompt, 'en', client)
                photo.seek(0)  # Повернути вказівник після читання
            except Exception as e:
                logger.error(f"Error analyzing image: {e}")
                description = "Image uploaded - analysis pending"
        
        try:
            # Знайти або створити knowledge block "Photos"
            knowledge_block, created = KnowledgeBlock.objects.get_or_create(
                client=client,
                name='Photos',
                defaults={
                    'description': 'Photos with AI analysis from sandbox',
                    'is_active': True,
                    'is_permanent': False,
                }
            )
            
            # Створити унікальну назву для фото
            file_hash = hashlib.md5(photo.read()).hexdigest()[:8]
            photo.seek(0)  # Повернути вказівник після читання
            
            # Визначити розширення файлу
            import os
            original_name = photo.name
            _, ext = os.path.splitext(original_name or '')
            file_ext = (ext or '').lower().lstrip('.')
            # Якщо розширення не визначено або не підтримується, використовуємо jpg
            if not file_ext or file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                file_ext = 'jpg'
            
            # Створити назву з описом
            short_desc = description[:50] + '...' if len(description) > 50 else description
            title = f"Photo: {short_desc}"
            
            # Створити ClientDocument
            document = ClientDocument.objects.create(
                client=client,
                knowledge_block=knowledge_block,
                title=title,
                file=photo,
                file_type=file_ext,
                file_size=photo.size,
                is_processed=False,
                metadata={
                    'source': 'sandbox_photo',
                    'ai_description': description,
                    'is_clean_description': is_clean,
                    'file_hash': file_hash,
                    'created_from': 'photo_upload_test'
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
                'message': 'Photo saved to knowledge base and indexing started',
                'knowledge_block': {
                    'id': knowledge_block.id,
                    'name': knowledge_block.name,
                    'created': created,
                },
                'document': {
                    'id': document.id,
                    'title': document.title,
                    'file_size': document.file_size,
                },
                'task_id': task_id,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error saving photo: {e}")
            return Response({'error': f'Failed to save photo: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PackageReceiveView(APIView):
    """
    API endpoint для прийняття пакетів з mg.nexelin.
    Підтримує дії: create, clone, update
    
    Відповідно до документації Package API:
    - create: створює новий пакет (клієнт)
    - clone: клонує існуючий пакет (клієнт) без ембедингів та документів
    - update: оновлює існуючий пакет (клієнт)
    """
    permission_classes = [AllowAny]  # Може бути захищено через API key або інший механізм
    
    def post(self, request):
        """
        Обробка POST запитів з mg.nexelin для створення/клонування/оновлення пакетів.
        
        Expected JSON payload:
        {
            "action": "create|clone|update",
            "name": "Package name",
            "guid": "unique-guid",
            "package_type": "AI_TYPE_ID",
            "description": "Description",
            "active": true,
            "parent": "base-guid"  // required for clone
        }
        """
        # Перевірка Content-Type
        content_type = request.content_type
        if 'application/json' not in (content_type or ''):
            return Response({
                'error': 'Unsupported Media Type',
                'message': 'Content-Type must be application/json'
            }, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        
        data = request.data or {}
        action = data.get('action')
        guid = data.get('guid')
        
        # Валідація обов'язкових полів
        if not action:
            return Response({
                'error': 'Bad Request',
                'message': 'Field "action" is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if action not in ['create', 'clone', 'update']:
            return Response({
                'error': 'Bad Request',
                'message': f'Invalid action: {action}. Must be one of: create, clone, update'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not guid:
            return Response({
                'error': 'Bad Request',
                'message': 'Field "guid" is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Імпортуємо функцію для маппінгу package_type -> client_type
            from MASTER.clients.package_sync import _get_client_type_from_package_type
            
            if action == 'create':
                return self._handle_create(data, guid, _get_client_type_from_package_type)
            elif action == 'clone':
                return self._handle_clone(data, guid, _get_client_type_from_package_type)
            elif action == 'update':
                return self._handle_update(data, guid)
        except Exception as e:
            logger.error(f"Error processing package {action} request: {e}", exc_info=True)
            return Response({
                'error': 'Internal Server Error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _handle_create(self, data, guid, get_client_type_func):
        """Обробка створення нового пакету (клієнта)"""
        # Валідація обов'язкових полів для create
        required_fields = ['name', 'package_type', 'description']
        for field in required_fields:
            if field not in data:
                return Response({
                    'error': 'Bad Request',
                    'message': f'Field "{field}" is required for create action'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Перевірка чи guid вже існує
        if Client.objects.filter(tag=guid).exists():
            return Response({
                'error': 'Bad Request',
                'message': f'Package with guid "{guid}" already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Маппінг package_type -> client_type
        package_type = data.get('package_type')
        client_type = get_client_type_func(package_type)
        
        # Використовуємо name як user (як очікує mg.nexelin API)
        user_name = data.get('name', '').strip()
        if not user_name:
            user_name = f"Client {guid[:8]}"
        
        # Створення користувача (для внутрішньої системи)
        username = f"client_{guid}"
        User = get_user_model()
        
        # Перевірка чи користувач вже існує
        if User.objects.filter(username=username).exists():
            # Якщо користувач існує, використовуємо його
            user = User.objects.get(username=username)
        else:
            # Створюємо нового користувача
            user = User.objects.create(
                username=username,
                email=f"{username[:40]}@mg.nexelin.local",
                first_name=user_name[:30] or 'Client',
                last_name='',
            )
            user.set_password(get_random_string(12))
            if hasattr(user, 'role'):
                user.role = 'client'
            user.save()
        
        # Створення клієнта
        # Використовуємо user_name (name з payload) як user для Client
        # company_name автоматично скопіюється з user в методі save() моделі
        # Для нових клієнтів завжди встановлюємо is_active=True, щоб вони могли автентифікуватися
        client = Client.objects.create(
            user=user_name,  # Використовуємо name як user (як очікує mg.nexelin)
            tag=guid,
            # company_name не встановлюємо явно - воно автоматично скопіюється з user в save()
            description=data.get('description', ''),
            is_active=True,  # Новий клієнт завжди активний для доступу
            client_type=client_type,
        )
        
        logger.info(f"Created client {client.id} from package create request (guid: {guid})")
        
        return Response({
            'success': True,
            'message': 'Package created successfully',
            'client': {
                'id': client.id,
                'user': client.user,  # Додаємо user для mg.nexelin API
                'guid': client.tag,
                'name': client.company_name,
                'company_name': client.company_name,
                'tag': client.tag,
                'description': client.description,
                'client_type': client.client_type,
                'is_active': client.is_active,
            }
        }, status=status.HTTP_201_CREATED)
    
    def _handle_clone(self, data, guid, get_client_type_func):
        """Обробка клонування пакету (клієнта) без ембедингів та документів"""
        # Валідація обов'язкових полів для clone
        parent_guid = data.get('parent')
        if not parent_guid:
            return Response({
                'error': 'Bad Request',
                'message': 'Field "parent" is required for clone action'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        required_fields = ['name', 'package_type', 'description']
        for field in required_fields:
            if field not in data:
                return Response({
                    'error': 'Bad Request',
                    'message': f'Field "{field}" is required for clone action'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Перевірка чи guid вже існує
        if Client.objects.filter(tag=guid).exists():
            return Response({
                'error': 'Bad Request',
                'message': f'Package with guid "{guid}" already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Знаходимо батьківський клієнт
        try:
            parent_client = Client.objects.get(tag=parent_guid)
        except Client.DoesNotExist:
            return Response({
                'error': 'Not Found',
                'message': f'Parent package with guid "{parent_guid}" not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Маппінг package_type -> client_type
        package_type = data.get('package_type')
        client_type = get_client_type_func(package_type)
        
        # Використовуємо name як user (як очікує mg.nexelin API)
        user_name = data.get('name', '').strip()
        if not user_name:
            user_name = f"Client {guid[:8]}"
        
        # Створення користувача (для внутрішньої системи)
        username = f"client_{guid}"
        User = get_user_model()
        
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create(
                username=username,
                email=f"{username[:40]}@mg.nexelin.local",
                first_name=user_name[:30] or 'Client',
                last_name='',
            )
            user.set_password(get_random_string(12))
            if hasattr(user, 'role'):
                user.role = 'client'
            user.save()
        
        # Клонування клієнта БЕЗ ембедингів та документів
        # Копіюємо тільки основні поля клієнта
        # company_name автоматично скопіюється з user в методі save() моделі
        # Для нових клієнтів завжди встановлюємо is_active=True, щоб вони могли автентифікуватися
        client = Client.objects.create(
            user=user_name,  # Використовуємо name як user (як очікує mg.nexelin)
            tag=guid,
            # company_name не встановлюємо явно - воно автоматично скопіюється з user в save()
            description=data.get('description', ''),
            is_active=True,  # Новий клієнт завжди активний для доступу
            client_type=client_type,
            # Копіюємо конфігурацію з батьківського клієнта
            branch=parent_client.branch,
            specialization=parent_client.specialization,
            embedding_model=parent_client.embedding_model,
            llm_provider_model=parent_client.llm_provider_model,
            llm_provider=parent_client.llm_provider,
            llm_model_name=parent_client.llm_model_name,
            features=parent_client.features.copy() if parent_client.features else {},
            custom_system_prompt=parent_client.custom_system_prompt,
            # Не копіюємо: logo, documents, embeddings, api_key (генерується автоматично)
        )
        
        logger.info(f"Cloned client {client.id} from parent {parent_client.id} (guid: {guid}, parent_guid: {parent_guid})")
        
        return Response({
            'success': True,
            'message': 'Package cloned successfully',
            'client': {
                'id': client.id,
                'user': client.user,  # Додаємо user для mg.nexelin API
                'guid': client.tag,
                'name': client.company_name,
                'company_name': client.company_name,
                'tag': client.tag,
                'description': client.description,
                'client_type': client.client_type,
                'is_active': client.is_active,
                'parent_guid': parent_guid,
            }
        }, status=status.HTTP_201_CREATED)
    
    def _handle_update(self, data, guid):
        """Обробка оновлення пакету (клієнта)"""
        # Валідація обов'язкових полів для update
        required_fields = ['name', 'description']
        for field in required_fields:
            if field not in data:
                return Response({
                    'error': 'Bad Request',
                    'message': f'Field "{field}" is required for update action'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Знаходимо клієнта
        try:
            client = Client.objects.get(tag=guid)
        except Client.DoesNotExist:
            return Response({
                'error': 'Not Found',
                'message': f'Package with guid "{guid}" not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Оновлюємо поля
        client.company_name = data.get('name', client.company_name)
        client.description = data.get('description', client.description)
        client.is_active = data.get('active', client.is_active)
        client.save(update_fields=['company_name', 'description', 'is_active'])
        
        logger.info(f"Updated client {client.id} from package update request (guid: {guid})")
        
        return Response({
            'success': True,
            'message': 'Package updated successfully',
            'client': {
                'id': client.id,
                'user': client.user,  # Додаємо user для mg.nexelin API
                'guid': client.tag,
                'name': client.company_name,
                'company_name': client.company_name,
                'tag': client.tag,
                'description': client.description,
                'client_type': client.client_type,
                'is_active': client.is_active,
            }
        }, status=status.HTTP_200_OK)
