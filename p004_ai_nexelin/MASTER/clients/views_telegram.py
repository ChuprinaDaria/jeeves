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


def get_rating_message(language: str, rating: str) -> tuple[str, str]:
    """
    Повертає перекладені фрази для оцінки бесіди на основі мови користувача.
    
    Args:
        language: Код мови (uk, en, de, fr, es, it, nl, da)
        rating: Тип оцінки ('positive' або 'negative')
    
    Returns:
        tuple: (rating_text, confirmation_text) - фрази для callback та підтвердження
    """
    # Словник перекладів для фраз оцінки
    rating_translations = {
        'uk': {
            'positive': ('👍 Дякуємо за позитивну оцінку!', '✅ Ви оцінили розмову: 👍'),
            'negative': ('👎 Дякуємо за відгук!', '✅ Ви оцінили розмову: 👎'),
        },
        'en': {
            'positive': ('👍 Thank you for your positive rating!', '✅ You rated the conversation: 👍'),
            'negative': ('👎 Thank you for your feedback!', '✅ You rated the conversation: 👎'),
        },
        'de': {
            'positive': ('👍 Vielen Dank für Ihre positive Bewertung!', '✅ Sie haben die Unterhaltung bewertet: 👍'),
            'negative': ('👎 Vielen Dank für Ihr Feedback!', '✅ Sie haben die Unterhaltung bewertet: 👎'),
        },
        'fr': {
            'positive': ('👍 Merci pour votre évaluation positive !', '✅ Vous avez évalué la conversation : 👍'),
            'negative': ('👎 Merci pour vos commentaires !', '✅ Vous avez évalué la conversation : 👎'),
        },
        'es': {
            'positive': ('👍 ¡Gracias por su evaluación positiva!', '✅ Ha calificado la conversación: 👍'),
            'negative': ('👎 ¡Gracias por sus comentarios!', '✅ Ha calificado la conversación: 👎'),
        },
        'it': {
            'positive': ('👍 Grazie per la tua valutazione positiva!', '✅ Hai valutato la conversazione: 👍'),
            'negative': ('👎 Grazie per il tuo feedback!', '✅ Hai valutato la conversazione: 👎'),
        },
        'nl': {
            'positive': ('👍 Bedankt voor uw positieve beoordeling!', '✅ U heeft het gesprek beoordeeld: 👍'),
            'negative': ('👎 Bedankt voor uw feedback!', '✅ U heeft het gesprek beoordeeld: 👎'),
        },
        'da': {
            'positive': ('👍 Tak for din positive vurdering!', '✅ Du har vurderet samtalen: 👍'),
            'negative': ('👎 Tak for din feedback!', '✅ Du har vurderet samtalen: 👎'),
        },
    }
    
    # Отримуємо переклади для вказаної мови або використовуємо англійську як fallback
    lang_translations = rating_translations.get(language, rating_translations.get('en'))
    rating_text, confirmation_text = lang_translations.get(rating, lang_translations['positive'])
    
    return rating_text, confirmation_text


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


def set_telegram_webhook(bot_token: str, webhook_url: str, secret_token: str = None) -> bool:
    """
    Встановлює webhook для Telegram бота
    
    Args:
        bot_token: Telegram Bot Token
        webhook_url: Webhook URL (може містити ?tag= для ідентифікації клієнта)
        secret_token: Secret token для безпеки (опціонально, використовується client.tag)
    """
    try:
        # Спочатку видаляємо старий webhook
        delete_telegram_webhook(bot_token)
        
        url = f"{TELEGRAM_API_URL}{bot_token}/setWebhook"
        payload = {
            "url": webhook_url,
        }
        
        # Додаємо secret_token якщо він переданий (для безпеки та ідентифікації клієнта)
        if secret_token:
            payload["secret_token"] = secret_token
        
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
            # Store client_hint for use in helper methods
            self._current_client_hint = client_hint
            
            # Перевіряємо, чи це callback_query (натискання на кнопки)
            if 'callback_query' in data:
                return self.handle_callback_query(data['callback_query'], client_hint)
            
            # Перевіряємо, чи це оновлення повідомлення
            if 'message' not in data:
                # Може бути інші типи оновлень
                logger.debug(f"Received non-message update: {data}")
                return HttpResponse("OK")
            
            # Check if this is a manager reply to an escalation
            message = data['message']
            reply_to = message.get('reply_to_message')
            from_user = message.get('from', {})
            sender_id = from_user.get('id')
            
            # First, check if this is a reply to an escalation message
            if reply_to and client_hint:
                manager_result = self.handle_manager_reply(message, reply_to, client_hint)
                if manager_result:
                    return manager_result
            
            # Second, check if sender is a manager with ANY waiting conversation (even without reply)
            # This handles cases where manager just types a response without using Telegram's "Reply"
            if sender_id and client_hint:
                manager_result = self.handle_manager_direct_message(message, sender_id, client_hint)
                if manager_result:
                    return manager_result
            
            chat_id = message.get('chat', {}).get('id')
            message_text = message.get('text', '')
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
            
            # Генеруємо привітальне повідомлення з використанням промпту клієнта
            welcome_text = self._generate_welcome_message(client, first_name)
            
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
        # Store client_hint for use in _get_bot_token_for_chat
        self._current_client_hint = client_hint
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
            
            # Генеруємо привітання через RAG і промпт клієнта
            response_text = self._generate_welcome_message(client, first_name)
            
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
                now = timezone.now()
                # Detect language from first message
                from MASTER.clients.tasks import detect_language_from_messages
                initial_messages = [{'role': 'user', 'content': message_text}]
                detected_language = detect_language_from_messages(initial_messages)
                
                conversation = ClientWhatsAppConversation.objects.create(
                    client=client,
                    customer_phone=f"telegram_{chat_id}",
                    telegram_chat_id=str(chat_id),
                    started_at=now,
                    last_activity_at=now,  # Встановлюємо last_activity_at при створенні
                    language=detected_language,  # Встановлюємо мову при створенні
                    messages=[{
                        'role': 'user',
                        'content': message_text,
                        'timestamp': now.isoformat()
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
                # Оновлюємо last_activity_at для відстеження неактивності
                conversation.last_activity_at = timezone.now()
                
                # Detect and update language if not set or was default
                if not conversation.language or conversation.language == 'uk':
                    from MASTER.clients.tasks import detect_language_from_messages
                    detected_language = detect_language_from_messages(conversation.messages)
                    conversation.language = detected_language
                    updated_fields.append('language')
                
                updated_fields.extend(['messages', 'total_messages', 'updated_at', 'last_activity_at'])
                
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
    
    def handle_manager_reply(self, message, reply_to, client_hint):
        """
        Handle manager's reply to an HITL escalation message.
        
        Returns HttpResponse if this was a manager reply, None otherwise.
        """
        try:
            from_user = message.get('from', {})
            sender_id = from_user.get('id')
            message_text = message.get('text', '')
            reply_message_id = reply_to.get('message_id')
            
            logger.info(f"HITL: Checking if message is manager reply: sender_id={sender_id}, reply_to_msg_id={reply_message_id}")
            
            if not sender_id or not message_text or not reply_message_id:
                logger.debug(f"HITL: Missing data - sender_id={sender_id}, text={bool(message_text)}, reply_id={reply_message_id}")
                return None
            
            # Check if sender is a manager for this client
            manager_ids = client_hint.get_manager_telegram_ids() if hasattr(client_hint, 'get_manager_telegram_ids') else []
            logger.info(f"HITL: Client {client_hint.id if client_hint else 'None'} manager_ids={manager_ids}, sender_id={sender_id}")
            
            if sender_id not in manager_ids:
                logger.info(f"HITL: Sender {sender_id} is NOT in manager list {manager_ids}, checking other clients...")
                
                # Try to find ANY client where this sender is a manager with a waiting conversation
                from MASTER.clients.models import Client
                for client in Client.objects.filter(hitl_enabled=True):
                    client_manager_ids = client.get_manager_telegram_ids()
                    if sender_id in client_manager_ids:
                        # Found a client where sender is a manager, check for waiting conversations
                        conv = ClientWhatsAppConversation.objects.filter(
                            client=client,
                            is_waiting_for_manager=True,
                            last_escalation_message_id=str(reply_message_id)
                        ).first()
                        if conv:
                            logger.info(f"HITL: Found waiting conversation {conv.id} for manager {sender_id} on client {client.id}")
                            client_hint = client
                            manager_ids = client_manager_ids
                            break
                
                if sender_id not in manager_ids:
                    logger.debug(f"HITL: Sender {sender_id} is not a manager for any client")
                    return None  # Not a manager, process as regular message
            
            # Find conversation waiting for this manager's response
            conversation = ClientWhatsAppConversation.objects.filter(
                client=client_hint,
                is_waiting_for_manager=True,
                last_escalation_message_id=str(reply_message_id)
            ).first()
            
            logger.info(f"HITL: Looking for conversation with client={client_hint.id}, waiting=True, escalation_msg_id={reply_message_id}")
            
            if not conversation:
                # Also try to find by escalation_manager_id
                conversation = ClientWhatsAppConversation.objects.filter(
                    client=client_hint,
                    is_waiting_for_manager=True,
                    escalation_manager_id=str(sender_id)
                ).first()
                logger.info(f"HITL: Fallback search by escalation_manager_id={sender_id}, found={conversation is not None}")
            
            if not conversation:
                logger.warning(f"HITL: No waiting conversation found for manager {sender_id} reply to message {reply_message_id}")
                return None  # No matching escalation found
            
            # Process the manager's response
            from MASTER.clients.tasks import process_manager_hitl_response
            
            logger.info(f"Manager {sender_id} replied to escalation for conversation {conversation.id}")
            
            # Send confirmation to manager
            bot_token = client_hint.telegram_bot_token
            if bot_token:
                chat_id = message.get('chat', {}).get('id')
                confirm_msg = f"✅ Got it! Processing your response and sending to the customer..."
                send_telegram_message(bot_token, chat_id, confirm_msg)
            
            # Process asynchronously
            process_manager_hitl_response.delay(conversation.id, message_text, sender_id)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error handling manager reply: {e}", exc_info=True)
            return None
    
    def handle_manager_direct_message(self, message, sender_id, client_hint):
        """
        Handle manager's direct message (not a reply) when there's a waiting conversation.
        
        This handles cases where manager just types their response without using 
        Telegram's "Reply" feature.
        
        Returns HttpResponse if this was a manager message for escalation, None otherwise.
        """
        try:
            message_text = message.get('text', '')
            if not message_text:
                return None
            
            # Check if sender is a manager for this client or any HITL-enabled client
            from MASTER.clients.models import Client
            
            manager_client = None
            manager_ids = []
            
            # First check current client_hint
            if client_hint and hasattr(client_hint, 'get_manager_telegram_ids'):
                manager_ids = client_hint.get_manager_telegram_ids()
                if sender_id in manager_ids:
                    manager_client = client_hint
            
            # If not found, search all HITL-enabled clients
            if not manager_client:
                for client in Client.objects.filter(hitl_enabled=True):
                    client_manager_ids = client.get_manager_telegram_ids()
                    if sender_id in client_manager_ids:
                        manager_client = client
                        manager_ids = client_manager_ids
                        break
            
            if not manager_client:
                return None  # Not a manager
            
            # Find the most recent conversation waiting for this manager's response
            conversation = ClientWhatsAppConversation.objects.filter(
                client=manager_client,
                is_waiting_for_manager=True,
                escalation_manager_id=str(sender_id)
            ).order_by('-updated_at').first()
            
            if not conversation:
                # Try any waiting conversation for this client
                conversation = ClientWhatsAppConversation.objects.filter(
                    client=manager_client,
                    is_waiting_for_manager=True
                ).order_by('-updated_at').first()
            
            if not conversation:
                logger.debug(f"HITL: Manager {sender_id} sent message but no waiting conversations found")
                return None
            
            logger.info(f"HITL: Manager {sender_id} sent direct message for conversation {conversation.id}")
            
            # Process the manager's response
            from MASTER.clients.tasks import process_manager_hitl_response
            
            # Send confirmation to manager
            bot_token = manager_client.telegram_bot_token
            if bot_token:
                chat_id = message.get('chat', {}).get('id')
                customer_id = conversation.customer_phone or conversation.telegram_chat_id or f"Conv #{conversation.id}"
                confirm_msg = f"✅ Got it! Sending your response to customer {customer_id}..."
                send_telegram_message(bot_token, chat_id, confirm_msg)
            
            # Process asynchronously
            process_manager_hitl_response.delay(conversation.id, message_text, sender_id)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error handling manager direct message: {e}", exc_info=True)
            return None
    
    def handle_callback_query(self, callback_query, client_hint=None):
        """
        Обробляє callback_query від Telegram (натискання на кнопки)
        """
        try:
            from django.utils import timezone
            from MASTER.clients.models import ClientWhatsAppConversation
            import requests
            
            callback_data = callback_query.get('data', '')
            chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
            message_id = callback_query.get('message', {}).get('message_id')
            
            logger.info(f"Telegram callback_query: chat_id={chat_id}, data={callback_data}")
            
            # Обробляємо оцінку: rate_{conversation_id}_{rating}
            if callback_data.startswith('rate_'):
                parts = callback_data.split('_')
                if len(parts) == 3:
                    conversation_id = int(parts[1])
                    rating = parts[2]  # 'positive' or 'negative'
                    
                    try:
                        # CRITICAL: Filter by client for security - sandbox chats must not leak
                        # Get client from callback query if not provided
                        if not client_hint:
                            # Try to get client from chat_id
                            from MASTER.clients.models import Client
                            temp_conv = ClientWhatsAppConversation.objects.filter(
                                Q(telegram_chat_id=str(chat_id)) | Q(customer_phone=f"telegram_{chat_id}")
                            ).first()
                            if temp_conv:
                                client_hint = temp_conv.client
                        
                        if not client_hint:
                            logger.error(f"Security violation: cannot determine client for conversation {conversation_id}")
                            return HttpResponse("Unauthorized", status=403)
                        
                        # Get conversation with client filter for security
                        conversation = ClientWhatsAppConversation.objects.get(id=conversation_id, client=client_hint)
                        
                        # Оновлюємо оцінку
                        conversation.user_rating = rating
                        conversation.rating_timestamp = timezone.now()
                        conversation.save(update_fields=['user_rating', 'rating_timestamp'])
                        
                        # Smart alert: immediate email ONLY for negative rating (critical)
                        if rating == 'negative':
                            from MASTER.clients.tasks import close_session_and_send_email
                            try:
                                close_session_and_send_email.delay(conversation.id, force_send=True)
                                logger.info(
                                    f"🔴 Negative rating received for Telegram conversation {conversation_id}, scheduling urgent email"
                                )
                            except Exception as e:
                                logger.error(f"Failed to schedule email for negative rating: {e}")
                        
                        # Відправляємо підтвердження користувачу мовою користувача
                        bot_token = conversation.client.telegram_bot_token
                        if bot_token:
                            # Отримуємо мову користувача з conversation або використовуємо 'en' як fallback
                            user_language = conversation.language or 'en'
                            rating_text, confirmation_text = get_rating_message(user_language, rating)
                            
                            # Відправляємо callback answer (підказка при натисканні кнопки)
                            url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
                            callback_response = requests.post(url, json={
                                "callback_query_id": callback_query.get('id'),
                                "text": rating_text,
                                "show_alert": False
                            }, timeout=10)
                            
                            # Оновлюємо повідомлення з оцінкою мовою користувача
                            url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
                            edit_response = requests.post(url, json={
                                "chat_id": chat_id,
                                "message_id": message_id,
                                "text": confirmation_text,
                            }, timeout=10)
                            
                            # Також відправляємо нове повідомлення з підтвердженням оцінки
                            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            send_response = requests.post(url, json={
                                "chat_id": chat_id,
                                "text": rating_text,
                            }, timeout=10)
                            
                            if send_response.status_code != 200:
                                logger.error(f"Failed to send rating confirmation message to Telegram: {send_response.text}")
                            else:
                                logger.info(f"Rating confirmation sent to Telegram chat {chat_id} for conversation {conversation_id}")
                        
                        logger.info(f"Rating saved: conversation_id={conversation_id}, rating={rating}")
                        return HttpResponse("OK")
                        
                    except ClientWhatsAppConversation.DoesNotExist:
                        logger.error(f"Conversation {conversation_id} not found for callback")
                        return HttpResponse("Conversation not found", status=404)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error handling callback_query: {str(e)}", exc_info=True)
            return HttpResponse("Error", status=500)
    
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
            
            # HITL: Check if conversation is waiting for manager response
            if getattr(conversation, 'is_waiting_for_manager', False):
                # Check timeout - if waiting for more than 30 minutes, cancel waiting state
                from datetime import timedelta
                timeout_minutes = 30
                escalation_timeout = timezone.now() - timedelta(minutes=timeout_minutes)
                
                if conversation.updated_at and conversation.updated_at < escalation_timeout:
                    # Timeout reached - reset waiting state and continue with normal response
                    logger.info(f"HITL: Timeout reached for conversation {conversation.id}, resetting waiting state")
                    conversation.is_waiting_for_manager = False
                    conversation.manager_escalation_context = ''
                    conversation.save(update_fields=['is_waiting_for_manager', 'manager_escalation_context', 'updated_at'])
                    # Continue to generate normal response below
                else:
                    # Still within timeout - return waiting message
                    waiting_messages = {
                        'en': "I'm still waiting for confirmation from my colleague. Please hold on, I'll get back to you shortly.",
                        'de': "Ich warte noch auf die Bestätigung von meinem Kollegen. Bitte warten Sie einen Moment.",
                        'fr': "J'attends toujours la confirmation de mon collègue. Veuillez patienter.",
                        'es': "Todavía estoy esperando la confirmación de mi colega. Por favor espere un momento.",
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
            
            # Визначаємо мову повідомлення
            # Використовуємо conversation.language якщо встановлено, інакше визначаємо з повідомлень
            from MASTER.clients.tasks import detect_language_from_messages
            
            # Detect language from current message and existing messages
            all_messages = list(conversation.messages) if conversation.messages else []
            all_messages.append({'role': 'user', 'content': message_body})
            detected_language = detect_language_from_messages(all_messages)
            
            if conversation.language and conversation.language != 'uk' and conversation.language in ['en', 'de', 'fr', 'es', 'it', 'nl', 'da']:
                language = conversation.language
            else:
                # Use detected language and update conversation
                language = detected_language
                conversation.language = language
                conversation.save(update_fields=['language'])
            
            logger.info(f"Using language '{language}' for conversation {conversation.id} (message: '{message_body[:30]}...')")
            
            # Використовуємо RAG API для генерації відповіді
            try:
                from MASTER.rag.response_generator import ResponseGenerator, RAGResponse
                
                generator = ResponseGenerator()
                rag_response = generator.generate(
                    query=message_body,
                    client=client,  # type: ignore
                    stream=False,
                    language=language
                )
                
                if isinstance(rag_response, RAGResponse):
                    response_text = rag_response.answer
                    logger.info(f"RAG response generated: {len(response_text)} chars, {rag_response.num_chunks} chunks, language={language}")

                    # Store RAG sources into conversation.context_metadata for reporting (per answer)
                    try:
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
                        # cap growth
                        conversation.context_metadata['rag_history'] = history[-50:]
                        conversation.context_metadata['last_rag_sources'] = rag_response.sources
                        conversation.save(update_fields=['context_metadata', 'updated_at'])
                    except Exception as e:
                        logger.warning(f"Failed to store RAG sources for conversation {conversation.id}: {e}")
                    
                    # HITL: Check if escalation is required
                    if rag_response.requires_escalation and getattr(client, 'hitl_enabled', False):
                        manager_ids = client.get_manager_telegram_ids() if hasattr(client, 'get_manager_telegram_ids') else []
                        if manager_ids:
                            # Trigger escalation
                            from MASTER.clients.tasks import notify_manager_of_escalation
                            notify_manager_of_escalation.delay(conversation.id, rag_response.escalation_summary or message_body[:200])
                            logger.info(f"HITL escalation triggered for conversation {conversation.id}")
                else:
                    logger.error("Unexpected generator response when stream=False")
                    response_text = "Вибачте, виникла помилка при генерації відповіді." if language == 'uk' else "Sorry, an error occurred while generating the response."
                
            except Exception as e:
                logger.error(f"RAG generation failed: {str(e)}", exc_info=True)
                response_text = "Дякую за повідомлення! Як можу допомогти?" if language == 'uk' else "Thank you for your message! How can I help you?"
            
            # Зберігаємо повідомлення в розмову
            conversation.add_message('user', message_body)
            conversation.add_message('assistant', response_text)
            
            # Update conversation language if not set or was default
            if not conversation.language or conversation.language == 'uk':
                conversation.language = language
                conversation.save(update_fields=['language'])
            
            # Real-time negative sentiment detection
            # Check user message for negative indicators and trigger immediate alert
            self._check_realtime_negative_sentiment(conversation, message_body)
            
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
        Витягує Client з webhook-запиту.
        
        Пріоритет:
        1. secret_token з заголовка X-Telegram-Bot-Api-Secret-Token (client.tag)
        2. tag параметр з URL query string
        3. Fallback: перший клієнт з увімкненим Telegram (для сумісності)
        """
        try:
            # Спробуємо отримати secret_token з заголовка (Telegram передає його якщо встановлено)
            secret_token = getattr(request, "headers", {}).get("X-Telegram-Bot-Api-Secret-Token") or request.META.get(
                "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"
            )
            
            if secret_token:
                # secret_token = client.tag
                client = Client.objects.filter(tag=secret_token).first()
                if client:
                    logger.info(f"Found client via secret_token (tag): {client.tag}")
                    return client
                logger.warning(f"Telegram webhook: client not found for secret_token (tag): {secret_token}")
            
            # Fallback: отримуємо tag з URL параметрів
            tag = request.GET.get('tag') or request.GET.get('client_tag')
            if tag:
                client = Client.objects.filter(tag=tag).first()
                if client:
                    logger.info(f"Found client via URL tag parameter: {tag}")
                    return client
                logger.warning(f"Telegram webhook: client not found for tag: {tag}")
            
            # Останній fallback: перший клієнт з увімкненим Telegram (для сумісності)
            # Це не ідеально, але забезпечує роботу якщо tag не передано
            fallback_client = Client.objects.filter(
                telegram_enabled=True,
                telegram_bot_token__isnull=False
            ).first()
            
            if fallback_client:
                logger.warning(f"Using fallback client (no tag found in request): {fallback_client.id}")
            
            return fallback_client
            
        except Exception as e:
            logger.error(f"Error getting client from request: {str(e)}", exc_info=True)
            return None
    
    def _get_bot_token_for_chat(self, chat_id: int, client_hint=None) -> str:
        """
        Знаходить bot token для чату (через активну розмову або перший доступний)
        CRITICAL: Must filter by client for security - sandbox chats must not leak
        """
        try:
            from MASTER.clients.models import ClientWhatsAppConversation, Client
            
            # Use client_hint from parameter or instance variable
            if not client_hint:
                client_hint = getattr(self, '_current_client_hint', None)
            
            if client_hint:
                # Use provided client_hint for security
                # CRITICAL: Positional arguments (Q objects) must come before keyword arguments
                conversation = ClientWhatsAppConversation.objects.filter(
                    Q(telegram_chat_id=str(chat_id)) | Q(customer_phone=f"telegram_{chat_id}"),
                    client=client_hint,
                    is_active=True
                ).first()
            else:
                # Fallback: find conversation and get client from it (less secure, but needed for backward compatibility)
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
    
    def _generate_welcome_message(self, client: Client, first_name: str = None) -> str:
        """
        Генерує привітальне повідомлення для Telegram бота.
        
        Пріоритет:
        1. Кастомне повідомлення з telegram_welcome_message (якщо налаштовано)
        2. Fallback: базове привітання з назвою компанії
        """
        try:
            # 1. Перевіряємо чи є кастомне привітання
            custom_message = getattr(client, 'telegram_welcome_message', '') or ''
            if custom_message.strip():
                # Підставляємо {name} якщо є
                welcome_text = custom_message.strip()
                if '{name}' in welcome_text:
                    welcome_text = welcome_text.replace('{name}', first_name or '')
                # Прибираємо подвійні пробіли якщо name був пустий
                welcome_text = ' '.join(welcome_text.split())
                logger.info(f"Using custom welcome message for client: {client.company_name}")
                return welcome_text
            
            # 2. Fallback: базове привітання (якщо кастомне не налаштовано)
            greeting = f"Привіт{', ' + first_name if first_name else ''}! 👋\n\n"
            fallback_text = greeting + f"Вітаємо в {client.company_name}!\n\nЧим можу допомогти?"
            
            logger.info(f"Using default welcome message for client: {client.company_name} (no custom message configured)")
            return fallback_text
            
        except Exception as e:
            logger.error(f"Error generating welcome message: {e}", exc_info=True)
            # Останній fallback при помилці
            greeting = f"Привіт{', ' + first_name if first_name else ''}! 👋\n\n"
            return greeting + f"Вітаємо в {client.company_name}. Чим можу допомогти?"
    
    def _check_realtime_negative_sentiment(self, conversation, user_message: str):
        """
        Real-time check for obvious negative sentiment in user messages.
        Triggers immediate alert if strong negative indicators are detected.
        
        This is a quick keyword-based check for obvious cases.
        The full AI-based rating happens after 20 min inactivity.
        """
        try:
            if not user_message or conversation.ai_rating == 'negative':
                return  # Already negative or no message
            
            message_lower = user_message.lower()
            
            # Strong negative indicators (multi-language)
            negative_phrases = [
                # English
                "don't like", "dont like", "not happy", "unhappy", "frustrated",
                "angry", "terrible", "horrible", "awful", "worst", "hate",
                "disappointed", "useless", "waste of time", "doesn't work",
                "not working", "broken", "stupid", "idiot", "ridiculous",
                "unacceptable", "disgusting", "pathetic", "complaint",
                # Ukrainian
                "не подобається", "незадоволен", "розчарован", "злий", "жахлив",
                "огидн", "безнадійн", "марн", "не працює", "зламан", "дурн",
                "неприйнятн", "скарг",
                # German
                "nicht zufrieden", "enttäuscht", "frustriert", "wütend", "schrecklich",
                "furchtbar", "nutzlos", "funktioniert nicht", "kaputt", "dumm",
                "unakzeptabel", "beschwerde",
                # French
                "pas content", "mécontent", "déçu", "frustré", "en colère", "terrible",
                "horrible", "inutile", "ne fonctionne pas", "cassé", "stupide",
                "inacceptable", "plainte",
            ]
            
            # Check for negative indicators
            is_negative = any(phrase in message_lower for phrase in negative_phrases)
            
            if is_negative:
                logger.info(f"🔴 Real-time NEGATIVE detected in conversation {conversation.id}: '{user_message[:100]}...'")
                
                # Update ai_rating to negative
                conversation.ai_rating = 'negative'
                conversation.rating_timestamp = timezone.now()
                conversation.save(update_fields=['ai_rating', 'rating_timestamp', 'updated_at'])
                
                # Trigger immediate email alert
                from MASTER.clients.tasks import close_session_and_send_email
                close_session_and_send_email.delay(conversation.id, force_send=True)
                logger.info(f"🔴 Immediate alert email triggered for conversation {conversation.id}")
                
        except Exception as e:
            logger.warning(f"Error in real-time sentiment check: {e}", exc_info=True)

