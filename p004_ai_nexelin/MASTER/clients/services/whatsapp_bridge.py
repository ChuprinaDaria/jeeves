"""
Service layer for WhatsApp Bridge (mautrix-whatsapp) integration.
Handles Matrix user creation, WhatsApp login via provisioning API, and status checks.
"""
import hashlib
import hmac
import logging

import httpx

from MASTER.clients.models import WhatsAppBridgeConfig

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


def start_whatsapp_login(client) -> dict:
    """
    Start WhatsApp login via mautrix-whatsapp provisioning API.
    Returns dict with login_id and qr code data.
    """
    config = _get_config()

    # Ensure Matrix user exists
    user_id, _ = create_matrix_user(client)

    # Call provisioning API to start login
    headers = {
        "Authorization": f"Bearer {config.provisioning_secret}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(
        f"{config.provisioning_url}/_matrix/provision/v2/login",
        json={"user_id": user_id},
        headers=headers,
        timeout=15.0,
    )
    if resp.status_code != 200:
        raise WhatsAppBridgeError(f"Provisioning login failed: {resp.status_code} {resp.text}")

    data = resp.json()

    # Update client status
    client.whatsapp_bridge_status = 'qr_pending'
    client.whatsapp_bridge_error = ''
    client.save(update_fields=['whatsapp_bridge_status', 'whatsapp_bridge_error'])

    return {
        'login_id': data.get('login_id', ''),
        'qr': data.get('qr', ''),
        'status': 'qr_pending',
    }


def check_login_status(client, login_id: str) -> dict:
    """
    Poll mautrix-whatsapp provisioning API for login status.
    Returns current status with optional phone number on success.
    """
    config = _get_config()
    headers = {
        "Authorization": f"Bearer {config.provisioning_secret}",
    }
    resp = httpx.get(
        f"{config.provisioning_url}/_matrix/provision/v2/login/{login_id}",
        headers=headers,
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise WhatsAppBridgeError(f"Login status check failed: {resp.status_code}")

    data = resp.json()
    status = data.get('status', 'unknown')

    if status == 'success':
        from django.utils import timezone
        phone = data.get('phone', '')
        client.whatsapp_bridge_status = 'connected'
        client.whatsapp_bridge_phone = phone
        client.whatsapp_bridge_connected_at = timezone.now()
        client.whatsapp_bridge_error = ''
        client.save(update_fields=[
            'whatsapp_bridge_status', 'whatsapp_bridge_phone',
            'whatsapp_bridge_connected_at', 'whatsapp_bridge_error',
        ])
        return {'status': 'connected', 'phone': phone}

    elif status in ('cancelled', 'failed', 'error'):
        error_msg = data.get('error', 'Login failed or was cancelled')
        client.whatsapp_bridge_status = 'error'
        client.whatsapp_bridge_error = error_msg
        client.save(update_fields=['whatsapp_bridge_status', 'whatsapp_bridge_error'])
        return {'status': 'error', 'error': error_msg}

    # Still pending — may have new QR code
    return {
        'status': 'qr_pending',
        'qr': data.get('qr', ''),
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
