"""
Tests for multi-bridge integration: BridgeMessageView auth, BridgeService, MCP bridge_tools.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from asgiref.sync import async_to_sync
from django.test import override_settings
from rest_framework.test import APIClient

from MASTER.clients.models import Client
from MASTER.clients.models_bridge import BridgeConfig, ClientBridgeConnection
from MASTER.clients.services.bridge_service import BridgeService, BridgeServiceError
from MASTER.tools.models import ToolCard, ToolConnection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**kwargs):
    """Create a minimal Client for testing."""
    defaults = {
        'user': 'testuser',
        'company_name': 'Test GmbH',
        'tag': kwargs.pop('tag', 'test-client'),
    }
    defaults.update(kwargs)
    return Client.objects.create(**defaults)


def _make_bridge_config(bridge_type='whatsapp', auth_flow='qr_code', **kwargs):
    defaults = {
        'bridge_type': bridge_type,
        'is_enabled': True,
        'provisioning_url': 'https://bridge.test/api',
        'provisioning_secret': 'secret-123',
        'bot_username': '@wabot:test.local',
        'auth_flow': auth_flow,
        'display_name': 'WhatsApp',
        'icon': 'whatsapp',
        'popup_url': 'https://web.whatsapp.com',
        'cookie_domains': ['.whatsapp.com'],
        'required_cookies': ['WABrowserId'],
    }
    defaults.update(kwargs)
    return BridgeConfig.objects.create(**defaults)


def _make_tool_card(slug='whatsapp', **kwargs):
    defaults = {
        'name': 'WhatsApp',
        'slug': slug,
        'tagline': 'WhatsApp bridge',
        'description': 'WhatsApp bridge tool',
        'icon': 'whatsapp',
        'color': '#25D366',
        'category': 'communication',
        'transport_type': 'builtin',
        'auth_type': 'qr_code',
    }
    defaults.update(kwargs)
    return ToolCard.objects.create(**defaults)


def _make_httpx_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data)
    return resp


def _mock_httpx_client(get_response=None, post_response=None):
    """Build a mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    if get_response is not None:
        mock_client.get = AsyncMock(return_value=get_response)
    if post_response is not None:
        mock_client.post = AsyncMock(return_value=post_response)
    return mock_client


# ===========================================================================
# 1. BridgeMessageView auth validation
# ===========================================================================

@pytest.mark.django_db
class TestBridgeMessageViewAuth:
    """BridgeMessageView must reject requests without valid X-Service-Token."""

    URL = '/api/clients/bridges/message/'

    def _post(self, data=None, headers=None):
        api = APIClient()
        return api.post(self.URL, data=data or {}, format='json', **(headers or {}))

    @override_settings(INTEGRATION_SERVICE_TOKEN='valid-token-123')
    def test_missing_token_returns_403(self):
        resp = self._post(data={'client_id': 1, 'bridge_type': 'whatsapp'})
        assert resp.status_code == 403

    @override_settings(INTEGRATION_SERVICE_TOKEN='valid-token-123')
    def test_wrong_token_returns_403(self):
        resp = self._post(
            data={'client_id': 1, 'bridge_type': 'whatsapp'},
            headers={'HTTP_X_SERVICE_TOKEN': 'wrong-token'},
        )
        assert resp.status_code == 403

    @override_settings(INTEGRATION_SERVICE_TOKEN='')
    def test_token_not_configured_returns_503(self):
        resp = self._post(
            data={'client_id': 1, 'bridge_type': 'whatsapp'},
            headers={'HTTP_X_SERVICE_TOKEN': 'anything'},
        )
        assert resp.status_code == 503

    @override_settings(INTEGRATION_SERVICE_TOKEN='valid-token-123')
    def test_valid_token_passes_auth(self):
        """With valid token, auth passes — we get 400 (missing client_id) not 403."""
        resp = self._post(
            data={'bridge_type': 'whatsapp'},  # no client_id
            headers={'HTTP_X_SERVICE_TOKEN': 'valid-token-123'},
        )
        assert resp.status_code == 400

    @override_settings(INTEGRATION_SERVICE_TOKEN='valid-token-123')
    def test_valid_token_client_not_found_returns_404(self):
        resp = self._post(
            data={'client_id': 99999, 'bridge_type': 'whatsapp'},
            headers={'HTTP_X_SERVICE_TOKEN': 'valid-token-123'},
        )
        assert resp.status_code == 404


# ===========================================================================
# 2. BridgeService.start_login (mock httpx)
# ===========================================================================

@pytest.mark.django_db
class TestBridgeServiceStartLogin:
    """BridgeService.start_login with mocked httpx calls."""

    def test_cookies_flow_returns_popup_url(self):
        client = _make_client(tag='cookies-client')
        config = _make_bridge_config(
            bridge_type='meta-facebook',
            auth_flow='cookies',
            display_name='Facebook',
            popup_url='https://facebook.com/login',
            cookie_domains=['.facebook.com'],
            required_cookies=['c_user', 'xs'],
        )
        # Pre-create connection with matrix creds so _ensure_matrix_user skips
        ClientBridgeConnection.objects.create(
            client=client,
            bridge_config=config,
            matrix_user_id='@test:local',
            matrix_access_token='syt_fake',
            status='disconnected',
        )

        flows_resp = _make_httpx_response(200, [{'id': 'flow-1'}])
        step_resp = _make_httpx_response(200, {
            'type': 'cookies',
            'process_id': 'proc-1',
            'step_id': 'step-1',
        })
        mock_http = _mock_httpx_client(get_response=flows_resp, post_response=step_resp)

        with patch('MASTER.clients.services.bridge_service.httpx.AsyncClient', return_value=mock_http):
            service = BridgeService()
            result = async_to_sync(service.start_login)(client, 'meta-facebook')

        assert result['auth_flow'] == 'cookies'
        assert result['popup_url'] == 'https://facebook.com/login'
        assert result['process_id'] == 'proc-1'
        assert result['step_id'] == 'step-1'
        assert result['bridge_type'] == 'meta-facebook'

    def test_qr_code_flow_returns_qr_data(self):
        client = _make_client(tag='qr-client')
        config = _make_bridge_config(
            bridge_type='whatsapp',
            auth_flow='qr_code',
        )
        ClientBridgeConnection.objects.create(
            client=client,
            bridge_config=config,
            matrix_user_id='@qrtest:local',
            matrix_access_token='syt_qr_fake',
            status='disconnected',
        )

        flows_resp = _make_httpx_response(200, [{'id': 'wa-flow-1'}])
        step_resp = _make_httpx_response(200, {
            'type': 'display_and_wait',
            'process_id': 'qr-proc',
            'step_id': 'qr-step',
            'display_and_wait': {'data': 'qr-image-data-base64'},
        })
        mock_http = _mock_httpx_client(get_response=flows_resp, post_response=step_resp)

        with patch('MASTER.clients.services.bridge_service.httpx.AsyncClient', return_value=mock_http):
            service = BridgeService()
            result = async_to_sync(service.start_login)(client, 'whatsapp')

        assert result['auth_flow'] == 'qr_code'
        assert result['qr'] == 'qr-image-data-base64'
        assert result['process_id'] == 'qr-proc'

    def test_start_login_disabled_bridge_raises(self):
        client = _make_client(tag='disabled-client')
        _make_bridge_config(
            bridge_type='linkedin',
            is_enabled=False,
            display_name='LinkedIn',
        )

        service = BridgeService()
        with pytest.raises(BridgeServiceError, match='Bridge disabled'):
            async_to_sync(service.start_login)(client, 'linkedin')

    def test_start_login_missing_config_raises(self):
        client = _make_client(tag='no-config-client')

        service = BridgeService()
        with pytest.raises(BridgeServiceError, match='Bridge config not found'):
            async_to_sync(service.start_login)(client, 'telegram')

    def test_start_login_saves_pending_status(self):
        """After start_login, connection status should be 'pending'."""
        client = _make_client(tag='pending-status-client')
        config = _make_bridge_config(bridge_type='whatsapp-pending')
        ClientBridgeConnection.objects.create(
            client=client,
            bridge_config=config,
            matrix_user_id='@pending:local',
            matrix_access_token='syt_pending',
            status='disconnected',
        )

        flows_resp = _make_httpx_response(200, [{'id': 'f1'}])
        step_resp = _make_httpx_response(200, {
            'type': 'display_and_wait',
            'process_id': 'p-pending',
            'step_id': 's-pending',
            'display_and_wait': {'data': 'qr'},
        })
        mock_http = _mock_httpx_client(get_response=flows_resp, post_response=step_resp)

        with patch('MASTER.clients.services.bridge_service.httpx.AsyncClient', return_value=mock_http):
            service = BridgeService()
            async_to_sync(service.start_login)(client, 'whatsapp-pending')

        conn = ClientBridgeConnection.objects.get(client=client, bridge_config=config)
        assert conn.status == 'pending'
        assert conn.login_process_id == 'p-pending'
        assert conn.login_step_id == 's-pending'


# ===========================================================================
# 3. MCP bridge_tools
# ===========================================================================

@pytest.mark.django_db
class TestBridgeTools:
    """MCP bridge_tools dispatcher tests."""

    def _fake_mcp_connection(self, client):
        """Fake MCP connection object with .client attribute."""
        conn = MagicMock()
        conn.client = client
        return conn

    def test_bridge_start_connection_dispatches_to_service(self):
        """bridge_start_connection calls BridgeService.start_login."""
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='dispatch-client')
        fake_conn = self._fake_mcp_connection(client)

        mock_result = {
            'auth_flow': 'qr_code',
            'qr': 'data123',
            'process_id': 'p1',
            'step_id': 's1',
        }

        with patch(
            'MASTER.mcp_hub.builtin.bridge_tools.bridge_service.start_login',
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = async_to_sync(bridge_tools)(fake_conn, 'bridge_start_connection', bridge_type='whatsapp')

        assert result['type'] == 'qr_code'
        assert result['qr'] == 'data123'
        assert result['bridge_type'] == 'whatsapp'

    def test_bridge_start_connection_cookies_flow(self):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='cookies-dispatch')
        fake_conn = self._fake_mcp_connection(client)

        mock_result = {
            'auth_flow': 'cookies',
            'popup_url': 'https://facebook.com/login',
            'cookie_domains': ['.facebook.com'],
            'required_cookies': ['c_user'],
            'process_id': 'p2',
            'step_id': 's2',
        }

        with patch(
            'MASTER.mcp_hub.builtin.bridge_tools.bridge_service.start_login',
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = async_to_sync(bridge_tools)(fake_conn, 'bridge_start_connection', bridge_type='meta-facebook')

        assert result['type'] == 'auth_popup'
        assert result['auth_flow'] == 'cookies'
        assert result['popup_url'] == 'https://facebook.com/login'

    def test_canvas_add_tool_connection_creates_records(self):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='canvas-add-client')
        _make_tool_card(slug='whatsapp')
        fake_conn = self._fake_mcp_connection(client)

        result = async_to_sync(bridge_tools)(
            fake_conn,
            'canvas_add_tool_connection',
            bridge_type='whatsapp',
            targets=['assistant', 'manager'],
        )

        assert result['type'] == 'connection_created'
        assert result['targets'] == ['assistant', 'manager']
        assert len(result['nodes_created']) == 2

        # Verify DB records
        count = ToolConnection.objects.filter(client=client).count()
        assert count == 2

    def test_canvas_add_tool_connection_uses_default_scopes(self):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='canvas-default-scopes')
        _make_tool_card(slug='meta-facebook')
        _make_bridge_config(
            bridge_type='meta-facebook',
            display_name='Facebook',
            default_scopes=['assistant', 'leads'],
        )
        fake_conn = self._fake_mcp_connection(client)

        result = async_to_sync(bridge_tools)(
            fake_conn,
            'canvas_add_tool_connection',
            bridge_type='meta-facebook',
        )

        assert result['targets'] == ['assistant', 'leads']

    def test_canvas_list_connections_returns_data(self):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='canvas-list-client')
        tool_card = _make_tool_card(slug='whatsapp-list')
        ToolConnection.objects.create(
            client=client,
            tool_card=tool_card,
            status='connected',
            target='assistant',
        )
        fake_conn = self._fake_mcp_connection(client)

        with patch(
            'MASTER.mcp_hub.builtin.bridge_tools.bridge_service.list_connections',
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = async_to_sync(bridge_tools)(fake_conn, 'canvas_list_connections')

        assert 'canvas_connections' in result
        assert len(result['canvas_connections']) == 1
        assert result['canvas_connections'][0]['tool_card__slug'] == 'whatsapp-list'

    def test_unknown_tool_returns_error(self):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='unknown-tool-client')
        fake_conn = self._fake_mcp_connection(client)

        result = async_to_sync(bridge_tools)(fake_conn, 'nonexistent_tool')
        assert 'error' in result
        assert 'Unknown tool' in result['error']

    def test_bridge_start_connection_missing_type_returns_error(self):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        client = _make_client(tag='missing-type-client')
        fake_conn = self._fake_mcp_connection(client)

        result = async_to_sync(bridge_tools)(fake_conn, 'bridge_start_connection')
        assert 'error' in result
        assert 'bridge_type is required' in result['error']
