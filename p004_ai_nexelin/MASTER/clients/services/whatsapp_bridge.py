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


def _poll_login_worker(client_id: int, login_process_id: str, access_token: str, config):
    """Background thread: polls mautrix-whatsapp v3 provisioning API for login status."""
    session = _login_sessions.get(client_id)
    if not session:
        return

    headers = _provision_headers(access_token)
    base_url = f"{config.provisioning_url}/_matrix/provision/v3"

    try:
        for _ in range(120):  # up to ~4 minutes
            if session.get('status') not in ('qr_pending',):
                break
            time.sleep(2)

            try:
                resp = httpx.get(
                    f"{base_url}/login/step/{login_process_id}",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    # Try alternative: check logins list
                    resp2 = httpx.get(f"{base_url}/logins", headers=headers, timeout=5.0)
                    if resp2.status_code == 200:
                        logins = resp2.json().get('login_ids', [])
                        if logins:
                            session['status'] = 'connected'
                            session['phone'] = ''
                            _update_client_connected(client_id, '')
                            break
                    continue

                data = resp.json()
                step_type = data.get('step_type', data.get('type', ''))

                if step_type == 'display_and_wait' and data.get('display_and_wait', {}).get('data'):
                    # QR code data
                    qr_data = data['display_and_wait']['data']
                    session['qr'] = qr_data
                elif step_type == 'complete' or data.get('complete'):
                    session['status'] = 'connected'
                    phone = data.get('complete', {}).get('phone', '')
                    session['phone'] = phone
                    _update_client_connected(client_id, phone)
                    break

            except Exception as e:
                logger.debug(f"Login poll error for client {client_id}: {e}")
                continue

        # If still pending after timeout
        if session.get('status') == 'qr_pending':
            session['status'] = 'error'
            session['error'] = 'Login timed out'

    except Exception as e:
        session['status'] = 'error'
        session['error'] = f"Login polling failed: {e}"
        logger.error(f"Login poll failed for client {client_id}: {e}")


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


def start_whatsapp_login(client) -> dict:
    """
    Start WhatsApp login via mautrix-whatsapp v3 provisioning API.
    Uses HTTP POST to start login, then polls for QR code and status.
    Returns initial status; frontend polls check_login_status for updates.
    """
    config = _get_config()

    # Ensure Matrix user exists
    user_id, access_token = create_matrix_user(client)

    headers = _provision_headers(access_token)
    base_url = f"{config.provisioning_url}/_matrix/provision/v3"

    # Start login via v3 API
    resp = httpx.post(
        f"{base_url}/login/start",
        headers=headers,
        json={"flow_id": "qr"},
        timeout=15.0,
    )

    if resp.status_code != 200:
        raise WhatsAppBridgeError(f"Failed to start login: {resp.status_code} {resp.text}")

    data = resp.json()
    login_process_id = data.get('login_process_id', data.get('id', ''))
    logger.info(f"Started WhatsApp login for client {client.id}, process_id={login_process_id}")

    # Check if we already have a QR step
    qr_data = ''
    step_type = data.get('step_type', data.get('type', ''))
    if step_type == 'display_and_wait':
        qr_data = data.get('display_and_wait', {}).get('data', '')

    # If we need to submit a step first (some flows require it)
    next_step = data.get('next_step', '')
    if next_step and not qr_data:
        step_resp = httpx.post(
            f"{base_url}/login/step/{login_process_id}",
            headers=headers,
            json={"step_type": next_step},
            timeout=15.0,
        )
        if step_resp.status_code == 200:
            step_data = step_resp.json()
            step_type = step_data.get('step_type', '')
            if step_type == 'display_and_wait':
                qr_data = step_data.get('display_and_wait', {}).get('data', '')

    # Initialize session
    session = {
        'qr': qr_data,
        'status': 'qr_pending',
        'phone': '',
        'error': '',
        'login_process_id': login_process_id,
    }
    _login_sessions[client.id] = session

    # Start polling in background thread
    t = threading.Thread(
        target=_poll_login_worker,
        args=(client.id, login_process_id, access_token, config),
        daemon=True,
    )
    t.start()

    # Update client status
    client.whatsapp_bridge_status = 'qr_pending'
    client.whatsapp_bridge_error = ''
    client.save(update_fields=['whatsapp_bridge_status', 'whatsapp_bridge_error'])

    return {
        'login_id': str(client.id),
        'qr': qr_data,
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
