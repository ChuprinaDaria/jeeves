"""Async tool implementations for the Matrix MCP server.

Each function opens a ``nio.AsyncClient``, performs the action, and closes the
client. Heavy state (sync, device-list caching) is *not* persisted between calls
yet — for prod we'll likely want a long-lived client per Jeeves Client.
"""
from __future__ import annotations

import json
from typing import Any

from mcp_servers.matrix.client import MatrixClientError, get_async_client


async def list_rooms(client_id: int) -> str:
    client = await get_async_client(client_id)
    try:
        from nio import responses as nio_responses

        resp = await client.joined_rooms()
        if isinstance(resp, nio_responses.JoinedRoomsError):
            raise MatrixClientError(f"joined_rooms failed: {resp.message}")
        rooms = []
        for room_id in resp.rooms:
            name_resp = await client.room_get_state_event(room_id, "m.room.name")
            name = getattr(name_resp, "content", {}).get("name") if hasattr(name_resp, "content") else None
            rooms.append({"room_id": room_id, "name": name})
        return json.dumps({"rooms": rooms}, ensure_ascii=False)
    finally:
        await client.close()


async def read_room_history(client_id: int, room_id: str, limit: int = 20) -> str:
    client = await get_async_client(client_id)
    try:
        sync_resp = await client.sync(timeout=3000)
        token = getattr(sync_resp, "next_batch", None)
        if not token:
            return json.dumps({"messages": []}, ensure_ascii=False)
        resp = await client.room_messages(room_id, token, limit=limit)
        messages: list[dict[str, Any]] = []
        for ev in getattr(resp, "chunk", []) or []:
            body = getattr(ev, "body", None) or getattr(ev, "source", {}).get("content", {}).get("body")
            messages.append(
                {
                    "sender": getattr(ev, "sender", None),
                    "body": body,
                    "ts": getattr(ev, "server_timestamp", None),
                    "type": ev.__class__.__name__,
                }
            )
        return json.dumps({"messages": messages}, ensure_ascii=False)
    finally:
        await client.close()


async def send_message(client_id: int, room_id: str, body: str) -> str:
    client = await get_async_client(client_id)
    try:
        resp = await client.room_send(
            room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": body},
        )
        event_id = getattr(resp, "event_id", None)
        return json.dumps({"ok": event_id is not None, "event_id": event_id}, ensure_ascii=False)
    finally:
        await client.close()


async def send_typing(client_id: int, room_id: str, typing: bool = True, timeout_ms: int = 30000) -> str:
    client = await get_async_client(client_id)
    try:
        await client.room_typing(room_id, typing_state=typing, timeout=timeout_ms)
        return json.dumps({"ok": True}, ensure_ascii=False)
    finally:
        await client.close()


async def mark_read(client_id: int, room_id: str, event_id: str) -> str:
    client = await get_async_client(client_id)
    try:
        await client.room_read_markers(room_id, fully_read_event=event_id, read_event=event_id)
        return json.dumps({"ok": True}, ensure_ascii=False)
    finally:
        await client.close()


async def invite_user(client_id: int, room_id: str, user_id: str) -> str:
    """Invite a Matrix user to a room — used for HITL escalation (invite manager)."""
    client = await get_async_client(client_id)
    try:
        resp = await client.room_invite(room_id, user_id)
        ok = not hasattr(resp, "message")
        return json.dumps({"ok": ok, "error": getattr(resp, "message", None)}, ensure_ascii=False)
    finally:
        await client.close()


async def create_dm_room(
    client_id: int | None,
    invitee_mxid: str,
    name: str | None = None,
) -> str:
    """Create a private 1:1 Matrix room with another user.

    Used to seed a conversation from the agent's side (e.g. HITL room with a
    manager, or a smoke-test room). Bridge-created rooms appear automatically
    via the bridge bot — only call this for *Matrix-native* DMs.
    """
    client = await get_async_client(client_id)
    try:
        from nio import RoomVisibility

        kwargs: dict[str, Any] = {
            "visibility": RoomVisibility.private,
            "invite": [invitee_mxid],
            "is_direct": True,
        }
        if name:
            kwargs["name"] = name
        resp = await client.room_create(**kwargs)
        room_id = getattr(resp, "room_id", None)
        if not room_id:
            return json.dumps(
                {"ok": False, "error": getattr(resp, "message", "room_create returned no room_id")},
                ensure_ascii=False,
            )
        return json.dumps({"ok": True, "room_id": room_id, "invited": [invitee_mxid]}, ensure_ascii=False)
    finally:
        await client.close()
