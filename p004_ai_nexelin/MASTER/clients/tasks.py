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
    five_minutes_ago = now - timedelta(minutes=5)
    twenty_minutes_ago = now - timedelta(minutes=20)
    
    # Debug: Log all active conversations
    all_active = ClientWhatsAppConversation.objects.filter(is_active=True)
    logger.info(f"Total active conversations: {all_active.count()}")
    
    # Debug: Log conversations with details
    for conv in all_active[:10]:  # Log first 10 for debugging
        last_activity = conv.last_activity_at or conv.updated_at
        if last_activity:
            minutes_inactive = (now - last_activity).total_seconds() / 60
            logger.info(f"  Conv {conv.id}: last_activity={last_activity}, inactive_minutes={minutes_inactive:.1f}, "
                       f"user_rating={conv.user_rating}, rating_request_sent={conv.rating_request_sent}, "
                       f"platform={conv.context_metadata.get('platform') if conv.context_metadata else None}")
    
    # Find active conversations with last activity more than 5 minutes ago
    # Use updated_at if last_activity_at is NULL
    # Include conversations that have user_rating BUT have new messages after rating (new session)
    inactive_5min = ClientWhatsAppConversation.objects.filter(
        is_active=True
    ).filter(
        Q(last_activity_at__lte=five_minutes_ago) | 
        Q(last_activity_at__isnull=True, updated_at__lte=five_minutes_ago)
    )
    
    # Filter: exclude conversations with rating UNLESS they have new messages after rating (new session)
    conversations_to_check = []
    for conv in inactive_5min:
        has_rating = conv.user_rating in ['positive', 'negative']
        
        if not has_rating:
            # No rating - can send rating request
            conversations_to_check.append(conv)
        else:
            # Has rating - check if there are new messages after rating (new session)
            # Use last_activity_at as it's more reliable than parsing message timestamps
            if conv.rating_timestamp and conv.last_activity_at:
                # If last activity is after rating timestamp, it's a new session
                if conv.last_activity_at > conv.rating_timestamp:
                    logger.info(f"Conv {conv.id}: Has rating but new activity after rating (new session at {conv.last_activity_at}), resetting for new rating request")
                    # Reset rating flags for new session
                    conv.rating_request_sent = False
                    conv.user_rating = None
                    conv.rating_timestamp = None
                    conv.save(update_fields=['rating_request_sent', 'user_rating', 'rating_timestamp'])
                    conversations_to_check.append(conv)
                else:
                    logger.debug(f"Conv {conv.id}: Has rating and no new activity after rating (rating={conv.rating_timestamp}, last_activity={conv.last_activity_at}), skipping")
            elif conv.rating_timestamp and not conv.last_activity_at:
                # Has rating_timestamp but no last_activity_at - use updated_at as fallback
                if conv.updated_at > conv.rating_timestamp:
                    logger.info(f"Conv {conv.id}: Has rating but updated_at after rating (new session), resetting for new rating request")
                    conv.rating_request_sent = False
                    conv.user_rating = None
                    conv.rating_timestamp = None
                    conv.save(update_fields=['rating_request_sent', 'user_rating', 'rating_timestamp'])
                    conversations_to_check.append(conv)
                else:
                    logger.debug(f"Conv {conv.id}: Has rating and no new activity after rating, skipping")
            else:
                # Has rating but no rating_timestamp - skip (shouldn't happen, but safe fallback)
                logger.debug(f"Conv {conv.id}: Has rating but no rating_timestamp, skipping")
    
    inactive_5min = conversations_to_check
    
    logger.info(f"Found {len(inactive_5min)} conversations inactive for 5+ min (before rating_request_sent check)")
    
    # Debug: Log inactive conversations
    for conv in inactive_5min[:5]:  # Log first 5 for debugging
        last_activity = conv.last_activity_at or conv.updated_at
        if last_activity:
            minutes_inactive = (now - last_activity).total_seconds() / 60
            logger.info(f"  Inactive conv {conv.id}: last_activity={last_activity}, inactive_minutes={minutes_inactive:.1f}, "
                       f"user_rating={conv.user_rating}, rating_request_sent={conv.rating_request_sent}")
    
    # Find active conversations with last activity more than 20 minutes ago
    # Use updated_at if last_activity_at is NULL
    inactive_20min = ClientWhatsAppConversation.objects.filter(
        is_active=True
    ).filter(
        Q(last_activity_at__lte=twenty_minutes_ago) | 
        Q(last_activity_at__isnull=True, updated_at__lte=twenty_minutes_ago)
    )
    
    # Send rating request after 5 minutes
    rating_requests_sent = 0
    for conversation in inactive_5min:
        if not conversation.user_rating and not conversation.rating_request_sent:
            send_rating_request.delay(conversation.id)
            rating_requests_sent += 1
    
    # Close and send email after 20 minutes
    emails_scheduled = 0
    for conversation in inactive_20min:
        # Перевіряємо чи email вже надіслано
        if conversation.email_sent:
            # Якщо email вже надіслано, перевіряємо чи не було нової активності після відправки
            # Використовуємо last_activity_at або updated_at якщо last_activity_at NULL
            activity_time = conversation.last_activity_at or conversation.updated_at
            
            if conversation.email_sent_at and activity_time:
                # Якщо НЕ було нової активності після відправки email (activity_time <= email_sent_at),
                # не відправляємо повторно той самий email
                if activity_time <= conversation.email_sent_at:
                    logger.info(f"Conversation {conversation.id} email already sent and no new activity, skipping")
                    continue
                # Якщо була нова активність після відправки email, але сесія все ще неактивна (потрапила в inactive_20min),
                # це означає що після нової активності знову пройшло 20 хвилин - відправляємо новий email
                else:
                    logger.info(f"Conversation {conversation.id} has new activity after email was sent, will send new email")
            else:
                # Якщо email_sent=True але немає дати відправки, пропускаємо
                logger.info(f"Conversation {conversation.id} email_sent=True but no email_sent_at, skipping")
                continue
        
        # Відправляємо email (або перший раз, або повторно після нової активності)
        # Auto-rate if user hasn't rated yet (after 20 minutes of inactivity)
        if not conversation.user_rating and not conversation.ai_rating:
            # Call auto_rate synchronously first, then send email
            auto_rate_and_close_session.delay(conversation.id)
            emails_scheduled += 1
        else:
            # User already rated, just close and send email
            close_session_and_send_email.delay(conversation.id)
            emails_scheduled += 1
    
    logger.info(f"Found {len(inactive_5min)} conversations inactive for 5+ min, {inactive_20min.count()} for 20+ min")
    logger.info(f"Scheduled {rating_requests_sent} rating requests and {emails_scheduled} email reports")
    
    # Return simple dict without Celery task results to avoid JSON serialization errors
    return {
        "status": "success",
        "checked_5min": len(inactive_5min),
        "checked_20min": inactive_20min.count(),
        "rating_requests_scheduled": rating_requests_sent,
        "emails_scheduled": emails_scheduled
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
    Auto-rate conversation using AI after 5 minutes of inactivity (fallback if user doesn't rate).
    This is now a fallback - primary is send_rating_request.
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
        
        # Auto-rate if rating request was sent OR if called from auto_rate_and_close_session (20+ min)
        # Remove the check for rating_request_sent to allow auto-rating after 20 minutes
        
        # Generate rating using LLM
        messages_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:200]}"
            for msg in conversation.messages[-10:]  # Last 10 messages
        ])
        
        prompt = f"""Analyze this customer support conversation and rate it as positive (👍) or negative (👎).

Conversation:
{messages_text}

Respond with ONLY one word: "positive" or "negative"
Consider:
- Was the customer's issue resolved?
- Was the assistant helpful and professional?
- Was the customer satisfied with the responses?

Rating:"""
        
        llm_client = LLMClient()
        result = llm_client.generate_response(
            user_query=prompt,
            context="",
            client=conversation.client,
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
            if 'positive' in response_lower or '👍' in response:
                rating = 'positive'
            elif 'negative' in response_lower or '👎' in response:
                rating = 'negative'
        
        # Default to positive if unclear
        if not rating:
            rating = 'positive'
        
        conversation.ai_rating = rating
        conversation.rating_timestamp = timezone.now()
        conversation.save(update_fields=['ai_rating', 'rating_timestamp'])
        
        logger.info(f"Auto-rated conversation {conversation_id} as {rating}")
        return {"status": "success", "rating": rating}
        
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
            # Already rated, just close and send email
            close_session_and_send_email.delay(conversation_id)
            return {"status": "skipped", "message": "Already rated"}
        
        # Auto-rate first (call synchronously to ensure rating is saved before email)
        # We use .apply() instead of .delay() to ensure sequential execution
        rating_result = auto_rate_conversation.apply(args=[conversation_id])
        
        # Extract result value to avoid JSON serialization error
        # rating_result is EagerResult, we need to get the actual value
        try:
            rating_value = rating_result.get() if hasattr(rating_result, 'get') else rating_result.result
        except Exception:
            rating_value = {"status": "unknown", "rating": None}
        
        # Reload conversation to get updated rating
        conversation.refresh_from_db()
        
        # Then close and send email
        close_session_and_send_email.delay(conversation_id)
        
        # Extract rating from result dict for logging
        rating = rating_value.get('rating') if isinstance(rating_value, dict) else None
        logger.info(f"Auto-rated and closing session {conversation_id}: rating={rating}")
        
        # Return simple dict without Celery result objects to avoid JSON serialization errors
        return {"status": "success", "rating": rating}
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to auto-rate and close session {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def close_session_and_send_email(self, conversation_id: int):
    """
    Close chat session and send summary email to client after 20 minutes of inactivity.
    """
    from django.utils import timezone
    from datetime import timedelta
    from MASTER.clients.models import ClientWhatsAppConversation
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        
        # CRITICAL: Double-check inactivity before sending email (prevent race conditions and timezone issues)
        now = timezone.now()
        twenty_minutes_ago = now - timedelta(minutes=20)
        
        # Check if conversation is still inactive (using timezone-aware comparison)
        last_activity = conversation.last_activity_at or conversation.updated_at
        if last_activity and last_activity > twenty_minutes_ago:
            logger.info(f"Conversation {conversation_id} is still active (last_activity={last_activity}, now={now}), skipping email")
            return {"status": "skipped", "message": "Conversation is still active"}
        
        # Skip if email already sent AND no new activity after email was sent
        if conversation.email_sent:
            # Перевіряємо чи була нова активність після відправки email
            # Використовуємо last_activity_at або updated_at якщо last_activity_at NULL
            activity_time = conversation.last_activity_at or conversation.updated_at
            
            if conversation.email_sent_at and activity_time:
                if activity_time > conversation.email_sent_at:
                    # Була нова активність після відправки email, не відправляємо повторно
                    logger.info(f"Conversation {conversation_id} has new activity after email was sent, skipping")
                    return {"status": "skipped", "message": "New activity after email was sent"}
            # Email вже надіслано і немає нової активності
            logger.info(f"Conversation {conversation_id} email already sent, skipping")
            return {"status": "skipped", "message": "Email already sent"}
        
        # Check if client has email reports enabled
        if not conversation.client.email_report_enabled:
            logger.info(f"Email reports disabled for client {conversation.client.id}, closing session only")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "Email reports disabled"}
        
        # Check if SMTP is configured for the client
        if not conversation.client.email_smtp_enabled:
            logger.warning(f"SMTP not enabled for client {conversation.client.id}, cannot send email")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "SMTP not enabled. Check email settings."}
        
        # Check if SMTP settings are complete
        if not conversation.client.email_smtp_host or not conversation.client.email_smtp_username or not conversation.client.email_smtp_password:
            logger.warning(f"Incomplete SMTP settings for client {conversation.client.id}: host={bool(conversation.client.email_smtp_host)}, username={bool(conversation.client.email_smtp_username)}, password={bool(conversation.client.email_smtp_password)}")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "Incomplete SMTP settings. Check email settings."}
        
        # Always use email_from_address as recipient
        recipient_email = conversation.client.email_from_address or conversation.client.email_smtp_username
        if not recipient_email:
            logger.warning(f"No email recipient configured for client {conversation.client.id} (email_from_address required)")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "No email recipient configured"}
        
        # Generate summary if not exists
        if not conversation.summary:
            summary = generate_chat_summary(conversation)
            conversation.summary = summary
            conversation.save(update_fields=['summary'])
        
        # Generate full chat text
        chat_text = format_chat_as_text(conversation)
        
        # Send email to email_from_address
        email_result = send_chat_summary_email(conversation, chat_text, recipients=[recipient_email])
        
        # Update conversation
        conversation.is_active = False
        conversation.ended_at = timezone.now()
        
        # Only mark as sent if email was actually sent successfully
        if email_result.get("success") and email_result.get("sent_count", 0) > 0:
            conversation.email_sent = True
            conversation.email_sent_at = timezone.now()
            logger.info(f"Closed session {conversation_id} and sent email successfully: {email_result}")
        else:
            # Email failed to send, log error but still close session
            logger.error(f"Failed to send email for conversation {conversation_id}: {email_result}")
            conversation.email_sent = False
        
        conversation.save(update_fields=['is_active', 'ended_at', 'email_sent', 'email_sent_at'])
        
        return {"status": "success" if email_result.get("success") else "partial", "email_result": email_result}
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to close session and send email for {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


def generate_chat_summary(conversation):
    """
    Generate AI summary of the conversation.
    Returns a fallback summary if LLM generation fails.
    """
    from MASTER.rag.llm_client import LLMClient
    
    # Check if messages exist
    if not conversation.messages:
        return "No messages in this conversation."
    
    # Validate messages format
    if not isinstance(conversation.messages, list):
        logger.warning(f"Conversation {conversation.id} has invalid messages format: {type(conversation.messages)}")
        return "Unable to generate summary: invalid message format."
    
    if len(conversation.messages) == 0:
        return "No messages in this conversation."
    
    # Format messages for summary
    try:
        messages_text = "\n".join([
            f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
            for msg in conversation.messages
            if isinstance(msg, dict) and msg.get('content')
        ])
        
        if not messages_text or len(messages_text.strip()) < 10:
            return "Unable to generate summary: insufficient message content."
    except Exception as e:
        logger.error(f"Error formatting messages for conversation {conversation.id}: {str(e)}", exc_info=True)
        return "Unable to generate summary: error processing messages."
    
    # Detect language from messages instead of defaulting to Ukrainian
    detected_language = detect_language_from_messages(conversation.messages)
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
        llm_client = LLMClient()
        
        # For Ollama, limit message length to avoid timeout issues
        # Truncate messages_text if too long (keep last 2000 chars for context)
        max_context_length = 2000
        if len(messages_text) > max_context_length:
            logger.info(f"Truncating messages for summary generation (conversation {conversation.id}): {len(messages_text)} -> {max_context_length} chars")
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
        
        # Log which model will be used for summary generation
        client = conversation.client
        # Extract provider and model info correctly (support both FK and legacy fields)
        provider_name = 'unknown'
        model_name = 'unknown'
        if client:
            # Priority 1: Check llm_provider_model (FK)
            llm_provider_obj = getattr(client, "llm_provider_model", None)
            if llm_provider_obj is not None:
                provider_name = getattr(llm_provider_obj, "provider_type", "unknown")
                model_name = getattr(llm_provider_obj, "model_name", "unknown")
            else:
                # Priority 2: Check legacy string fields
                provider_name = getattr(client, 'llm_provider', 'unknown')
                model_name = getattr(client, 'llm_model_name', 'unknown')
        provider_info = f"{provider_name}/{model_name}"
        logger.info(f"Generating summary for conversation {conversation.id} using client model: {provider_info}")
        
        result = llm_client.generate_response(
            user_query=prompt,
            context="",
            client=client,  # Use client's configured model (e.g., ollama_light/qwen2.5:1.5b)
            stream=False
        )
        # Handle dict response (new format) or string (old format)
        if isinstance(result, dict):
            summary = result.get('content', '')
        else:
            summary = str(result)
        
        if summary and summary.strip():
            return summary.strip()
        else:
            # Extract provider info for logging
            provider_name = 'unknown'
            if conversation.client:
                llm_provider_obj = getattr(conversation.client, "llm_provider_model", None)
                if llm_provider_obj is not None:
                    provider_name = getattr(llm_provider_obj, "provider_type", "unknown")
                else:
                    provider_name = getattr(conversation.client, 'llm_provider', 'unknown')
            logger.warning(f"LLM returned empty summary for conversation {conversation.id} (provider: {provider_name})")
            # Fallback to basic summary
            return _generate_fallback_summary(conversation, messages_text, lang_name)
            
    except Exception as e:
        error_msg = str(e)
        # Extract provider info for logging
        provider_name = 'unknown'
        if conversation.client:
            llm_provider_obj = getattr(conversation.client, "llm_provider_model", None)
            if llm_provider_obj is not None:
                provider_name = getattr(llm_provider_obj, "provider_type", "unknown")
            else:
                provider_name = getattr(conversation.client, 'llm_provider', 'unknown')
        logger.error(f"Failed to generate summary for conversation {conversation.id} (provider: {provider_name}): {error_msg}", exc_info=True)
        
        # Check if it's a timeout or connection error (common with Ollama)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower() or "read timed out" in error_msg.lower():
            logger.warning(f"Ollama timeout/connection error for conversation {conversation.id}, using fallback summary")
        
        # Fallback to basic summary instead of error message
        return _generate_fallback_summary(conversation, messages_text, lang_name)


def _generate_fallback_summary(conversation, messages_text, lang_name):
    """
    Generate a basic fallback summary when LLM generation fails.
    """
    try:
        # Count messages by role
        user_messages = [msg for msg in conversation.messages if isinstance(msg, dict) and msg.get('role') == 'user']
        assistant_messages = [msg for msg in conversation.messages if isinstance(msg, dict) and msg.get('role') == 'assistant']
        
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
    """
    from datetime import datetime
    
    lines = [
        f"Chat Session Report",
        f"{'=' * 50}",
        f"Client: {conversation.client.company_name}",
        f"Customer: {conversation.customer_phone}",
        f"Session ID: {conversation.session_id or 'N/A'}",
        f"Started: {conversation.started_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.started_at else 'N/A'}",
        f"Ended: {conversation.ended_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.ended_at else 'N/A'}",
        f"Total Messages: {conversation.total_messages}",
        f"Language: {conversation.language}",
        f"Rating: {conversation.user_rating or conversation.ai_rating or 'Not rated'}",
        f"{'=' * 50}",
        "",
        "CONVERSATION:",
        "",
    ]
    
    for i, msg in enumerate(conversation.messages, 1):
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
    
    if conversation.summary:
        lines.append("")
        lines.append("SUMMARY:")
        lines.append(conversation.summary)
    
    return "\n".join(lines)


def send_chat_summary_email(conversation, chat_text, recipients=None):
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
        use_tls = conversation.client.email_smtp_use_tls
        use_ssl = not use_tls and conversation.client.email_smtp_port == 465
        
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
        )
        
        # Prepare email
        subject = f"Chat Session Summary - {conversation.client.company_name}"
        
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

