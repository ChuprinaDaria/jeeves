"""
Service layer for WhatsApp Bridge (mautrix-whatsapp) integration.
Handles Matrix user creation, WhatsApp login via provisioning API, and status checks.
Uses WebSocket for QR login (mautrix-whatsapp v0.10.x provisioning v1 API).
"""
import hashlib
import hmac
import json
import logging
import threading
import time

import httpx

from MASTER.clients.models import WhatsAppBridgeConfig

# In-memory store for active login sessions
# {client_id: {'qr': str, 'status': str, 'phone': str, 'error': str, 'ws_thread': Thread}}
_login_sessions = {}

logger = logging.getLogger(__name__)


class WhatsAppBridgeError(Exception):
    """Base error for WhatsApp Bridge operations."""
    pass


def _get_config() -> WhatsAppBridgeConfig:
    """Load global bridge config. Raises if not configured or disabled."""
    try:
        config = WhatsAppBridgeConfig.objects.get(pk=1)
    except WhatsAppBridgeConfig.DoesNotExist:
        raise WhatsAppBridgeError("WhatsApp Bridge is not configured. Set up in Django admin.")
    if not config.is_enabled:
        raise WhatsAppBridgeError("WhatsApp Bridge is globally disabled.")
    return config


def create_matrix_user(client) -> tuple[str, str]:
    """
    Register a dedicated Matrix user on Synapse for this client.
    Uses Synapse's shared-secret registration admin API.
    Returns (user_id, access_token).
    """
    config = _get_config()
    username = config.bot_username_template.replace('{client_id}', str(client.id))
    user_id = f"@{username}:{config.homeserver_domain}"

    # Check if user already exists and has token
    if client.whatsapp_bridge_matrix_user_id and client.whatsapp_bridge_matrix_access_token:
        return client.whatsapp_bridge_matrix_user_id, client.whatsapp_bridge_matrix_access_token

    # Synapse shared-secret registration
    # Step 1: Get nonce
    nonce_url = f"{config.homeserver_url}/_synapse/admin/v1/register"
    nonce_resp = httpx.get(nonce_url, timeout=10.0)
    if nonce_resp.status_code != 200:
        raise WhatsAppBridgeError(f"Failed to get registration nonce: {nonce_resp.status_code}")

    nonce = nonce_resp.json()["nonce"]

    # Step 2: Generate HMAC
    password = f"bridge_bot_{client.id}_{config.homeserver_domain}"
    mac_msg = f"{nonce}\0{username}\0{password}\0notadmin"
    mac = hmac.new(
        config.registration_shared_secret.encode(),
        mac_msg.encode(),
        hashlib.sha1,
    ).hexdigest()

    # Step 3: Register
    reg_resp = httpx.post(
        nonce_url,
        json={
            "nonce": nonce,
            "username": username,
            "password": password,
            "admin": False,
            "mac": mac,
        },
        timeout=10.0,
    )

    if reg_resp.status_code == 200:
        data = reg_resp.json()
        access_token = data["access_token"]
        actual_user_id = data.get("user_id", user_id)
        logger.info(f"Created Matrix user {actual_user_id} for client {client.id}")
    elif reg_resp.status_code == 400 and "User ID already taken" in reg_resp.text:
        # User exists, login instead
        login_resp = httpx.post(
            f"{config.homeserver_url}/_matrix/client/v3/login",
            json={
                "type": "m.login.password",
                "identifier": {"type": "m.id.user", "user": username},
                "password": password,
            },
            timeout=10.0,
        )
        if login_resp.status_code != 200:
            raise WhatsAppBridgeError(f"Matrix user exists but login failed: {login_resp.text}")
        data = login_resp.json()
        access_token = data["access_token"]
        actual_user_id = data.get("user_id", user_id)
        logger.info(f"Logged into existing Matrix user {actual_user_id} for client {client.id}")
    else:
        raise WhatsAppBridgeError(f"Matrix user registration failed: {reg_resp.status_code} {reg_resp.text}")

    # Save to client
    client.whatsapp_bridge_matrix_user_id = actual_user_id
    client.whatsapp_bridge_matrix_access_token = access_token
    client.save(update_fields=['whatsapp_bridge_matrix_user_id', 'whatsapp_bridge_matrix_access_token'])

    return actual_user_id, access_token


def _ws_login_worker(client_id: int, user_id: str, config):
    """Background thread: connects to mautrix-whatsapp provisioning WebSocket for QR login."""
    import websocket

    session = _login_sessions.get(client_id, {})
    ws_url = config.provisioning_url.replace('http://', 'ws://').replace('https://', 'wss://')
    ws_url = f"{ws_url}/_matrix/provision/v1/login?user_id={user_id}"

    try:
        ws = websocket.create_connection(
            ws_url,
            header=[f"Authorization: Bearer {config.provisioning_secret}"],
            timeout=120,
        )
        while session.get('status') == 'qr_pending':
            try:
                msg = ws.recv()
                if not msg:
                    break
                data = json.loads(msg)
                code = data.get('code', '')
                if code == 'qr':
                    session['qr'] = data.get('qr', '')
                elif code == 'login_complete' or data.get('success'):
                    phone = data.get('phone', '')
                    session['status'] = 'connected'
                    session['phone'] = phone
                    # Update client in DB
                    from django.utils import timezone
                    from MASTER.clients.models import Client
                    try:
                        c = Client.objects.get(id=client_id)
                        c.whatsapp_bridge_status = 'connected'
                        c.whatsapp_bridge_phone = phone
                        c.whatsapp_bridge_connected_at = timezone.now()
                        c.whatsapp_bridge_error = ''
                        c.save(update_fields=[
                            'whatsapp_bridge_status', 'whatsapp_bridge_phone',
                            'whatsapp_bridge_connected_at', 'whatsapp_bridge_error',
                        ])
                    except Exception:
                        pass
                    break
                elif code in ('error', 'fail'):
                    session['status'] = 'error'
                    session['error'] = data.get('error', 'Login failed')
                    break
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                session['status'] = 'error'
                session['error'] = str(e)
                break
        ws.close()
    except Exception as e:
        session['status'] = 'error'
        session['error'] = f"WebSocket connection failed: {e}"
        logger.error(f"WS login failed for client {client_id}: {e}")


def start_whatsapp_login(client) -> dict:
    """
    Start WhatsApp login via mautrix-whatsapp provisioning WebSocket (v1 API).
    Opens a background WebSocket that receives QR codes.
    Returns initial status; frontend polls check_login_status for QR updates.
    """
    config = _get_config()

    # Ensure Matrix user exists
    user_id, _ = create_matrix_user(client)

    # Initialize session
    session = {
        'qr': '',
        'status': 'qr_pending',
        'phone': '',
        'error': '',
    }
    _login_sessions[client.id] = session

    # Start WebSocket in background thread
    t = threading.Thread(
        target=_ws_login_worker,
        args=(client.id, user_id, config),
        daemon=True,
    )
    t.start()

    # Wait briefly for first QR code
    for _ in range(20):  # up to 2 seconds
        time.sleep(0.1)
        if session.get('qr') or session.get('status') != 'qr_pending':
            break

    # Update client status
    client.whatsapp_bridge_status = 'qr_pending'
    client.whatsapp_bridge_error = ''
    client.save(update_fields=['whatsapp_bridge_status', 'whatsapp_bridge_error'])

    if session.get('status') == 'error':
        raise WhatsAppBridgeError(session.get('error', 'Login failed'))

    return {
        'login_id': str(client.id),
        'qr': session.get('qr', ''),
        'status': 'qr_pending',
    }


def check_login_status(client, login_id: str) -> dict:
    """
    Check login status from in-memory session (fed by WebSocket background thread).
    """
    session = _login_sessions.get(client.id)
    if not session:
        return {'status': 'error', 'error': 'No active login session'}

    status = session.get('status', 'unknown')

    if status == 'connected':
        # Clean up session
        _login_sessions.pop(client.id, None)
        return {'status': 'connected', 'phone': session.get('phone', '')}

    elif status == 'error':
        error = session.get('error', 'Login failed')
        _login_sessions.pop(client.id, None)
        client.whatsapp_bridge_status = 'error'
        client.whatsapp_bridge_error = error
        client.save(update_fields=['whatsapp_bridge_status', 'whatsapp_bridge_error'])
        return {'status': 'error', 'error': error}

    # Still pending — return latest QR
    return {
        'status': 'qr_pending',
        'qr': session.get('qr', ''),
    }


def logout_whatsapp(client) -> bool:
    """
    Disconnect WhatsApp via provisioning API.
    """
    config = _get_config()

    if not client.whatsapp_bridge_matrix_user_id:
        return False

    headers = {
        "Authorization": f"Bearer {config.provisioning_secret}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(
            f"{config.provisioning_url}/_matrix/provision/v2/logout",
            json={"user_id": client.whatsapp_bridge_matrix_user_id},
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code not in (200, 204):
            logger.warning(f"Provisioning logout returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Provisioning logout failed: {e}")

    # Reset client fields regardless
    client.whatsapp_bridge_status = 'disconnected'
    client.whatsapp_bridge_phone = ''
    client.whatsapp_bridge_connected_at = None
    client.whatsapp_bridge_error = ''
    client.save(update_fields=[
        'whatsapp_bridge_status', 'whatsapp_bridge_phone',
        'whatsapp_bridge_connected_at', 'whatsapp_bridge_error',
    ])
    return True


def get_connection_status(client) -> dict:
    """
    Check actual WhatsApp connection status via provisioning API.
    """
    config = _get_config()

    if not client.whatsapp_bridge_matrix_user_id:
        return {'status': 'disconnected'}

    headers = {
        "Authorization": f"Bearer {config.provisioning_secret}",
    }
    try:
        resp = httpx.get(
            f"{config.provisioning_url}/_matrix/provision/v2/whoami",
            params={"user_id": client.whatsapp_bridge_matrix_user_id},
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('whatsapp', {}).get('jid'):
                return {
                    'status': 'connected',
                    'phone': data['whatsapp'].get('phone', client.whatsapp_bridge_phone),
                }
        return {'status': 'disconnected'}
    except Exception as e:
        logger.error(f"Connection status check failed: {e}")
        return {'status': 'unknown', 'error': str(e)}
