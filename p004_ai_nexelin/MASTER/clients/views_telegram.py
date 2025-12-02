"""
Telegram Bot Integration Views

Handles:
- Telegram webhook for receiving messages
- RAG chat integration
- Conversation management
"""

import json
import logging
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from django.utils import timezone
from django.db.models import Q

from .models import Client, ClientWhatsAppConversation, ClientQRCode
from MASTER.restaurant.models import RestaurantTable, RestaurantConversation

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot"


def escape_html(text: str) -> str:
    """
    Екранує HTML спецсимволи для Telegram parse_mode='HTML'
    """
    if not text:
        return text
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def send_telegram_message(bot_token: str, chat_id: int, message_text: str) -> bool:
    """
    Відправляє повідомлення через Telegram Bot API
    """
    try:
        # Перевіряємо, чи є bot_token
        if not bot_token:
            logger.error(f"Cannot send Telegram message: bot_token is empty for chat_id={chat_id}")
            return False
        
        # Обмежуємо довжину повідомлення (Telegram limit: 4096 символів)
        if len(message_text) > 4096:
            logger.warning(f"Message too long ({len(message_text)} chars), truncating to 4096")
            message_text = message_text[:4093] + "..."
        
        url = f"{TELEGRAM_API_URL}{bot_token}/sendMessage"
        
        # Спочатку пробуємо з HTML parse_mode (екрануємо спецсимволи)
        escaped_text = escape_html(message_text)
        payload = {
            "chat_id": chat_id,
            "text": escaped_text,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        # Якщо 400 помилка (Bad Request) - перевіряємо причину
        if response.status_code == 400:
            error_data = response.json()
            error_description = error_data.get('description', '')
            
            # Якщо це помилка "chat not found", логуємо спеціально
            if 'chat not found' in error_description.lower():
                logger.warning(f"Chat not found: chat_id={chat_id}. User must start the bot first with /start command.")
                return False
            
            # Інакше пробуємо без parse_mode
            logger.warning(f"HTML parse failed, trying without parse_mode. Error: {response.text}")
            payload = {
                "chat_id": chat_id,
                "text": message_text,  # Оригінальний текст без екранування
            }
            response = requests.post(url, json=payload, timeout=10)
        
        response.raise_for_status()
        
        logger.info(f"Telegram message sent successfully: chat_id={chat_id}, length={len(message_text)}")
        return True
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"Failed to send Telegram message to chat_id={chat_id}: {e}")
        if e.response:
            error_data = e.response.json() if e.response.headers.get('content-type') == 'application/json' else {}
            logger.error(f"Telegram API response: {e.response.text}")
            
            # Спеціальна обробка для "chat not found"
            if error_data.get('description') and 'chat not found' in error_data.get('description', '').lower():
                logger.warning(f"User with chat_id={chat_id} has not started the bot yet. They need to send /start first.")
        return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message to chat_id={chat_id}: {e}", exc_info=True)
        return False


def set_telegram_webhook(bot_token: str, webhook_url: str) -> bool:
    """
    Встановлює webhook для Telegram бота
    """
    try:
        # Спочатку видаляємо старий webhook
        delete_telegram_webhook(bot_token)
        
        url = f"{TELEGRAM_API_URL}{bot_token}/setWebhook"
        payload = {
            "url": webhook_url,
            # Не використовуємо secret_token, щоб уникнути конфліктів
            # Клієнта визначаємо через URL параметр або інші методи
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        # Спочатку отримуємо JSON результат
        result = response.json()
        
        # Логування детальної інформації про помилку
        if not result.get('ok'):
            error_description = result.get('description', 'Unknown error')
            logger.error(f"Telegram API error: {error_description}")
            logger.error(f"Full response: {result}")
            return False
        
        logger.info(f"Telegram webhook set successfully: {webhook_url}")
        return True
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error setting Telegram webhook: {str(e)}", exc_info=True)
        try:
            error_detail = e.response.json()
            logger.error(f"Telegram API error details: {error_detail}")
        except:
            pass
        return False
    except Exception as e:
        logger.error(f"Error setting Telegram webhook: {str(e)}", exc_info=True)
        return False


def delete_telegram_webhook(bot_token: str) -> bool:
    """
    Видаляє webhook для Telegram бота
    """
    try:
        url = f"{TELEGRAM_API_URL}{bot_token}/deleteWebhook"
        response = requests.post(url, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            logger.info("Telegram webhook deleted successfully")
            return True
        else:
            logger.error(f"Failed to delete Telegram webhook: {result.get('description', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting Telegram webhook: {str(e)}", exc_info=True)
        return False


@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    """
    Webhook для обробки повідомлень від Telegram Bot
    """
    
    def get(self, request):
        """Telegram перевіряє webhook через GET - відповідаємо OK"""
        return HttpResponse("Telegram webhook is active", status=200)
    
    def head(self, request):
        """Telegram перевіряє webhook через HEAD - відповідаємо OK"""
        return HttpResponse("", status=200)
    
    def post(self, request):
        try:
            # Отримуємо дані з Telegram
            body = request.body.decode('utf-8')
            data = json.loads(body)
            
            logger.info(f"Telegram webhook received: {data}")

            # Визначаємо клієнта за secret_token з webhook-запиту
            client_hint = self._get_client_from_request(request)
            
            # Перевіряємо, чи це оновлення повідомлення
            if 'message' not in data:
                # Може бути інші типи оновлень (callback_query, etc.)
                logger.debug(f"Received non-message update: {data}")
                return HttpResponse("OK")
            
            message = data['message']
            chat_id = message.get('chat', {}).get('id')
            message_text = message.get('text', '')
            from_user = message.get('from', {})
            username = from_user.get('username', '')
            first_name = from_user.get('first_name', '')
            
            logger.info(f"Telegram message: chat_id={chat_id}, text={message_text[:100]}, username={username}")
            
            if not chat_id or not message_text:
                logger.warning("Missing chat_id or message_text")
                return HttpResponse("Missing required fields", status=400)
            
            # Обробляємо /start команду
            if message_text.strip() == '/start':
                return self.handle_start_command(chat_id, username, first_name, client_hint)
            
            # Обробляємо START2 команду
            if message_text.startswith('START2'):
                return self.handle_start2_command(chat_id, message_text, username, first_name, client_hint)
            
            # Обробляємо звичайні повідомлення
            return self.handle_regular_message(chat_id, message_text, username, first_name, client_hint)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Telegram webhook: {e}")
            return HttpResponse("Invalid JSON", status=400)
        except Exception as e:
            logger.error(f"Telegram webhook error: {str(e)}", exc_info=True)
            return HttpResponse("Internal server error", status=500)
    
    def handle_start_command(self, chat_id: int, username: str, first_name: str, client_hint=None):
        """
        Обробляє /start команду
        """
        try:
            logger.info(f"Processing /start command from chat_id={chat_id}, username={username}")
            
            # Визначаємо клієнта (з webhook або перший доступний)
            if client_hint and client_hint.telegram_bot_token:
                client = client_hint
            else:
                client = Client.objects.filter(
                    telegram_enabled=True,
                    telegram_bot_token__isnull=False
                ).first()
            
            if not client:
                logger.warning("No Telegram-enabled client found for /start command")
                return HttpResponse("No client configured", status=500)
            
            # Створюємо або оновлюємо розмову при /start
            # Це важливо для збереження telegram_chat_id
            conversation = ClientWhatsAppConversation.objects.filter(
                client=client
            ).filter(
                Q(telegram_chat_id=str(chat_id)) | Q(customer_phone=f"telegram_{chat_id}")
            ).order_by('-started_at').first()
            
            created = False
            if not conversation:
                conversation = ClientWhatsAppConversation.objects.create(
                    client=client,
                    customer_phone=f"telegram_{chat_id}",
                    telegram_chat_id=str(chat_id),
                    started_at=timezone.now(),
                    messages=[{
                        'role': 'user',
                        'content': '/start',
                        'timestamp': timezone.now().isoformat()
                    }],
                    context_metadata={'platform': 'telegram', 'username': username, 'first_name': first_name}
                )
                created = True
                logger.info(f"Created new conversation for /start: chat_id={chat_id}, conversation_id={conversation.id}")
            else:
                # Оновлюємо існуючу розмову
                updated_fields = []
                if not conversation.telegram_chat_id:
                    conversation.telegram_chat_id = str(chat_id)
                    updated_fields.append('telegram_chat_id')
                if not conversation.customer_phone:
                    conversation.customer_phone = f"telegram_{chat_id}"
                    updated_fields.append('customer_phone')
                if not conversation.context_metadata:
                    conversation.context_metadata = {}
                if conversation.context_metadata.get('platform') != 'telegram':
                    conversation.context_metadata['platform'] = 'telegram'
                    updated_fields.append('context_metadata')
                if not conversation.is_active:
                    conversation.is_active = True
                    updated_fields.append('is_active')
                
                # Додаємо /start повідомлення до історії
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': '/start',
                    'timestamp': timezone.now().isoformat()
                })
                conversation.total_messages = len(conversation.messages)
                updated_fields.extend(['messages', 'total_messages', 'updated_at'])
                
                if updated_fields:
                    conversation.save(update_fields=updated_fields)
                logger.info(f"Updated existing conversation for /start: chat_id={chat_id}, conversation_id={conversation.id}")
            
            # Привітальне повідомлення
            welcome_text = f"Привіт{', ' + first_name if first_name else ''}! 👋\n\n"
            welcome_text += f"Вітаємо в {client.company_name}.\n\n"
            welcome_text += "Для початку роботи, будь ласка:\n"
            welcome_text += "1. Відскануйте QR-код на вашому столику або в закладі\n"
            welcome_text += "2. Або надішліть мені будь-яке питання, і я спробую допомогти!\n\n"
            welcome_text += "Чим можу бути корисним?"
            
            # Відправляємо welcome message
            success = send_telegram_message(client.telegram_bot_token, chat_id, welcome_text)
            
            if success:
                logger.info(f"Welcome message sent to chat_id={chat_id}")
                # Додаємо welcome message до розмови
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'assistant',
                    'content': welcome_text,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.total_messages = len(conversation.messages)
                conversation.save(update_fields=['messages', 'total_messages', 'updated_at'])
            else:
                logger.warning(f"Failed to send welcome message to chat_id={chat_id}")
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error processing /start command: {str(e)}", exc_info=True)
            return HttpResponse("Error processing /start", status=500)
    
    def handle_start2_command(self, chat_id: int, message_text: str, username: str, first_name: str, client_hint=None):
        """
        Обробляє START2 команду з QR-коду
        """
        try:
            # Парсимо START2 команду (аналогічно WhatsApp)
            logger.info(f"Processing START2 command: {message_text}")
            
            parts = message_text.split()
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
                logger.warning(f"Invalid START2 format: {message_text}")
                send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Невірний формат команди START2.")
                return HttpResponse("Invalid START2 format", status=400)
            
            # Перевіряємо підпис
            if not self.verify_signature(ref_data, table_number, signature):
                logger.warning(f"Invalid signature for START2: {message_text}")
                send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Невірний підпис команди.")
                return HttpResponse("Invalid signature", status=400)
            
            # Декодуємо ref_data
            try:
                import base64
                if not ref_data:
                    raise ValueError("ref_data is empty")
                # Додаємо padding якщо потрібно
                ref_data += '=' * (4 - len(ref_data) % 4)
                decoded = base64.urlsafe_b64decode(ref_data).decode('utf-8')
                branch_slug, specialization_slug, client_token = decoded.split('~')
            except Exception as e:
                logger.error(f"Failed to decode ref_data: {e}")
                send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Помилка декодування даних.")
                return HttpResponse("Invalid ref_data", status=400)
            
            # Знаходимо клієнта за токеном
            logger.info(f"Looking for client with token: {client_token}")
            try:
                client = Client.objects.get(api_keys__key=client_token, api_keys__is_active=True)
                logger.info(f"Found client: {client.company_name}")
            except Client.DoesNotExist:
                logger.warning(f"Client not found for token: {client_token}")
                send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Клієнт не знайдено.")
                return HttpResponse("Client not found", status=404)
            
            # Перевіряємо чи увімкнено Telegram для цього клієнта
            if not client.telegram_enabled or not client.telegram_bot_token:
                logger.warning(f"Telegram not enabled for client: {client.id}")
                send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Telegram інтеграція не активна для цього клієнта.")
                return HttpResponse("Telegram not enabled", status=400)
            
            # Спробуємо знайти QR код
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
                    send_telegram_message(client.telegram_bot_token, chat_id, "QR код або столик не знайдено.")
                    return HttpResponse("QR code or table not found", status=404)
            
            # Створюємо або оновлюємо розмову
            # 1) Пробуємо знайти існуючу розмову по telegram_chat_id або старому префіксу customer_phone=telegram_<chat_id>
            conversation = ClientWhatsAppConversation.objects.filter(
                client=client
            ).filter(
                Q(telegram_chat_id=str(chat_id)) | Q(customer_phone=f"telegram_{chat_id}")
            ).order_by('-started_at').first()

            created = False
            if not conversation:
                # 2) Якщо розмови ще немає — створюємо нову
                conversation = ClientWhatsAppConversation.objects.create(
                    client=client,
                    qr_code=qr_code,
                    table=table,
                    customer_phone=f"telegram_{chat_id}",  # зберігаємо для сумісності
                    telegram_chat_id=str(chat_id),
                    started_at=timezone.now(),
                    messages=[{
                        'role': 'user',
                        'content': message_text,
                        'timestamp': timezone.now().isoformat()
                    }],
                    context_metadata={'platform': 'telegram'}
                )
                created = True
            else:
                # 3) Якщо розмова є, але ще немає telegram_chat_id — зберігаємо його
                updated_fields = []
                if not conversation.telegram_chat_id:
                    conversation.telegram_chat_id = str(chat_id)
                    updated_fields.append('telegram_chat_id')
                if not conversation.customer_phone:
                    conversation.customer_phone = f"telegram_{chat_id}"
                    updated_fields.append('customer_phone')
                if not conversation.context_metadata:
                    conversation.context_metadata = {}
                if conversation.context_metadata.get('platform') != 'telegram':
                    conversation.context_metadata['platform'] = 'telegram'
                    updated_fields.append('context_metadata')
                if updated_fields:
                    updated_fields.append('updated_at')
                    conversation.save(update_fields=updated_fields)
            
            # Оновлюємо platform в context_metadata якщо не створено
            if not created:
                if not conversation.context_metadata:
                    conversation.context_metadata = {}
                conversation.context_metadata['platform'] = 'telegram'
                conversation.save(update_fields=['context_metadata', 'updated_at'])
            
            if not created:
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': message_text,
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
            
            # Додаємо відповідь до розмови
            if not conversation.messages:
                conversation.messages = []
            conversation.messages.append({
                'role': 'assistant',
                'content': response_text,
                'timestamp': timezone.now().isoformat()
            })
            conversation.save()
            
            # Відправляємо повідомлення
            send_telegram_message(client.telegram_bot_token, chat_id, response_text)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error processing START2 command: {str(e)}", exc_info=True)
            send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Вибачте, виникла помилка. Спробуйте пізніше.")
            return HttpResponse("Error processing START2", status=500)
    
    def handle_regular_message(self, chat_id: int, message_text: str, username: str, first_name: str, client_hint=None):
        """
        Обробляє звичайні повідомлення з RAG логікою
        """
        try:
            # Визначаємо клієнта
            if client_hint and client_hint.telegram_bot_token:
                client = client_hint
            else:
                client = Client.objects.filter(
                    telegram_enabled=True,
                    telegram_bot_token__isnull=False
                ).first()
            
            if not client:
                logger.warning(f"No Telegram-enabled client found for chat_id={chat_id}")
                return HttpResponse("No client configured", status=500)
            
            # Шукаємо активну розмову
            conversation = ClientWhatsAppConversation.objects.filter(
                client=client
            ).filter(
                Q(telegram_chat_id=str(chat_id)) | Q(customer_phone=f"telegram_{chat_id}")
            ).order_by('-started_at').first()
            
            # Якщо розмови немає, створюємо її
            if not conversation:
                logger.info(f"Creating new conversation for regular message: chat_id={chat_id}")
                conversation = ClientWhatsAppConversation.objects.create(
                    client=client,
                    customer_phone=f"telegram_{chat_id}",
                    telegram_chat_id=str(chat_id),
                    started_at=timezone.now(),
                    messages=[{
                        'role': 'user',
                        'content': message_text,
                        'timestamp': timezone.now().isoformat()
                    }],
                    context_metadata={'platform': 'telegram', 'username': username, 'first_name': first_name}
                )
            else:
                # Оновлюємо context_metadata для Telegram conversations (якщо не встановлено)
                updated_fields = []
                if not conversation.telegram_chat_id:
                    conversation.telegram_chat_id = str(chat_id)
                    updated_fields.append('telegram_chat_id')
                if not conversation.customer_phone:
                    conversation.customer_phone = f"telegram_{chat_id}"
                    updated_fields.append('customer_phone')
                if not conversation.context_metadata:
                    conversation.context_metadata = {}
                if conversation.context_metadata.get('platform') != 'telegram':
                    conversation.context_metadata['platform'] = 'telegram'
                    updated_fields.append('context_metadata')
                if not conversation.is_active:
                    conversation.is_active = True
                    updated_fields.append('is_active')
                
                # Додаємо повідомлення користувача до історії
                if not conversation.messages:
                    conversation.messages = []
                conversation.messages.append({
                    'role': 'user',
                    'content': message_text,
                    'timestamp': timezone.now().isoformat()
                })
                conversation.total_messages = len(conversation.messages)
                updated_fields.extend(['messages', 'total_messages', 'updated_at'])
                
                if updated_fields:
                    conversation.save(update_fields=updated_fields)
            
            # Використовуємо RAG для генерації відповіді
            response_text = self.generate_rag_response(message_text, conversation, chat_id)
            
            logger.info(f"Regular message processed: chat_id={chat_id}, message={message_text[:100]}")
            
            # Відправляємо повідомлення
            bot_token = conversation.client.telegram_bot_token
            if bot_token:
                send_telegram_message(bot_token, chat_id, response_text)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error processing regular message: {str(e)}", exc_info=True)
            send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Вибачте, виникла помилка. Спробуйте пізніше.")
            return HttpResponse("Error processing message", status=500)
    
    def generate_rag_response_without_conversation(self, message_body: str, chat_id: int, client=None) -> str:
        """
        Генерує відповідь за допомогою RAG без активної розмови
        """
        try:
            # Якщо клієнт не переданий з webhook, знаходимо першого клієнта з даними
            if client is None:
                client = Client.objects.filter(
                    telegram_enabled=True,
                    telegram_bot_token__isnull=False
                ).exclude(
                    embeddings__isnull=True
                ).first()
            
            if client is None:
                client = Client.objects.filter(telegram_enabled=True).first()
            
            if not client:
                return "Привіт! Для початку роботи надішліть команду START2 з QR-коду."
            
            # Використовуємо RAG API для генерації відповіді
            try:
                from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,  # type: ignore
                    stream=False
                )
                
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated (no conversation): {len(response_text)} chars, {rag_response.num_chunks} chunks")
                else:
                    logger.error("Unexpected generator response when stream=False")
                    response_text = "Вибачте, виникла помилка при генерації відповіді."
                
            except Exception as e:
                logger.error(f"RAG generation failed (no conversation): {str(e)}", exc_info=True)
                response_text = "Привіт! Як можу допомогти? Надішліть команду START2 з QR-коду для кращої допомоги."
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error in generate_rag_response_without_conversation: {str(e)}", exc_info=True)
            return "Вибачте, виникла помилка. Спробуйте пізніше."
    
    def generate_rag_response(self, message_body: str, conversation: ClientWhatsAppConversation, chat_id: int) -> str:
        """
        Генерує відповідь за допомогою RAG для розмови
        """
        try:
            client = conversation.client
            
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
                
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated: {len(response_text)} chars, {rag_response.num_chunks} chunks")
                else:
                    logger.error("Unexpected generator response when stream=False")
                    response_text = "Вибачте, виникла помилка при генерації відповіді."
                
            except Exception as e:
                logger.error(f"RAG generation failed: {str(e)}", exc_info=True)
                response_text = "Дякую за повідомлення! Як можу допомогти?"
            
            # Зберігаємо повідомлення в розмову
            conversation.add_message('user', message_body)
            conversation.add_message('assistant', response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {str(e)}", exc_info=True)
            return "Вибачте, виникла помилка. Спробуйте ще раз."
    
    def verify_signature(self, ref_data: str, table_number: str, signature: str) -> bool:
        """
        Перевіряє HMAC підпис START2 команди
        """
        try:
            secret = settings.WHATSAPP_QR_SECRET
            if not secret:
                logger.warning("WHATSAPP_QR_SECRET not configured")
                return False
            
            import base64
            import hmac
            import hashlib
            
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
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}", exc_info=True)
            return False
    
    def _get_client_from_request(self, request):
        """
        Витягує Client з webhook-запиту за допомогою secret_token.
        Ми зберігаємо в secret_token сам telegram_bot_token клієнта.
        """
        try:
            # Django 3.2+ має request.headers, але залишимо і META для надійності
            secret_token = getattr(request, "headers", {}).get("X-Telegram-Bot-Api-Secret-Token") or request.META.get(
                "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"
            )
            if not secret_token:
                return None
            client = Client.objects.filter(telegram_bot_token=secret_token).first()
            if not client:
                logger.warning(f"Telegram webhook: client not found for secret_token")
            return client
        except Exception as e:
            logger.error(f"Error getting client from request: {str(e)}", exc_info=True)
            return None
    
    def _get_bot_token_for_chat(self, chat_id: int) -> str:
        """
        Знаходить bot token для чату (через активну розмову або перший доступний)
        """
        try:
            conversation = ClientWhatsAppConversation.objects.filter(
                Q(telegram_chat_id=str(chat_id)) | Q(customer_phone=f"telegram_{chat_id}"),
                is_active=True
            ).first()
            
            if conversation and conversation.client.telegram_bot_token:
                logger.info(f"Found bot token for chat_id={chat_id} via conversation")
                return conversation.client.telegram_bot_token
            
            # Fallback: перший клієнт з увімкненим Telegram
            client = Client.objects.filter(
                telegram_enabled=True,
                telegram_bot_token__isnull=False
            ).first()
            
            if client:
                logger.info(f"Using fallback bot token for chat_id={chat_id} from client: {client.company_name}")
                return client.telegram_bot_token
            
            logger.warning(f"No bot token found for chat_id={chat_id}")
            return ""
        except Exception as e:
            logger.error(f"Error finding bot token for chat_id={chat_id}: {e}", exc_info=True)
            return ""

