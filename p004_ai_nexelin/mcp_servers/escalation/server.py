"""
mcp-escalation — FastMCP server for HITL manager escalation.

Provides:
- escalate_to_manager(client_id, conversation_id, reason, ...) — escalate to live manager
- check_manager_availability(client_id) — check if manager is online
- escalations://active/{client_id} — list active escalations
"""
from __future__ import annotations

import json
import logging

from mcp_servers.common.django_setup import setup

setup()

from asgiref.sync import sync_to_async  # noqa: E402
from django.utils import timezone  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-escalation",
    description="Escalate conversations to live human managers and track resolution.",
)


# ---------------------------------------------------------------------------
# Sync helpers
# ---------------------------------------------------------------------------

def _escalate_sync(client_id, conversation_id, reason, customer_name, channel, summary):
    from MASTER.clients.models import Client, ClientWhatsAppConversation

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"error": f"Client {client_id} not found"}

    # Find and update conversation
    conv = None
    try:
        conv = ClientWhatsAppConversation.objects.get(
            client=client,
            customer_phone=conversation_id,
        )
        conv.is_escalated_to_manager = True
        conv.manager_escalation_context = f"Reason: {reason}\nSummary: {summary}"
        conv.escalation_started_at = timezone.now()
        conv.escalation_original_query = summary or reason
        conv.save(update_fields=[
            "is_escalated_to_manager",
            "manager_escalation_context",
            "escalation_started_at",
            "escalation_original_query",
        ])
    except ClientWhatsAppConversation.DoesNotExist:
        pass  # Conversation may not exist for all channels

    # Notify manager
    manager_notified = _notify_manager(client, reason, customer_name, channel, summary)

    return {
        "escalation_id": f"esc-{client_id}-{int(timezone.now().timestamp())}",
        "conversation_id": conversation_id,
        "manager_notified": manager_notified,
        "estimated_wait": "2-5 minutes" if manager_notified else "Manager offline",
        "reason": reason,
    }


def _notify_manager(client, reason, customer_name, channel, summary):
    """Send notification to manager via Telegram or Matrix."""
    notification_text = (
        f"🔔 Escalation from {channel}\n"
        f"Customer: {customer_name or 'Unknown'}\n"
        f"Reason: {reason}\n"
    )
    if summary:
        notification_text += f"Summary: {summary}\n"

    # Try Telegram notification
    manager_ids = client.get_manager_telegram_ids() if hasattr(client, "get_manager_telegram_ids") else []
    bot_token = getattr(client, "telegram_bot_token", "")

    if bot_token and manager_ids:
        try:
            import requests

            for manager_id in manager_ids:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": manager_id, "text": notification_text, "parse_mode": "HTML"},
                    timeout=10,
                )
            return True
        except Exception as e:
            logger.error(f"Telegram escalation notification failed: {e}")

    # Try Matrix notification
    if getattr(client, "matrix_homeserver_url", None):
        try:
            from MASTER.clients.services.whatsapp_bridge import notify_matrix_managers

            notify_matrix_managers(client, notification_text)
            return True
        except Exception as e:
            logger.error(f"Matrix escalation notification failed: {e}")

    logger.warning(f"No manager notification channel configured for client {client.pk}")
    return False


def _check_availability_sync(client_id):
    from MASTER.clients.models import Client

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"available": False, "error": f"Client {client_id} not found"}

    has_telegram = bool(getattr(client, "telegram_bot_token", ""))
    manager_ids = client.get_manager_telegram_ids() if hasattr(client, "get_manager_telegram_ids") else []
    has_matrix = bool(getattr(client, "matrix_homeserver_url", ""))

    return {
        "available": (has_telegram and len(manager_ids) > 0) or has_matrix,
        "channels": {
            "telegram": has_telegram and len(manager_ids) > 0,
            "matrix": has_matrix,
        },
        "telegram_manager_count": len(manager_ids),
    }


def _active_escalations_sync(client_id):
    from MASTER.clients.models import ClientWhatsAppConversation

    convs = (
        ClientWhatsAppConversation.objects.filter(
            client_id=client_id,
            is_escalated_to_manager=True,
        )
        .order_by("-escalation_started_at")
        .values(
            "customer_phone",
            "manager_escalation_context",
            "escalation_started_at",
            "matrix_escalation_active",
        )[:20]
    )

    return {
        "client_id": client_id,
        "active_count": len(convs),
        "escalations": [
            {
                "customer": c["customer_phone"],
                "context": c["manager_escalation_context"],
                "started_at": c["escalation_started_at"].isoformat() if c["escalation_started_at"] else None,
                "matrix_active": c["matrix_escalation_active"],
            }
            for c in convs
        ],
    }


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def escalate_to_manager(
    client_id: int,
    conversation_id: str,
    reason: str,
    customer_name: str = "",
    channel: str = "unknown",
    summary: str = "",
) -> str:
    """Escalate a conversation to a live human manager.

    Call this tool when:
    - The customer explicitly asks to speak with a human or manager
    - The question is outside the knowledge base scope and you cannot help
    - The customer is frustrated, angry, or the situation is sensitive
    - A complex issue requires human judgment (refunds, complaints, legal matters)
    - You are unsure about the answer and it could have serious consequences

    Args:
        client_id: Numeric client ID.
        conversation_id: Customer identifier (phone number or chat_id).
        reason: Clear explanation of why escalation is needed.
        customer_name: Customer name if known.
        channel: Source channel (whatsapp, telegram, web).
        summary: Brief summary of the conversation so far.
    """
    result = await sync_to_async(_escalate_sync)(
        client_id, conversation_id, reason, customer_name, channel, summary,
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def check_manager_availability(client_id: int) -> str:
    """Check if a live human manager is currently available.

    Call this before telling the customer about wait times or availability.

    Args:
        client_id: Numeric client ID.
    """
    result = await sync_to_async(_check_availability_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MCP resource
# ---------------------------------------------------------------------------

@mcp.resource("escalations://active/{client_id}")
async def active_escalations(client_id: int) -> str:
    """Currently active (unresolved) escalations for this client."""
    result = await sync_to_async(_active_escalations_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
