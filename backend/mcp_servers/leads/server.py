"""MCP Leads server — lead management tools for Nexelin agents."""
import json
import logging
from datetime import timedelta
from django.utils import timezone
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Bootstrap Django ORM
from mcp_servers.common.django_setup import setup
setup()

from MASTER.clients.models import Lead, Client
from MASTER.agents.models import AgentSession
from django.db.models import Count, Avg, Q

mcp = FastMCP("mcp-leads")


@mcp.tool()
async def save_lead(
    client_id: int,
    session_id: str,
    name: str = "",
    email: str = "",
    phone: str = "",
    request_summary: str = "",
    interest_score: int = 3,
    source: str = "web",
) -> str:
    """Save or update a lead from the current conversation.
    Call this when you learn the customer's name, email, phone, or understand their need.
    Updates existing lead for the same session, or creates a new one."""
    from asgiref.sync import sync_to_async

    def _save():
        client = Client.objects.get(pk=client_id)

        if not session_id:
            return json.dumps({"status": "error", "message": "session_id is required"})

        try:
            session = AgentSession.objects.get(pk=session_id)
        except AgentSession.DoesNotExist:
            return json.dumps({"status": "error", "message": f"session {session_id} not found"})

        lead, created = Lead.objects.get_or_create(
            client=client,
            agent_session=session,
            defaults={'source': source},
        )

        if name:
            lead.name = name[:255]
        if email:
            lead.email = email[:254]
        if phone:
            lead.phone = phone[:50]
        if request_summary:
            lead.request_summary = request_summary[:1000]
        if interest_score:
            lead.interest_score = max(1, min(5, int(interest_score)))
        if source and created:
            lead.source = source

        lead.save()
        action = "Created" if created else "Updated"
        return json.dumps({
            "status": "ok",
            "action": action,
            "lead_id": lead.id,
            "name": lead.name,
            "interest_score": lead.interest_score,
        })

    return await sync_to_async(_save)()


@mcp.tool()
async def qualify_conversation(
    client_id: int,
    session_id: str,
) -> str:
    """Analyze the current session and return existing lead data if any.
    Call at end of conversation to review collected lead information."""
    from asgiref.sync import sync_to_async

    def _qualify():
        try:
            lead = Lead.objects.get(
                client_id=client_id,
                agent_session_id=session_id,
            )
            return json.dumps({
                "has_lead": True,
                "lead_id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "request_summary": lead.request_summary,
                "interest_score": lead.interest_score,
                "status": lead.status,
            })
        except Lead.DoesNotExist:
            return json.dumps({"has_lead": False})

    return await sync_to_async(_qualify)()


@mcp.tool()
async def search_leads(
    client_id: int,
    status: str = "",
    source: str = "",
    min_interest: int = 0,
    search: str = "",
    period: str = "",
    limit: int = 25,
) -> str:
    """Search existing leads with filters.
    period: '7d', '30d', '2026-03', or empty for all.
    Returns list of matching leads."""
    from asgiref.sync import sync_to_async

    def _search():
        qs = Lead.objects.filter(client_id=client_id)

        if status:
            qs = qs.filter(status=status)
        if source:
            qs = qs.filter(source=source)
        if min_interest:
            qs = qs.filter(interest_score__gte=min_interest)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(request_summary__icontains=search)
            )
        if period:
            now = timezone.now()
            if period.endswith('d'):
                days = int(period[:-1])
                qs = qs.filter(created_at__gte=now - timedelta(days=days))
            elif '-' in period:
                parts = period.split('-')
                year, month = int(parts[0]), int(parts[1])
                qs = qs.filter(created_at__year=year, created_at__month=month)

        leads = list(qs.order_by('-created_at')[:limit].values(
            'id', 'name', 'email', 'phone', 'request_summary',
            'interest_score', 'status', 'source', 'created_at',
        ))

        for lead in leads:
            lead['created_at'] = lead['created_at'].isoformat() if lead['created_at'] else None

        return json.dumps({"leads": leads, "total": qs.count()})

    return await sync_to_async(_search)()


@mcp.tool()
async def get_lead_stats(
    client_id: int,
    period: str = "30d",
) -> str:
    """Lead statistics: count by status, by source, average interest score.
    period: '7d', '30d', '90d', or 'all'."""
    from asgiref.sync import sync_to_async

    def _stats():
        qs = Lead.objects.filter(client_id=client_id)

        if period != 'all' and period.endswith('d'):
            days = int(period[:-1])
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))

        total = qs.count()
        by_status = dict(qs.values_list('status').annotate(c=Count('id')).values_list('status', 'c'))
        by_source = dict(qs.values_list('source').annotate(c=Count('id')).values_list('source', 'c'))
        avg_interest = qs.aggregate(avg=Avg('interest_score'))['avg']

        converted = by_status.get('converted', 0)
        conversion_rate = (converted / total * 100) if total > 0 else 0

        return json.dumps({
            "total": total,
            "by_status": by_status,
            "by_source": by_source,
            "avg_interest_score": round(avg_interest or 0, 1),
            "conversion_rate": round(conversion_rate, 1),
            "period": period,
        })

    return await sync_to_async(_stats)()


@mcp.tool()
async def search_conversations(
    client_id: int,
    period: str = "7d",
    channel: str = "",
    has_lead: bool = True,
    limit: int = 20,
) -> str:
    """Search recent conversations with message history.
    Use to review conversations and find unqualified leads.
    period: '1d', '7d', '30d'. channel: 'telegram', 'whatsapp_meta', 'web', or empty for all.
    has_lead: True=only with leads, False=only without leads, empty=all."""
    from asgiref.sync import sync_to_async

    def _search():
        from MASTER.clients.models import ClientWhatsAppConversation

        qs = ClientWhatsAppConversation.objects.filter(client_id=client_id)

        if period and period.endswith('d'):
            days = int(period[:-1])
            qs = qs.filter(updated_at__gte=timezone.now() - timedelta(days=days))

        if channel:
            if channel == 'telegram':
                qs = qs.filter(telegram_chat_id__isnull=False).exclude(telegram_chat_id='')
            elif channel in ('whatsapp_meta', 'whatsapp'):
                qs = qs.filter(telegram_chat_id__isnull=True)

        # Filter by lead existence
        if has_lead is False:
            qs = qs.filter(leads__isnull=True)
        elif has_lead is True:
            qs = qs.filter(leads__isnull=False).distinct()

        conversations = []
        for conv in qs.order_by('-updated_at')[:limit]:
            messages = conv.messages or []
            # Last 10 messages for context
            recent = messages[-10:] if len(messages) > 10 else messages

            # Check if has lead
            lead_info = None
            lead = conv.leads.first()
            if lead:
                lead_info = {
                    "id": lead.id,
                    "name": lead.name,
                    "interest_score": lead.interest_score,
                    "status": lead.status,
                }

            conversations.append({
                "conversation_id": conv.id,
                "phone": conv.customer_phone or "",
                "channel": "telegram" if conv.telegram_chat_id else "whatsapp",
                "total_messages": conv.total_messages,
                "last_activity": conv.last_activity_at.isoformat() if conv.last_activity_at else None,
                "recent_messages": recent,
                "lead": lead_info,
            })

        return json.dumps({"conversations": conversations, "total": len(conversations)})

    return await sync_to_async(_search)()


@mcp.tool()
async def batch_qualify(
    client_id: int,
    period: str = "7d",
    min_messages: int = 3,
) -> str:
    """Scan all conversations without leads in the given period and return
    summaries for qualification. Only includes conversations with at least
    min_messages messages. Returns conversation data for you to analyze
    and decide which ones to save_lead for."""
    from asgiref.sync import sync_to_async

    def _batch():
        from MASTER.clients.models import ClientWhatsAppConversation

        now = timezone.now()
        days = int(period[:-1]) if period.endswith('d') else 7
        cutoff = now - timedelta(days=days)

        qs = ClientWhatsAppConversation.objects.filter(
            client_id=client_id,
            updated_at__gte=cutoff,
            leads__isnull=True,
            total_messages__gte=min_messages,
        ).order_by('-updated_at')

        candidates = []
        for conv in qs[:50]:  # cap at 50
            messages = conv.messages or []
            # Extract user messages for context
            user_msgs = [m for m in messages if m.get('role') == 'user']

            candidates.append({
                "conversation_id": conv.id,
                "phone": conv.customer_phone or "",
                "channel": "telegram" if conv.telegram_chat_id else "whatsapp",
                "total_messages": conv.total_messages,
                "started": conv.created_at.isoformat() if conv.created_at else None,
                "last_activity": conv.last_activity_at.isoformat() if conv.last_activity_at else None,
                "user_messages": [m.get('content', '')[:200] for m in user_msgs[-5:]],
                "full_messages": messages[-8:],
            })

        return json.dumps({
            "candidates": candidates,
            "total_unqualified": len(candidates),
            "period": period,
            "hint": "Review each conversation and call save_lead for promising ones.",
        })

    return await sync_to_async(_batch)()


if __name__ == "__main__":
    mcp.run(transport="stdio")
