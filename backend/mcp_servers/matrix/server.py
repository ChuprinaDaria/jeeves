"""MCP Matrix server — unified messaging via Synapse + mautrix bridges.

Lets Concierge agents talk to clients across Instagram DM, FB Messenger,
WhatsApp, Telegram and Google Chat through a single Matrix Client-Server API.

Per-client credentials live in ``tools.ToolConnection.credentials`` (slug=``matrix``):
``{homeserver_url?, user_id, access_token}``. Falls back to the service-account
bot (``MATRIX_HOMESERVER_URL`` / ``MATRIX_BOT_USER_ID`` / ``MATRIX_BOT_TOKEN``).
"""
from mcp_servers.common.django_setup import setup
setup()

from fastmcp import FastMCP  # noqa: E402

from mcp_servers.matrix.tools import (  # noqa: E402
    list_rooms as _list_rooms,
    read_room_history as _read_room_history,
    send_message as _send_message,
    send_typing as _send_typing,
    mark_read as _mark_read,
    invite_user as _invite_user,
)

mcp = FastMCP(
    "mcp-matrix",
    description="Concierge Matrix server. Send/read DMs across IG, FB Messenger, WhatsApp, Telegram via mautrix bridges.",
)


@mcp.tool()
async def matrix_list_rooms(client_id: int) -> str:
    """List joined Matrix rooms for the client (each bridged DM is a room)."""
    return await _list_rooms(client_id)


@mcp.tool()
async def matrix_read_room_history(client_id: int, room_id: str, limit: int = 20) -> str:
    """Read recent messages from a Matrix room.

    Args:
        client_id: Jeeves Client id (resolves credentials).
        room_id: Matrix room id (e.g. ``!abc:matrix.example.com``).
        limit: number of messages (default 20, max ~100 per CS API page).
    """
    return await _read_room_history(client_id, room_id, limit)


@mcp.tool()
async def matrix_send_message(client_id: int, room_id: str, body: str) -> str:
    """Send a plain-text message to a Matrix room.

    Args:
        client_id: Jeeves Client id.
        room_id: Matrix room id.
        body: message text.
    """
    return await _send_message(client_id, room_id, body)


@mcp.tool()
async def matrix_send_typing(client_id: int, room_id: str, typing: bool = True, timeout_ms: int = 30000) -> str:
    """Show a typing indicator in a room. Bridges forward it to the source platform when supported."""
    return await _send_typing(client_id, room_id, typing, timeout_ms)


@mcp.tool()
async def matrix_mark_read(client_id: int, room_id: str, event_id: str) -> str:
    """Mark a Matrix event as read (sends read receipt + fully_read marker)."""
    return await _mark_read(client_id, room_id, event_id)


@mcp.tool()
async def matrix_invite_user(client_id: int, room_id: str, user_id: str) -> str:
    """Invite a Matrix user to a room — used for HITL escalation (e.g. invite a manager)."""
    return await _invite_user(client_id, room_id, user_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
