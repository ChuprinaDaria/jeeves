"""
mcp-canvas — FastMCP server that lets Jeeves edit his own flow canvas.

The canvas (Tools page) wires tools to agent targets via ToolConnection rows;
these tools give the assistant real CRUD over that wiring, so "connect email
to the consultant" works from a chat message.

Provides:
- canvas_list_connections(client_id) — current canvas wiring
- canvas_list_available_tools(client_id) — what can be connected
- canvas_add_tool_connection(client_id, tool_slug, targets) — wire a tool
- canvas_remove_tool_connection(client_id, tool_slug, target) — detach an edge
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
    "mcp-canvas",
    description="Edit the client's flow canvas: connect/disconnect tools for the agents.",
)

VALID_TARGETS = ('assistant', 'manager', 'leads')


# ---------------------------------------------------------------------------
# Sync helpers (plain functions — unit-testable without MCP transport)
# ---------------------------------------------------------------------------

def _get_client(client_id):
    from Jeeves.clients.models import Client
    try:
        return Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return None


def list_connections_sync(client_id):
    from Jeeves.tools.models import ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    connections = (
        ToolConnection.objects.filter(client=client, enabled=True)
        .exclude(status='disconnected')
        .select_related('tool_card')
        .order_by('tool_card__slug', 'target')
    )
    return {
        "connections": [
            {
                "tool": conn.tool_card.slug,
                "name": conn.tool_card.name,
                "target": conn.target,
                "status": conn.status,
            }
            for conn in connections
        ]
    }


def list_available_tools_sync(client_id):
    from Jeeves.tools.models import ToolCard, ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    connected = set(
        ToolConnection.objects.filter(client=client, enabled=True)
        .exclude(status='disconnected')
        .values_list('tool_card__slug', 'target')
    )
    tools = []
    for card in ToolCard.objects.filter(is_active=True).order_by('sort_order', 'name'):
        tools.append({
            "tool": card.slug,
            "name": card.name,
            "tagline": card.tagline,
            "needs_credentials": card.auth_type != 'none',
            "connected_targets": sorted(t for s, t in connected if s == card.slug),
        })
    return {"tools": tools}


def add_connection_sync(client_id, tool_slug, targets):
    from Jeeves.tools.models import ToolCard, ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    targets = [t.strip().lower() for t in (targets or []) if t]
    invalid = [t for t in targets if t not in VALID_TARGETS]
    if not targets or invalid:
        return {"error": f"targets must be a non-empty subset of {list(VALID_TARGETS)}"}

    try:
        card = ToolCard.objects.get(slug=tool_slug, is_active=True)
    except ToolCard.DoesNotExist:
        return {"error": f"Unknown tool '{tool_slug}'. Use canvas_list_available_tools first."}

    # Credentials are shared per tool: if any existing connection of this card
    # is already authorized, new targets inherit that; otherwise tools with
    # auth stay 'pending' until the owner authorizes them in the portal.
    has_credentials = (
        card.auth_type == 'none'
        or ToolConnection.objects.filter(
            client=client, tool_card=card, status='connected').exists()
    )

    results = []
    for target in targets:
        conn, _created = ToolConnection.objects.get_or_create(
            client=client, tool_card=card, target=target)
        conn.enabled = True
        if has_credentials:
            conn.status = 'connected'
            if not conn.connected_at:
                conn.connected_at = timezone.now()
        elif conn.status in ('disconnected', 'error', 'expired'):
            conn.status = 'pending'
        conn.save()
        results.append({"target": target, "status": conn.status})

    out = {"tool": card.slug, "name": card.name, "results": results}
    if not has_credentials:
        out["needs_credentials"] = True
        out["note"] = (
            "The tool is wired on the canvas but needs the owner to authorize "
            "it (credentials) on the Tools page before it becomes active."
        )
    return out


def remove_connection_sync(client_id, tool_slug, target):
    from Jeeves.tools.models import ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    target = (target or '').strip().lower()
    if target not in VALID_TARGETS:
        return {"error": f"target must be one of {list(VALID_TARGETS)}"}

    conn = ToolConnection.objects.filter(
        client=client, tool_card__slug=tool_slug, target=target).select_related('tool_card').first()
    if conn is None or not conn.enabled:
        return {"error": f"'{tool_slug}' is not connected to '{target}'"}
    if conn.tool_card.is_system:
        return {"error": f"'{tool_slug}' is a system tool and cannot be detached"}

    # Detach the edge but keep credentials (same semantics as the canvas UI)
    conn.enabled = False
    conn.save(update_fields=['enabled', 'updated_at'])
    return {"tool": tool_slug, "target": target, "detached": True}


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def canvas_list_connections(client_id: int, session_id: str = "", user_id: str = "") -> str:
    """List the current canvas wiring: which tools are connected to which
    agent target (assistant = Jeeves, manager = customer-facing consultant,
    leads = lead capture)."""
    result = await sync_to_async(list_connections_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_list_available_tools(client_id: int, session_id: str = "", user_id: str = "") -> str:
    """List every tool in the catalog that can be wired on the canvas,
    including whether it needs credentials and where it is already connected."""
    result = await sync_to_async(list_available_tools_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_add_tool_connection(
    client_id: int,
    tool_slug: str,
    targets: list[str],
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Connect a tool to one or more agent targets on the canvas.

    targets: list of 'assistant' (Jeeves), 'manager' (customer-facing
    consultant) and/or 'leads' (lead capture). The node appears on the
    canvas immediately."""
    result = await sync_to_async(add_connection_sync)(client_id, tool_slug, targets)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_remove_tool_connection(
    client_id: int,
    tool_slug: str,
    target: str,
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Detach a tool from an agent target on the canvas. Credentials are
    kept, so reconnecting later does not require re-authorization."""
    result = await sync_to_async(remove_connection_sync)(client_id, tool_slug, target)
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
