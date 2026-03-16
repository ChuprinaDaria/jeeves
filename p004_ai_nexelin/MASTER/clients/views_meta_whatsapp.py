from django.views import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.utils import timezone

import json, hmac, hashlib, logging, requests, base64
from urllib.parse import unquote

from .models import Client, ClientQRCode, ClientWhatsAppConversation
from MASTER.restaurant.models import RestaurantTable, RestaurantConversation

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v23.0"

def verify_xhub_signature(raw_body: bytes, x_hub_signature_256: str, app_secret: str) -> bool:
    try:
        expected = 'sha256=' + hmac.new(
            app_secret.encode('utf-8'),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, x_hub_signature_256)
    except Exception as e:
        logger.error("Signature verification error: %s", e, exc_info=True)
        return False

def send_whatsapp_text(to_number: str, body: str, *, client=None) -> bool:
    """Відправляє повідомлення через Meta WhatsApp API (пер-клієнтно)"""
    try:
        phone_number_id = None
        access_token = None

        if client is not None:
            phone_number_id = getattr(client, 'meta_phone_number_id', '') or None
            access_token = getattr(client, 'meta_access_token', '') or None

        # Backward fallback до глобальних налаштувань, якщо не задані у клієнта
        if not phone_number_id:
            phone_number_id = getattr(settings, 'META_PHONE_NUMBER_ID', '')
        if not access_token:
            access_token = getattr(settings, 'META_ACCESS_TOKEN', '')

        if not phone_number_id or not access_token:
            logger.warning("Meta WhatsApp credentials are not configured")
            return False

        url = f"{GRAPH_URL}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": body, "preview_url": False}
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        logger.info(f"Meta WhatsApp message sent successfully to {to_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Meta WhatsApp message: {str(e)}", exc_info=True)
        return False

@method_decorator(csrf_exempt, name='dispatch')
class MetaWhatsAppWebhookView(View):
    """
    Webhook для обробки повідомлень від Meta WhatsApp Business API
    """
    
    def get(self, request, *args, **kwargs):
        """Верифікація webhook для Meta"""
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        # Логуємо вхідні параметри для відлагодження
        logger.info(f"Meta WhatsApp webhook verification request: mode={mode}, token_length={len(token) if token else 0}, challenge_length={len(challenge) if challenge else 0}")
        
        # Перевіряємо mode
        if mode != "subscribe":
            logger.warning(f"Meta WhatsApp webhook verification failed: invalid mode={mode}")
            return HttpResponse(status=403)
        
        if not token:
            logger.warning("Meta WhatsApp webhook verification failed: missing verify_token")
            return HttpResponse(status=403)
        
        if not challenge:
            logger.warning("Meta WhatsApp webhook verification failed: missing challenge")
            return HttpResponse(status=403)
        
        # Спроба знайти клієнта за verify_token (пер-клієнтна перевірка)
        from MASTER.clients.models import Client
        client = Client.objects.filter(meta_verify_token=token, whatsapp_meta_enabled=True).first()
        
        if client is not None:
            logger.info(f"Meta WhatsApp webhook verified successfully for client: {client.id} ({client.company_name})")
            return HttpResponse(challenge)
        
        # Fallback до глобального токену, якщо per-client не знайдено
        global_token = getattr(settings, 'META_VERIFY_TOKEN', '')
        if global_token and token == global_token:
            logger.info("Meta WhatsApp webhook verified successfully using global META_VERIFY_TOKEN")
            return HttpResponse(challenge)
        
        # Детальне логування для відлагодження
        logger.warning(f"Meta WhatsApp webhook verification failed:")
        logger.warning(f"  - Received token: {token[:10]}... (length: {len(token)})")
        logger.warning(f"  - Clients with this token: {Client.objects.filter(meta_verify_token=token).count()}")
        logger.warning(f"  - Clients with enabled WhatsApp: {Client.objects.filter(whatsapp_meta_enabled=True).count()}")
        logger.warning(f"  - Global token set: {bool(global_token)}")
        if global_token:
            logger.warning(f"  - Global token match: {token == global_token}")
        
        return HttpResponse(status=403)

    def post(self, request, *args, **kwargs):
        """Обробка вхідних повідомлень від Meta"""
        try:
            # Перевірка підпису
            raw_body = request.body
            x_hub_signature = request.headers.get('X-Hub-Signature-256', '')
            
            from MASTER.clients.models import Client
            meta_app_secret = getattr(settings, 'META_APP_SECRET', '')

            # Перевірка підпису: пріоритет пер-клієнтного секрету, якщо можемо ідентифікувати
            # На POST подіях Meta надсилає phone_number_id у body->entry->changes->value->metadata
            body_preview = json.loads(raw_body.decode("utf-8"))
            phone_number_id = None
            try:
                for entry in body_preview.get('entry', []):
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        md = value.get('metadata', {})
                        if 'phone_number_id' in md:
                            phone_number_id = md.get('phone_number_id')
                            break
                    if phone_number_id:
                        break
            except Exception:
                pass

            client_for_secret = None
            if phone_number_id:
                client_for_secret = Client.objects.filter(meta_phone_number_id=phone_number_id, whatsapp_meta_enabled=True).first()
            if client_for_secret and getattr(client_for_secret, 'meta_app_secret', ''):
                meta_app_secret = client_for_secret.meta_app_secret

            if x_hub_signature and meta_app_secret:
                if not verify_xhub_signature(raw_body, x_hub_signature, meta_app_secret):
                    logger.warning("Invalid Meta webhook signature")
                    return HttpResponse(status=403)
            
            body = body_preview
            logger.info(f"Meta WhatsApp Webhook POST: {json.dumps(body, indent=2)}")
            
            # Meta відправляє події в полі 'entry'
            if 'object' in body and body['object'] == 'whatsapp_business_account':
                for entry in body.get('entry', []):
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        
                        # Обробка статусів (доставка, прочитано) - пропускаємо
                        if 'statuses' in value:
                            continue
                        
                        # Обробка повідомлень
                        if 'messages' in value:
                            for message in value['messages']:
                                self.handle_message(message, value.get('metadata', {}))
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing Meta webhook: {str(e)}", exc_info=True)
            return HttpResponse(status=500)
    
    def handle_message(self, message, metadata):
        """Обробляє одне повідомлення від Meta"""
        try:
            # Визначаємо клієнта за phone_number_id (пер-клієнтна конфігурація)
            from MASTER.clients.models import Client, ClientWhatsAppConversation, ClientQRCode
            client = None
            phone_number_id = (metadata or {}).get('phone_number_id')
            if phone_number_id:
                client = Client.objects.filter(meta_phone_number_id=phone_number_id, whatsapp_meta_enabled=True).first()

            from_number = message.get('from', '')
            message_type = message.get('type', '')
            message_id = message.get('id', '')
            
            # Отримуємо текст повідомлення
            message_body = ''
            if message_type == 'text':
                message_body = message.get('text', {}).get('body', '')
            elif message_type == 'interactive':
                # Обробка кнопок/меню
                interactive = message.get('interactive', {})
                if 'button_reply' in interactive:
                    message_body = interactive['button_reply'].get('title', '')
                elif 'list_reply' in interactive:
                    message_body = interactive['list_reply'].get('title', '')
            else:
                logger.info(f"Unsupported message type: {message_type}")
                return
            
            if not message_body:
                logger.warning(f"Empty message body for message {message_id}")
                return
            
            logger.info(f"Processing Meta message: from={from_number}, type={message_type}, body={message_body[:100]}")
            
            # Перевіряємо чи це START2 команда
            if message_body.strip().upper().startswith('START2'):
                self.handle_start2_command(from_number, message_body)
            else:
                self.handle_regular_message(from_number, message_body, client)
                
        except Exception as e:
            logger.error(f"Error handling Meta message: {str(e)}", exc_info=True)
    
    def handle_start2_command(self, from_number, message_body):
        """Обробляє START2 команду (аналогічно Twilio)"""
        try:
            logger.info(f"Processing START2 command: {message_body}")
            
            parts = message_body.split()
            ref_data = None
            table_number = None
            signature = None
            
            for part in parts[1:]:  # Пропускаємо 'START2'
                if part.startswith('ref='):
                    ref_data = part[4:]
                elif part.startswith('tbl='):
                    table_number = part[4:]
                elif part.startswith('sig='):
                    signature = part[4:]
            
            logger.info(f"Parsed START2: ref={ref_data}, tbl={table_number}, sig={signature}")
            
            if not all([ref_data, table_number, signature]):
                logger.warning(f"Invalid START2 format: {message_body}")
                send_whatsapp_text(from_number, "Невірний формат команди START2")
                return
            
            # Перевіряємо підпис
            if not self.verify_signature(ref_data, table_number, signature):
                logger.warning(f"Invalid signature for START2: {message_body}")
                send_whatsapp_text(from_number, "Невірний підпис команди")
                return
            
            # Декодуємо ref_data
            try:
                if not ref_data:
                    raise ValueError("ref_data is empty")
                ref_data += '=' * (4 - len(ref_data) % 4)
                decoded = base64.urlsafe_b64decode(ref_data).decode('utf-8')
                branch_slug, specialization_slug, client_token = decoded.split('~')
            except Exception as e:
                logger.error(f"Failed to decode ref_data: {e}")
                send_whatsapp_text(from_number, "Невірні дані в команді")
                return
            
            # Знаходимо клієнта за токеном
            logger.info(f"Looking for client with token: {client_token}")
            try:
                client = Client.objects.get(api_keys__key=client_token, api_keys__is_active=True)
                logger.info(f"Found client: {client.company_name}")
            except Client.DoesNotExist:
                logger.warning(f"Client not found for token: {client_token}")
                send_whatsapp_text(from_number, "Клієнт не знайдено")
                return
            
            # Шукаємо QR код або стіл
            qr_code = None
            table = None
            
            try:
                qr_code = ClientQRCode.objects.get(
                    client=client,
                    qr_token=table_number,
                    is_active=True
                )
                logger.info(f"Found ClientQRCode: {qr_code.name}")
            except ClientQRCode.DoesNotExist:
                try:
                    table = RestaurantTable.objects.get(
                        client=client,
                        table_number=table_number,
                        is_active=True
                    )
                    logger.info(f"Found RestaurantTable: {table.table_number}")
                except RestaurantTable.DoesNotExist:
                    logger.warning(f"QR code or table not found: {table_number}")
                    send_whatsapp_text(from_number, "QR код або стіл не знайдено")
                    return
            
            # Створюємо або оновлюємо розмову
            conversation, created = ClientWhatsAppConversation.objects.get_or_create(
                customer_phone=from_number,
                client=client,
                qr_code=qr_code,
                table=table,
                is_active=True,
                defaults={
                    'started_at': timezone.now(),
                    'messages': [{
                        'role': 'user',
                        'content': message_body,
                        'timestamp': timezone.now().isoformat()
                    }]
                }
            )
            
            if not created:
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': message_body,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.save()

            # Send universal greeting on first contact
            greeting = getattr(client, 'greeting_message', '') or ''
            if greeting.strip() and created:
                send_whatsapp_text(from_number, greeting.strip(), client=client)
                conversation.messages.append({
                    'role': 'assistant',
                    'content': greeting.strip(),
                    'timestamp': timezone.now().isoformat()
                })
                conversation.total_messages = len(conversation.messages)
                conversation.save(update_fields=['messages', 'total_messages'])

            # Створюємо відповідь
            if qr_code:
                location_name = qr_code.name or qr_code.location or "цей QR код"
                response_text = f"Привіт! Ви зайшли через {location_name} в {client.company_name}. Чим можу допомогти?"
            elif table:
                response_text = f"Привіт! Ви зайшли до столика {table_number} в {client.company_name}. Чим можу допомогти?"
            else:
                response_text = f"Привіт! Вітаємо в {client.company_name}. Чим можу допомогти?"
            
            # Додаємо відповідь до розмови
            if not conversation.messages:
                conversation.messages = []
            conversation.messages.append({
                'role': 'assistant',
                'content': response_text,
                'timestamp': timezone.now().isoformat()
            })
            conversation.save()
            
            logger.info(f"START2 processed successfully: client={client.id}, phone={from_number}")
            
            # Відправляємо повідомлення (пер-клієнтно)
            send_whatsapp_text(from_number, response_text, client=client)
            
        except Exception as e:
            logger.error(f"Error processing START2 command: {str(e)}", exc_info=True)
            send_whatsapp_text(from_number, "Вибачте, виникла помилка. Спробуйте пізніше.")
    
    def handle_regular_message(self, from_number, message_body, client):
        """Обробляє звичайні повідомлення з RAG логікою"""
        try:
            # Якщо клієнт не визначений метаданими, спробуємо знайти за активною розмовою
            conversation = ClientWhatsAppConversation.objects.filter(
                customer_phone=from_number,
                is_active=True
            ).first()
            
            # Backward compatibility
            if not conversation:
                conversation_restaurant = RestaurantConversation.objects.filter(
                    customer_phone=from_number,
                    is_active=True
                ).first()
                if conversation_restaurant:
                    conversation, _ = ClientWhatsAppConversation.objects.get_or_create(
                        customer_phone=from_number,
                        client=conversation_restaurant.client,
                        table=conversation_restaurant.table,
                        is_active=True,
                        defaults={
                            'started_at': conversation_restaurant.started_at,
                            'messages': conversation_restaurant.messages,
                            'total_messages': conversation_restaurant.total_messages,
                        }
                    )
            
            if not conversation:
                response_text = self.generate_rag_response_without_conversation(message_body)
            else:
                response_text = self.generate_rag_response(message_body, conversation)
            
            logger.info(f"Regular message processed: phone={from_number}")
            
            # Відправляємо повідомлення (пер-клієнтно, якщо відомо)
            send_whatsapp_text(from_number, response_text, client=conversation.client if conversation else client)
            
        except Exception as e:
            logger.error(f"Error processing regular message: {str(e)}", exc_info=True)
            send_whatsapp_text(from_number, "Вибачте, виникла помилка. Спробуйте пізніше.")
    
    def generate_rag_response_without_conversation(self, message_body):
        """Генерує відповідь за допомогою RAG без активної розмови"""
        try:
            # Знаходимо клієнта з embeddings (не тільки ресторани)
            client = Client.objects.exclude(
                embeddings__isnull=True
            ).first()
            
            if not client:
                client = Client.objects.first()
            
            if not client:
                return "Привіт! Для початку роботи надішліть команду START2 з QR-коду."
            
            # Використовуємо RAG API
            try:
                from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,
                    stream=False
                )
                
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated (no conversation): {len(response_text)} chars")
                else:
                    response_text = "Вибачте, виникла помилка при генерації відповіді."
                
            except Exception as e:
                logger.error(f"RAG generation failed (no conversation): {str(e)}", exc_info=True)
                response_text = f"Привіт! Як можу допомогти? Надішліть команду START2 з QR-коду для кращої допомоги."
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error in generate_rag_response_without_conversation: {str(e)}", exc_info=True)
            return "Вибачте, виникла помилка. Спробуйте пізніше."
    
    def generate_rag_response(self, message_body, conversation):
        """Генерує відповідь за допомогою RAG для розмови"""
        try:
            client = conversation.client
            
            # HITL: Check if conversation is waiting for manager response
            # NEW ARCHITECTURE: Allow chat to continue, but inform user about pending escalation
            pending_escalation_notice = ""
            if getattr(conversation, 'is_waiting_for_manager', False):
                # Check timeout using escalation_started_at field
                from datetime import timedelta
                timeout_minutes = 10
                escalation_started = getattr(conversation, 'escalation_started_at', None)
                
                if escalation_started and (timezone.now() - escalation_started) > timedelta(minutes=timeout_minutes):
                    # Timeout reached - reset waiting state
                    logger.info(f"HITL: Timeout reached for Meta WhatsApp conversation {conversation.id}, resetting waiting state")
                    lang = getattr(conversation, 'escalation_language', None) or getattr(conversation, 'language', 'en') or 'en'
                    timeout_messages = {
                        'en': "I apologize, but I wasn't able to get confirmation from my colleague in time. Let me try to help you directly.\n\n",
                        'de': "Es tut mir leid, aber ich konnte keine rechtzeitige Bestätigung von meinem Kollegen erhalten. Lassen Sie mich versuchen, Ihnen direkt zu helfen.\n\n",
                        'fr': "Je suis désolé, mais je n'ai pas pu obtenir la confirmation de mon collègue à temps. Permettez-moi d'essayer de vous aider directement.\n\n",
                        'es': "Lo siento, pero no pude obtener la confirmación de mi colega a tiempo. Permítame intentar ayudarle directamente.\n\n",
                        'it': "Mi scuso, ma non sono riuscito a ottenere la conferma dal mio collega in tempo. Permettetemi di provare ad aiutarvi direttamente.\n\n",
                        'nl': "Het spijt me, maar ik kon niet op tijd bevestiging krijgen van mijn collega. Laat me proberen u direct te helpen.\n\n",
                        'da': "Jeg beklager, men jeg kunne ikke få bekræftelse fra min kollega i tide. Lad mig prøve at hjælpe dig direkte.\n\n",
                        'uk': "Вибачте, але я не зміг отримати підтвердження від колеги вчасно. Дозвольте мені спробувати допомогти вам безпосередньо.\n\n",
                        'ru': "Извините, но я не смог получить подтверждение от коллеги вовремя. Позвольте мне попробовать помочь вам напрямую.\n\n",
                    }
                    pending_escalation_notice = timeout_messages.get(lang, timeout_messages['en'])
                    conversation.is_waiting_for_manager = False
                    conversation.manager_escalation_context = ''
                    conversation.escalation_started_at = None
                    conversation.escalation_original_query = ''
                    conversation.escalation_language = ''
                    conversation.save(update_fields=[
                        'is_waiting_for_manager', 
                        'manager_escalation_context', 
                        'escalation_started_at',
                        'escalation_original_query',
                        'escalation_language',
                        'updated_at'
                    ])
                else:
                    # Still within timeout - add a note but continue with normal response
                    waiting_notes = {
                        'en': "(Note: I'm still waiting for confirmation from my colleague on a previous question. I'll update you when I hear back.)\n\n",
                        'de': "(Hinweis: Ich warte noch auf Bestätigung von meinem Kollegen zu einer früheren Frage. Ich melde mich, sobald ich Antwort habe.)\n\n",
                        'fr': "(Note: J'attends toujours la confirmation de mon collègue sur une question précédente. Je vous tiendrai informé.)\n\n",
                        'es': "(Nota: Todavía estoy esperando la confirmación de mi colega sobre una pregunta anterior. Le informaré cuando tenga respuesta.)\n\n",
                        'it': "(Nota: Sto ancora aspettando la conferma dal mio collega su una domanda precedente. La informerò quando avrò notizie.)\n\n",
                        'nl': "(Opmerking: Ik wacht nog op bevestiging van mijn collega over een eerdere vraag. Ik laat het u weten zodra ik iets hoor.)\n\n",
                        'da': "(Bemærk: Jeg venter stadig på bekræftelse fra min kollega om et tidligere spørgsmål. Jeg giver dig besked, når jeg hører noget.)\n\n",
                        'uk': "(Примітка: Я все ще чекаю на підтвердження від колеги щодо попереднього питання. Повідомлю вас, як тільки отримаю відповідь.)\n\n",
                        'ru': "(Примечание: Я всё ещё жду подтверждения от коллеги по предыдущему вопросу. Сообщу вам, когда получу ответ.)\n\n",
                    }
                    lang = getattr(conversation, 'language', 'en') or 'en'
                    pending_escalation_notice = waiting_notes.get(lang, waiting_notes['en'])
            
            from MASTER.clients.tasks import detect_language_from_messages, detect_explicit_language_request
            
            detected_language = detect_language_from_messages([{'role': 'user', 'content': message_body}]) or 'en'
            explicit_lang = detect_explicit_language_request(message_body)
            
            update_fields = []
            
            if detected_language:
                conversation.last_user_language = detected_language
                update_fields.append('last_user_language')
                if detected_language != getattr(conversation, 'language', ''):
                    conversation.language = detected_language
                    update_fields.append('language')
            
            # forced_language зберігається до наступного явного запиту на зміну
            # Якщо знайдено новий явний запит - оновлюємо, якщо ні - залишаємо як є
            if explicit_lang:
                conversation.forced_language = explicit_lang
                update_fields.append('forced_language')
            # Якщо explicit_lang is None - не чіпаємо forced_language (залишаємо попереднє значення)
            
            if update_fields:
                conversation.save(update_fields=update_fields)
            
            # Потік 3: Бот → юзер (без ескалації)
            # Те саме — відповідаємо мовою останнього повідомлення юзера.
            # Виняток: якщо юзер явно написав "говори тільки англійською" — фіксуємо до наступного явного запиту на зміну.
            language = (
                getattr(conversation, 'forced_language', '') or  # Явний запит юзера (найвищий пріоритет)
                getattr(conversation, 'last_user_language', '') or  # Мова останнього повідомлення юзера
                detected_language or
                'en'
            )
            
            # Використовуємо RAG API
            try:
                from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,
                    stream=False,
                    language=language
                )
                
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated: {len(response_text)} chars")

                    # Store RAG sources into conversation.context_metadata for reporting (per answer)
                    try:
                        if isinstance(conversation, ClientWhatsAppConversation):
                            if not conversation.context_metadata or not isinstance(conversation.context_metadata, dict):
                                conversation.context_metadata = {}
                            history = conversation.context_metadata.get('rag_history')
                            if not isinstance(history, list):
                                history = []
                            history.append({
                                'ts': timezone.now().isoformat(),
                                'query': (message_body or '')[:200],
                                'sources': rag_response.sources,
                            })
                            conversation.context_metadata['rag_history'] = history[-50:]
                            conversation.context_metadata['last_rag_sources'] = rag_response.sources
                            conversation.save(update_fields=['context_metadata', 'updated_at'])
                    except Exception as e:
                        logger.warning(f"Failed to store RAG sources for conversation {getattr(conversation, 'id', None)}: {e}")
                    
                    # HITL: Check if escalation is required
                    if rag_response.requires_escalation and getattr(client, 'hitl_enabled', False):
                        manager_ids = client.get_manager_telegram_ids() if hasattr(client, 'get_manager_telegram_ids') else []
                        if manager_ids:
                            # Trigger escalation
                            from MASTER.clients.tasks import notify_manager_of_escalation
                            notify_manager_of_escalation.delay(conversation.id, rag_response.escalation_summary or message_body[:200])
                            logger.info(f"HITL escalation triggered for Meta WhatsApp conversation {conversation.id}")
                    
                    # Matrix HITL (parallel with Telegram)
                    if rag_response.requires_escalation:
                        from MASTER.clients.tasks import send_matrix_escalation
                        escalation_lang = getattr(conversation, 'forced_language', '') or getattr(conversation, 'last_user_language', '') or language or 'en'
                        send_matrix_escalation(conversation, client, "whatsapp", message_body, rag_response.escalation_summary, escalation_lang)
                else:
                    response_text = "Sorry, an error occurred while generating the response."
                
            except Exception as e:
                logger.error(f"RAG generation failed: {str(e)}", exc_info=True)
                response_text = f"Thank you for your message! How can I help you?"
            
            # Add pending escalation notice if there's an active escalation
            if pending_escalation_notice:
                response_text = pending_escalation_notice + response_text
            
            # Зберігаємо повідомлення в розмову
            if isinstance(conversation, ClientWhatsAppConversation):
                conversation.add_message('user', message_body)
                conversation.add_message('assistant', response_text)
            else:
                # Backward compatibility
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': message_body,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.messages.append({
                    'role': 'assistant',
                    'content': response_text,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.save()
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {str(e)}", exc_info=True)
            return "Sorry, an error occurred. Please try again."
    
    def verify_signature(self, ref_data, table_number, signature):
        """Перевіряє HMAC підпис START2 команди"""
        try:
            secret = getattr(settings, 'WHATSAPP_QR_SECRET', '')
            if not secret:
                logger.warning("WHATSAPP_QR_SECRET not configured")
                return False
            
            ref_data_with_padding = ref_data + '=' * (4 - len(ref_data) % 4)
            decoded = base64.urlsafe_b64decode(ref_data_with_padding).decode('utf-8')
            payload = f"{decoded}|{table_number}"
            
            expected_sig = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()[:16]
            
            return hmac.compare_digest(expected_sig, signature)
            
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}", exc_info=True)
            return False