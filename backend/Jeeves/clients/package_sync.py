import logging
from typing import Optional
import requests

from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()

# Try to import Celery shared_task, fallback to no-op if not available
try:
    from celery import shared_task
except ImportError:
    logger.warning("Celery not available, async tasks will be disabled")
    # Create a no-op decorator
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


def _get_client_type_from_package_type(package_type: str) -> str:
    """
    Map package_type ID from MG platform to client_type.
    Returns client type based on package type identifier.
    
    Can be overridden via settings.MG_PACKAGE_TYPE_MAP if needed.
    """
    # Check if custom mapping is configured in settings
    custom_map = getattr(settings, 'MG_PACKAGE_TYPE_MAP', None)
    if custom_map and isinstance(custom_map, dict):
        # Reverse lookup
        for client_type, pkg_type in custom_map.items():
            if pkg_type == package_type:
                return client_type
        return custom_map.get('default', 'generic')
    
    # Default reverse mapping - should match package types from MG platform
    package_type_to_client_type = {
        'AI_TYPE_GENERIC': 'generic',
        'AI_TYPE_RESTAURANT': 'restaurant',
        'AI_TYPE_HOTEL': 'hotel',
        'AI_TYPE_MEDICAL': 'medical',
        'AI_TYPE_RETAIL': 'retail',
        'AI_TYPE_WHITE_LABEL': 'white_label',
    }
    return package_type_to_client_type.get(package_type, 'generic')


def _get_package_type_id(client_type: str) -> str:
    """
    Map client_type to package_type ID for MG platform.
    Returns package type identifier based on client type.
    
    Can be overridden via settings.MG_PACKAGE_TYPE_MAP if needed.
    """
    # Check if custom mapping is configured in settings
    custom_map = getattr(settings, 'MG_PACKAGE_TYPE_MAP', None)
    if custom_map and isinstance(custom_map, dict):
        return custom_map.get(client_type, custom_map.get('default', 'AI_TYPE_GENERIC'))
    
    # Default mapping - client_type -> package_type
    client_type_to_package_type = {
        'generic': 'AI_TYPE_GENERIC',
        'restaurant': 'AI_TYPE_RESTAURANT',
        'hotel': 'AI_TYPE_HOTEL',
        'medical': 'AI_TYPE_MEDICAL',
        'retail': 'AI_TYPE_RETAIL',
        'white_label': 'AI_TYPE_WHITE_LABEL',
    }
    return client_type_to_package_type.get(client_type, 'AI_TYPE_GENERIC')


def create_package_on_mg(client) -> Optional[dict]:
    """
    Create a new package on MG platform when client is created.
    
    Args:
        client: Client instance
        
    Returns:
        Response JSON (dict) or None on failure
    """
    try:
        url = getattr(settings, "MG_PACKAGE_URL", "").strip()
        if not url:
            logger.debug("MG package sync is not configured (MG_PACKAGE_URL)")
            return None
        
        # Check if client has tag (required for GUID)
        if not client.tag:
            logger.warning(f"Client {client.id} has no tag, skipping package creation on MG")
            return None
        
        # Prepare payload for create action
        package_type = _get_package_type_id(client.client_type)
        
        payload = {
            "action": "create",
            "name": client.company_name or client.user or f"Client {client.id}",
            "guid": client.tag,  # Package GUID (required)
            "package_type": package_type,  # AI package type identifier (required)
            "description": client.description or "",  # Package description (required)
            "active": client.is_active,  # Package activation status (required)
        }
        
        # Optional: parent package GUID for cloning (if needed)
        parent_guid = getattr(settings, "MG_BASE_PACKAGE_GUID", "").strip()
        if parent_guid:
            payload["parent"] = parent_guid
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add authentication if configured
        api_key = getattr(settings, "MG_SYNC_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        
        try:
            return resp.json()
        except Exception:
            logger.info("MG package creation responded with non-JSON, status=%s", resp.status_code)
            return {"status_code": resp.status_code, "text": resp.text[:200]}
            
    except requests.RequestException as e:
        logger.warning("MG package creation failed: %s", str(e))
    except Exception as e:
        logger.error("MG package creation unexpected error: %s", str(e), exc_info=True)
    return None


def update_package_on_mg(client) -> Optional[dict]:
    """
    Update an existing package on MG platform when client is updated.
    
    Args:
        client: Client instance
        
    Returns:
        Response JSON (dict) or None on failure
    """
    try:
        url = getattr(settings, "MG_PACKAGE_URL", "").strip()
        if not url:
            logger.debug("MG package sync is not configured (MG_PACKAGE_URL)")
            return None
        
        # Check if client has tag (required for GUID)
        if not client.tag:
            logger.warning(f"Client {client.id} has no tag, skipping package update on MG")
            return None
        
        # Prepare payload for update action
        payload = {
            "action": "update",
            "name": client.company_name or client.user or f"Client {client.id}",
            "guid": client.tag,  # Package GUID (required)
            "description": client.description or "",  # Updated description (required)
            "active": client.is_active,  # Package status (required)
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add authentication if configured
        api_key = getattr(settings, "MG_SYNC_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        
        try:
            return resp.json()
        except Exception:
            logger.info("MG package update responded with non-JSON, status=%s", resp.status_code)
            return {"status_code": resp.status_code, "text": resp.text[:200]}
            
    except requests.RequestException as e:
        logger.warning("MG package update failed: %s", str(e))
    except Exception as e:
        logger.error("MG package update unexpected error: %s", str(e), exc_info=True)
    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def create_package_on_mg_async(self, client_id: int) -> Optional[dict]:
    """
    Celery task for asynchronous creation of package on MG.
    
    Args:
        client_id: ID of Client record
        
    Returns:
        Response JSON (dict) or None on failure
    """
    try:
        from Jeeves.clients.models import Client
        client = Client.objects.get(pk=client_id)
        return create_package_on_mg(client)
    except Client.DoesNotExist:
        logger.error(f"Client with id={client_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error in async MG package creation for client_id={client_id}: {e}", exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def update_package_on_mg_async(self, client_id: int) -> Optional[dict]:
    """
    Celery task for asynchronous update of package on MG.
    
    Args:
        client_id: ID of Client record
        
    Returns:
        Response JSON (dict) or None on failure
    """
    try:
        from Jeeves.clients.models import Client
        client = Client.objects.get(pk=client_id)
        return update_package_on_mg(client)
    except Client.DoesNotExist:
        logger.error(f"Client with id={client_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error in async MG package update for client_id={client_id}: {e}", exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)


def create_package_on_mg_async_delay(client_id: int):
    """
    Convenience function to enqueue async task for creating package on MG.
    This is a non-blocking call that returns immediately.
    
    Args:
        client_id: ID of Client record
    """
    try:
        create_package_on_mg_async.delay(client_id)
    except Exception as e:
        logger.warning(f"Failed to enqueue async MG package creation task for client_id={client_id}: {e}")


def update_package_on_mg_async_delay(client_id: int):
    """
    Convenience function to enqueue async task for updating package on MG.
    This is a non-blocking call that returns immediately.
    
    Args:
        client_id: ID of Client record
    """
    try:
        update_package_on_mg_async.delay(client_id)
    except Exception as e:
        logger.warning(f"Failed to enqueue async MG package update task for client_id={client_id}: {e}")

