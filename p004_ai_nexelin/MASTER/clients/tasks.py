"""
Celery tasks для керування Zero-контейнерами клієнтів та QR-кодами.
"""
import logging
from celery import shared_task
from typing import Dict, Any

logger = logging.getLogger(__name__)


def detect_language_from_messages(messages):
    """
    Detect language from conversation messages.
    Returns language code (uk, en, de, fr, es, it, nl, da) based on message content.
    """
    if not messages:
        return 'en'
    
    # Collect all user and assistant messages
    all_text = ''
    for msg in messages:
        if isinstance(msg, dict) and msg.get('content'):
            all_text += ' ' + msg.get('content', '').lower()
    
    if not all_text:
        return 'en'
    
    # Language detection patterns
    # English
    eng_words = ['hello', 'hi', 'who', 'are', 'you', 'what', 'how', 'can', 'help', 'please', 'thank', 'thanks', 'yes', 'no', 'ok', 'okay']
    if any(word in all_text for word in eng_words):
        return 'en'
    
    # German
    de_words = ['hallo', 'guten', 'tag', 'morgen', 'abend', 'bitte', 'danke', 'hilfe', 'können', 'sie', 'wie', 'was']
    if any(word in all_text for word in de_words):
        return 'de'
    
    # French
    fr_words = ['bonjour', 'bonsoir', 'salut', 'merci', 'aider', 'pouvez', 'comment', 'quoi', 'oui', 'non']
    if any(word in all_text for word in fr_words):
        return 'fr'
    
    # Spanish
    es_words = ['hola', 'buenos', 'días', 'tardes', 'gracias', 'ayuda', 'puede', 'cómo', 'qué', 'sí', 'no']
    if any(word in all_text for word in es_words):
        return 'es'
    
    # Italian
    it_words = ['ciao', 'buongiorno', 'buonasera', 'grazie', 'aiuto', 'può', 'come', 'cosa', 'sì', 'no']
    if any(word in all_text for word in it_words):
        return 'it'
    
    # Dutch
    nl_words = ['hallo', 'goedemorgen', 'goedenavond', 'dank', 'help', 'kunt', 'hoe', 'wat', 'ja', 'nee']
    if any(word in all_text for word in nl_words):
        return 'nl'
    
    # Danish
    da_words = ['hej', 'godmorgen', 'goddag', 'tak', 'hjælp', 'kan', 'hvordan', 'hvad', 'ja', 'nej']
    if any(word in all_text for word in da_words):
        return 'da'
    
    # Ukrainian/Russian (check for Cyrillic characters)
    uk_chars = ['і', 'ї', 'є', 'ґ', 'привіт', 'допомога', 'дякую', 'так', 'ні']
    if any(char in all_text for char in uk_chars):
        return 'uk'
    
    # Default to English
    return 'en'


def get_rating_request_message(language: str) -> str:
    """
    Get localized rating request message based on language code.
    """
    rating_messages = {
        'uk': 'Будь ласка, оцініть нашу розмову: 👍 або 👎',
        'en': 'Please rate our conversation: 👍 or 👎',
        'de': 'Bitte bewerten Sie unser Gespräch: 👍 oder 👎',
        'fr': 'Veuillez évaluer notre conversation : 👍 ou 👎',
        'es': 'Por favor, califique nuestra conversación: 👍 o 👎',
        'it': 'Per favore, valuta la nostra conversazione: 👍 o 👎',
        'nl': 'Beoordeel ons gesprek: 👍 of 👎',
        'da': 'Bedøm vores samtale: 👍 eller 👎',
    }
    return rating_messages.get(language, rating_messages['en'])


@shared_task(bind=True, max_retries=3)
def start_zero_container_task(self, config_id: int) -> Dict[str, Any]:
    """
    Асинхронна задача для запуску Zero-контейнера.
    
    Args:
        config_id: ID об'єкта ClientZeroConfig
        
    Returns:
        Dict з результатом операції
    """
    from MASTER.clients.models import ClientZeroConfig
    from MASTER.clients.docker_manager import ZeroDockerManager
    
    try:
        config = ClientZeroConfig.objects.select_related('client').get(id=config_id)
        
        if not config.enabled:
            logger.warning(f"ClientZeroConfig {config_id} is disabled, skipping start")
            return {"status": "disabled", "message": "Configuration is disabled"}
        
        # Оновлюємо статус на "starting"
        config.status = 'starting'
        config.last_error = ""
        config.save(update_fields=['status', 'last_error'])
        
        # Генеруємо ім'я контейнера
        if not config.container_name:
            config.container_name = f"zero_client_{config.client.id}"
            config.save(update_fields=['container_name'])
        
        # Запускаємо контейнер
        manager = ZeroDockerManager()
        result = manager.start_zero_container(
            container_name=config.container_name,
            env=config.build_env(),
            host_port=config.host_port,
            image=config.image,
            repo_url=config.repo_url,
            repo_branch=config.repo_branch,
        )
        
        # Оновлюємо config з результатами
        config.container_id = result.get('container_id', '')
        config.host_port = result.get('host_port') or config.host_port
        config.status = 'running'
        config.save(update_fields=['container_id', 'host_port', 'status'])
        
        logger.info(f"Zero container for client {config.client.id} started: {result}")
        return {"status": "success", "result": result}
        
    except ClientZeroConfig.DoesNotExist:
        error_msg = f"ClientZeroConfig with id={config_id} does not exist"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"Failed to start Zero container: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Оновлюємо статус на error
        try:
            config = ClientZeroConfig.objects.get(id=config_id)
            config.status = 'error'
            config.last_error = error_msg
            config.save(update_fields=['status', 'last_error'])
        except Exception:
            pass
        
        # Retry якщо це можливо
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True)
def stop_zero_container_task(self, config_id: int, remove: bool = False) -> Dict[str, Any]:
    """
    Асинхронна задача для зупинки Zero-контейнера.
    
    Args:
        config_id: ID об'єкта ClientZeroConfig
        remove: Чи видаляти контейнер після зупинки
        
    Returns:
        Dict з результатом операції
    """
    from MASTER.clients.models import ClientZeroConfig
    from MASTER.clients.docker_manager import ZeroDockerManager
    
    try:
        config = ClientZeroConfig.objects.get(id=config_id)
        
        if not config.container_name:
            logger.warning(f"No container_name for ClientZeroConfig {config_id}")
            return {"status": "error", "message": "No container name specified"}
        
        # Оновлюємо статус на "stopping"
        config.status = 'stopping'
        config.save(update_fields=['status'])
        
        # Зупиняємо контейнер
        manager = ZeroDockerManager()
        result = manager.stop_zero_container(
            container_name=config.container_name,
            remove=remove
        )
        
        # Оновлюємо статус
        if result['status'] in ['stopped', 'not_found']:
            config.status = 'stopped'
            if remove:
                config.container_id = ""
        else:
            config.status = 'error'
            config.last_error = result.get('message', '')
        
        config.save(update_fields=['status', 'container_id', 'last_error'])
        
        logger.info(f"Zero container for client {config.client.id} stopped: {result}")
        return {"status": "success", "result": result}
        
    except ClientZeroConfig.DoesNotExist:
        error_msg = f"ClientZeroConfig with id={config_id} does not exist"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"Failed to stop Zero container: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        try:
            config = ClientZeroConfig.objects.get(id=config_id)
            config.status = 'error'
            config.last_error = error_msg
            config.save(update_fields=['status', 'last_error'])
        except Exception:
            pass
        
        return {"status": "error", "message": error_msg}


@shared_task
def check_zero_container_health_task(config_id: int) -> Dict[str, Any]:
    """
    Перевірка стану Zero-контейнера.
    
    Args:
        config_id: ID об'єкта ClientZeroConfig
        
    Returns:
        Dict зі статусом контейнера
    """
    from MASTER.clients.models import ClientZeroConfig
    from MASTER.clients.docker_manager import ZeroDockerManager
    
    try:
        config = ClientZeroConfig.objects.get(id=config_id)
        
        if not config.container_name:
            return {"status": "no_container", "message": "No container configured"}
        
        manager = ZeroDockerManager()
        status = manager.get_container_status(config.container_name)
        
        # Синхронізуємо статус якщо потрібно
        if status['exists']:
            docker_status = status.get('status', '')
            if docker_status == 'running' and config.status != 'running':
                config.status = 'running'
                config.save(update_fields=['status'])
            elif docker_status in ['exited', 'dead'] and config.status == 'running':
                config.status = 'stopped'
                config.last_error = f"Container exited unexpectedly"
                config.save(update_fields=['status', 'last_error'])
        else:
            if config.status == 'running':
                config.status = 'stopped'
                config.last_error = "Container not found"
                config.save(update_fields=['status', 'last_error'])
        
        logger.info(f"Health check for client {config.client.id}: {status}")
        return {"status": "success", "container_status": status}
        
    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}


@shared_task
def restart_zero_container_task(config_id: int) -> Dict[str, Any]:
    """
    Перезапуск Zero-контейнера.
    
    Args:
        config_id: ID об'єкта ClientZeroConfig
        
    Returns:
        Dict з результатом операції
    """
    from MASTER.clients.models import ClientZeroConfig
    from MASTER.clients.docker_manager import ZeroDockerManager
    
    try:
        config = ClientZeroConfig.objects.get(id=config_id)
        
        if not config.container_name:
            return {"status": "error", "message": "No container name specified"}
        
        manager = ZeroDockerManager()
        result = manager.restart_zero_container(config.container_name)
        
        if result['status'] == 'restarted':
            config.status = 'running'
            config.last_error = ""
            config.save(update_fields=['status', 'last_error'])
        else:
            config.status = 'error'
            config.last_error = result.get('message', '')
            config.save(update_fields=['status', 'last_error'])
        
        logger.info(f"Zero container for client {config.client.id} restarted: {result}")
        return {"status": "success", "result": result}
        
    except Exception as e:
        error_msg = f"Failed to restart Zero container: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}


@shared_task(bind=True, max_retries=3)
def regenerate_qrs_for_client_task(self, client_id: int) -> Dict[str, Any]:
    """
    Асинхронна задача для регенерації QR-кодів всіх столиків клієнта.
    
    Args:
        client_id: ID клієнта (ресторану)
        
    Returns:
        Dict з результатом операції
    """
    try:
        from .models import Client
        from MASTER.restaurant.models import RestaurantTable
        
        client = Client.objects.get(id=client_id)
        
        if client.client_type != 'restaurant':
            return {"status": "skipped", "message": "Client is not a restaurant"}
        
        tables = RestaurantTable.objects.filter(client=client)
        regenerated_count = 0
        
        for table in tables:
            try:
                table.generate_qr_code()
                table.save(update_fields=["qr_code"])
                regenerated_count += 1
            except Exception as e:
                logger.error(f"Failed to regenerate QR for table {table.table_number}: {str(e)}")
        
        logger.info(f"Regenerated QR codes for {regenerated_count} tables of client {client_id}")
        return {
            "status": "success", 
            "regenerated_count": regenerated_count,
            "total_tables": tables.count()
        }
        
    except Exception as e:
        if "Client" in str(type(e)) and "DoesNotExist" in str(type(e)):
            error_msg = f"Client with id {client_id} not found"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        else:
            error_msg = f"Failed to regenerate QR codes for client {client_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}


@shared_task(bind=True, max_retries=3)
def process_web_parsing_request(self, parsing_request_id: int) -> Dict[str, Any]:
    """
    Process web parsing request: download documents and create knowledge block.
    
    Args:
        parsing_request_id: ID of WebParsingRequest
        
    Returns:
        Dict with operation result
    """
    from MASTER.clients.models import WebParsingRequest, KnowledgeBlock, ClientDocument
    import requests
    import os
    from urllib.parse import urljoin, urlparse
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    
    try:
        parsing_request = WebParsingRequest.objects.select_related('client').get(id=parsing_request_id)
        
        if parsing_request.status != WebParsingRequest.STATUS_COMPLETED:
            return {"status": "skipped", "message": "Request is not completed"}
        
        if not parsing_request.path_to_documents:
            return {"status": "error", "message": "Path to documents is not set"}
        
        if parsing_request.knowledge_block:
            return {"status": "skipped", "message": "Knowledge block already created"}
        
        # Parse path_to_documents (format: "https://server.com/path/to/documents" or "/path/to/documents")
        path = parsing_request.path_to_documents.strip()
        
        # Extract website name from URL for knowledge block name
        from urllib.parse import urlparse
        parsed_url = urlparse(parsing_request.website_url)
        website_name = parsed_url.netloc.replace('www.', '') if parsed_url.netloc else 'Website'
        
        # Create knowledge block
        knowledge_block, created = KnowledgeBlock.objects.get_or_create(
            client=parsing_request.client,
            name=website_name,
            defaults={
                'description': f"Knowledge extracted from {parsing_request.website_url}",
                'is_active': True,
                'is_permanent': False,
            }
        )
        
        if not created:
            # If block exists, update description
            knowledge_block.description = f"Knowledge extracted from {parsing_request.website_url}"
            knowledge_block.save(update_fields=['description'])
        
        # Link knowledge block to parsing request
        parsing_request.knowledge_block = knowledge_block
        parsing_request.save(update_fields=['knowledge_block'])
        
        # Download files from path_to_documents
        # For now, we'll create a placeholder document
        # In production, you would:
        # 1. List files in the directory (via API or file system)
        # 2. Download each file
        # 3. Create ClientDocument for each
        
        # Example: Create a document with metadata about the parsing
        # In real implementation, you would download actual files
        logger.info(f"Processing web parsing request {parsing_request_id} for {parsing_request.website_url}")
        logger.info(f"Path to documents: {path}")
        logger.info(f"Created knowledge block: {knowledge_block.name} (ID: {knowledge_block.id})")
        
        # TODO: Implement actual file downloading from path_to_documents
        # This would involve:
        # - Connecting to the server (FTP, SFTP, HTTP, etc.)
        # - Listing files in the directory
        # - Downloading each file
        # - Creating ClientDocument for each file
        
        return {
            "status": "success",
            "knowledge_block_id": knowledge_block.id,
            "knowledge_block_name": knowledge_block.name,
            "message": f"Knowledge block '{knowledge_block.name}' created. Files need to be downloaded manually or via separate process."
        }
        
    except WebParsingRequest.DoesNotExist:
        error_msg = f"WebParsingRequest with id={parsing_request_id} does not exist"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"Failed to process web parsing request {parsing_request_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Retry if possible
        raise self.retry(exc=e, countdown=60)


@shared_task
def check_inactive_chat_sessions():
    """
    Periodic task to check inactive chat sessions.
    Runs every minute to:
    - Auto-rate conversations after 5 minutes of inactivity (if not rated)
    - Close sessions and send emails after 20 minutes of inactivity
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Q
    from MASTER.clients.models import ClientWhatsAppConversation
    
    logger.info("Checking inactive chat sessions...")
    
    now = timezone.now()
    twenty_minutes_ago = now - timedelta(minutes=20)
    
    # Find active conversations with last activity more than 20 minutes ago
    inactive_20min = ClientWhatsAppConversation.objects.filter(
        is_active=True
    ).filter(
        Q(last_activity_at__lte=twenty_minutes_ago) | 
        Q(last_activity_at__isnull=True, updated_at__lte=twenty_minutes_ago)
    )
    
    inactive_count = inactive_20min.count()
    
    # Close and send email after 20 minutes
    sessions_closed = 0
    for conversation in inactive_20min:
        # Auto-rate if user hasn't rated yet
        if not conversation.user_rating and not conversation.ai_rating:
            # Auto-rate and close session (sends alarm email only if negative)
            auto_rate_and_close_session.delay(conversation.id)
            sessions_closed += 1
        else:
            # Already has rating - check if negative for alarm email
            is_negative = conversation.user_rating == 'negative' or conversation.ai_rating == 'negative'
            if is_negative:
                # Send alarm email for negative rating
                close_session_and_send_email.delay(conversation.id)
                sessions_closed += 1
            else:
                # Positive/neutral - just close without email
                conversation.is_active = False
                conversation.ended_at = now
                conversation.save(update_fields=['is_active', 'ended_at'])
                sessions_closed += 1
    
    logger.info(f"Closed {sessions_closed} inactive sessions (no auto-emails, use daily digest)")
    
    return {
        "status": "success",
        "checked_20min": inactive_count,
        "sessions_closed": sessions_closed
    }


@shared_task(bind=True, max_retries=3)
def send_rating_request(self, conversation_id: int):
    """
    Send rating request message to user after 5 minutes of inactivity.
    Works for Web Chat, Telegram, and WhatsApp.
    """
    from django.utils import timezone
    from datetime import timedelta
    from MASTER.clients.models import ClientWhatsAppConversation
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        
        # Skip if already rated or request already sent
        if conversation.user_rating or conversation.rating_request_sent:
            return {"status": "skipped", "message": "Already rated or request sent"}
        
        if not conversation.messages:
            return {"status": "skipped", "message": "No messages"}
        
        # CRITICAL: Double-check inactivity before sending (prevent race conditions and timezone issues)
        now = timezone.now()
        five_minutes_ago = now - timedelta(minutes=5)
        
        # Check if conversation is still inactive (using timezone-aware comparison)
        last_activity = conversation.last_activity_at or conversation.updated_at
        if last_activity and last_activity > five_minutes_ago:
            logger.info(f"Conversation {conversation_id} is still active (last_activity={last_activity}, now={now}), skipping rating request")
            return {"status": "skipped", "message": "Conversation is still active"}
        
        # Determine platform: prioritize telegram_chat_id over context_metadata
        # This ensures Telegram conversations are correctly identified even if context_metadata is wrong
        platform = None
        
        # CRITICAL: Check telegram_chat_id FIRST (most reliable indicator)
        if conversation.telegram_chat_id:
            platform = 'telegram'
            logger.info(f"Conversation {conversation_id}: Detected platform=telegram from telegram_chat_id={conversation.telegram_chat_id}")
        elif conversation.customer_phone and conversation.customer_phone.startswith('telegram_'):
            platform = 'telegram'
            logger.info(f"Conversation {conversation_id}: Detected platform=telegram from customer_phone prefix")
        
        # If not Telegram, check context_metadata
        if not platform:
            platform = conversation.context_metadata.get('platform', None) if conversation.context_metadata else None
            if platform:
                logger.info(f"Conversation {conversation_id}: Using platform={platform} from context_metadata")
        
        # If still not determined, use fallback detection
        if not platform:
            # Check if client has telegram_bot_token - if yes, default to telegram instead of whatsapp
            if conversation.client and conversation.client.telegram_bot_token:
                platform = 'telegram'
                logger.info(f"Conversation {conversation_id}: Detected platform=telegram from client.telegram_bot_token")
            elif conversation.customer_phone and conversation.customer_phone.startswith('web_'):
                platform = 'web'
                logger.info(f"Conversation {conversation_id}: Detected platform=web from customer_phone prefix")
            else:
                platform = 'whatsapp'
                logger.info(f"Conversation {conversation_id}: Defaulting to platform=whatsapp")
        
        # Final validation: if platform is 'web' but we have telegram_chat_id, it's Telegram!
        if platform in ['web', 'web_widget', 'iframe'] and conversation.telegram_chat_id:
            platform = 'telegram'
            logger.warning(f"Conversation {conversation_id}: Overriding platform from {platform} to telegram (has telegram_chat_id)")
        
        logger.info(f"Conversation {conversation_id}: Final platform={platform} for rating request")
        
        # Determine language: always detect from conversation.messages to get actual user language
        # This ensures rating request is in the same language the user actually used
        detected_language = detect_language_from_messages(conversation.messages)
        
        # Update conversation.language if not set or was default/invalid
        if not conversation.language or conversation.language == 'uk' or conversation.language not in ['en', 'de', 'fr', 'es', 'it', 'nl', 'da']:
            conversation.language = detected_language
            conversation.save(update_fields=['language'])
        
        # Use detected language for rating message
        language = detected_language
        
        # Get localized rating request message
        rating_message = get_rating_request_message(language)
        
        # Send rating request based on platform
        if platform == 'web' or platform == 'web_widget' or platform == 'iframe':
            # For Web Chat - add message to conversation (do NOT send via Meta WhatsApp)
            logger.info(f"Attempting to add rating request to web chat conversation {conversation_id} in language {language}")
            conversation.add_message('assistant', rating_message)
            conversation.rating_request_sent = True
            conversation.rating_request_sent_at = timezone.now()
            conversation.save(update_fields=['rating_request_sent', 'rating_request_sent_at', 'messages', 'total_messages', 'updated_at', 'last_activity_at'])
            logger.info(f"✅ Rating request added to web chat conversation {conversation_id} in language {language}")
            
            # NOTE: Email is NOT sent here - it will be sent only after:
            # 1. User rates the conversation (positive rating triggers immediate email)
            # 2. 20 minutes of inactivity (auto_rate_and_close_session -> close_session_and_send_email)
            
        elif platform == 'telegram':
            # For Telegram - send message with inline keyboard
            import json
            import requests
            
            # Get telegram_chat_id from conversation or customer_phone
            telegram_chat_id = None
            if conversation.telegram_chat_id:
                try:
                    telegram_chat_id = int(conversation.telegram_chat_id)
                except (ValueError, TypeError):
                    pass
            
            if not telegram_chat_id and conversation.customer_phone and conversation.customer_phone.startswith('telegram_'):
                try:
                    telegram_chat_id = int(conversation.customer_phone.replace('telegram_', ''))
                except (ValueError, TypeError):
                    pass
            
            if telegram_chat_id and conversation.client and conversation.client.telegram_bot_token:
                bot_token = conversation.client.telegram_bot_token
                
                # Create inline keyboard with rating buttons
                keyboard = {
                    "inline_keyboard": [[
                        {"text": "👍", "callback_data": f"rate_{conversation.id}_positive"},
                        {"text": "👎", "callback_data": f"rate_{conversation.id}_negative"}
                    ]]
                }
                
                # Send message with keyboard
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": telegram_chat_id,
                    "text": rating_message,
                    "reply_markup": json.dumps(keyboard)
                }
                
                logger.info(f"Attempting to send rating request to Telegram chat_id={telegram_chat_id} for conversation {conversation_id} in language {language}")
                logger.debug(f"Telegram API payload: url={url}, chat_id={telegram_chat_id}, text_length={len(rating_message)}")
                
                try:
                    response = requests.post(url, json=payload, timeout=10)
                    response.raise_for_status()  # Raise exception for bad status codes
                    
                    # Parse response to verify success
                    try:
                        response_data = response.json()
                        if response_data.get('ok') is True:
                            message_id = response_data.get('result', {}).get('message_id')
                            conversation.rating_request_sent = True
                            conversation.rating_request_sent_at = timezone.now()
                            conversation.save(update_fields=['rating_request_sent', 'rating_request_sent_at'])
                            logger.info(f"✅ Rating request sent to Telegram chat {telegram_chat_id} for conversation {conversation_id} in language {language}, message_id={message_id}")
                            
                            # Send email with chat summary immediately after rating request
                            try:
                                from MASTER.clients.tasks import send_chat_summary_email, format_chat_as_text, generate_chat_summary
                                
                                # Check if email reports are enabled
                                if conversation.client.email_report_enabled and conversation.client.email_smtp_enabled:
                                    # Generate summary if not exists
                                    if not conversation.summary:
                                        summary = generate_chat_summary(conversation)
                                        conversation.summary = summary
                                        conversation.save(update_fields=['summary'])
                                    
                                    # Generate full chat text
                                    chat_text = format_chat_as_text(conversation)
                                    
                                    # Get recipient email
                                    recipient_email = conversation.client.email_from_address or conversation.client.email_smtp_username
                                    
                                    if recipient_email:
                                        # Send email (do NOT close session - user may still write)
                                        email_result = send_chat_summary_email(conversation, chat_text, recipients=[recipient_email])
                                        if email_result.get("success") and email_result.get("sent_count", 0) > 0:
                                            logger.info(f"✅ Chat summary email sent immediately after rating request for conversation {conversation_id}")
                                        else:
                                            logger.warning(f"⚠️ Failed to send email after rating request for conversation {conversation_id}: {email_result}")
                                    else:
                                        logger.warning(f"⚠️ No email recipient configured for client {conversation.client.id}, skipping email")
                                else:
                                    logger.debug(f"Email reports disabled or SMTP not enabled for client {conversation.client.id}, skipping email")
                            except Exception as e:
                                logger.error(f"Failed to send email after rating request for conversation {conversation_id}: {e}", exc_info=True)
                                # Don't fail the whole task if email fails
                        else:
                            error_description = response_data.get('description', 'Unknown error')
                            logger.error(f"❌ Telegram API returned ok=False: {error_description}, full_response={response_data}")
                            # DO NOT set rating_request_sent=True if Telegram API says it failed
                    except (ValueError, KeyError) as e:
                        logger.error(f"❌ Failed to parse Telegram API response: {e}, response_text={response.text[:500]}")
                        # DO NOT set rating_request_sent=True if we can't verify success
                        
                except requests.RequestException as e:
                    logger.error(f"❌ Failed to send Telegram rating request (network error): {e}")
                    # DO NOT set rating_request_sent=True on network errors
                    # Raise exception to trigger Celery retry
                    raise
                except Exception as e:
                    logger.error(f"❌ Unexpected error sending Telegram rating request: {e}", exc_info=True)
                    # DO NOT set rating_request_sent=True on unexpected errors
                    raise
            else:
                missing = []
                if not telegram_chat_id:
                    missing.append("telegram_chat_id")
                if not (conversation.client and conversation.client.telegram_bot_token):
                    missing.append("telegram_bot_token")
                logger.warning(f"⚠️ Cannot send Telegram rating request for conversation {conversation_id}: missing {', '.join(missing)}")
            
        elif platform == 'whatsapp':
            # For WhatsApp (Meta) - send text message via Meta API
            # Only send if it's actually WhatsApp, not web chat or telegram
            from MASTER.clients.views_meta_whatsapp import send_whatsapp_text
            
            # Verify it's actually WhatsApp (not web or telegram)
            customer_phone = conversation.customer_phone
            if customer_phone and not customer_phone.startswith('web_') and not customer_phone.startswith('telegram_'):
                logger.info(f"Attempting to send rating request to WhatsApp {customer_phone} for conversation {conversation_id}")
                success = send_whatsapp_text(
                    customer_phone,
                    rating_message,
                    client=conversation.client
                )
                
                if success:
                    conversation.rating_request_sent = True
                    conversation.rating_request_sent_at = timezone.now()
                    conversation.save(update_fields=['rating_request_sent', 'rating_request_sent_at'])
                    logger.info(f"✅ Rating request sent to WhatsApp {customer_phone} for conversation {conversation_id} in language {language}")
                else:
                    logger.error(f"❌ Failed to send WhatsApp rating request to {customer_phone} for conversation {conversation_id}")
            else:
                logger.warning(f"⚠️ Cannot send WhatsApp rating request: invalid customer_phone format '{customer_phone}' for conversation {conversation_id}")
        else:
            logger.warning(f"⚠️ Unknown platform '{platform}' for conversation {conversation_id}, skipping rating request")
        
        return {"status": "success", "platform": platform, "language": language}
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to send rating request for conversation {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def auto_rate_conversation(self, conversation_id: int):
    """
    Auto-rate conversation using AI (client's configured model).
    
    Determines if conversation is NEGATIVE (requires alarm email) or POSITIVE.
    Uses the client's LLM model for consistent quality assessment.
    """
    from django.utils import timezone
    from MASTER.clients.models import ClientWhatsAppConversation
    from MASTER.rag.llm_client import LLMClient
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        
        # Skip if already rated
        if conversation.user_rating or conversation.ai_rating:
            return {"status": "skipped", "message": "Already rated"}
        
        if not conversation.messages:
            return {"status": "skipped", "message": "No messages"}
        
        # Get client's model info for logging
        client = conversation.client
        model_info = "default"
        if client and hasattr(client, 'llm_provider_model') and client.llm_provider_model:
            model_info = f"{client.llm_provider_model.provider_type}/{client.llm_provider_model.model_name}"
        elif client and hasattr(client, 'llm_provider'):
            model_info = f"{client.llm_provider}/{getattr(client, 'llm_model_name', 'unknown')}"
        
        logger.info(f"🤖 Auto-rating conversation {conversation_id} using model: {model_info}")
        
        # Prepare conversation text for analysis
        messages_text = "\n".join([
            f"{'USER' if msg.get('role') == 'user' else 'ASSISTANT'}: {msg.get('content', '')[:300]}"
            for msg in conversation.messages[-15:]  # Last 15 messages for better context
        ])
        
        # Enhanced prompt for accurate negative detection
        prompt = f"""You are analyzing a customer support conversation to detect if there are any issues that require immediate business attention.

CONVERSATION:
{messages_text}

ANALYZE FOR NEGATIVE INDICATORS:
1. Customer frustration, anger, or disappointment
2. Unresolved issues or complaints
3. Bot/AI failures (wrong answers, confusion, loops)
4. Customer explicitly expressing dissatisfaction
5. Requests for human support that weren't addressed
6. Profanity or strong negative language
7. Customer threatening to leave, complain, or request refund
8. Multiple repeated questions (bot not understanding)

RATING CRITERIA:
- NEGATIVE: Any of the above indicators present, OR customer clearly unhappy
- POSITIVE: Customer satisfied, issue resolved, helpful interaction

YOUR TASK: Respond with ONLY one word - either "NEGATIVE" or "POSITIVE".
If unsure, lean towards NEGATIVE (better to alert business than miss an issue).

RATING:"""
        
        llm_client = LLMClient()
        result = llm_client.generate_response(
            user_query=prompt,
            context="",
            client=client,  # Uses client's configured LLM model
            stream=False
        )
        
        # Handle dict response (new format) or string (old format)
        if isinstance(result, dict):
            response = result.get('content', '')
        else:
            response = str(result)
        
        rating = None
        if response:
            response_lower = response.strip().lower()
            # Check for negative first (stricter detection)
            if 'negative' in response_lower or '👎' in response:
                rating = 'negative'
            elif 'positive' in response_lower or '👍' in response:
                rating = 'positive'
        
        # Default to positive only if response is truly unclear
        if not rating:
            logger.warning(f"⚠️ AI rating unclear for conversation {conversation_id}, response: {response[:100]}")
            rating = 'positive'
        
        conversation.ai_rating = rating
        conversation.rating_timestamp = timezone.now()
        conversation.save(update_fields=['ai_rating', 'rating_timestamp'])
        
        log_emoji = "🔴" if rating == 'negative' else "🟢"
        logger.info(f"{log_emoji} Auto-rated conversation {conversation_id} as {rating.upper()} (model: {model_info})")
        
        return {"status": "success", "rating": rating, "model": model_info}
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to auto-rate conversation {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def auto_rate_and_close_session(self, conversation_id: int):
    """
    Auto-rate conversation and then close session and send email.
    Called after 20 minutes of inactivity if user hasn't rated.
    """
    from django.utils import timezone
    from MASTER.clients.models import ClientWhatsAppConversation
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        
        # Skip if already rated
        if conversation.user_rating or conversation.ai_rating:
            # Already rated - only send email if negative (alarm policy)
            is_negative = conversation.user_rating == 'negative' or conversation.ai_rating == 'negative'
            if is_negative:
                close_session_and_send_email.delay(conversation_id)
            else:
                # Positive/neutral - just close without email
                conversation.is_active = False
                conversation.ended_at = timezone.now()
                conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "Already rated"}
        
        # Auto-rate first (call synchronously to ensure rating is saved before deciding on email)
        rating_result = auto_rate_conversation.apply(args=[conversation_id])
        
        # Extract result value
        try:
            rating_value = rating_result.get() if hasattr(rating_result, 'get') else rating_result.result
        except Exception:
            rating_value = {"status": "unknown", "rating": None}
        
        # Reload conversation to get updated rating
        conversation.refresh_from_db()
        
        # Extract rating from result
        rating = rating_value.get('rating') if isinstance(rating_value, dict) else None
        is_negative = rating == 'negative' or conversation.ai_rating == 'negative'
        
        # Only send alarm email if AI detected NEGATIVE
        email_sent = False
        if is_negative:
            logger.info(f"🔴 AI detected NEGATIVE for conversation {conversation_id}, sending alarm email")
            close_session_and_send_email.delay(conversation_id)
            email_sent = True
        else:
            # Positive - just close session, no email (use daily digest instead)
            logger.info(f"🟢 AI rated conversation {conversation_id} as POSITIVE, closing without email")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
        
        return {
            "status": "success", 
            "rating": rating, 
            "alarm_email": email_sent,
            "model": rating_value.get('model') if isinstance(rating_value, dict) else None
        }
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to auto-rate and close session {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def close_session_and_send_email(self, conversation_id: int, force_send: bool = False):
    """
    Close chat session and (optionally) send summary email.

    Refactored to reduce spam:
    - By default, we DO NOT email every closed session.
    - Immediate email is sent ONLY when:
      1) force_send=True (manual trigger), OR
      2) user_rating/ai_rating is 'negative' (critical alert).
    """
    from django.utils import timezone
    from datetime import timedelta
    from MASTER.clients.models import ClientWhatsAppConversation
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        
        now = timezone.now()

        # CRITICAL: Double-check inactivity before closing/sending (avoid race conditions)
        if not force_send:
            twenty_minutes_ago = now - timedelta(minutes=20)
            last_activity = conversation.last_activity_at or conversation.updated_at
            if last_activity and last_activity > twenty_minutes_ago:
                logger.info(
                    f"Conversation {conversation_id} is still active "
                    f"(last_activity={last_activity}, now={now}), skipping close/email"
                )
                return {"status": "skipped", "message": "Conversation is still active"}
        
        # Skip if email already sent (unless forced)
        if conversation.email_sent and not force_send:
            activity_time = conversation.last_activity_at or conversation.updated_at
            if conversation.email_sent_at and activity_time and activity_time > conversation.email_sent_at:
                logger.info(
                    f"Conversation {conversation_id} has new activity after email was sent; "
                    f"skipping to avoid duplicates"
                )
                return {"status": "skipped", "message": "New activity after email was sent"}
            logger.info(f"Conversation {conversation_id} email already sent, skipping")
            return {"status": "skipped", "message": "Email already sent"}
        
        # Generate summary if not exists - no fallback, must succeed
        if not conversation.summary:
            logger.info(f"🔄 Generating summary for conversation {conversation_id} in close_session_and_send_email")
            summary = generate_chat_summary(conversation)
            if summary and summary.strip():
                conversation.summary = summary
                conversation.save(update_fields=['summary'])
                logger.info(f"✅ Summary saved for conversation {conversation_id}, length={len(summary)}")
            else:
                logger.error(f"❌ Summary generation returned empty for conversation {conversation_id}")
                raise ValueError(f"Summary generation returned empty for conversation {conversation_id}")

        # Decide whether we should send an email for this conversation
        is_negative = (conversation.user_rating == 'negative') or (conversation.ai_rating == 'negative')
        should_send = bool(force_send or is_negative)

        # If we are not sending: just close + keep summary, no email
        if not should_send:
            if not force_send:
                conversation.is_active = False
                conversation.ended_at = now
                conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "closed_no_email", "message": "Closed without email (non-critical)"}

        # Respect per-client toggle (manual trigger can override)
        if not conversation.client.email_report_enabled and not force_send:
            logger.info(
                f"Email reports disabled for client {conversation.client.id}; "
                f"skipping email for conversation {conversation_id}"
            )
            if not force_send:
                conversation.is_active = False
                conversation.ended_at = now
                conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "Email reports disabled"}

        # Validate SMTP only if we are sending
        if not conversation.client.email_smtp_enabled:
            logger.warning(f"SMTP not enabled for client {conversation.client.id}, cannot send email")
            if not force_send:
                conversation.is_active = False
                conversation.ended_at = now
                conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "SMTP not enabled. Check email settings."}

        if (
            not conversation.client.email_smtp_host
            or not conversation.client.email_smtp_username
            or not conversation.client.email_smtp_password
        ):
            logger.warning(
                f"Incomplete SMTP settings for client {conversation.client.id}: "
                f"host={bool(conversation.client.email_smtp_host)}, "
                f"username={bool(conversation.client.email_smtp_username)}, "
                f"password={bool(conversation.client.email_smtp_password)}"
            )
            if not force_send:
                conversation.is_active = False
                conversation.ended_at = now
                conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "Incomplete SMTP settings. Check email settings."}

        # Use smart recipients list
        recipients = conversation.client.get_report_recipients() if conversation.client else []
        if not recipients:
            fallback_recipient = conversation.client.email_from_address or conversation.client.email_smtp_username
            if fallback_recipient:
                recipients = [fallback_recipient]

        if not recipients:
            logger.warning(f"No email recipients configured for client {conversation.client.id}")
            if not force_send:
                conversation.is_active = False
                conversation.ended_at = now
                conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "No email recipients configured"}
        
        # Generate full chat text
        chat_text = format_chat_as_text(conversation)

        subject_prefix = "🔴 URGENT NEGATIVE " if is_negative else ""
        email_result = send_chat_summary_email(
            conversation,
            chat_text,
            recipients=recipients,
            subject_prefix=subject_prefix,
        )

        # Update email flags
        email_sent_ok = bool(email_result.get("success") and email_result.get("sent_count", 0) > 0)
        if email_sent_ok:
            conversation.email_sent = True
            conversation.email_sent_at = now
        else:
            conversation.email_sent = False

        update_fields = ['email_sent', 'email_sent_at']

        # Close session only for the inactivity flow
        if not force_send:
            conversation.is_active = False
            conversation.ended_at = now
            update_fields.extend(['is_active', 'ended_at'])

        conversation.save(update_fields=update_fields)

        return {
            "status": "success" if email_sent_ok else "partial",
            "email_result": email_result,
        }
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to close session and send email for {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


def generate_chat_summary(conversation):
    """
    Generate AI summary of the conversation.
    Only includes messages from this session (between started_at and ended_at/now).
    Uses conversationmessage_set.all() to get messages from database.
    ALWAYS returns a summary - never returns None or empty string.
    """
    from MASTER.rag.llm_client import LLMClient
    from django.utils import timezone
    from datetime import datetime
    
    # Get messages from database using conversationmessage_set
    # Filter by created_at between started_at and ended_at
    session_start = conversation.started_at
    session_end = conversation.ended_at or timezone.now()
    
    try:
        # Try to get messages from ConversationMessage model via related manager
        if hasattr(conversation, 'conversationmessage_set'):
            db_messages = conversation.conversationmessage_set.all()
            logger.info(f"📊 Using conversationmessage_set: found {db_messages.count()} total messages")
            
            # Filter messages by created_at between session_start and session_end
            session_messages = db_messages.filter(
                created_at__gte=session_start,
                created_at__lte=session_end
            ).order_by('created_at')
            
            logger.info(f"📊 Filtered {session_messages.count()} messages for session ({session_start} to {session_end})")
            
            # Convert QuerySet to list of dicts for processing
            session_messages_list = []
            for msg in session_messages:
                session_messages_list.append({
                    'role': getattr(msg, 'role', 'unknown'),
                    'content': getattr(msg, 'content', ''),
                    'timestamp': msg.created_at.isoformat() if hasattr(msg, 'created_at') else ''
                })
            
            session_messages = session_messages_list
            
        else:
            # Fallback to JSONField if conversationmessage_set doesn't exist
            logger.warning(f"⚠️ conversationmessage_set not found for conversation {conversation.id}, falling back to JSONField")
            if not conversation.messages:
                return "No messages in this conversation."
            
            if not isinstance(conversation.messages, list):
                logger.warning(f"Conversation {conversation.id} has invalid messages format: {type(conversation.messages)}")
                return "No messages in this conversation."
            
            # Filter messages from JSONField by timestamp
            session_messages = []
            for msg in conversation.messages:
                if not isinstance(msg, dict) or not msg.get('content'):
                    continue
                
                timestamp_str = msg.get('timestamp', '')
                if timestamp_str:
                    try:
                        msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        msg_time = timezone.make_aware(msg_time) if timezone.is_naive(msg_time) else msg_time
                        
                        # Only include messages from this session
                        if session_start and session_end:
                            if session_start <= msg_time <= session_end:
                                session_messages.append(msg)
                        elif session_start:
                            if msg_time >= session_start:
                                session_messages.append(msg)
                    except Exception:
                        # If timestamp parsing fails, include message (fallback)
                        session_messages.append(msg)
                else:
                    # If no timestamp, include message (fallback)
                    session_messages.append(msg)
    
    except Exception as e:
        logger.error(f"❌ Error getting messages for conversation {conversation.id}: {str(e)}", exc_info=True)
        return "No messages in this conversation."
    
    if len(session_messages) == 0:
        logger.warning(f"⚠️ No messages found in session for conversation {conversation.id}")
        return "No messages in this session."
    
    # Log filtering result for debugging
    logger.info(f"📊 Processing {len(session_messages)} messages for summary generation (session: {session_start} to {session_end})")
    
    # Format messages for summary
    messages_text = ""
    try:
        messages_text = "\n".join([
            f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
            for msg in session_messages
            if isinstance(msg, dict) and msg.get('content')
        ])
        
        if not messages_text or len(messages_text.strip()) < 10:
            logger.warning(f"⚠️ Insufficient message content for summary: {len(messages_text)} chars")
            raise ValueError("Insufficient message content")
    except Exception as e:
        logger.error(f"❌ Error formatting messages for conversation {conversation.id}: {str(e)}", exc_info=True)
        raise ValueError(f"Error formatting messages: {str(e)}")
    
    # Detect language from messages
    # Convert session_messages to format expected by detect_language_from_messages
    messages_for_detection = session_messages if isinstance(session_messages, list) else list(session_messages)
    detected_language = detect_language_from_messages(messages_for_detection)
    language = detected_language if detected_language else (conversation.language or 'en')
    
    lang_map = {
        'uk': 'Ukrainian',
        'en': 'English',
        'ru': 'Russian',
        'de': 'German',
        'fr': 'French',
        'es': 'Spanish',
        'it': 'Italian',
        'nl': 'Dutch',
        'da': 'Danish'
    }
    lang_name = lang_map.get(language, 'English')
    
    prompt = f"""Summarize the conversation in the same language as the user's messages. Do not force Ukrainian if the chat is in English.

Generate a concise summary of this customer support conversation in {lang_name} language. Be concise and avoid repetitive words.

Conversation:
{messages_text}

Provide a summary that includes:
1. Main topic/issue discussed
2. Key points covered
3. Resolution or outcome
4. Customer satisfaction (if evident)

Summary ({lang_name}):"""
    
    try:
        # Get client and verify it exists
        client = conversation.client
        if not client:
            logger.error(f"❌ SUMMARY GENERATION FAILED: Conversation {conversation.id} has no client assigned")
            raise ValueError(f"Conversation {conversation.id} has no client assigned")
        
        # Refresh client from DB to ensure we have latest LLM settings
        try:
            from MASTER.clients.models import Client
            client = Client.objects.select_related('llm_provider_model').get(pk=client.pk)
            logger.info(f"✅ Refreshed client {client.id} ({client.company_name}) from DB for summary generation")
        except Client.DoesNotExist:
            logger.error(f"❌ SUMMARY GENERATION FAILED: Client {client.id} not found in database")
            raise ValueError(f"Client {client.id} not found in database")
        
        # Extract provider and model info correctly (support both FK and legacy fields)
        provider_name = 'unknown'
        model_name = 'unknown'
        llm_provider_obj = None
        
        # Priority 1: Check llm_provider_model (FK)
        llm_provider_obj = getattr(client, "llm_provider_model", None)
        if llm_provider_obj is not None:
            provider_name = getattr(llm_provider_obj, "provider_type", "unknown")
            model_name = getattr(llm_provider_obj, "model_name", "unknown")
            logger.info(f"📋 Using LLMProvider FK: provider_type={provider_name}, model_name={model_name}, provider_id={llm_provider_obj.id}")
        else:
            # Priority 2: Check legacy string fields
            provider_name = getattr(client, 'llm_provider', 'unknown')
            model_name = getattr(client, 'llm_model_name', 'unknown')
            logger.info(f"📋 Using legacy fields: llm_provider={provider_name}, llm_model_name={model_name}")
        
        provider_info = f"{provider_name}/{model_name}"
        logger.info(f"🚀 SUMMARY GENERATION START: conversation_id={conversation.id}, client_id={client.id}, provider={provider_info}")
        
        # For Ollama, limit message length to avoid timeout issues
        # Truncate messages_text if too long (keep last 2000 chars for context)
        max_context_length = 2000
        original_length = len(messages_text)
        if len(messages_text) > max_context_length:
            logger.info(f"✂️ Truncating messages for summary: {original_length} -> {max_context_length} chars")
            messages_text = "..." + messages_text[-max_context_length:]
        
        # Update prompt with truncated messages
        prompt = f"""Summarize the conversation in the same language as the user's messages. Do not force Ukrainian if the chat is in English.

Generate a concise summary of this customer support conversation in {lang_name} language. Be concise and avoid repetitive words.

Conversation:
{messages_text}

Provide a summary that includes:
1. Main topic/issue discussed
2. Key points covered
3. Resolution or outcome
4. Customer satisfaction (if evident)

Summary ({lang_name}):"""
        
        logger.info(f"📝 Prompt prepared: length={len(prompt)}, language={lang_name}, session_messages={len(session_messages)}")
        
        # Initialize LLM client
        llm_client = LLMClient()
        logger.info(f"🔧 LLMClient initialized, calling generate_response with client={client.id}")
        
        # Call LLM
        import time
        start_time = time.time()
        try:
            result = llm_client.generate_response(
                user_query=prompt,
                context="",
                client=client,  # Use client's configured model (e.g., ollama_light/qwen2.5:1.5b)
                stream=False
            )
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ LLM call completed in {elapsed_time:.2f}s")
        except Exception as llm_error:
            elapsed_time = time.time() - start_time
            logger.error(f"❌ LLM call failed after {elapsed_time:.2f}s: {type(llm_error).__name__}: {str(llm_error)}", exc_info=True)
            raise
        
        # Handle dict response (new format) or string (old format)
        if isinstance(result, dict):
            summary = result.get('content', '')
            usage = result.get('usage', {})
            model_used = result.get('model', 'unknown')
            provider_used = result.get('provider', 'unknown')
            logger.info(f"📦 LLM response format: dict, model={model_used}, provider={provider_used}, usage={usage}, content_length={len(summary) if summary else 0}")
        else:
            summary = str(result)
            logger.info(f"📦 LLM response format: string, content_length={len(summary) if summary else 0}")
        
        if summary and summary.strip():
            logger.info(f"✅ SUMMARY GENERATION SUCCESS: conversation_id={conversation.id}, summary_length={len(summary)}, preview={summary[:100]}...")
            return summary.strip()
        else:
            logger.error(f"❌ SUMMARY GENERATION FAILED: LLM returned empty summary for conversation {conversation.id}, provider={provider_name}/{model_name}, result_type={type(result)}")
            raise ValueError(f"LLM returned empty summary for conversation {conversation.id}")
            
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Extract provider info for logging
        provider_name = 'unknown'
        model_name = 'unknown'
        if conversation.client:
            llm_provider_obj = getattr(conversation.client, "llm_provider_model", None)
            if llm_provider_obj is not None:
                provider_name = getattr(llm_provider_obj, "provider_type", "unknown")
                model_name = getattr(llm_provider_obj, "model_name", "unknown")
            else:
                provider_name = getattr(conversation.client, 'llm_provider', 'unknown')
                model_name = getattr(conversation.client, 'llm_model_name', 'unknown')
        
        logger.error(f"❌ SUMMARY GENERATION FAILED: conversation_id={conversation.id}, error_type={error_type}, provider={provider_name}/{model_name}, error={error_msg}", exc_info=True)
        
        # Check if it's a timeout or connection error (common with Ollama)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower() or "read timed out" in error_msg.lower():
            logger.warning(f"⚠️ Ollama timeout/connection error detected for conversation {conversation.id}")
        
        # Re-raise exception instead of fallback - let caller handle it
        raise


def _generate_fallback_summary(conversation, messages_text, lang_name):
    """
    Generate a basic fallback summary when LLM generation fails.
    Only includes messages from this session.
    Uses conversationmessage_set.all() to get messages from database.
    """
    from django.utils import timezone
    from datetime import datetime
    
    try:
        # Get messages from database using conversationmessage_set
        session_start = conversation.started_at
        session_end = conversation.ended_at or timezone.now()
        
        # Try to get messages from ConversationMessage model via related manager
        if hasattr(conversation, 'conversationmessage_set'):
            db_messages = conversation.conversationmessage_set.all()
            
            # Filter messages by created_at between session_start and session_end
            session_messages_qs = db_messages.filter(
                created_at__gte=session_start,
                created_at__lte=session_end
            ).order_by('created_at')
            
            # Convert QuerySet to list of dicts for processing
            session_messages = []
            for msg in session_messages_qs:
                session_messages.append({
                    'role': getattr(msg, 'role', 'unknown'),
                    'content': getattr(msg, 'content', ''),
                    'timestamp': msg.created_at.isoformat() if hasattr(msg, 'created_at') else ''
                })
        else:
            # Fallback to JSONField if conversationmessage_set doesn't exist
            session_messages = []
            if conversation.messages:
                for msg in conversation.messages:
                    if not isinstance(msg, dict):
                        continue
                    
                    timestamp_str = msg.get('timestamp', '')
                    if timestamp_str:
                        try:
                            msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            msg_time = timezone.make_aware(msg_time) if timezone.is_naive(msg_time) else msg_time
                            
                            # Only include messages from this session
                            if session_start and session_end:
                                if session_start <= msg_time <= session_end:
                                    session_messages.append(msg)
                            elif session_start:
                                if msg_time >= session_start:
                                    session_messages.append(msg)
                        except Exception:
                            # If timestamp parsing fails, include message (fallback)
                            session_messages.append(msg)
                    else:
                        # If no timestamp, include message (fallback)
                        session_messages.append(msg)
        
        # Count messages by role (only from this session)
        user_messages = [msg for msg in session_messages if msg.get('role') == 'user']
        assistant_messages = [msg for msg in session_messages if msg.get('role') == 'assistant']
        
        # Get first and last user messages
        first_user_msg = user_messages[0].get('content', '')[:100] if user_messages else ''
        last_user_msg = user_messages[-1].get('content', '')[:100] if user_messages else ''
        
        # Basic summary
        summary_parts = []
        if lang_name == 'Ukrainian':
            summary_parts.append(f"Розмова містить {len(user_messages)} повідомлень від клієнта та {len(assistant_messages)} відповідей.")
            if first_user_msg:
                summary_parts.append(f"Перше питання: {first_user_msg}...")
            if last_user_msg and last_user_msg != first_user_msg:
                summary_parts.append(f"Останнє повідомлення: {last_user_msg}...")
        else:
            summary_parts.append(f"Conversation contains {len(user_messages)} customer messages and {len(assistant_messages)} assistant responses.")
            if first_user_msg:
                summary_parts.append(f"First question: {first_user_msg}...")
            if last_user_msg and last_user_msg != first_user_msg:
                summary_parts.append(f"Last message: {last_user_msg}...")
        
        return " ".join(summary_parts) if summary_parts else f"Conversation with {conversation.total_messages} messages."
        
    except Exception as e:
        logger.error(f"Error generating fallback summary: {str(e)}", exc_info=True)
        return f"Conversation summary: {conversation.total_messages} messages exchanged."


def format_chat_as_text(conversation):
    """
    Format full conversation as text for email attachment.
    Only includes messages from this session (between started_at and ended_at/now).
    Uses conversationmessage_set.all() to get messages from database.
    """
    from datetime import datetime
    from django.utils import timezone
    
    # Get messages from database using conversationmessage_set
    session_start = conversation.started_at
    session_end = conversation.ended_at or timezone.now()
    
    try:
        # Try to get messages from ConversationMessage model via related manager
        if hasattr(conversation, 'conversationmessage_set'):
            db_messages = conversation.conversationmessage_set.all()
            
            # Filter messages by created_at between session_start and session_end
            session_messages_qs = db_messages.filter(
                created_at__gte=session_start,
                created_at__lte=session_end
            ).order_by('created_at')
            
            # Convert QuerySet to list of dicts for processing
            session_messages = []
            for msg in session_messages_qs:
                session_messages.append({
                    'role': getattr(msg, 'role', 'unknown'),
                    'content': getattr(msg, 'content', ''),
                    'timestamp': msg.created_at.isoformat() if hasattr(msg, 'created_at') else ''
                })
        else:
            # Fallback to JSONField if conversationmessage_set doesn't exist
            session_messages = []
            if conversation.messages:
                for msg in conversation.messages:
                    if not isinstance(msg, dict):
                        continue
                    
                    timestamp_str = msg.get('timestamp', '')
                    if not timestamp_str:
                        continue
                    
                    try:
                        msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        msg_time = timezone.make_aware(msg_time) if timezone.is_naive(msg_time) else msg_time
                        
                        # Only include messages from this session
                        if session_start and session_end:
                            if session_start <= msg_time <= session_end:
                                session_messages.append(msg)
                        elif session_start:
                            if msg_time >= session_start:
                                session_messages.append(msg)
                    except Exception:
                        # If timestamp parsing fails, include message (fallback)
                        session_messages.append(msg)
    except Exception as e:
        logger.error(f"Error getting messages for format_chat_as_text: {str(e)}", exc_info=True)
        session_messages = []
    
    # Refresh conversation from database to ensure we have latest rating
    conversation.refresh_from_db(fields=['user_rating', 'ai_rating', 'summary'])
    
    # Get rating - check both user_rating and ai_rating, handle empty strings
    rating = conversation.user_rating or conversation.ai_rating
    if not rating or rating.strip() == '':
        rating = 'Not rated'
    elif rating == 'positive':
        rating = '👍 Positive'
    elif rating == 'negative':
        rating = '👎 Negative'
    
    lines = [
        f"Chat Session Report",
        f"{'=' * 50}",
        f"Client: {conversation.client.company_name}",
        f"Customer: {conversation.customer_phone}",
        f"Session ID: {conversation.session_id or 'N/A'}",
        f"Started: {conversation.started_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.started_at else 'N/A'}",
        f"Ended: {conversation.ended_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.ended_at else 'N/A'}",
        f"Total Messages: {len(session_messages)}",
        f"Language: {conversation.language}",
        f"Rating: {rating}",
        f"{'=' * 50}",
        "",
        "CONVERSATION:",
        "",
    ]
    
    # Log filtering result for debugging
    logger.debug(f"format_chat_as_text: Filtered {len(session_messages)} messages from {len(conversation.messages)} total for conversation {conversation.id} (session: {session_start} to {session_end})")
    
    for i, msg in enumerate(session_messages, 1):
        role = msg.get('role', 'unknown').upper()
        content = msg.get('content', '')
        timestamp = msg.get('timestamp', '')
        
        # Parse timestamp
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = 'N/A'
        except:
            time_str = timestamp
        
        lines.append(f"[{time_str}] {role}:")
        lines.append(content)
        lines.append("")
    
    # Always add summary section - show error message if generation failed
    lines.append("")
    lines.append("SUMMARY:")
    if conversation.summary:
        lines.append(conversation.summary)
    else:
        lines.append("Summary generation failed due to an error.")
    
    return "\n".join(lines)


def send_chat_summary_email(conversation, chat_text, recipients=None, subject_prefix: str = ""):
    """
    Send chat summary email to client recipients with attachment.
    Uses Django's get_connection with client-specific SMTP settings.
    
    Args:
        conversation: ClientWhatsAppConversation instance
        chat_text: Formatted chat text to attach
        recipients: Optional list of email addresses. If None, uses email_from_address or email_smtp_username
    """
    from django.core.mail import get_connection, EmailMultiAlternatives
    
    if not conversation.client.email_smtp_enabled:
        logger.error(f"SMTP not enabled for client {conversation.client.id}")
        return {"success": False, "error": "SMTP not enabled", "message": "Email not sent. Check email settings."}
    
    # Validate SMTP settings
    if not conversation.client.email_smtp_host:
        logger.error(f"SMTP host not configured for client {conversation.client.id}")
        return {"success": False, "error": "SMTP host not configured", "message": "Email not sent. Check email settings."}
    
    if not conversation.client.email_smtp_username:
        logger.error(f"SMTP username not configured for client {conversation.client.id}")
        return {"success": False, "error": "SMTP username not configured", "message": "Email not sent. Check email settings."}
    
    if not conversation.client.email_smtp_password:
        logger.error(f"SMTP password not configured for client {conversation.client.id}")
        return {"success": False, "error": "SMTP password not configured", "message": "Email not sent. Check email settings."}
    
    try:
        # Determine use_tls and use_ssl based on client settings
        # If use_tls is True, use STARTTLS (port 587)
        # If use_tls is False and port is 465, use SSL
        port = int(getattr(conversation.client, 'email_smtp_port', 0) or 0)
        if port == 465:
            # SSL (implicit TLS) for port 465
            use_ssl = True
            use_tls = False
        else:
            use_tls = conversation.client.email_smtp_use_tls
            use_ssl = False
        
        # Get from_email address
        from_email = conversation.client.email_from_address or conversation.client.email_smtp_username
        from_name = conversation.client.email_from_name or conversation.client.company_name or "AI Assistant"
        from_address = f"{from_name} <{from_email}>"
        
        # Create SMTP connection with client-specific settings
        # Using exact field names from Client model:
        # - client.email_smtp_host
        # - client.email_smtp_port
        # - client.email_smtp_username
        # - client.email_smtp_password
        # - client.email_smtp_use_tls
        # - client.email_from_address
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=conversation.client.email_smtp_host,
            port=conversation.client.email_smtp_port,
            username=conversation.client.email_smtp_username,
            password=conversation.client.email_smtp_password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=30,
        )
        
        # Prepare email
        prefix = (subject_prefix or "").strip()
        if prefix:
            prefix = prefix + " "
        subject = f"{prefix}Chat Session Summary - {conversation.client.company_name}"
        
        # Email body with summary
        summary_html = conversation.summary.replace(chr(10), '<br>') if conversation.summary else 'No summary available.'
        rating_display = conversation.user_rating or conversation.ai_rating or 'Not rated'
        if rating_display == 'positive':
            rating_display = '👍 Positive'
        elif rating_display == 'negative':
            rating_display = '👎 Negative'
        
        body_html = f"""
        <html>
        <body>
            <h2>Chat Session Summary</h2>
            <p><strong>Client:</strong> {conversation.client.company_name}</p>
            <p><strong>Customer:</strong> {conversation.customer_phone}</p>
            <p><strong>Session ID:</strong> {conversation.session_id or 'N/A'}</p>
            <p><strong>Started:</strong> {conversation.started_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.started_at else 'N/A'}</p>
            <p><strong>Ended:</strong> {conversation.ended_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.ended_at else 'N/A'}</p>
            <p><strong>Total Messages:</strong> {conversation.total_messages}</p>
            <p><strong>Rating:</strong> {rating_display}</p>
            
            <h3>Summary:</h3>
            <p>{summary_html}</p>
            
            <p><em>Full conversation transcript is attached as a text file.</em></p>
        </body>
        </html>
        """
        
        body_text = f"""
Chat Session Summary

Client: {conversation.client.company_name}
Customer: {conversation.customer_phone}
Session ID: {conversation.session_id or 'N/A'}
Started: {conversation.started_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.started_at else 'N/A'}
Ended: {conversation.ended_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.ended_at else 'N/A'}
Total Messages: {conversation.total_messages}
Rating: {rating_display}

Summary:
{conversation.summary or 'No summary available.'}

Full conversation transcript is attached as a text file.
        """
        
        # Determine recipient emails
        if recipients is None:
            # Always use email_from_address as recipient
            recipient_email = conversation.client.email_from_address or conversation.client.email_smtp_username
            if recipient_email:
                recipients = [recipient_email]
            else:
                logger.error(f"No email recipient configured for client {conversation.client.id}")
                return {"success": False, "error": "No email recipient configured", "message": "Email not sent. Configure email_from_address in Email Setup."}
        
        # Ensure recipients is a list
        if not isinstance(recipients, list):
            recipients = [recipients] if recipients else []
        
        if not recipients:
            logger.error(f"No email recipients provided for client {conversation.client.id}")
            return {"success": False, "error": "No email recipients provided", "message": "Email not sent. No recipients specified."}
        
        results = []
        
        # Attachment filename
        filename = f"chat_session_{conversation.id}_{conversation.session_id or 'unknown'}.txt"
        
        # Send email to all recipients
        for recipient_email in recipients:
            if not recipient_email:
                continue
                
            try:
                # Create EmailMultiAlternatives for HTML + plain text
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=body_text,
                    from_email=from_address,
                    to=[recipient_email],
                    connection=connection,
                )
                # Attach HTML alternative
                email.attach_alternative(body_html, "text/html")
                
                # Add attachment
                email.attach(
                    filename=filename,
                    content=chat_text.encode('utf-8'),
                    mimetype='text/plain'
                )
                
                # Send email with fail_silently=False to see errors in Celery logs
                email.send(fail_silently=False)
                
                results.append({"recipient": recipient_email, "success": True})
                logger.info(f"Sent chat summary email to {recipient_email} for conversation {conversation.id}")
            except Exception as e:
                logger.error(f"Failed to send email to {recipient_email}: {str(e)}", exc_info=True)
                results.append({"recipient": recipient_email, "success": False, "error": str(e)})
        
        return {
            "success": True,
            "sent_count": sum(1 for r in results if r.get("success")),
            "total_count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to send chat summary email: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


def _get_conversation_platform(conversation) -> str:
    """Best-effort platform inference for reporting."""
    try:
        if getattr(conversation, 'telegram_chat_id', ''):
            return 'telegram'
        customer_phone = getattr(conversation, 'customer_phone', '') or ''
        if customer_phone.startswith('telegram_'):
            return 'telegram'

        platform = None
        context_metadata = getattr(conversation, 'context_metadata', None) or {}
        if isinstance(context_metadata, dict):
            platform = context_metadata.get('platform')

        if platform in ['web', 'web_widget', 'iframe']:
            return 'web'
        if customer_phone.startswith('web_'):
            return 'web'
    except Exception:
        pass
    return 'whatsapp'


def _get_last_user_quote(conversation, max_len: int = 180) -> str:
    """Extract a short user quote from JSON messages (best-effort)."""
    try:
        messages = getattr(conversation, 'messages', None)
        if not isinstance(messages, list):
            return ""
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if msg.get('role') != 'user':
                continue
            content = (msg.get('content') or '').strip()
            if content:
                return content[:max_len] + ("…" if len(content) > max_len else "")
    except Exception:
        return ""
    return ""


def _generate_daily_meta_summary(client, summaries: list[str]) -> str:
    """
    Generate a "Daily Meta-Summary" via the existing LLM client.
    Keep the prompt short and token-safe.
    """
    if not summaries:
        return "No chats for today."

    from MASTER.rag.llm_client import LLMClient

    # Token safety: include up to 40 short summaries
    clipped = [s.strip() for s in summaries if s and s.strip()]
    clipped = clipped[:40]
    clipped = [s[:240] + ("…" if len(s) > 240 else "") for s in clipped]

    prompt = (
        "You are preparing a daily digest for a business owner.\n"
        "Based on the chat summaries below, write a short meta-summary with:\n"
        "1) Most frequent topics\n"
        "2) Overall sentiment\n"
        "3) Business advice / next actions\n\n"
        "Chat summaries:\n"
        + "\n".join([f"- {s}" for s in clipped])
        + "\n\nRespond concisely in English."
    )

    llm = LLMClient()
    result = llm.generate_response(
        user_query=prompt,
        context="",
        client=client,
        stream=False,
    )

    if isinstance(result, dict):
        return (result.get('content') or '').strip() or "Meta-summary unavailable."
    return str(result).strip() or "Meta-summary unavailable."


def _send_daily_digest_email(
    *,
    client,
    recipients: list[str],
    subject: str,
    body_html: str,
    body_text: str,
    attachments: list[tuple[str, bytes, str]],
) -> dict:
    """Send ONE digest email per client (one message, multiple attachments)."""
    from django.core.mail import get_connection, EmailMultiAlternatives

    port = int(getattr(client, 'email_smtp_port', 0) or 0)
    # Port 465 = SSL (implicit TLS), should NOT use STARTTLS
    if port == 465:
        use_ssl = True
        use_tls = False
    else:
        use_tls = client.email_smtp_use_tls
        use_ssl = False

    from_email = client.email_from_address or client.email_smtp_username
    from_name = client.email_from_name or client.company_name or "AI Assistant"
    from_address = f"{from_name} <{from_email}>"

    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=client.email_smtp_host,
        port=client.email_smtp_port,
        username=client.email_smtp_username,
        password=client.email_smtp_password,
        use_tls=use_tls,
        use_ssl=use_ssl,
    )

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_address,
            to=recipients,
            connection=connection,
        )
        email.attach_alternative(body_html, "text/html")

        for filename, content, mimetype in attachments:
            email.attach(filename=filename, content=content, mimetype=mimetype)

        email.send(fail_silently=False)
        return {"success": True, "sent_to": recipients, "attachments": len(attachments)}
    except Exception as e:
        logger.error(f"Failed to send daily digest email for client {client.id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@shared_task
def send_daily_digest(manual: bool = False):
    """
    Daily digest at 17:00 (scheduled via CELERY_BEAT_SCHEDULE).

    - Aggregates today's chats per client
    - Generates a daily meta-summary via LLM
    - Highlights top 5 positives and all negatives
    - Attaches transcripts for ALL negative conversations

    Args:
        manual: If True, uses last 24 hours instead of today 09:00-17:00 window.
                This allows immediate testing without waiting for scheduled time.
    """
    from datetime import datetime, time, timedelta
    from django.utils import timezone
    from django.db.models import Count, Q
    from django.db.models.functions import ExtractHour
    from MASTER.clients.models import Client, ClientWhatsAppConversation

    tz = timezone.get_current_timezone()
    now = timezone.now()

    if manual:
        # Manual trigger: last 24 hours
        start = now - timedelta(hours=24)
        end = now
        today = timezone.localdate()
        logger.info(f"📊 Manual daily digest triggered: {start} to {end}")
    else:
        # Scheduled: today 09:00 -> 17:00 (or now if before 17:00)
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time(hour=9, minute=0)), tz)
        scheduled_end = timezone.make_aware(datetime.combine(today, time(hour=17, minute=0)), tz)
        end = min(now, scheduled_end)
        logger.info(f"📊 Scheduled daily digest: {start} to {end}")

    results: list[dict] = []

    clients = Client.objects.filter(email_report_enabled=True).select_related('active_custom_prompt')
    for client in clients:
        # Only send if SMTP is usable
        if not client.email_smtp_enabled:
            continue
        if not (client.email_smtp_host and client.email_smtp_username and client.email_smtp_password):
            continue

        recipients = client.get_report_recipients()
        if not recipients:
            fallback = client.email_from_address or client.email_smtp_username
            if fallback:
                recipients = [fallback]
        if not recipients:
            continue

        qs = ClientWhatsAppConversation.objects.filter(
            client=client,
            started_at__gte=start,
            started_at__lt=end,
        ).order_by('started_at')

        total_chats = qs.count()
        if total_chats == 0:
            continue

        # Ratings
        negative_q = Q(user_rating='negative') | Q(ai_rating='negative')
        positive_q = Q(user_rating='positive') | Q(ai_rating='positive')
        negative_count = qs.filter(negative_q).count()
        positive_count = qs.filter(positive_q).count()
        
        # HITL Escalations - when AI didn't have enough knowledge
        escalation_q = Q(is_waiting_for_manager=True) | ~Q(manager_escalation_context='')
        escalation_count = qs.filter(escalation_q).count()

        # Top activity hours (by started_at)
        hours = list(
            qs.annotate(hour=ExtractHour('started_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        # Platform counts
        platform_counts = {'whatsapp': 0, 'telegram': 0, 'web': 0}
        conversations = list(qs)
        for conv in conversations:
            platform = _get_conversation_platform(conv)
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

        # Ensure summaries exist + collect them
        summaries: list[str] = []
        for conv in conversations:
            if not (conv.summary or '').strip():
                try:
                    summary = generate_chat_summary(conv)
                    if summary and summary.strip():
                        conv.summary = summary.strip()
                        conv.save(update_fields=['summary'])
                except Exception as e:
                    logger.warning(f"Daily digest: failed to generate summary for conv={conv.id}: {e}")
            if (conv.summary or '').strip():
                summaries.append(conv.summary.strip())

        meta_summary = _generate_daily_meta_summary(client, summaries)

        # Highlight positives (top 5 by rating_timestamp, fallback started_at)
        positives = sorted(
            [c for c in conversations if (c.user_rating == 'positive' or c.ai_rating == 'positive')],
            key=lambda c: (c.rating_timestamp or c.started_at or start),
            reverse=True,
        )[:5]
        positive_rows = [
            {
                "id": c.id,
                "user": c.customer_phone,
                "quote": _get_last_user_quote(c),
                "summary": (c.summary or "").strip(),
            }
            for c in positives
        ]

        # All negatives + attachments
        negatives = [c for c in conversations if (c.user_rating == 'negative' or c.ai_rating == 'negative')]
        negative_rows = [
            {
                "id": c.id,
                "user": c.customer_phone,
                "rating": c.user_rating or c.ai_rating,
                "summary": (c.summary or "").strip(),
            }
            for c in negatives
        ]
        
        # HITL Escalations - conversations where AI needed human help
        escalations = [c for c in conversations if c.is_waiting_for_manager or (c.manager_escalation_context or '').strip()]
        escalation_rows = [
            {
                "id": c.id,
                "user": c.customer_phone,
                "question": (c.manager_escalation_context or "").strip()[:200],
                "resolved": not c.is_waiting_for_manager,
            }
            for c in escalations
        ]

        attachments: list[tuple[str, bytes, str]] = []
        for c in negatives:
            try:
                transcript = format_chat_as_text(c)
                filename = f"NEGATIVE_chat_{today.isoformat()}_{c.id}_{c.session_id or 'unknown'}.txt"
                attachments.append((filename, transcript.encode('utf-8'), 'text/plain'))
            except Exception as e:
                logger.warning(f"Daily digest: failed to build transcript for conv={c.id}: {e}")

        # Render HTML (simple, clean)
        hours_str = ", ".join(
            [f"{(h.get('hour') if h.get('hour') is not None else 'N/A')}:00 ({h.get('count', 0)})" for h in hours]
        )
        subject_prefix = "🔴 " if negative_count > 0 else ""
        subject = f"{subject_prefix}Daily Digest - {client.company_name} - {today.isoformat()}"

        # Build escalation status emoji
        escalation_emoji = "🟢" if escalation_count == 0 else ("🟡" if escalation_count <= 2 else "🔴")
        
        body_html = f"""
        <html>
        <body>
          <h2>Daily Digest — {today.isoformat()}</h2>
          <p><strong>Client:</strong> {client.company_name}</p>
          <h3>Stats</h3>
          <ul>
            <li><strong>Total chats:</strong> {total_chats}</li>
            <li><strong>WhatsApp:</strong> {platform_counts.get('whatsapp', 0)}</li>
            <li><strong>Telegram:</strong> {platform_counts.get('telegram', 0)}</li>
            <li><strong>Web:</strong> {platform_counts.get('web', 0)}</li>
            <li><strong>Positive:</strong> {positive_count}</li>
            <li><strong>Negative:</strong> {negative_count}</li>
            <li><strong>{escalation_emoji} AI Knowledge Gaps (Escalations):</strong> {escalation_count}</li>
            <li><strong>Top hours:</strong> {hours_str or 'N/A'}</li>
          </ul>

          <h3>Daily Meta-Summary</h3>
          <p>{(meta_summary or 'N/A').replace(chr(10), '<br>')}</p>

          <h3>🧠 AI Knowledge Gaps (Escalations)</h3>
          <p><em>Questions where AI didn't have enough information and needed human help:</em></p>
          <ul>
            {''.join([f"<li><strong>{r['user']}</strong> (conv #{r['id']}): {r['question'] or 'No context saved'} {'✅ Resolved' if r['resolved'] else '⏳ Pending'}</li>" for r in escalation_rows]) or "<li>✅ No escalations - AI had sufficient knowledge for all conversations!</li>"}
          </ul>

          <h3>Top 5 Positive Feedback</h3>
          <ol>
            {''.join([f"<li><strong>{r['user']}</strong>: {r['quote'] or r['summary'][:180]}</li>" for r in positive_rows]) or "<li>N/A</li>"}
          </ol>

          <h3>All Negative Conversations</h3>
          <ul>
            {''.join([f"<li><strong>{r['user']}</strong> (conv #{r['id']}): {r['summary'] or 'No summary'}</li>" for r in negative_rows]) or "<li>None</li>"}
          </ul>

          <p><em>Note:</em> Full transcripts are attached for negative conversations.</p>
        </body>
        </html>
        """

        body_text = (
            f"Daily Digest — {today.isoformat()}\n"
            f"Client: {client.company_name}\n\n"
            f"Total chats: {total_chats}\n"
            f"WhatsApp: {platform_counts.get('whatsapp', 0)}\n"
            f"Telegram: {platform_counts.get('telegram', 0)}\n"
            f"Web: {platform_counts.get('web', 0)}\n"
            f"Positive: {positive_count}\n"
            f"Negative: {negative_count}\n"
            f"{escalation_emoji} AI Knowledge Gaps (Escalations): {escalation_count}\n"
            f"Top hours: {hours_str or 'N/A'}\n\n"
            f"Daily Meta-Summary:\n{meta_summary}\n"
        )

        send_result = _send_daily_digest_email(
            client=client,
            recipients=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments,
        )

        results.append(
            {
                "client_id": client.id,
                "client": client.company_name,
                "total_chats": total_chats,
                "negative": negative_count,
                "escalations": escalation_count,
                "sent": bool(send_result.get("success")),
                "send_result": send_result,
            }
        )

    return {"success": True, "date": today.isoformat(), "results": results}


# =============================================================================
# HITL (Human-in-the-Loop) Escalation Tasks
# =============================================================================

@shared_task(bind=True, max_retries=3)
def notify_manager_of_escalation(self, conversation_id: int, question_summary: str) -> Dict[str, Any]:
    """
    Notify managers via Telegram when AI escalates a question.
    
    Args:
        conversation_id: ID of the ClientWhatsAppConversation
        question_summary: Summary of the question that needs manager input
    
    Returns:
        Dict with success status and details
    """
    import requests
    from MASTER.clients.models import Client, ClientWhatsAppConversation
    
    def escape_html(text: str) -> str:
        """Escape HTML special characters for Telegram HTML parse_mode."""
        if not text:
            return text
        return (
            text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
        )
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        client = conversation.client
        
        # Check if HITL is enabled
        if not getattr(client, 'hitl_enabled', False):
            logger.warning(f"HITL not enabled for client {client.id}, skipping escalation")
            return {"success": False, "error": "HITL not enabled"}
        
        # Get manager Telegram IDs
        manager_ids = client.get_manager_telegram_ids()
        if not manager_ids:
            logger.warning(f"No manager Telegram IDs configured for client {client.id}")
            return {"success": False, "error": "No managers configured"}
        
        # Check if any manager IDs are also customer chat IDs (e.g., manager tested the bot)
        # We LOG a warning but DON'T filter them out - explicitly configured manager IDs are trusted
        customer_chat_ids = set(
            ClientWhatsAppConversation.objects.filter(
                client=client,
                telegram_chat_id__isnull=False
            ).exclude(
                telegram_chat_id=''
            ).values_list('telegram_chat_id', flat=True)
        )
        
        # Convert to int set for comparison
        customer_ids_int = set()
        for cid in customer_chat_ids:
            try:
                customer_ids_int.add(int(cid))
            except (ValueError, TypeError):
                continue
        
        # Check for overlap but trust explicitly configured manager IDs
        overlap_ids = [mid for mid in manager_ids if mid in customer_ids_int]
        if overlap_ids:
            logger.info(
                f"Note: Manager IDs {overlap_ids} for client {client.id} also appear as customer chat IDs. "
                f"This is normal if managers tested the bot. Proceeding with escalation."
            )
        
        # Use all configured manager IDs (trust explicit configuration)
        valid_manager_ids = manager_ids
        
        # Check if client has Telegram bot token
        bot_token = client.telegram_bot_token
        if not bot_token:
            logger.error(f"No Telegram bot token for client {client.id}")
            return {"success": False, "error": "No bot token"}
        
        # Build the escalation message - use HTML parse_mode to avoid markdown issues
        customer_id = conversation.customer_phone or conversation.telegram_chat_id or f"Conv #{conversation.id}"
        platform = conversation.context_metadata.get('platform', 'unknown') if conversation.context_metadata else 'unknown'
        
        # Escape special characters in user-provided content
        escaped_company = escape_html(client.company_name)
        escaped_customer = escape_html(str(customer_id))
        escaped_question = escape_html(question_summary)
        
        message = (
            f"🆘 <b>ESCALATION NEEDED</b>\n\n"
            f"<b>Client:</b> {escaped_company}\n"
            f"<b>Customer:</b> {escaped_customer}\n"
            f"<b>Platform:</b> {platform}\n"
            f"<b>Conversation ID:</b> {conversation.id}\n\n"
            f"<b>Question:</b>\n{escaped_question}\n\n"
            f"💬 Reply to this message with your answer. The AI will rephrase it and send to the customer."
        )
        
        # Send to all valid managers (not customers)
        results = []
        first_message_id = None
        first_manager_id = None
        
        for manager_id in valid_manager_ids:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": manager_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=10)
                response_data = response.json()
                
                if response_data.get('ok'):
                    msg_id = response_data.get('result', {}).get('message_id')
                    results.append({"manager_id": manager_id, "success": True, "message_id": msg_id})
                    if first_message_id is None:
                        first_message_id = str(msg_id)
                        first_manager_id = str(manager_id)
                    logger.info(f"Escalation notification sent to manager {manager_id}")
                else:
                    error = response_data.get('description', 'Unknown error')
                    results.append({"manager_id": manager_id, "success": False, "error": error})
                    logger.error(f"Failed to send escalation to manager {manager_id}: {error}")
                    
            except Exception as e:
                results.append({"manager_id": manager_id, "success": False, "error": str(e)})
                logger.error(f"Error sending escalation to manager {manager_id}: {e}")
        
        # Update conversation with escalation status
        conversation.is_waiting_for_manager = True
        conversation.manager_escalation_context = question_summary
        if first_message_id:
            conversation.last_escalation_message_id = first_message_id
        if first_manager_id:
            conversation.escalation_manager_id = first_manager_id
        conversation.save(update_fields=[
            'is_waiting_for_manager', 
            'manager_escalation_context',
            'last_escalation_message_id',
            'escalation_manager_id'
        ])
        
        successful = sum(1 for r in results if r.get('success'))
        return {
            "success": successful > 0,
            "conversation_id": conversation_id,
            "managers_notified": successful,
            "total_managers": len(valid_manager_ids),
            "results": results
        }
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found for escalation")
        return {"success": False, "error": "Conversation not found"}
    except Exception as e:
        logger.error(f"Error in notify_manager_of_escalation: {e}", exc_info=True)
        # Retry on failure
        raise self.retry(exc=e, countdown=60)


@shared_task
def process_manager_hitl_response(conversation_id: int, manager_response: str, manager_telegram_id: int) -> Dict[str, Any]:
    """
    Process manager's response to an escalated question.
    
    The AI will rephrase the manager's response to maintain tone of voice,
    then send it to the customer.
    
    Args:
        conversation_id: ID of the conversation
        manager_response: Raw response text from the manager
        manager_telegram_id: Telegram ID of the manager who responded
    
    Returns:
        Dict with success status and the final response sent to customer
    """
    from MASTER.clients.models import ClientWhatsAppConversation
    from MASTER.rag.llm_client import LLMClient
    from MASTER.clients.views_telegram import send_telegram_message
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        client = conversation.client
        
        if not conversation.is_waiting_for_manager:
            logger.warning(f"Conversation {conversation_id} was not waiting for manager response")
            return {"success": False, "error": "Not waiting for manager"}
        
        # Use LLM to rephrase manager's response to maintain tone
        llm_client = LLMClient()
        
        rephrase_prompt = f"""The customer asked: "{conversation.manager_escalation_context}"

A human supervisor provided this answer: "{manager_response}"

Please rephrase this answer in a professional and friendly tone, as if you (the AI assistant) verified the information. 
Start with something like "Thank you for waiting. I've confirmed the details..." or similar.
Keep the core information accurate but make it sound natural.
Respond in the same language as the customer's question."""

        try:
            result = llm_client.generate_response(
                user_query=rephrase_prompt,
                context="",
                client=client,
                stream=False
            )
            
            if isinstance(result, dict):
                final_response = result.get('content', manager_response)
            else:
                final_response = str(result) if result else manager_response
                
        except Exception as e:
            logger.warning(f"Failed to rephrase manager response: {e}, using original")
            final_response = f"Thank you for waiting. Here's the information: {manager_response}"
        
        # Send response to customer based on platform
        platform = conversation.context_metadata.get('platform', 'unknown') if conversation.context_metadata else 'unknown'
        send_success = False
        
        if platform == 'telegram' and conversation.telegram_chat_id:
            bot_token = client.telegram_bot_token
            if bot_token:
                send_success = send_telegram_message(bot_token, int(conversation.telegram_chat_id), final_response)
        elif platform == 'whatsapp' and conversation.customer_phone:
            # For WhatsApp, we'd need to use the Meta WhatsApp API
            # This is a placeholder - implement based on your WhatsApp integration
            logger.info(f"WhatsApp response would be sent to {conversation.customer_phone}")
            send_success = True  # Assume success for now, implement WhatsApp sending
        else:
            logger.warning(f"Unknown platform {platform} for conversation {conversation_id}")
        
        # Update conversation
        if not conversation.messages:
            conversation.messages = []
        
        # Add manager response as assistant message
        from django.utils import timezone
        conversation.messages.append({
            'role': 'assistant',
            'content': final_response,
            'timestamp': timezone.now().isoformat(),
            'metadata': {'hitl_response': True, 'manager_id': manager_telegram_id}
        })
        
        # Reset escalation state
        conversation.is_waiting_for_manager = False
        conversation.manager_escalation_context = ""
        conversation.last_escalation_message_id = ""
        conversation.escalation_manager_id = ""
        conversation.total_messages = len(conversation.messages)
        conversation.last_activity_at = timezone.now()
        
        conversation.save(update_fields=[
            'messages', 
            'is_waiting_for_manager',
            'manager_escalation_context',
            'last_escalation_message_id',
            'escalation_manager_id',
            'total_messages',
            'last_activity_at'
        ])
        
        logger.info(f"HITL response processed for conversation {conversation_id}")
        
        return {
            "success": send_success,
            "conversation_id": conversation_id,
            "response_sent": final_response[:200],
            "platform": platform
        }
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"success": False, "error": "Conversation not found"}
    except Exception as e:
        logger.error(f"Error processing manager HITL response: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

