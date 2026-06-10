"""Celery tasks for the Jeeves agents app.

Currently hosts the Matrix long-poll listener: a long-lived ``nio.AsyncClient.sync_forever``
loop that maps inbound room messages back to a Jeeves ``Client`` (via
``clients.MatrixRoomBinding``) and dispatches them through the dual-mode agent
pipeline so the agent can reply via the existing ``mcp_matrix`` MCP server.

Spawned via Celery beat (``matrix-listener-bootstrap`` schedule entry, fires
once per minute and short-circuits if already running) so a fresh worker
auto-recovers after restart.
"""
from __future__ import annotations

import asyncio
import logging
import os

from asgiref.sync import sync_to_async
from celery import shared_task

logger = logging.getLogger(__name__)

# Module-level guard so beat's per-minute kick doesn't spawn N listeners.
_LISTENER_RUNNING = False


@shared_task(name='agents.matrix_listener_bootstrap')
def matrix_listener_bootstrap() -> str:
    """Beat entrypoint — ensures a single listener is alive per worker process.

    Idempotent: returns immediately if a listener is already running in this
    process. The actual loop is launched as a fire-and-forget asyncio task
    inside the celery worker's event loop.
    """
    global _LISTENER_RUNNING
    if _LISTENER_RUNNING:
        return 'already-running'

    if not os.environ.get('MATRIX_BOT_TOKEN'):
        return 'skipped:no-token'

    _LISTENER_RUNNING = True
    # Run in a dedicated thread so it doesn't block the celery worker's pool.
    import threading
    thread = threading.Thread(target=_run_listener_thread, name='matrix-listener', daemon=True)
    thread.start()
    return 'started'


def _run_listener_thread() -> None:
    """Thread target — owns its own asyncio loop."""
    global _LISTENER_RUNNING
    try:
        asyncio.run(_listener_loop())
    except Exception:  # pragma: no cover — logged for ops visibility
        logger.exception('matrix_listener crashed; will respawn on next beat tick')
    finally:
        _LISTENER_RUNNING = False


async def _listener_loop() -> None:
    """Sync forever against Synapse via the service-account bot.

    All bridged DMs land in rooms the puppet (or bot) is joined to. We use
    `MatrixRoomBinding` to resolve room_id → Jeeves Client. Messages from rooms
    we don't have a binding for are ignored (e.g. bridge-management rooms).

    Also auto-accepts room invites — bridges like mautrix-telegram create
    per-DM portal rooms and invite the logged-in puppet to each.
    """
    from mcp_servers.matrix.client import get_async_client

    nio_client = await get_async_client(None)  # service-account bot
    try:
        from nio import InviteMemberEvent, RoomMessageText

        async def on_message(room, event) -> None:
            await _handle_message(room.room_id, event.sender, event.body, event.event_id)

        async def on_invite(room, event) -> None:
            if event.membership != 'invite' or event.state_key != nio_client.user_id:
                return
            try:
                await nio_client.join(room.room_id)
                logger.info('matrix_listener: auto-joined invited room %s', room.room_id)
            except Exception:
                logger.exception('matrix_listener: failed to join %s', room.room_id)

        nio_client.add_event_callback(on_message, RoomMessageText)
        nio_client.add_event_callback(on_invite, InviteMemberEvent)
        logger.info('matrix_listener: starting sync_forever as %s', nio_client.user_id)

        # Drain any pending invites before entering the long sync.
        first_sync = await nio_client.sync(timeout=3000)
        invited = getattr(nio_client, 'invited_rooms', {}) or {}
        for room_id in list(invited.keys()):
            try:
                await nio_client.join(room_id)
                logger.info('matrix_listener: accepted pending invite for %s', room_id)
            except Exception:
                logger.exception('matrix_listener: failed initial join of %s', room_id)

        next_batch = getattr(first_sync, 'next_batch', None)
        await nio_client.sync_forever(timeout=30000, full_state=False, since=next_batch)
    finally:
        await nio_client.close()


async def _handle_message(room_id: str, sender: str, body: str, event_id: str) -> None:
    """Resolve room → client and hand off to the agent dispatcher."""
    from Jeeves.clients.models import MatrixRoomBinding
    from django.conf import settings

    bot_mxid = settings.MATRIX_BOT_USER_ID

    # Owner-only in-chat control: `!jeeves on <client_tag>`, `!jeeves off`,
    # `!jeeves status`. Sent by the bot itself (jeeves-bot session in Element)
    # — anyone else's messages are ignored as commands.
    if body and body.startswith('!jeeves'):
        if sender == bot_mxid:
            await _handle_jeeves_command(room_id, body)
        return

    if sender == bot_mxid:
        return  # ignore self echoes

    binding = await sync_to_async(
        lambda: MatrixRoomBinding.objects.select_related('client').filter(
            room_id=room_id, is_active=True
        ).first()
    )()
    if binding is None:
        logger.debug('matrix_listener: ignoring room %s (no binding)', room_id)
        return

    # Skip if it's the puppet for this client talking (puppet sends as the client)
    client = binding.client
    puppet_mxid = await _puppet_mxid_for(client.pk)
    if sender == puppet_mxid:
        return

    logger.info(
        'matrix_listener: routing event %s from %s in %s to client %s',
        event_id, sender, room_id, client.pk,
    )

    # Hand off to the existing dispatch pipeline. Run in a thread because the
    # MCP orchestrator launches subprocesses and we're already inside an event loop.
    from Jeeves.agents.dispatch import generate_response_dual

    def _dispatch() -> str:
        return generate_response_dual(
            body, client,
            conversation=None,
            channel='matrix',
            external_user_id=sender,
        )

    try:
        reply = await asyncio.get_running_loop().run_in_executor(None, _dispatch)
    except Exception:
        logger.exception('agent dispatch failed for room %s event %s', room_id, event_id)
        return

    if not reply:
        return

    from mcp_servers.matrix import tools as matrix_tools

    await matrix_tools.send_message(client.pk, room_id, reply)
    await sync_to_async(_mark_event_handled)(binding, event_id)


def _mark_event_handled(binding, event_id: str) -> None:
    binding.last_event_id = event_id
    binding.save(update_fields=['last_event_id', 'updated_at'])


async def _handle_jeeves_command(room_id: str, body: str) -> None:
    """Parse `!jeeves <cmd> [args]` and post a reply into the same room.

    Supported:
      `!jeeves on <client_tag>` — bind this room to a Jeeves client, agent will auto-reply.
      `!jeeves off`             — disable auto-reply for this room.
      `!jeeves status`          — report binding state.
    """
    parts = body.split(maxsplit=2)
    cmd = parts[1].lower() if len(parts) >= 2 else 'status'
    arg = parts[2].strip() if len(parts) >= 3 else ''

    from Jeeves.clients.models import Client, MatrixRoomBinding
    from mcp_servers.matrix import tools as matrix_tools

    reply = ''
    if cmd == 'on':
        if not arg:
            reply = 'Usage: `!jeeves on <client_tag>`'
        else:
            def _do_bind() -> str:
                try:
                    client = Client.objects.get(tag=arg, is_active=True)
                except Client.DoesNotExist:
                    return f'No active client with tag `{arg}`.'
                binding, created = MatrixRoomBinding.objects.update_or_create(
                    room_id=room_id,
                    defaults={'client': client, 'is_active': True},
                )
                verb = 'Bound' if created else 'Re-enabled'
                return f'✅ {verb} this room to client `{client.tag}` (id={client.pk}).'
            reply = await sync_to_async(_do_bind)()
    elif cmd == 'off':
        def _do_off() -> str:
            updated = MatrixRoomBinding.objects.filter(room_id=room_id).update(is_active=False)
            return '🛑 Auto-reply disabled for this room.' if updated else 'This room had no active binding.'
        reply = await sync_to_async(_do_off)()
    elif cmd == 'status':
        def _do_status() -> str:
            binding = (
                MatrixRoomBinding.objects.select_related('client')
                .filter(room_id=room_id).first()
            )
            if not binding:
                return 'No binding for this room. Use `!jeeves on <client_tag>` to enable.'
            state = 'ACTIVE' if binding.is_active else 'paused'
            return f'Bound to client `{binding.client.tag}` ({state}).'
        reply = await sync_to_async(_do_status)()
    else:
        reply = (
            'Commands:\n'
            '`!jeeves on <client_tag>` — enable auto-reply\n'
            '`!jeeves off` — disable\n'
            '`!jeeves status` — show binding'
        )

    try:
        await matrix_tools.send_message(None, room_id, reply)
    except Exception:
        logger.exception('matrix_listener: failed to post jeeves command reply')


async def _puppet_mxid_for(client_id: int) -> str | None:
    """Resolve the puppet MXID for a client (if a ToolConnection exists)."""
    from Jeeves.tools.models import ToolConnection

    def _lookup() -> str | None:
        conn = (
            ToolConnection.objects
            .filter(client_id=client_id, tool_card__slug='matrix', enabled=True)
            .first()
        )
        if not conn:
            return None
        return (conn.credentials or {}).get('user_id')

    return await sync_to_async(_lookup)()
