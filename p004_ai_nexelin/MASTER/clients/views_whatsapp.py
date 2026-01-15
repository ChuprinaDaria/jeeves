from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
import json
import base64
import hmac
import hashlib
from urllib.parse import unquote
from .models import Client, ClientQRCode, ClientWhatsAppConversation
from MASTER.restaurant.models import RestaurantTable, RestaurantConversation
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
            
            # Спробуємо знайти QR код за qr_token (table_number тепер може бути qr_token)
            qr_code = None
            table = None
            
            try:
                # Спочатку шукаємо ClientQRCode за qr_token
                qr_code = ClientQRCode.objects.get(
                    client=client,
                    qr_token=table_number,
                    is_active=True
                )
                logger.info(f"Found ClientQRCode: {qr_code.name}")
            except ClientQRCode.DoesNotExist:
                # Якщо не знайдено, спробуємо знайти RestaurantTable (backward compatibility)
                try:
                    table = RestaurantTable.objects.get(
                        client=client,
                        table_number=table_number,
                        is_active=True
                    )
                    logger.info(f"Found RestaurantTable: {table.table_number}")
                except RestaurantTable.DoesNotExist:
                    logger.warning(f"QR code or table not found: {table_number} for client {getattr(client, 'id', 'unknown')}")
                    return HttpResponse("QR code or table not found", status=404)
            
            # Створюємо або оновлюємо розмову
            # Використовуємо ClientWhatsAppConversation для всіх клієнтів
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
                # Оновлюємо існуючу розмову
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': message_body,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.save()
            
            # Створюємо відповідь
            if qr_code:
                location_name = qr_code.name or qr_code.location or "цей QR код"
                response_text = f"Привіт! Ви зайшли через {location_name} в {client.company_name}. Чим можу допомогти?"
            elif table:
                response_text = f"Привіт! Ви зайшли до столика {table_number} в {client.company_name}. Чим можу допомогти?"
            else:
                response_text = f"Привіт! Вітаємо в {client.company_name}. Чим можу допомогти?"
            
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
            table_id = getattr(table, 'id', None) if table else None
            logger.info(f"START2 processed successfully: client={getattr(client, 'id', 'unknown')}, qr_code={qr_id}, table={table_id}, phone={from_number}, conversation={getattr(conversation, 'id', 'unknown')}")
            
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
            # Шукаємо активну розмову для цього номера (спочатку ClientWhatsAppConversation, потім RestaurantConversation для сумісності)
            conversation = ClientWhatsAppConversation.objects.filter(
                customer_phone=from_number,
                is_active=True
            ).first()
            
            # Backward compatibility: якщо не знайдено, шукаємо RestaurantConversation
            if not conversation:
                conversation_restaurant = RestaurantConversation.objects.filter(
                    customer_phone=from_number,
                    is_active=True
                ).first()
                if conversation_restaurant:
                    # Конвертуємо RestaurantConversation в ClientWhatsAppConversation
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
            # Знаходимо першого клієнта ресторану з даними
            client = Client.objects.filter(
                client_type='restaurant'
            ).exclude(
                embeddings__isnull=True
            ).first()
            
            if not client:
                # Якщо немає клієнтів з даними, використовуємо будь-якого ресторанного клієнта
                client = Client.objects.filter(client_type='restaurant').first()
            
            if not client:
                return "Привіт! Для початку роботи надішліть команду START2 з QR-коду столика."
            
            # Використовуємо RAG API для генерації відповіді
            try:
                from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
                
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
            
            # Перевіряємо чи це ClientWhatsAppConversation
            is_client_conversation = isinstance(conversation, ClientWhatsAppConversation)
            
            # HITL: Check if conversation is waiting for manager response
            if getattr(conversation, 'is_waiting_for_manager', False):
                waiting_messages = {
                    'en': "I'm still waiting for confirmation from my colleague. Please hold on, I'll get back to you shortly.",
                    'de': "Ich warte noch auf die Bestätigung von meinem Kollegen. Bitte warten Sie einen Moment.",
                    'fr': "J'attends toujours la confirmation de mon collègue. Veuillez patienter.",
                    'es': "Sigo esperando la confirmación de un colega. Por favor, espere un momento; le responderé en breve.",
                    'it': "Sto ancora aspettando la conferma dal mio collega. Attenda un momento per favore.",
                    'nl': "Ik wacht nog op bevestiging van mijn collega. Even geduld alstublieft.",
                    'da': "Jeg venter stadig på bekræftelse fra min kollega. Vent venligst et øjeblik.",
                    'uk': "I'm still checking with my colleague. Please wait a moment.",
                }
                lang = getattr(conversation, 'language', 'en') or 'en'
                return waiting_messages.get(lang, waiting_messages['en'])
            
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
                from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,  # type: ignore
                    stream=False
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
                            from MASTER.clients.tasks import notify_manager_of_escalation
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
            
            # Зберігаємо повідомлення в розмову
            # Використовуємо метод add_message якщо це ClientWhatsAppConversation
            if is_client_conversation:
                conversation.add_message('user', message_body)
                conversation.add_message('assistant', response_text)
            else:
                # Backward compatibility для RestaurantConversation
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
