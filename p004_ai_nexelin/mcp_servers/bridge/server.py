"""MCP Bridge server — tools for Oleg to manage platform connections."""
import json
import logging
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async, async_to_sync
from django.utils import timezone
from MASTER.clients.models import Client
from MASTER.clients.services.bridge_service import bridge_service, BridgeServiceError
from MASTER.tools.models import ToolCard, ToolConnection

mcp = FastMCP("mcp-bridge")


@mcp.tool()
async def bridge_start_connection(
    client_id: int,
    bridge_type: str = "",
) -> str:
    """Start connecting a messaging platform via cookie bridge.
    Supported bridge_type: meta-facebook, meta-instagram, linkedin.
    WhatsApp uses a separate QR flow — do NOT call this for WhatsApp.
    Returns auth flow info (popup URL for cookie extraction via Chrome Extension)."""
    if not bridge_type:
        return json.dumps({"error": "bridge_type is required (meta-facebook, meta-instagram, linkedin)"})

    client = await sync_to_async(Client.objects.get)(pk=client_id)
    try:
        result = await bridge_service.start_login(client, bridge_type)
    except BridgeServiceError as e:
        return json.dumps({"error": str(e)})

    if result.get('auth_flow') == 'cookies':
        return json.dumps({
            "type": "auth_popup",
            "status": "auth_required",
            "auth_flow": "cookies",
            "bridge_type": bridge_type,
            "popup_url": result.get("popup_url", ""),
            "cookie_domains": result.get("cookie_domains", []),
            "required_cookies": result.get("required_cookies", []),
            "message": f"User needs to authenticate via the Nexelin Chrome extension. "
                       f"The extension will open {result.get('popup_url', '')} and extract cookies.",
        })
    elif result.get('auth_flow') == 'qr_code':
        return json.dumps({
            "type": "qr_code",
            "status": "qr_pending",
            "auth_flow": "qr_code",
            "bridge_type": bridge_type,
            "qr": result.get("qr", ""),
            "message": "QR code generated. User needs to scan it with their WhatsApp app.",
        })
    else:
        return json.dumps(result)


@mcp.tool()
async def bridge_check_status(
    client_id: int,
    bridge_type: str = "",
) -> str:
    """Check the connection status of a messaging bridge.
    If bridge_type is empty, returns status of all bridges."""
    client = await sync_to_async(Client.objects.get)(pk=client_id)

    try:
        if not bridge_type:
            connections = await bridge_service.list_connections(client)
            return json.dumps({"connections": connections})

        result = await bridge_service.check_status(client, bridge_type)
        return json.dumps({
            "type": "status_card",
            "bridge_type": bridge_type,
            "status": result.get("status", "disconnected"),
            "remote_id": result.get("remote_id"),
            "connected_at": str(result.get("connected_at", "")),
            "error": result.get("error", ""),
        })
    except BridgeServiceError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def canvas_add_tool_connection(
    client_id: int,
    bridge_type: str = "",
    targets: list[str] | None = None,
) -> str:
    """Add a connected bridge to the flow canvas with chosen targets.
    targets: list of 'assistant', 'manager', 'leads'.
    Default targets: LinkedIn -> ['leads'], Facebook/Instagram -> ['assistant', 'manager']."""
    if not bridge_type:
        return json.dumps({"error": "bridge_type is required"})

    client = await sync_to_async(Client.objects.get)(pk=client_id)

    try:
        tool_card = await sync_to_async(ToolCard.objects.get)(slug=bridge_type)
    except ToolCard.DoesNotExist:
        return json.dumps({"error": f"ToolCard not found for {bridge_type}"})

    if not targets:
        from MASTER.clients.models_bridge import BridgeConfig
        try:
            config = await sync_to_async(BridgeConfig.objects.get)(bridge_type=bridge_type)
            targets = config.default_scopes
        except BridgeConfig.DoesNotExist:
            targets = ['assistant']

    nodes_created = []
    for target in targets:
        conn, created = await sync_to_async(ToolConnection.objects.update_or_create)(
            client=client,
            tool_card=tool_card,
            target=target,
            defaults={
                'status': 'connected',
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            },
        )
        nodes_created.append(f"{target}-{bridge_type}")

    return json.dumps({
        "type": "connection_created",
        "status": "connected",
        "bridge_type": bridge_type,
        "targets": targets,
        "nodes_created": nodes_created,
    })


@mcp.tool()
async def canvas_remove_tool_connection(
    client_id: int,
    connection_id: int = 0,
    bridge_type: str = "",
) -> str:
    """Remove a bridge connection from the canvas.
    Provide either connection_id or bridge_type."""
    client = await sync_to_async(Client.objects.get)(pk=client_id)

    if connection_id:
        try:
            conn = await sync_to_async(ToolConnection.objects.get)(pk=connection_id, client=client)
            await sync_to_async(conn.delete)()
            return json.dumps({"type": "connection_removed", "status": "removed", "connection_id": connection_id})
        except ToolConnection.DoesNotExist:
            return json.dumps({"error": f"Connection {connection_id} not found"})

    if bridge_type:
        try:
            tool_card = await sync_to_async(ToolCard.objects.get)(slug=bridge_type)
        except ToolCard.DoesNotExist:
            return json.dumps({"error": f"ToolCard not found for {bridge_type}"})

        deleted, _ = await sync_to_async(
            ToolConnection.objects.filter(client=client, tool_card=tool_card).delete
        )()
        return json.dumps({"type": "connection_removed", "status": "removed", "bridge_type": bridge_type, "deleted_count": deleted})

    return json.dumps({"error": "connection_id or bridge_type required"})


@mcp.tool()
async def canvas_list_connections(
    client_id: int,
) -> str:
    """List all current tool connections on the canvas."""
    client = await sync_to_async(Client.objects.get)(pk=client_id)

    connections = await sync_to_async(list)(
        ToolConnection.objects.filter(client=client)
        .select_related('tool_card')
        .values(
            'id', 'tool_card__slug', 'tool_card__name', 'status',
            'target', 'connected_at', 'enabled'
        )
    )

    # Convert datetimes to strings for JSON
    for c in connections:
        if c.get('connected_at'):
            c['connected_at'] = str(c['connected_at'])

    try:
        bridge_connections = await bridge_service.list_connections(client)
    except Exception:
        bridge_connections = []

    return json.dumps({
        "canvas_connections": connections,
        "bridge_connections": bridge_connections,
    })


if __name__ == "__main__":
    mcp.run()
