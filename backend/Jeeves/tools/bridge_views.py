"""Matrix bridge login endpoints exposed to the client portal.

Drives interactive bridge login flows (WhatsApp QR, Telegram phone+code+2FA,
Meta cookies) through the existing Matrix infrastructure. The client portal
hits these endpoints; under the hood we DM the bridge bot from the service
account, capture replies via the Synapse CS API, and translate them into a
small JSON state machine the UI can render.

Per-client puppet credentials aren't used here — bridge logins happen on the
service-account `jeeves-bot`. That keeps the bridge graph single-tenant for
now; multi-tenant per-client puppets are a follow-up.
"""
from __future__ import annotations

import asyncio
import base64
import time
import urllib.parse

import httpx
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


SUPPORTED_NETWORKS = {
    'whatsapp': {
        'bot': 'whatsappbot',
        'login_command': 'login qr',
        'qr_message_type': 'm.image',
    },
    'telegram': {
        'bot': 'telegrambot',
        'login_command': 'login phone',
        'qr_message_type': None,  # phone+code flow, no QR
    },
    'instagram': {
        # mautrix-meta in `instagram` mode — bot is still @metabot.
        'bot': 'metabot',
        'login_command': 'login instagram',
        'qr_message_type': None,
    },
    'facebook': {
        # mautrix-meta in `facebook`/`messenger` mode — separate instance,
        # bot also @metabot (one bridge per mode in this deployment).
        'bot': 'metabot',
        'login_command': 'login facebook',
        'qr_message_type': None,
    },
}


def _hs() -> str:
    base = (settings.MATRIX_HOMESERVER_URL or '').rstrip('/')
    if not base:
        raise RuntimeError('MATRIX_HOMESERVER_URL is not configured')
    return base


def _auth() -> dict[str, str]:
    token = settings.MATRIX_BOT_TOKEN
    if not token:
        raise RuntimeError('MATRIX_BOT_TOKEN is not configured')
    return {'Authorization': f'Bearer {token}'}


def _bot_user_id() -> str:
    uid = settings.MATRIX_BOT_USER_ID
    if not uid:
        raise RuntimeError('MATRIX_BOT_USER_ID is not configured')
    return uid


def _matrix_domain() -> str:
    return _bot_user_id().split(':', 1)[1]


def _bridge_mxid(network: str) -> str:
    return f'@{SUPPORTED_NETWORKS[network]["bot"]}:{_matrix_domain()}'


def _find_or_create_management_room(client: httpx.Client, bridge_mxid: str) -> str:
    """Reuse an existing DM with the bridge bot, or create one."""
    resp = client.get(
        f'{_hs()}/_matrix/client/v3/user/{urllib.parse.quote(_bot_user_id())}/account_data/m.direct',
        headers=_auth(),
    )
    if resp.status_code == 200:
        direct = resp.json()
        existing = direct.get(bridge_mxid)
        if existing:
            return existing[0]

    # No DM yet — create one. Synapse's CS API: room_create with invite + is_direct.
    create = client.post(
        f'{_hs()}/_matrix/client/v3/createRoom',
        headers={**_auth(), 'Content-Type': 'application/json'},
        json={
            'preset': 'trusted_private_chat',
            'invite': [bridge_mxid],
            'is_direct': True,
            'name': f'{bridge_mxid} bridge management',
        },
    )
    create.raise_for_status()
    room_id = create.json()['room_id']

    # Persist the DM mapping so we reuse it next time.
    new_direct = (direct if resp.status_code == 200 else {})
    new_direct[bridge_mxid] = [room_id]
    client.put(
        f'{_hs()}/_matrix/client/v3/user/{urllib.parse.quote(_bot_user_id())}/account_data/m.direct',
        headers={**_auth(), 'Content-Type': 'application/json'},
        json=new_direct,
    )
    return room_id


def _send_text(client: httpx.Client, room_id: str, body: str) -> str:
    txn = f'jeeves-{int(time.time() * 1000)}'
    resp = client.put(
        f'{_hs()}/_matrix/client/v3/rooms/{urllib.parse.quote(room_id)}/send/m.room.message/{txn}',
        headers={**_auth(), 'Content-Type': 'application/json'},
        json={'msgtype': 'm.text', 'body': body},
    )
    resp.raise_for_status()
    return resp.json()['event_id']


def _read_recent(client: httpx.Client, room_id: str, limit: int = 5) -> list[dict]:
    sync = client.get(
        f'{_hs()}/_matrix/client/v3/sync?timeout=3000',
        headers=_auth(),
    )
    sync.raise_for_status()
    token = sync.json()['next_batch']
    resp = client.get(
        f'{_hs()}/_matrix/client/v3/rooms/{urllib.parse.quote(room_id)}/messages',
        headers=_auth(),
        params={'from': token, 'dir': 'b', 'limit': limit},
    )
    resp.raise_for_status()
    return resp.json().get('chunk', [])


def _download_mxc_to_b64(client: httpx.Client, mxc: str) -> str | None:
    if not mxc or not mxc.startswith('mxc://'):
        return None
    server_part, media_id = mxc[len('mxc://'):].split('/', 1)
    resp = client.get(
        f'{_hs()}/_matrix/client/v1/media/download/{server_part}/{media_id}',
        headers=_auth(),
    )
    if resp.status_code != 200:
        return None
    return base64.b64encode(resp.content).decode()


def _bridge_state(client: httpx.Client, room_id: str, network: str) -> dict:
    """Scan recent bridge messages to determine the current connection state.

    Returns the most recent text + a `connection_marker` priority — a
    "Successfully logged in" anywhere in the window beats a stale
    "expired/timeout" notice, because the bridge does not actively reset the
    state after a failed login attempt if the previous session is still alive.
    """
    bridge_mxid = _bridge_mxid(network)
    chunk = _read_recent(client, room_id, limit=50)
    connected_text = None
    last_text = None
    failure_text = None
    for ev in chunk:
        if ev.get('sender') != bridge_mxid:
            continue
        content = ev.get('content', {})
        if content.get('msgtype') not in ('m.notice', 'm.text'):
            continue
        body = content.get('body') or ''
        if last_text is None:
            last_text = body
        if connected_text is None and 'Successfully logged in' in body:
            connected_text = body
        body_lower = body.lower()
        if failure_text is None and (
            'timed out' in body_lower or 'expired' in body_lower or 'login failed' in body_lower
        ):
            failure_text = body

    # Connected wins over failure (the bridge keeps an existing session live
    # even if a separate fresh login attempt timed out).
    chosen = connected_text or failure_text or last_text
    return {
        'last_bridge_message': chosen,
        'room_id': room_id,
        'is_connected': bool(connected_text),
    }


class BridgeLoginStartView(APIView):
    """POST /api/tools/matrix/bridges/<network>/login/start

    Body (optional): ``{ "step_data": "..." }`` — used for follow-up steps in
    Telegram's phone → code → password flow. Omitted on the first call.

    Returns:
        ``{"login_id": "<room_id>", "qr": "<base64 png>"|null, "prompt": "..."|null, "step": "qr|phone|code|password|connected"}``
    """

    def post(self, request, network):
        client = getattr(request, 'client', None)
        if client is None:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        if network not in SUPPORTED_NETWORKS:
            return Response({'error': 'Unsupported network'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with httpx.Client(timeout=15.0) as http:
                room_id = _find_or_create_management_room(http, _bridge_mxid(network))
                step_data = (request.data.get('step_data') or '').strip()
                if step_data:
                    _send_text(http, room_id, step_data)
                else:
                    _send_text(http, room_id, SUPPORTED_NETWORKS[network]['login_command'])

                # Bridge takes 2-5s to respond. Wait then read history.
                payload = self._wait_for_response(http, room_id, network)
            return Response(payload)
        except Exception as exc:
            return Response(
                {'error': f'{type(exc).__name__}: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    @staticmethod
    def _wait_for_response(http: httpx.Client, room_id: str, network: str) -> dict:
        bridge_mxid = _bridge_mxid(network)
        deadline = time.time() + 12.0
        qr_b64 = None
        prompt = None
        step = 'sent'
        connected_patterns = (
            'Successfully logged in',
            "you're already logged in",
            'already logged in',
            'You are already logged in',
        )
        while time.time() < deadline:
            chunk = _read_recent(http, room_id, limit=10)
            saw_recent = False
            for ev in chunk:
                if ev.get('sender') != bridge_mxid:
                    continue
                content = ev.get('content', {})
                if content.get('msgtype') == 'm.image' and not qr_b64:
                    qr_b64 = _download_mxc_to_b64(http, content.get('url') or '')
                    if qr_b64:
                        step = 'qr'
                        saw_recent = True
                        break
                elif content.get('msgtype') in ('m.notice', 'm.text'):
                    body = content.get('body') or ''
                    body_lower = body.lower()
                    if any(p.lower() in body_lower for p in connected_patterns):
                        prompt = body
                        step = 'connected'
                        saw_recent = True
                        break
                    if any(kw in body for kw in ('Phone number', 'Code', 'Password', 'two-factor')):
                        prompt = body
                        step = 'code' if 'Code' in body else (
                            'password' if 'Password' in body or 'two-factor' in body else 'phone'
                        )
                        saw_recent = True
                        break
            if saw_recent:
                break
            time.sleep(1.5)
        return {
            'login_id': room_id,
            'qr': qr_b64,
            'prompt': prompt,
            'step': step,
        }


class BridgeStateView(APIView):
    """GET /api/tools/matrix/bridges/<network>/state/

    Returns current connection status for the bridge without requiring an
    active login_id. Looks up the bot's existing management DM with the bridge
    bot via ``m.direct`` and reads the most recent bridge messages to detect
    a successful login.
    """

    def get(self, request, network):
        client = getattr(request, 'client', None)
        if client is None:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        if network not in SUPPORTED_NETWORKS:
            return Response({'error': 'Unsupported network'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with httpx.Client(timeout=10.0) as http:
                resp = http.get(
                    f'{_hs()}/_matrix/client/v3/user/{urllib.parse.quote(_bot_user_id())}/account_data/m.direct',
                    headers=_auth(),
                )
                direct = resp.json() if resp.status_code == 200 else {}
                rooms = direct.get(_bridge_mxid(network)) or []
                if not rooms:
                    return Response({'status': 'disconnected'})
                state = _bridge_state(http, rooms[0], network)
        except Exception as exc:
            return Response(
                {'error': f'{type(exc).__name__}: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        last = state.get('last_bridge_message') or ''
        if state.get('is_connected'):
            # "Successfully logged in as +48727842737"
            # or "Successfully logged in as dcprn (`839685195`)"
            handle = ''
            after = last.split(' as ', 1)
            if len(after) == 2:
                tail = after[1].split('(', 1)[0].strip()
                handle = tail.rstrip('.,').strip('`')
            return Response({
                'status': 'connected',
                'message': last,
                'remote_handle': handle,
                'room_id': state['room_id'],
            })
        return Response({'status': 'disconnected', 'message': last})


class BridgeLoginStatusView(APIView):
    """GET /api/tools/matrix/bridges/<network>/login/status?login_id=<room_id>

    Polls bridge state via the most recent management-room messages. Returns
    a small JSON the UI re-evaluates to decide whether to stop polling.
    """

    def get(self, request, network):
        client = getattr(request, 'client', None)
        if client is None:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        if network not in SUPPORTED_NETWORKS:
            return Response({'error': 'Unsupported network'}, status=status.HTTP_400_BAD_REQUEST)

        room_id = request.GET.get('login_id')
        if not room_id:
            return Response({'error': 'login_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with httpx.Client(timeout=10.0) as http:
                state = _bridge_state(http, room_id, network)
        except Exception as exc:
            return Response(
                {'error': f'{type(exc).__name__}: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        last = state.get('last_bridge_message') or ''
        if state.get('is_connected'):
            return Response({'status': 'connected', 'message': last, 'room_id': room_id})
        if 'expired' in last.lower() or 'timed out' in last.lower():
            return Response({'status': 'expired', 'message': last, 'room_id': room_id})
        return Response({'status': 'pending', 'message': last, 'room_id': room_id})
