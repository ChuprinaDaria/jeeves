"""
Service layer for WhatsApp Bridge (mautrix-whatsapp v26+ megabridge) integration.
Handles Matrix user creation, WhatsApp login via provisioning v3 API, and status checks.
Uses HTTP polling for QR login (v3 provisioning API with Matrix access token auth).
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
# {client_id: {'qr': str, 'status': str, 'phone': str, 'error': str, 'login_id': str}}
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


def _provision_headers(access_token: str) -> dict:
    """Auth headers for provisioning API using Matrix access token."""
    return {"Authorization": f"Bearer {access_token}"}


def _provision_headers_secret(config) -> dict:
    """Auth headers for provisioning API using shared secret (fallback)."""
    return {"Authorization": f"Bearer {config.provisioning_secret}"}


def create_matrix_user(client) -> tuple[str, str]:
    """
    Register a dedicated Matrix user on Synapse for this client.
    Uses appservice registration (users in bridge namespace) with fallback
    to shared-secret registration for users outside namespace.
    Returns (user_id, access_token).
    """
    config = _get_config()
    username = config.bot_username_template.replace('{client_id}', str(client.id))
    user_id = f"@{username}:{config.homeserver_domain}"

    # Check if user already exists and has token — verify it's still valid
    if client.whatsapp_bridge_matrix_user_id and client.whatsapp_bridge_matrix_access_token:
        try:
            resp = httpx.get(
                f"{config.homeserver_url}/_matrix/client/v3/account/whoami",
                headers={"Authorization": f"Bearer {client.whatsapp_bridge_matrix_access_token}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return client.whatsapp_bridge_matrix_user_id, client.whatsapp_bridge_matrix_access_token
            logger.warning(f"Existing Matrix token invalid ({resp.status_code}), re-registering")
        except Exception as e:
            logger.warning(f"Failed to verify existing Matrix token: {e}")

    # Try appservice registration first (for users in bridge namespace like whatsapp_*)
    # as_token from bridge registration — used to register/login users in the whatsapp_ namespace
    as_token = getattr(config, 'provisioning_secret', '')  # reuse provisioning field or read from env
    # The bridge's actual appservice as_token (from registration.yaml)
    import os
    as_token = os.environ.get('MAUTRIX_AS_TOKEN', 'vMXiRA8ZJcmQ0ykpFC1RW1gr9stY6Eot8Amuxw2Me6kIoxUgp9wAMtUTPfu6e9C7')

    access_token = None
    actual_user_id = user_id

    if as_token:
        # Register via appservice API
        reg_resp = httpx.post(
            f"{config.homeserver_url}/_matrix/client/v3/register",
            json={
                "type": "m.login.application_service",
                "username": username,
            },
            headers={"Authorization": f"Bearer {as_token}"},
            timeout=10.0,
        )
        if reg_resp.status_code == 200:
            data = reg_resp.json()
            access_token = data.get("access_token", "")
            actual_user_id = data.get("user_id", user_id)
            logger.info(f"Created Matrix user {actual_user_id} via appservice for client {client.id}")
        elif reg_resp.status_code == 400 and "already taken" in reg_resp.text.lower():
            # User exists — login via appservice
            login_resp = httpx.post(
                f"{config.homeserver_url}/_matrix/client/v3/login",
                json={
                    "type": "m.login.application_service",
                    "identifier": {"type": "m.id.user", "user": username},
                },
                headers={"Authorization": f"Bearer {as_token}"},
                timeout=10.0,
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                access_token = data.get("access_token", "")
                actual_user_id = data.get("user_id", user_id)
                logger.info(f"Logged into existing Matrix user {actual_user_id} via appservice for client {client.id}")
            else:
                logger.warning(f"Appservice login failed: {login_resp.status_code} {login_resp.text}")
        else:
            logger.warning(f"Appservice registration failed: {reg_resp.status_code} {reg_resp.text}")

    # Fallback: shared-secret registration (for users outside bridge namespace)
    if not access_token:
        nonce_url = f"{config.homeserver_url}/_synapse/admin/v1/register"
        nonce_resp = httpx.get(nonce_url, timeout=10.0)
        if nonce_resp.status_code != 200:
            raise WhatsAppBridgeError(f"Failed to get registration nonce: {nonce_resp.status_code}")

        nonce = nonce_resp.json()["nonce"]
        password = f"bridge_bot_{client.id}_{config.homeserver_domain}"
        mac_msg = f"{nonce}\0{username}\0{password}\0notadmin"
        mac = hmac.new(
            config.registration_shared_secret.encode(),
            mac_msg.encode(),
            hashlib.sha1,
        ).hexdigest()

        reg_resp = httpx.post(
            nonce_url,
            json={"nonce": nonce, "username": username, "password": password, "admin": False, "mac": mac},
            timeout=10.0,
        )

        if reg_resp.status_code == 200:
            data = reg_resp.json()
            access_token = data["access_token"]
            actual_user_id = data.get("user_id", user_id)
            logger.info(f"Created Matrix user {actual_user_id} via shared-secret for client {client.id}")
        elif reg_resp.status_code == 400 and "User ID already taken" in reg_resp.text:
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

    if not access_token:
        raise WhatsAppBridgeError("Failed to obtain Matrix access token")

    client.whatsapp_bridge_matrix_user_id = actual_user_id
    client.whatsapp_bridge_matrix_access_token = access_token
    client.save(update_fields=['whatsapp_bridge_matrix_user_id', 'whatsapp_bridge_matrix_access_token'])

    return actual_user_id, access_token


def _matrix_request(access_token: str, homeserver_url: str, method: str, path: str, **kwargs) -> httpx.Response:
    """Make an authenticated Matrix client API request."""
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{homeserver_url}/_matrix/client/v3{path}"
    kwargs.setdefault('timeout', 10.0)
    kwargs.setdefault('headers', {})
    kwargs['headers'].update(headers)
    return getattr(httpx, method.lower())(url, **kwargs)


def _bot_login_worker(client_id: int, access_token: str, room_id: str, config):
    """Background thread: monitors Matrix room for QR code from bridge bot after !wa login."""
    session = _login_sessions.get(client_id)
    if not session:
        return

    hs = config.homeserver_url
    since = None

    try:
        for _ in range(120):  # up to ~4 minutes
            if session.get('status') not in ('qr_pending',):
                break
            time.sleep(2)

            try:
                # Sync to get new messages
                params = {"filter": json.dumps({
                    "room": {"rooms": [room_id], "timeline": {"limit": 5}},
                    "presence": {"types": []},
                }), "timeout": "3000"}
                if since:
                    params["since"] = since

                resp = _matrix_request(access_token, hs, "GET", "/sync", params=params, timeout=10.0)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                since = data.get("next_batch", since)

                # Check room events
                room_data = data.get("rooms", {}).get("join", {}).get(room_id, {})
                events = room_data.get("timeline", {}).get("events", [])

                for event in events:
                    if event.get("type") != "m.room.message":
                        continue
                    content = event.get("content", {})
                    body = content.get("body", "")

                    # Bridge sends QR as text content
                    if "Successfully logged in" in body or "logged in as" in body.lower():
                        session['status'] = 'connected'
                        # Try to extract phone from message
                        import re
                        phone_match = re.search(r'\+?\d{10,15}', body)
                        session['phone'] = phone_match.group(0) if phone_match else ''
                        _update_client_connected(client_id, session['phone'])
                        return

                    # Check for QR code (sent as image or as text)
                    if content.get("msgtype") == "m.image" and "qr" in body.lower():
                        # QR as image — get mxc URL
                        mxc = content.get("url", "")
                        session['qr_mxc'] = mxc
                    elif "qr" in body.lower() and len(body) > 50:
                        # QR data as text
                        session['qr'] = body.strip()

                    # Check for errors
                    if "error" in body.lower() or "failed" in body.lower():
                        if "login" in body.lower():
                            session['status'] = 'error'
                            session['error'] = body[:200]
                            return

            except Exception as e:
                logger.debug(f"Bot login poll error for client {client_id}: {e}")
                continue

        if session.get('status') == 'qr_pending':
            session['status'] = 'error'
            session['error'] = 'Login timed out'

    except Exception as e:
        session['status'] = 'error'
        session['error'] = f"Bot login failed: {e}"
        logger.error(f"Bot login failed for client {client_id}: {e}")


def _update_client_connected(client_id: int, phone: str):
    """Update client DB record after successful WhatsApp connection."""
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
    except Exception as e:
        logger.error(f"Failed to update client {client_id} status: {e}")


def _get_or_create_bot_dm(access_token: str, homeserver_url: str, bot_user_id: str) -> str:
    """Find or create a DM room with the bridge bot."""
    # Check existing DMs
    resp = _matrix_request(access_token, homeserver_url, "GET", "/joined_rooms")
    if resp.status_code == 200:
        for room_id in resp.json().get("joined_rooms", []):
            # Check room members
            members_resp = _matrix_request(access_token, homeserver_url, "GET", f"/rooms/{room_id}/members")
            if members_resp.status_code == 200:
                member_ids = [e["state_key"] for e in members_resp.json().get("chunk", [])
                              if e.get("content", {}).get("membership") == "join"]
                if bot_user_id in member_ids and len(member_ids) <= 2:
                    return room_id

    # Create new DM room
    resp = _matrix_request(access_token, homeserver_url, "POST", "/createRoom", json={
        "invite": [bot_user_id],
        "is_direct": True,
        "preset": "trusted_private_chat",
    })
    if resp.status_code != 200:
        raise WhatsAppBridgeError(f"Failed to create DM room with bridge bot: {resp.text}")

    return resp.json()["room_id"]


def start_whatsapp_login(client) -> dict:
    """
    Start WhatsApp login via bridge bot DM (megabridge approach).
    Creates a DM room with the bridge bot, sends !wa login command,
    then monitors for QR code response.
    """
    config = _get_config()

    # Ensure Matrix user exists
    user_id, access_token = create_matrix_user(client)

    bot_user_id = f"@whatsappbot:{config.homeserver_domain}"
    hs = config.homeserver_url

    # Get or create DM room with bridge bot
    room_id = _get_or_create_bot_dm(access_token, hs, bot_user_id)
    logger.info(f"Using bot DM room {room_id} for client {client.id}")

    # Send !wa login command
    import uuid
    txn_id = str(uuid.uuid4())
    resp = _matrix_request(access_token, hs, "PUT",
        f"/rooms/{room_id}/send/m.room.message/{txn_id}",
        json={"msgtype": "m.text", "body": "login"},
    )
    if resp.status_code not in (200, 201):
        raise WhatsAppBridgeError(f"Failed to send login command: {resp.status_code} {resp.text}")

    logger.info(f"Sent login command in room {room_id} for client {client.id}")

    # Initialize session
    session = {
        'qr': '',
        'status': 'qr_pending',
        'phone': '',
        'error': '',
        'room_id': room_id,
    }
    _login_sessions[client.id] = session

    # Wait briefly for initial response
    time.sleep(3)

    # Start background polling for bot response
    t = threading.Thread(
        target=_bot_login_worker,
        args=(client.id, access_token, room_id, config),
        daemon=True,
    )
    t.start()

    # Update client status
    client.whatsapp_bridge_status = 'qr_pending'
    client.whatsapp_bridge_error = ''
    client.save(update_fields=['whatsapp_bridge_status', 'whatsapp_bridge_error'])

    return {
        'login_id': str(client.id),
        'qr': session.get('qr', ''),
        'status': 'qr_pending',
    }


def check_login_status(client, login_id: str) -> dict:
    """
    Check login status from in-memory session (fed by polling background thread).
    """
    session = _login_sessions.get(client.id)
    if not session:
        return {'status': 'error', 'error': 'No active login session'}

    status = session.get('status', 'unknown')

    if status == 'connected':
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
    Disconnect WhatsApp via provisioning v3 API.
    """
    config = _get_config()

    if not client.whatsapp_bridge_matrix_user_id:
        return False

    # Try with Matrix access token first, fallback to shared secret
    access_token = client.whatsapp_bridge_matrix_access_token
    if access_token:
        headers = _provision_headers(access_token)
    else:
        headers = _provision_headers_secret(config)

    base_url = f"{config.provisioning_url}/_matrix/provision/v3"

    try:
        # Get active logins
        resp = httpx.get(f"{base_url}/logins", headers=headers, timeout=10.0)
        if resp.status_code == 200:
            logins = resp.json().get('login_ids', [])
            for login_id in logins:
                httpx.post(
                    f"{base_url}/logins/{login_id}/logout",
                    headers=headers,
                    timeout=10.0,
                )
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
    Check actual WhatsApp connection status via provisioning v3 API.
    """
    config = _get_config()

    if not client.whatsapp_bridge_matrix_user_id:
        return {'status': 'disconnected'}

    access_token = client.whatsapp_bridge_matrix_access_token
    if not access_token:
        return {'status': 'unknown', 'error': 'No Matrix access token'}

    headers = _provision_headers(access_token)
    base_url = f"{config.provisioning_url}/_matrix/provision/v3"

    try:
        resp = httpx.get(f"{base_url}/logins", headers=headers, timeout=10.0)
        if resp.status_code == 200:
            logins = resp.json().get('login_ids', [])
            if logins:
                return {
                    'status': 'connected',
                    'phone': client.whatsapp_bridge_phone,
                }
        return {'status': 'disconnected'}
    except Exception as e:
        logger.error(f"Connection status check failed: {e}")
        return {'status': 'unknown', 'error': str(e)}
