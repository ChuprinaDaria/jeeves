import logging
from datetime import datetime
from typing import Optional

import requests
from celery import shared_task
from django.conf import settings

from MASTER.processing.models import UsageStats

logger = logging.getLogger(__name__)


def _resolve_uid(usage: UsageStats) -> str:
    """Generate unique identifier for usage record."""
    if usage.client_id:
        return f"client-{usage.client_id}"
    if usage.branch_id:
        return f"branch-{usage.branch_id}"
    if usage.specialization_id:
        return f"spec-{usage.specialization_id}"
    return "unknown"


def _resolve_access_token(usage: UsageStats) -> Optional[str]:
    """
    Resolve package GUID (access_token) from Client.
    Priority: Client.tag (package GUID) → Client.api_key → settings fallback
    """
    # Try to get from client
    if usage.client_id:
        try:
            from MASTER.clients.models import Client
            client = Client.objects.get(pk=usage.client_id)
            # Client.tag is the package GUID
            if hasattr(client, 'tag') and client.tag:
                return client.tag.strip()
            # Fallback to api_key if tag is not set
            if hasattr(client, 'api_key') and client.api_key:
                return client.api_key.strip()
        except Exception:
            pass
    
    # Fallback to global setting
    return getattr(settings, "MG_SYNC_API_KEY", "").strip() or None


def _resolve_ai_model(usage: UsageStats) -> str:
    """
    Resolve AI model identifier.
    For embedding models: use model name/slug
    For LLM models: get from metadata or client
    """
    # Check if this is LLM usage (stored in metadata)
    metadata = getattr(usage, 'metadata', {}) or {}
    if isinstance(metadata, dict):
        llm_model = metadata.get('llm_model')
        if llm_model:
            return str(llm_model)
    
    # Default: embedding model
    model = usage.embedding_model
    if not model:
        return "unknown"
    return getattr(model, "slug", None) or getattr(model, "name", None) or getattr(model, "model_name", "unknown")


def _resolve_price_type(usage: UsageStats) -> str:
    """
    Resolve price type: pl (local), pc (cloud), ph (hybrid).
    For embedding: check is_local
    For LLM: check metadata or infer from provider type
    """
    # Check if this is LLM usage
    metadata = getattr(usage, 'metadata', {}) or {}
    if isinstance(metadata, dict):
        llm_provider = metadata.get('llm_provider', '').lower()
        # Ollama is typically local
        if 'ollama' in llm_provider:
            return "pl"
        # OpenAI, Anthropic, Kimi are cloud
        if llm_provider in ('openai', 'anthropic', 'kimi'):
            return "pc"
    
    # Default: embedding model
    model = usage.embedding_model
    if model and getattr(model, "is_local", False):
        return "pl"
    return "pc"


def send_usage_to_mg(usage: UsageStats) -> Optional[dict]:
    """
    Send a single usage record to MG in required format.
    Returns response JSON (dict) or None on failure.
    
    Note: This is the synchronous version. For async, use send_usage_to_mg_async().
    """
    try:
        # Check if client has disabled usage stats sync
        if usage.client_id:
            try:
                from MASTER.clients.models import Client
                client = Client.objects.get(pk=usage.client_id)
                if hasattr(client, 'sync_usage_stats') and not client.sync_usage_stats:
                    logger.debug(f"Usage stats sync disabled for client {client.id} ({client.company_name})")
                    return None
            except Exception as e:
                logger.warning(f"Error checking sync_usage_stats for client {usage.client_id}: {e}")
        
        url = getattr(settings, "MG_AI_USAGE_URL", "").strip()
        access_token = _resolve_access_token(usage)
        
        if not url or not access_token:
            logger.debug("MG sync is not configured (MG_AI_USAGE_URL / access_token)")
            return None

        # Format occurred date as required: "YYYY-MM-DD HH:MM:SS"
        occurred_dt = usage.created_at or datetime.utcnow()
        occurred_str = occurred_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Validate and convert tokens to int (prevent sending invalid large numbers)
        tokens_value = usage.tokens_used
        if tokens_value is None:
            logger.warning(f"UsageStats {usage.id} has None tokens_used, skipping sync")
            return None
        
        # Convert to int, but check for reasonable values (max 1 billion tokens per request)
        try:
            tokens_int = int(float(tokens_value))
            if tokens_int < 0:
                logger.warning(f"UsageStats {usage.id} has negative tokens: {tokens_int}, skipping sync")
                return None
            if tokens_int > 1_000_000_000:  # 1 billion tokens max
                logger.error(f"UsageStats {usage.id} has suspiciously large tokens value: {tokens_int}, skipping sync")
                return None
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f"UsageStats {usage.id} has invalid tokens_used value: {tokens_value}, error: {e}")
            return None

        payload = {
            "access_token": access_token,
            "tokens": tokens_int,
            "occurred": occurred_str,
            "uid": _resolve_uid(usage),
            "ai_model": _resolve_ai_model(usage),
            "ai_price_type": _resolve_price_type(usage),
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


