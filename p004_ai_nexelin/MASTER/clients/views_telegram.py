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

from .models import Client, ClientWhatsAppConversation, ClientQRCode
from MASTER.restaurant.models import RestaurantTable, RestaurantConversation

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot"


def send_telegram_message(bot_token: str, chat_id: int, message_text: str) -> bool:
    """
    Відправляє повідомлення через Telegram Bot API
    """
    try:
        url = f"{TELEGRAM_API_URL}{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Telegram message sent successfully: chat_id={chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}", exc_info=True)
        return False


def set_telegram_webhook(bot_token: str, webhook_url: str) -> bool:
    """
    Встановлює webhook для Telegram бота
    """
    try:
        url = f"{TELEGRAM_API_URL}{bot_token}/setWebhook"
        payload = {
            "url": webhook_url
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            logger.info(f"Telegram webhook set successfully: {webhook_url}")
            return True
        else:
            logger.error(f"Failed to set Telegram webhook: {result.get('description', 'Unknown error')}")
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
    
    def post(self, request):
        try:
            # Отримуємо дані з Telegram
            body = request.body.decode('utf-8')
            data = json.loads(body)
            
            logger.info(f"Telegram webhook received: {data}")
            
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
            
            # Обробляємо START2 команду
            if message_text.startswith('START2'):
                return self.handle_start2_command(chat_id, message_text, username, first_name)
            
            # Обробляємо звичайні повідомлення
            return self.handle_regular_message(chat_id, message_text, username, first_name)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Telegram webhook: {e}")
            return HttpResponse("Invalid JSON", status=400)
        except Exception as e:
            logger.error(f"Telegram webhook error: {str(e)}", exc_info=True)
            return HttpResponse("Internal server error", status=500)
    
    def handle_start2_command(self, chat_id: int, message_text: str, username: str, first_name: str):
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
            # Використовуємо telegram_chat_id замість phone number
            conversation, created = ClientWhatsAppConversation.objects.get_or_create(
                customer_phone=f"telegram_{chat_id}",  # Використовуємо telegram_ prefix
                client=client,
                qr_code=qr_code,
                table=table,
                is_active=True,
                defaults={
                    'started_at': timezone.now(),
                    'messages': [{
                        'role': 'user',
                        'content': message_text,
                        'timestamp': timezone.now().isoformat()
                    }],
                    'context_metadata': {'platform': 'telegram'}
                }
            )
            
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
    
    def handle_regular_message(self, chat_id: int, message_text: str, username: str, first_name: str):
        """
        Обробляє звичайні повідомлення з RAG логікою
        """
        try:
            # Шукаємо активну розмову
            conversation = ClientWhatsAppConversation.objects.filter(
                customer_phone=f"telegram_{chat_id}",
                is_active=True
            ).first()
            
            if not conversation:
                # Якщо немає активної розмови, використовуємо RAG з першим доступним клієнтом
                response_text = self.generate_rag_response_without_conversation(message_text, chat_id)
            else:
                # Використовуємо RAG для генерації відповіді
                response_text = self.generate_rag_response(message_text, conversation, chat_id)
            
            logger.info(f"Regular message processed: chat_id={chat_id}, message={message_text[:100]}")
            
            # Відправляємо повідомлення
            bot_token = conversation.client.telegram_bot_token if conversation else self._get_bot_token_for_chat(chat_id)
            if bot_token:
                send_telegram_message(bot_token, chat_id, response_text)
            
            return HttpResponse("OK")
            
        except Exception as e:
            logger.error(f"Error processing regular message: {str(e)}", exc_info=True)
            send_telegram_message(self._get_bot_token_for_chat(chat_id), chat_id, "Вибачте, виникла помилка. Спробуйте пізніше.")
            return HttpResponse("Error processing message", status=500)
    
    def generate_rag_response_without_conversation(self, message_body: str, chat_id: int) -> str:
        """
        Генерує відповідь за допомогою RAG без активної розмови
        """
        try:
            # Знаходимо першого клієнта з даними
            client = Client.objects.filter(
                telegram_enabled=True,
                telegram_bot_token__isnull=False
            ).exclude(
                embeddings__isnull=True
            ).first()
            
            if not client:
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
    
    def _get_bot_token_for_chat(self, chat_id: int) -> str:
        """
        Знаходить bot token для чату (через активну розмову або перший доступний)
        """
        try:
            conversation = ClientWhatsAppConversation.objects.filter(
                customer_phone=f"telegram_{chat_id}",
                is_active=True
            ).first()
            
            if conversation and conversation.client.telegram_bot_token:
                return conversation.client.telegram_bot_token
            
            # Fallback: перший клієнт з увімкненим Telegram
            client = Client.objects.filter(
                telegram_enabled=True,
                telegram_bot_token__isnull=False
            ).first()
            
            if client:
                return client.telegram_bot_token
            
            return ""
        except Exception:
            return ""

