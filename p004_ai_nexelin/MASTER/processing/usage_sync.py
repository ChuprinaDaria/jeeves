import logging
from datetime import datetime
from typing import Optional

import requests
from django.conf import settings

from MASTER.processing.models import UsageStats

logger = logging.getLogger(__name__)


def _resolve_uid(usage: UsageStats) -> str:
    if usage.client_id:
        return f"client-{usage.client_id}"
    if usage.branch_id:
        return f"branch-{usage.branch_id}"
    if usage.specialization_id:
        return f"spec-{usage.specialization_id}"
    return "unknown"


def _resolve_ai_model(usage: UsageStats) -> str:
    model = usage.embedding_model
    if not model:
        return "unknown"
    return getattr(model, "slug", None) or getattr(model, "name", None) or getattr(model, "model_name", "unknown")


def _resolve_price_type(usage: UsageStats) -> str:
    # pl - local price, pc - cloud, ph - hybrid
    # Heuristic:
    # - Local embedding models → 'pl'
    # - Non-local → 'pc'
    model = usage.embedding_model
    if model and getattr(model, "is_local", False):
        return "pl"
    return "pc"


def send_usage_to_mg(usage: UsageStats) -> Optional[dict]:
    """
    Send a single usage record to MG in required format.
    Returns response JSON (dict) or None on failure.
    """
    try:
        url = getattr(settings, "MG_AI_USAGE_URL", "").strip()
        access_token = getattr(settings, "MG_SYNC_API_KEY", "").strip()
        if not url or not access_token:
            logger.debug("MG sync is not configured (MG_AI_USAGE_URL / MG_SYNC_API_KEY)")
            return None

        payload = {
            "access_token": access_token,
            "tokens": int(usage.tokens_used),
            "occurred": (usage.created_at or datetime.utcnow()).isoformat(),
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


