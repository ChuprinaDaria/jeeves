import logging
import httpx
from asgiref.sync import sync_to_async
from django.utils import timezone
from MASTER.clients.models_bridge import BridgeConfig, ClientBridgeConnection

logger = logging.getLogger(__name__)


class BridgeServiceError(Exception):
    pass


class BridgeService:
    """Universal bridge service operating through mautrix Provisioning API v3."""

    def _get_config(self, bridge_type: str) -> BridgeConfig:
        """Get BridgeConfig or raise BridgeServiceError."""
        try:
            config = BridgeConfig.objects.get(bridge_type=bridge_type)
        except BridgeConfig.DoesNotExist:
            raise BridgeServiceError(f'Bridge config not found: {bridge_type}')
        if not config.is_enabled:
            raise BridgeServiceError(f'Bridge disabled: {bridge_type}')
        return config

    def _provision_headers(self, matrix_access_token: str = '', config: BridgeConfig = None) -> dict:
        """Build auth headers for mautrix provisioning API.

        API v3 uses Matrix bearer token. If no token available, falls back
        to provisioning shared secret (used in some admin-level endpoints).
        """
        headers = {'Content-Type': 'application/json'}
        if matrix_access_token:
            headers['Authorization'] = f'Bearer {matrix_access_token}'
        elif config and config.provisioning_secret:
            headers['Authorization'] = f'Bearer {config.provisioning_secret}'
        # NPM reverse proxy routes by Host header
        if config and config.provisioning_url and '195.201.202.162' in config.provisioning_url:
            headers['Host'] = 'matrix.nexelin.com'
        return headers

    def _provision_url(self, config: BridgeConfig, path: str, user_id: str = '') -> str:
        base = config.provisioning_url.rstrip('/')
        url = f'{base}/_matrix/provision{path}'
        if user_id:
            sep = '&' if '?' in url else '?'
            url = f'{url}{sep}user_id={user_id}'
        return url

    async def _get_or_create_connection(self, client, config: BridgeConfig) -> ClientBridgeConnection:
        conn, created = await sync_to_async(
            ClientBridgeConnection.objects.get_or_create
        )(
            client=client,
            bridge_config=config,
            defaults={'status': 'disconnected'},
        )
        return conn

    async def _ensure_matrix_user(self, client, conn: ClientBridgeConnection):
        """Create or reuse a dedicated Matrix user for this client.

        Checks existing credentials on the connection first, then falls back
        to any existing Matrix user on the Client model (from WhatsApp bridge),
        and finally creates a new one via the whatsapp_bridge utility.
        """
        if conn.matrix_user_id and conn.matrix_access_token:
            return

        # Check if another bridge connection already has Matrix credentials
        existing = await sync_to_async(
            lambda: ClientBridgeConnection.objects.filter(
                client=client,
            ).exclude(
                matrix_user_id='',
            ).exclude(
                matrix_access_token='',
            ).first()
        )()
        if existing:
            conn.matrix_user_id = existing.matrix_user_id
            conn.matrix_access_token = existing.matrix_access_token
            await sync_to_async(conn.save)(
                update_fields=['matrix_user_id', 'matrix_access_token']
            )
            return

        # Check legacy WhatsApp fields on Client model
        wa_user = await sync_to_async(lambda: client.whatsapp_bridge_matrix_user_id)()
        wa_token = await sync_to_async(lambda: client.whatsapp_bridge_matrix_access_token)()
        if wa_user and wa_token:
            conn.matrix_user_id = wa_user
            conn.matrix_access_token = wa_token
            await sync_to_async(conn.save)(
                update_fields=['matrix_user_id', 'matrix_access_token']
            )
            return

        # Last resort: create via whatsapp_bridge utility (will be extracted later)
        from MASTER.clients.services.whatsapp_bridge import create_matrix_user
        user_id, access_token = await sync_to_async(create_matrix_user)(client)
        conn.matrix_user_id = user_id
        conn.matrix_access_token = access_token
        await sync_to_async(conn.save)(
            update_fields=['matrix_user_id', 'matrix_access_token']
        )

    async def start_login(self, client, bridge_type: str) -> dict:
        """Initiate login flow. Returns auth_flow type + data needed by frontend."""
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)
        await self._ensure_matrix_user(client, conn)

        # Get available login flows
        uid = conn.matrix_user_id
        url = self._provision_url(config, '/v3/login/flows', user_id=uid)
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(url, headers=self._provision_headers(conn.matrix_access_token, config))
            if resp.status_code != 200:
                raise BridgeServiceError(f'Failed to get login flows: {resp.status_code} {resp.text}')
            flows = resp.json()

        if not flows:
            raise BridgeServiceError(f'No login flows available for {bridge_type}')

        # Start first available flow
        flow_id = flows[0].get('id', flows[0].get('flow_id', ''))
        url = self._provision_url(config, f'/v3/login/start/{flow_id}', user_id=uid)
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(url, headers=self._provision_headers(conn.matrix_access_token, config))
            if resp.status_code != 200:
                raise BridgeServiceError(f'Failed to start login: {resp.status_code} {resp.text}')
            step = resp.json()

        step_type = step.get('type', '')
        process_id = step.get('process_id', '')
        step_id = step.get('step_id', '')

        conn.login_process_id = process_id
        conn.login_step_id = step_id
        conn.login_flow_id = flow_id
        conn.status = 'pending'
        await sync_to_async(conn.save)(
            update_fields=['login_process_id', 'login_step_id', 'login_flow_id', 'status']
        )

        if step_type == 'cookies':
            return {
                'auth_flow': 'cookies',
                'popup_url': config.popup_url,
                'cookie_domains': config.cookie_domains,
                'required_cookies': config.required_cookies,
                'process_id': process_id,
                'step_id': step_id,
                'bridge_type': bridge_type,
            }
        elif step_type == 'display_and_wait':
            qr_data = step.get('display_and_wait', {}).get('data', '')
            return {
                'auth_flow': 'qr_code',
                'qr': qr_data,
                'process_id': process_id,
                'step_id': step_id,
                'bridge_type': bridge_type,
            }
        elif step_type == 'user_input':
            return {
                'auth_flow': 'user_input',
                'fields': step.get('user_input', {}).get('fields', []),
                'process_id': process_id,
                'step_id': step_id,
                'bridge_type': bridge_type,
            }
        else:
            raise BridgeServiceError(f'Unknown login step type: {step_type}')

    async def submit_cookies(self, client, bridge_type: str, cookies: dict) -> dict:
        """Submit browser cookies to complete login."""
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)

        if not conn.login_process_id or not conn.login_step_id:
            raise BridgeServiceError('No active login session. Call start_login first.')

        url = self._provision_url(
            config,
            f'/v3/login/step/{conn.login_process_id}/{conn.login_step_id}/cookies',
            user_id=conn.matrix_user_id,
        )
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                url,
                headers=self._provision_headers(conn.matrix_access_token, config),
                json={'cookies': cookies},
            )

        if resp.status_code != 200:
            error_msg = resp.json().get('error', resp.text)
            await sync_to_async(conn.mark_error)(error_msg)
            raise BridgeServiceError(f'Cookie submission failed: {error_msg}')

        result = resp.json()
        step_type = result.get('type', '')

        if step_type == 'complete':
            remote_id = result.get('user_login_id', '')
            await sync_to_async(conn.mark_connected)(remote_id=remote_id)
            return {'status': 'connected', 'remote_id': remote_id}
        elif step_type == 'user_input':
            conn.login_step_id = result.get('step_id', '')
            await sync_to_async(conn.save)(update_fields=['login_step_id'])
            return {
                'status': 'pending',
                'auth_flow': 'user_input',
                'fields': result.get('user_input', {}).get('fields', []),
                'process_id': conn.login_process_id,
                'step_id': conn.login_step_id,
            }
        else:
            raise BridgeServiceError(f'Unexpected step after cookies: {step_type}')

    async def check_status(self, client, bridge_type: str) -> dict:
        """Check connection status via provisioning API.

        Syncs local status with the bridge's actual state.
        """
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)

        if not conn.matrix_access_token:
            return {'status': conn.status, 'bridge_type': bridge_type}

        url = self._provision_url(config, '/v3/logins', user_id=conn.matrix_user_id)
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(url, headers=self._provision_headers(conn.matrix_access_token, config))
            if resp.status_code == 200:
                logins = resp.json()
                if logins:
                    # Sync local state if bridge reports connected
                    if conn.status != 'connected':
                        await sync_to_async(conn.mark_connected)(remote_id=conn.remote_id)
                    return {
                        'status': 'connected',
                        'bridge_type': bridge_type,
                        'remote_id': conn.remote_id,
                        'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
                    }
                else:
                    # Bridge has no active logins — mark expired if was connected
                    if conn.status == 'connected':
                        await sync_to_async(conn.mark_expired)()
                    return {
                        'status': 'expired' if conn.status == 'connected' else conn.status,
                        'bridge_type': bridge_type,
                        'remote_id': conn.remote_id,
                    }
        except Exception as e:
            logger.warning(f'Bridge status check failed for {bridge_type}: {e}')

        return {
            'status': conn.status,
            'bridge_type': bridge_type,
            'remote_id': conn.remote_id,
            'error': conn.error,
        }

    async def logout(self, client, bridge_type: str) -> dict:
        """Disconnect bridge."""
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)

        if conn.matrix_access_token:
            url = self._provision_url(config, '/v3/logout/all', user_id=conn.matrix_user_id)
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    await http.post(url, headers=self._provision_headers(conn.matrix_access_token, config))
            except Exception as e:
                logger.warning(f'Bridge logout API failed for {bridge_type}: {e}')

        await sync_to_async(conn.mark_disconnected)()
        return {'status': 'disconnected', 'bridge_type': bridge_type}

    async def list_connections(self, client) -> list:
        """List all bridge connections for a client."""
        connections = await sync_to_async(list)(
            ClientBridgeConnection.objects.filter(client=client)
            .select_related('bridge_config')
        )
        return [
            {
                'bridge_type': conn.bridge_config.bridge_type,
                'display_name': conn.bridge_config.display_name,
                'status': conn.status,
                'remote_id': conn.remote_id,
                'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
            }
            for conn in connections
        ]


bridge_service = BridgeService()
