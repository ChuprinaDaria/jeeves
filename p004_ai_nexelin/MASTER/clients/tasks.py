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

