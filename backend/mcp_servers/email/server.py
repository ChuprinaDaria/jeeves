"""MCP Email server — email tools for Concierge agents."""
import json
import logging
import os
from pathlib import Path

from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-email",
    description="Concierge email server. Send, read, search and analyze emails.",
)


def _get_email_service(client_id: int):
    """Get EmailService for a client."""
    from MASTER.clients.models import Client
    from MASTER.clients.email_service import EmailService
    client = Client.objects.get(pk=client_id)
    return EmailService(client)


def _resolve_language(session_id: str, language: str) -> str:
    """Resolve language: param -> AgentConfig -> fallback 'en'."""
    if language:
        return language
    try:
        from MASTER.agents.models import AgentSession
        session = AgentSession.objects.select_related('agent_config').get(pk=session_id)
        return session.agent_config.get_language()
    except Exception:
        return 'en'


# ---------------------------------------------------------------------------
# Assistant tools (Nexy)
# ---------------------------------------------------------------------------

@mcp.tool()
async def send_email(
    client_id: int,
    session_id: str,
    to_address: str,
    subject: str,
    body: str,
    is_html: bool = False,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> str:
    """Send an email via client's SMTP configuration.
    Use when the user asks to send an email to someone."""

    def _send():
        service = _get_email_service(client_id)
        return service.send_email(to_address, subject, body, is_html, cc, bcc)

    result = await sync_to_async(_send)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def send_email_with_attachment(
    client_id: int,
    session_id: str,
    to_address: str,
    subject: str,
    body: str,
    file_path: str,
    is_html: bool = False,
) -> str:
    """Send email with file attachment. file_path is relative to media/ directory.
    Use after create_spreadsheet to email the generated file.
    Example file_path: 'xlsx/21/report.xlsx'"""

    def _send():
        from django.conf import settings as django_settings

        media_root = Path(django_settings.MEDIA_ROOT).resolve()
        resolved = (media_root / file_path).resolve()

        if not str(resolved).startswith(str(media_root)):
            return {"success": False, "error": "Invalid file path"}
        if not resolved.is_file():
            return {"success": False, "error": f"File not found: {file_path}"}

        service = _get_email_service(client_id)
        return service.send_email_with_attachment(
            to_address, subject, body, str(resolved), is_html,
        )

    result = await sync_to_async(_send)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def read_emails(
    client_id: int,
    session_id: str,
    limit: int = 10,
    folder: str = "INBOX",
    days_back: int = 7,
) -> str:
    """Read recent emails via IMAP.
    Returns list of emails with subject, sender, date, and body preview."""

    def _read():
        service = _get_email_service(client_id)
        emails = service.get_recent_emails(limit=limit, folder=folder, days_back=days_back)
        return {"emails": emails, "total": len(emails)}

    result = await sync_to_async(_read)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def search_emails(
    client_id: int,
    session_id: str,
    from_address: str = "",
    subject: str = "",
    days_back: int = 30,
    limit: int = 20,
) -> str:
    """Search emails by sender and/or subject via IMAP."""

    def _search():
        service = _get_email_service(client_id)
        emails = service.search_emails(
            from_address=from_address or None,
            subject=subject or None,
            days_back=days_back,
            limit=limit,
        )
        return {"emails": emails, "total": len(emails)}

    result = await sync_to_async(_search)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def analyze_emails(
    client_id: int,
    session_id: str,
    days_back: int = 7,
    language: str = "",
) -> str:
    """Analyze recent emails: count, top senders, key topics, action items.
    Uses LLM for intelligent summarization in client's language."""

    def _analyze():
        lang = _resolve_language(session_id, language)
        service = _get_email_service(client_id)
        return service.analyze_recent_emails(days_back=days_back, language=lang)

    result = await sync_to_async(_analyze)()
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Manager tool (Consultant)
# ---------------------------------------------------------------------------

@mcp.tool()
async def send_commercial_email(
    client_id: int,
    session_id: str,
    to_address: str,
    proposal_type: str,
    subject: str = "",
    body: str = "",
    amount: str = "",
    currency: str = "EUR",
    items: list[dict] | None = None,
) -> str:
    """Send a structured commercial email (quote/invoice/offer/follow_up).
    Consultant uses this to send proposals to customers.
    Body is generated from template if empty. Subject auto-generated from proposal_type.
    NOT for arbitrary emails — only commercial proposals.

    Args:
        proposal_type: One of 'quote', 'invoice', 'offer', 'follow_up'.
        items: List of items, each with 'name', 'qty', 'price' keys.
    """

    VALID_TYPES = {"quote", "invoice", "offer", "follow_up"}
    if proposal_type not in VALID_TYPES:
        return json.dumps({"error": f"Invalid proposal_type. Must be one of: {sorted(VALID_TYPES)}"})

    def _send():
        from MASTER.clients.models import Client
        client = Client.objects.get(pk=client_id)
        company = getattr(client, 'company_name', '') or client.name or 'Our Company'

        type_labels = {
            "quote": "Price Quote",
            "invoice": "Invoice",
            "offer": "Commercial Offer",
            "follow_up": "Follow-up",
        }
        label = type_labels[proposal_type]

        final_subject = subject or f"{company} — {label}"

        if body:
            final_body = body
        else:
            lines = [f"Dear Customer,\n\nPlease find below our {label.lower()}.\n"]
            if items:
                lines.append("Items:")
                for item in items:
                    name = item.get('name', '')
                    qty = item.get('qty', 1)
                    price = item.get('price', '')
                    lines.append(f"  - {name}: {qty} x {price} {currency}")
            if amount:
                lines.append(f"\nTotal: {amount} {currency}")
            lines.append(f"\nBest regards,\n{company}")
            final_body = "\n".join(lines)

        service = _get_email_service(client_id)
        return service.send_email(to_address, final_subject, final_body)

    result = await sync_to_async(_send)()
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
