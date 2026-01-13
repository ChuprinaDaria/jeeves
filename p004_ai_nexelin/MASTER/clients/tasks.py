"""
Celery tasks для керування Zero-контейнерами клієнтів та QR-кодами.
"""
import logging
from celery import shared_task
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
    from MASTER.clients.models import ClientWhatsAppConversation
    
    logger.info("Checking inactive chat sessions...")
    
    now = timezone.now()
    five_minutes_ago = now - timedelta(minutes=5)
    twenty_minutes_ago = now - timedelta(minutes=20)
    
    # Find active conversations with last activity more than 5 minutes ago
    inactive_5min = ClientWhatsAppConversation.objects.filter(
        is_active=True,
        last_activity_at__lte=five_minutes_ago
    ).exclude(
        user_rating__isnull=False  # Skip if already rated by user
    )
    
    # Find active conversations with last activity more than 20 minutes ago
    inactive_20min = ClientWhatsAppConversation.objects.filter(
        is_active=True,
        last_activity_at__lte=twenty_minutes_ago
    )
    
    # Auto-rate after 5 minutes
    for conversation in inactive_5min:
        if not conversation.user_rating and not conversation.ai_rating:
            auto_rate_conversation.delay(conversation.id)
    
    # Close and send email after 20 minutes
    for conversation in inactive_20min:
        if not conversation.email_sent:
            close_session_and_send_email.delay(conversation.id)
    
    logger.info(f"Found {inactive_5min.count()} conversations inactive for 5+ min, {inactive_20min.count()} for 20+ min")
    return {
        "status": "success",
        "checked_5min": inactive_5min.count(),
        "checked_20min": inactive_20min.count()
    }


@shared_task(bind=True, max_retries=3)
def auto_rate_conversation(self, conversation_id: int):
    """
    Auto-rate conversation using AI after 5 minutes of inactivity.
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
        
        llm_client = LLMClient(conversation.client)
        response = llm_client.generate(prompt, temperature=0.3, max_tokens=10)
        
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
def close_session_and_send_email(self, conversation_id: int):
    """
    Close chat session and send summary email to client after 20 minutes of inactivity.
    """
    from django.utils import timezone
    from MASTER.clients.models import ClientWhatsAppConversation
    from MASTER.clients.email_service import EmailService
    
    try:
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(id=conversation_id)
        
        # Skip if email already sent
        if conversation.email_sent:
            return {"status": "skipped", "message": "Email already sent"}
        
        # Check if client has email reports enabled
        if not conversation.client.email_report_enabled:
            logger.info(f"Email reports disabled for client {conversation.client.id}, closing session only")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "Email reports disabled"}
        
        # Check if there are recipients
        recipients = conversation.client.email_report_recipients
        if not recipients or not isinstance(recipients, list) or len(recipients) == 0:
            logger.warning(f"No email recipients configured for client {conversation.client.id}")
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save(update_fields=['is_active', 'ended_at'])
            return {"status": "skipped", "message": "No email recipients"}
        
        # Generate summary if not exists
        if not conversation.summary:
            summary = generate_chat_summary(conversation)
            conversation.summary = summary
            conversation.save(update_fields=['summary'])
        
        # Generate full chat text
        chat_text = format_chat_as_text(conversation)
        
        # Send email
        email_result = send_chat_summary_email(conversation, chat_text)
        
        # Update conversation
        conversation.is_active = False
        conversation.ended_at = timezone.now()
        conversation.email_sent = True
        conversation.email_sent_at = timezone.now()
        conversation.save(update_fields=['is_active', 'ended_at', 'email_sent', 'email_sent_at'])
        
        logger.info(f"Closed session {conversation_id} and sent email: {email_result}")
        return {"status": "success", "email_result": email_result}
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"status": "error", "message": "Conversation not found"}
    except Exception as e:
        logger.error(f"Failed to close session and send email for {conversation_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


def generate_chat_summary(conversation):
    """
    Generate AI summary of the conversation.
    """
    from MASTER.rag.llm_client import LLMClient
    
    if not conversation.messages:
        return "No messages in this conversation."
    
    # Format messages for summary
    messages_text = "\n".join([
        f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
        for msg in conversation.messages
    ])
    
    language = conversation.language or 'uk'
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
    
    prompt = f"""Generate a concise summary of this customer support conversation in {lang_name} language.

Conversation:
{messages_text}

Provide a summary that includes:
1. Main topic/issue discussed
2. Key points covered
3. Resolution or outcome
4. Customer satisfaction (if evident)

Summary ({lang_name}):"""
    
    try:
        llm_client = LLMClient(conversation.client)
        summary = llm_client.generate(prompt, temperature=0.3, max_tokens=300)
        return summary.strip() if summary else "Summary generation failed."
    except Exception as e:
        logger.error(f"Failed to generate summary: {str(e)}", exc_info=True)
        return "Summary generation failed due to an error."


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


def send_chat_summary_email(conversation, chat_text):
    """
    Send chat summary email to client recipients with attachment.
    """
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    import smtplib
    
    if not conversation.client.email_smtp_enabled:
        return {"success": False, "error": "SMTP not enabled"}
    
    try:
        email_service = EmailService(conversation.client)
        
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
        
        # Send to all recipients
        recipients = conversation.client.email_report_recipients
        results = []
        
        for recipient in recipients:
            if not recipient or not isinstance(recipient, str):
                continue
            
            try:
                # Create message with attachment for each recipient
                msg = MIMEMultipart('mixed')  # Use 'mixed' to support attachments
                msg['From'] = f"{email_service.from_name} <{email_service.from_address}>"
                msg['To'] = recipient
                msg['Subject'] = subject
                
                # Create alternative part for text/html
                msg_alternative = MIMEMultipart('alternative')
                msg_alternative.attach(MIMEText(body_text, 'plain'))
                msg_alternative.attach(MIMEText(body_html, 'html'))
                msg.attach(msg_alternative)
                
                # Add attachment
                attachment = MIMEBase('application', 'octet-stream')
                attachment.set_payload(chat_text.encode('utf-8'))
                encoders.encode_base64(attachment)
                filename = f"chat_session_{conversation.id}_{conversation.session_id or 'unknown'}.txt"
                attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                msg.attach(attachment)
                
                # Connect and send
                if email_service.smtp_use_tls:
                    server = smtplib.SMTP(email_service.smtp_host, email_service.smtp_port)
                    server.starttls()
                else:
                    server = smtplib.SMTP_SSL(email_service.smtp_host, email_service.smtp_port)
                
                server.login(email_service.smtp_username, email_service.smtp_password)
                server.sendmail(email_service.from_address, [recipient], msg.as_string())
                server.quit()
                
                results.append({"recipient": recipient, "success": True})
                logger.info(f"Sent chat summary email to {recipient} for conversation {conversation.id}")
            except Exception as e:
                logger.error(f"Failed to send email to {recipient}: {str(e)}", exc_info=True)
                results.append({"recipient": recipient, "success": False, "error": str(e)})
        
        return {
            "success": True,
            "sent_count": sum(1 for r in results if r.get("success")),
            "total_count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to send chat summary email: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

