import logging
from datetime import datetime
from typing import Optional

import requests
from celery import shared_task
from django.conf import settings

from MASTER.processing.models import UsageStats

logger = logging.getLogger(__name__)


def _resolve_uid(usage: UsageStats) -> str:
    """
    Generate unique identifier for usage record.
    Returns string with max 255 characters (API requirement).
    """
    uid = None
    if usage.client_id:
        uid = f"client-{usage.client_id}"
    elif usage.branch_id:
        uid = f"branch-{usage.branch_id}"
    elif usage.specialization_id:
        uid = f"spec-{usage.specialization_id}"
    else:
        uid = "unknown"
    
    # Ensure uid doesn't exceed 255 characters (API requirement)
    if len(uid) > 255:
        uid = uid[:255]
    
    return uid


def _resolve_access_token(usage: UsageStats) -> Optional[str]:
    """
    Resolve package GUID from Client.
    This is used as 'guid' field in the API request.
    Priority: Client.tag (package GUID) → Client.api_key (fallback only)
    
    Note: Returns None if no package GUID can be resolved (don't use MG_SYNC_API_KEY
    as it's an authentication token, not a package GUID).
    """
    # Try to get from client (use direct ForeignKey access if available)
    client = None
    if hasattr(usage, 'client') and usage.client:
        client = usage.client
    elif usage.client_id:
        try:
            from MASTER.clients.models import Client
            client = Client.objects.get(pk=usage.client_id)
        except Exception:
            pass
    
    if client:
        # Client.tag is the package GUID (required for MG API)
        if hasattr(client, 'tag') and client.tag:
            return client.tag.strip()
        # Fallback to api_key if tag is not set (not ideal, but better than nothing)
        if hasattr(client, 'api_key') and client.api_key:
            logger.warning(f"Client {client.id} has no tag, using api_key as fallback for package GUID")
            return client.api_key.strip()
    
    # Return None if no package GUID can be resolved
    # Don't use MG_SYNC_API_KEY as it's an authentication token, not a package GUID
    return None


def _resolve_ai_model(usage: UsageStats) -> str:
    """
    Resolve AI model GUID identifier for mg.nexelin API.
    Priority: metadata['ai_model_guid'] → metadata['llm_model_guid'] → model id as fallback
    """
    metadata = getattr(usage, 'metadata', {}) or {}
    if isinstance(metadata, dict):
        # Try to get GUID from metadata (preferred)
        ai_model_guid = metadata.get('ai_model_guid') or metadata.get('llm_model_guid')
        if ai_model_guid:
            return str(ai_model_guid)
    
    # Fallback: use model id (may need to be converted to GUID format if required)
    model = usage.embedding_model
    if not model:
        return "unknown"
    
    # Try to get model id as GUID (assuming id might be GUID or can be used as identifier)
    model_id = getattr(model, 'pk', None) or getattr(model, 'id', None)
    if model_id:
        return str(model_id)
    
    return "unknown"


# Note: _resolve_price_type function removed as it's no longer needed
# The API endpoint /api/ai-token-usage doesn't require ai_price_type field


def send_usage_to_mg(usage: UsageStats) -> Optional[dict]:
    """
    Send a single usage record to MG in required format.
    Returns response JSON (dict) or None on failure.
    
    Note: This is the synchronous version. For async, use send_usage_to_mg_async().
    """
    try:
        # Check if client has disabled usage stats sync
        client = None
        if hasattr(usage, 'client') and usage.client:
            client = usage.client
        elif usage.client_id:
            try:
                from MASTER.clients.models import Client
                client = Client.objects.get(pk=usage.client_id)
            except Exception as e:
                logger.warning(f"Error getting client for usage {usage.id}: {e}")
        
        if client:
            if hasattr(client, 'sync_usage_stats') and not client.sync_usage_stats:
                logger.debug(f"Usage stats sync disabled for client {client.id} ({client.company_name})")
                return None
        
        url = getattr(settings, "MG_AI_USAGE_URL", "").strip()
        package_guid = _resolve_access_token(usage)  # This returns package GUID (Client.tag)
        
        if not url or not package_guid:
            logger.debug("MG sync is not configured (MG_AI_USAGE_URL / package_guid)")
            return None

        # Format occurred date as ISO 8601 with Z: "2025-12-01T11:55:02Z"
        occurred_dt = usage.created_at or datetime.utcnow()
        occurred_str = occurred_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Validate and convert tokens to int (prevent sending invalid large numbers)
        tokens_value = usage.tokens_used
        if tokens_value is None:
            logger.warning(f"UsageStats {usage.id} has None tokens_used, skipping sync")
            return None
        
        # Convert to int, but check for reasonable values (min: 1, max 1 billion tokens per request)
        try:
            tokens_int = int(float(tokens_value))
            if tokens_int < 1:  # API requires min: 1
                logger.warning(f"UsageStats {usage.id} has tokens < 1: {tokens_int}, skipping sync")
                return None
            if tokens_int > 1_000_000_000:  # 1 billion tokens max (reasonable limit)
                logger.error(f"UsageStats {usage.id} has suspiciously large tokens value: {tokens_int}, skipping sync")
                return None
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f"UsageStats {usage.id} has invalid tokens_used value: {tokens_value}, error: {e}")
            return None

        payload = {
            "guid": package_guid,  # Package GUID (required)
            "tokens": tokens_int,  # Number of used tokens (required, min: 1)
            "occurred": occurred_str,  # Date when usage occurred (required, ISO 8601 format)
            "uid": _resolve_uid(usage),  # Unique report identifier (required, max: 255)
            "ai_model": _resolve_ai_model(usage),  # GUID AI Sub model identifier (required, max: 255)
        }

        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            logger.info("MG usage sync responded with non-JSON, status=%s", resp.status_code)
            return {"status_code": resp.status_code, "text": resp.text[:200]}
    except requests.RequestException as e:
        logger.warning("MG usage sync failed: %s", str(e))
    except Exception as e:
        logger.error("MG usage sync unexpected error: %s", str(e), exc_info=True)
    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_usage_to_mg_async(self, usage_id: int) -> Optional[dict]:
    """
    Celery task for asynchronous sending of usage statistics to MG.
    
    Args:
        usage_id: ID of UsageStats record to send
        
    Returns:
        Response JSON (dict) or None on failure
    """
    try:
        usage = UsageStats.objects.get(pk=usage_id)
        return send_usage_to_mg(usage)
    except UsageStats.DoesNotExist:
        logger.error(f"UsageStats with id={usage_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error in async MG sync for usage_id={usage_id}: {e}", exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)


def send_usage_to_mg_async_delay(usage_id: int):
    """
    Convenience function to enqueue async task for sending usage stats.
    This is a non-blocking call that returns immediately.
    
    Args:
        usage_id: ID of UsageStats record to send
    """
    try:
        send_usage_to_mg_async.delay(usage_id)
    except Exception as e:
        logger.warning(f"Failed to enqueue async MG sync task for usage_id={usage_id}: {e}")


