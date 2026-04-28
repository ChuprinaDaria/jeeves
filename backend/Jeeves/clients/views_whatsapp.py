from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
import json
import base64
import hmac
import hashlib
from urllib.parse import unquote
from .models import Client, ClientQRCode, ClientWhatsAppConversation
from django.utils import timezone
import logging
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


def send_whatsapp_message(to_number, message_text):
    """
    Відправляє повідомлення через Twilio WhatsApp API
    """
    try:
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Очищаємо номер від зайвих пробілів та форматуємо для WhatsApp
        to_number = to_number.strip()
        if not to_number.startswith('whatsapp:'):
            to_number = f"whatsapp:{to_number}"
        
        # Відправляємо повідомлення
        message = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body=message_text
        )
        
        logger.info(f"WhatsApp message sent successfully: SID={message.sid}, to={to_number}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}", exc_info=True)
        return False


@method_decorator(csrf_exempt, name='dispatch')
class TwilioWhatsAppWebhookView(View):
    """
    Webhook для обробки повідомлень від Twilio WhatsApp
    """
    
    def post(self, request):
        try:
            # Отримуємо дані з Twilio
            body = request.body.decode('utf-8')
            data = request.POST
            
            # Логуємо вхідні дані для дебагу
            logger.info(f"WhatsApp webhook received: {data}")
            
            # Перевіряємо, чи це статус доставки
            message_status = data.get('MessageStatus')
            if message_status:
                logger.info(f"Message status update: {message_status}")
                return HttpResponse("OK")
            
            # Отримуємо номер телефону та повідомлення
            from_number = data.get('From', '').replace('whatsapp:', '').strip()
            # Видаляємо всі пробіли та перевіряємо формат
            from_number = from_number.replace(' ', '')
            if from_number and not from_number.startswith('+'):
                from_number = '+' + from_number
            message_body = unquote(data.get('Body', ''))
            
            logger.info(f"Parsed: from_number={from_number}, message_body={message_body}")
            
            if not from_number or not message_body:
                logger.warning("Missing from_number or message_body")
                return HttpResponse("Missing required fields", status=400)
            
            # Обробляємо START2 команду
            if message_body.startswith('START2'):
                return self.handle_start2_command(from_number, message_body)
            
            # Обробляємо звичайні повідомлення
            return self.handle_regular_message(from_number, message_body)
            
        except Exception as e:
            logger.error(f"WhatsApp webhook error: {str(e)}", exc_info=True)
            return HttpResponse("Internal server error", status=500)
    
    def handle_start2_command(self, from_number, message_body):
        """
        Обробляє START2 команду з QR-коду
        """
        try:
            # Парсимо START2 команду
            # Формат: START2 ref=<base64> tbl=<table_number> sig=<hmac>
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
                return HttpResponse("Invalid START2 format", status=400)
            
            # Перевіряємо підпис
            if not self.verify_signature(ref_data, table_number, signature):
                logger.warning(f"Invalid signature for START2: {message_body}")
                return HttpResponse("Invalid signature", status=400)
            
            # Декодуємо ref_data
            try:
                if not ref_data:
                    raise ValueError("ref_data is empty")
                # Додаємо padding якщо потрібно
                ref_data += '=' * (4 - len(ref_data) % 4)
                decoded = base64.urlsafe_b64decode(ref_data).decode('utf-8')
                branch_slug, specialization_slug, client_token = decoded.split('~')
            except Exception as e:
                logger.error(f"Failed to decode ref_data: {e}")
                return HttpResponse("Invalid ref_data", status=400)
            
            # Знаходимо клієнта за токеном
            logger.info(f"Looking for client with token: {client_token}")
            try:
                client = Client.objects.get(api_keys__key=client_token, api_keys__is_active=True)
                logger.info(f"Found client: {client.company_name}")
            except Client.DoesNotExist:
                logger.warning(f"Client not found for token: {client_token}")
                return HttpResponse("Client not found", status=404)
            
            # Шукаємо QR код за qr_token
            qr_code = None
            
            try:
                # Шукаємо ClientQRCode за qr_token
                qr_code = ClientQRCode.objects.get(
                    client=client,
                    qr_token=table_number,
                    is_active=True
                )
                logger.info(f"Found ClientQRCode: {qr_code.name}")
            except ClientQRCode.DoesNotExist:
                logger.warning(f"QR code not found: {table_number} for client {getattr(client, 'id', 'unknown')}")
                return HttpResponse("QR code not found", status=404)
            
            # Створюємо або оновлюємо розмову
            conversation, created = ClientWhatsAppConversation.objects.get_or_create(
                customer_phone=from_number,
                client=client,
                qr_code=qr_code,
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
                # Оновлюємо існуючу розмову
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': message_body,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.save()
            
            # Створюємо відповідь (language based on client.notification_language)
            lang = getattr(client, 'notification_language', 'en') or 'en'
            location_fallback = {
                'en': "this QR code",
                'de': "diesen QR-Code",
                'fr': "ce QR code",
                'es': "este código QR",
                'it': "questo QR code",
                'nl': "deze QR-code",
                'da': "denne QR-kode",
            }
            if qr_code:
                location_name = qr_code.name or qr_code.location or location_fallback.get(lang, location_fallback['en'])
                templates = {
                    'en': "Hi! You entered via {location} at {company}. How can I help?",
                    'de': "Hallo! Sie sind über {location} bei {company} eingestiegen. Wie kann ich helfen?",
                    'fr': "Bonjour ! Vous êtes entré via {location} chez {company}. Comment puis-je vous aider ?",
                    'es': "¡Hola! Entraste a través de {location} en {company}. ¿En qué puedo ayudarte?",
                    'it': "Ciao! Sei entrato tramite {location} da {company}. Come posso aiutarti?",
                    'nl': "Hallo! Je bent via {location} bij {company} binnengekomen. Hoe kan ik helpen?",
                    'da': "Hej! Du kom ind via {location} hos {company}. Hvordan kan jeg hjælpe?",
                }
                response_text = templates.get(lang, templates['en']).format(
                    location=location_name, company=client.company_name
                )
            else:
                templates = {
                    'en': "Hi! Welcome to {company}. How can I help?",
                    'de': "Hallo! Willkommen bei {company}. Wie kann ich helfen?",
                    'fr': "Bonjour ! Bienvenue chez {company}. Comment puis-je vous aider ?",
                    'es': "¡Hola! Bienvenido/a a {company}. ¿En qué puedo ayudarte?",
                    'it': "Ciao! Benvenuto/a in {company}. Come posso aiutarti?",
                    'nl': "Hallo! Welkom bij {company}. Hoe kan ik helpen?",
                    'da': "Hej! Velkommen hos {company}. Hvordan kan jeg hjælpe?",
                }
                response_text = templates.get(lang, templates['en']).format(company=client.company_name)
            
            # Додаємо відповідь асистента до розмови
            if not conversation.messages:
                conversation.messages = []
            conversation.messages.append({
                'role': 'assistant',
                'content': response_text,
                'timestamp': timezone.now().isoformat()
            })
            conversation.save()
            
            # Логуємо успішну обробку
            qr_id = getattr(qr_code, 'id', None) if qr_code else None
            logger.info(f"START2 processed successfully: client={getattr(client, 'id', 'unknown')}, qr_code={qr_id}, phone={from_number}, conversation={getattr(conversation, 'id', 'unknown')}")
            
            # ВІДПРАВЛЯЄМО ПОВІДОМЛЕННЯ ЧЕРЕЗ TWILIO API
            send_whatsapp_message(from_number, response_text)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error processing START2 command: {str(e)}", exc_info=True)
            return HttpResponse("Error processing START2", status=500)
    
    def handle_regular_message(self, from_number, message_body):
        """
        Обробляє звичайні повідомлення (не START2) з RAG логікою
        """
        try:
            # Шукаємо активну розмову для цього номера
            conversation = ClientWhatsAppConversation.objects.filter(
                customer_phone=from_number,
                is_active=True
            ).first()

            if not conversation:
                # Якщо немає активної розмови, використовуємо RAG з першим доступним клієнтом
                response_text = self.generate_rag_response_without_conversation(message_body)
            else:
                # Використовуємо RAG для генерації відповіді
                response_text = self.generate_rag_response(message_body, conversation)
            
            logger.info(f"Regular message processed: phone={from_number}, message={message_body[:100]}")
            
            # ВІДПРАВЛЯЄМО ПОВІДОМЛЕННЯ ЧЕРЕЗ TWILIO API
            send_whatsapp_message(from_number, response_text)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error processing regular message: {str(e)}", exc_info=True)
            return HttpResponse("Error processing message", status=500)
    
    def generate_rag_response_without_conversation(self, message_body):
        """
        Генерує відповідь за допомогою RAG без активної розмови
        """
        try:
            # Знаходимо першого клієнта з даними
            client = Client.objects.exclude(
                embeddings__isnull=True
            ).first()

            if not client:
                client = Client.objects.first()

            if not client:
                return "Привіт! Для початку роботи надішліть команду START2 з QR-коду."
            
            # Використовуємо RAG API для генерації відповіді
            try:
                from Jeeves.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,  # type: ignore
                    stream=False
                )
                
                # Перевіряємо, що отримали RAGResponse, а не генератор
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated (no conversation): {len(response_text)} chars, {rag_response.num_chunks} chunks")
                else:
                    logger.error("Unexpected generator response when stream=False")
                    response_text = "Вибачте, виникла помилка при генерації відповіді."
                
            except Exception as e:
                logger.error(f"RAG generation failed (no conversation): {str(e)}", exc_info=True)
                # Фолбек на просту логіку
                if any(word in message_body.lower() for word in ['меню', 'menu', 'їжа', 'страви']):
                    response_text = f"Ось наше меню! У нас є смачні страви. Чи хочете щось конкретне?"
                elif any(word in message_body.lower() for word in ['замовлення', 'order', 'замовити']):
                    response_text = f"Звичайно! Що б ви хотіли замовити?"
                else:
                    response_text = f"Привіт! Як можу допомогти? Надішліть команду START2 з QR-коду для кращої допомоги."
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error in generate_rag_response_without_conversation: {str(e)}", exc_info=True)
            return "Вибачте, виникла помилка. Спробуйте пізніше."

    def generate_rag_response(self, message_body, conversation):
        """
        Генерує відповідь за допомогою RAG для ClientWhatsAppConversation
        """
        try:
            # Отримуємо клієнта з розмови
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
                    logger.info(f"HITL: Timeout reached for WhatsApp conversation {conversation.id}, resetting waiting state")
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
            
            from Jeeves.clients.tasks import detect_language_from_messages, detect_explicit_language_request
            detected_language = detect_language_from_messages([{'role': 'user', 'content': message_body}]) or 'en'
            explicit_lang = detect_explicit_language_request(message_body)
            lang_fields = []
            conversation.last_user_language = detected_language
            lang_fields.append('last_user_language')
            # forced_language зберігається до наступного явного запиту на зміну
            # Якщо знайдено новий явний запит - оновлюємо, якщо ні - залишаємо як є
            if explicit_lang:
                conversation.forced_language = explicit_lang
                lang_fields.append('forced_language')
            # Якщо explicit_lang is None - не чіпаємо forced_language (залишаємо попереднє значення)
            conversation.save(update_fields=lang_fields)
            # Потік 3: Бот → юзер (без ескалації)
            # Те саме — відповідаємо мовою останнього повідомлення юзера.
            # Виняток: якщо юзер явно написав "говори тільки англійською" — фіксуємо до наступного явного запиту на зміну.
            language = (
                getattr(conversation, 'forced_language', '') or  # Явний запит юзера (найвищий пріоритет)
                getattr(conversation, 'last_user_language', '') or  # Мова останнього повідомлення юзера
                detected_language or
                'en'
            )

            # Формуємо контекст з історії розмови
            context_messages = []
            if conversation.messages:
                for msg in conversation.messages[-10:]:  # Останні 10 повідомлень
                    context_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
            
            # Додаємо поточне повідомлення
            context_messages.append({
                'role': 'user',
                'content': message_body
            })
            
            # Використовуємо RAG API для генерації відповіді
            try:
                from Jeeves.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,  # type: ignore
                    stream=False,
                    language=language,
                )

                # Перевіряємо, що отримали RAGResponse, а не генератор
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated: {len(response_text)} chars, {rag_response.num_chunks} chunks")

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
                            from Jeeves.clients.tasks import notify_manager_of_escalation
                            notify_manager_of_escalation.delay(conversation.id, rag_response.escalation_summary or message_body[:200])
                            logger.info(f"HITL escalation triggered for WhatsApp conversation {conversation.id}")
                    
                else:
                    # Це не повинно статися з stream=False, але для безпеки
                    logger.error("Unexpected generator response when stream=False")
                    response_text = "Sorry, an error occurred while generating the response."
                
            except Exception as e:
                logger.error(f"RAG generation failed: {str(e)}", exc_info=True)
                # Fallback logic
                if any(word in message_body.lower() for word in ['menu', 'food', 'dishes']):
                    response_text = f"Here's our menu! We have delicious dishes. Would you like something specific?"
                elif any(word in message_body.lower() for word in ['order', 'book']):
                    response_text = f"Of course! What would you like to order?"
                elif any(word in message_body.lower() for word in ['bill', 'payment', 'check']):
                    response_text = f"I'll bring the bill! Is there anything else you need?"
                else:
                    response_text = f"Thank you for your message! How can I help you?"
            
            # Add pending escalation notice if there's an active escalation
            if pending_escalation_notice:
                response_text = pending_escalation_notice + response_text
            
            # Зберігаємо повідомлення в розмову
            conversation.add_message('user', message_body)
            conversation.add_message('assistant', response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {str(e)}", exc_info=True)
            return "Вибачте, виникла помилка. Спробуйте ще раз."
    
    def verify_signature(self, ref_data, table_number, signature):
        """
        Перевіряє HMAC підпис START2 команди
        """
        try:
            secret = settings.WHATSAPP_QR_SECRET
            if not secret:
                logger.warning("WHATSAPP_QR_SECRET not configured")
                return False
            
            logger.info(f"Verifying signature: ref_data={ref_data}, table_number={table_number}, signature={signature}")
            
            # Відновлюємо оригінальні дані
            ref_data_with_padding = ref_data + '=' * (4 - len(ref_data) % 4)
            decoded = base64.urlsafe_b64decode(ref_data_with_padding).decode('utf-8')
            
            # Створюємо payload для перевірки
            payload = f"{decoded}|{table_number}"
            
            # Обчислюємо HMAC
            expected_sig = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()[:16]
            
            logger.info(f"Signature verification: expected={expected_sig}, received={signature}")
            result = hmac.compare_digest(signature, expected_sig)
            logger.info(f"Signature verification result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}", exc_info=True)
            return False
