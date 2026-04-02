# Multi-Bridge + Oleg Dynamic Connections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Meta (Facebook Messenger + Instagram DM) and LinkedIn bridges via mautrix, with Oleg controlling connections and canvas nodes through MCP tools in real-time chat.

**Architecture:** Universal BridgeService operating through mautrix Provisioning API v3 (megabridge spec). Cookie-based auth via existing Chrome extension. Oleg uses builtin MCP tools to start auth, check status, and manipulate canvas. Frontend renders rich message cards (auth popups, QR codes, target selectors) inline in chat. Real-time canvas updates via WebSocket events.

**Tech Stack:** Django 5.x, mautrix Go bridges (Docker), Chrome Extension Manifest V3, React 18, SSE for chat streaming, WebSocket for canvas events.

**Spec:** `docs/superpowers/specs/2026-04-02-multi-bridge-oleg-dynamic-connections-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `p004_ai_nexelin/MASTER/clients/models_bridge.py` | `BridgeConfig` and `ClientBridgeConnection` models |
| `p004_ai_nexelin/MASTER/clients/services/bridge_service.py` | Universal bridge service (provisioning API v3) |
| `p004_ai_nexelin/MASTER/clients/views_bridge.py` | Universal bridge API endpoints |
| `p004_ai_nexelin/MASTER/clients/urls_bridge.py` | URL routing for bridge endpoints |
| `p004_ai_nexelin/MASTER/mcp_hub/builtin/bridge_tools.py` | MCP tools for Oleg (5 tools) |
| `p004_ai_nexelin/MASTER/clients/migrations/0058_bridge_config_models.py` | DB migration |
| `p004_ai_nexelin/MASTER/tools/migrations/0016_seed_meta_linkedin_tools.py` | Seed ToolCard data |
| `matrix-stack/setup-bridges.sh` | Setup script for all bridges |
| `matrix-stack/meta-facebook/config.yaml` | mautrix-meta config (facebook mode) |
| `matrix-stack/meta-instagram/config.yaml` | mautrix-meta config (instagram mode) |
| `matrix-stack/linkedin/config.yaml` | mautrix-linkedin config |
| `nextlen/src/components/sandbox/chat/RichMessageCard.jsx` | Rich message renderer (auth popup, QR, status, target selector) |
| `p004_ai_nexelin/chrome_extension/content/cookie-extractor.js` | Cookie extraction for Meta/LinkedIn |

### Modified Files
| File | Changes |
|------|---------|
| `matrix-stack/docker-compose.yml` | Add 3 new bridge services + DB config |
| `matrix-stack/synapse/homeserver.yaml` | Register new bridge appservices |
| `matrix-stack/setup-whatsapp-bridge.sh` | Extend to handle all bridges |
| `p004_ai_nexelin/MASTER/clients/urls.py` | Include `urls_bridge.py` |
| `p004_ai_nexelin/MASTER/tools/seed_data.py` | Add Meta FB, Meta IG, LinkedIn ToolCards |
| `p004_ai_nexelin/MASTER/mcp_hub/executor.py` | No changes needed (dynamic import works) |
| `p004_ai_nexelin/MASTER/agents/orchestrator.py` | Add bridge tools to assistant scope |
| `nextlen/src/components/sandbox/ChatWindow.jsx` | Render RichMessageCard for typed tool responses |
| `nextlen/src/components/tools/FlowCanvas.jsx` | Listen for WebSocket events, add/remove nodes |
| `nextlen/src/components/tools/ConnectModal.jsx` | Support `cookies` auth_type |
| `p004_ai_nexelin/chrome_extension/manifest.json` | Add cookies permission + host permissions |
| `p004_ai_nexelin/chrome_extension/background/service-worker.js` | Handle cookie extraction messages |
| `services/integration-service/internal/hitl/bridge.go` | Add bridge_type to ConversationMapping |
| `services/integration-service/internal/hitl/orchestrator.go` | Route by bridge_type, universal message endpoint |

---

## Task 1: Infrastructure — Docker Services for New Bridges

**Files:**
- Modify: `matrix-stack/docker-compose.yml:61-117`
- Create: `matrix-stack/meta-facebook/config.yaml`
- Create: `matrix-stack/meta-instagram/config.yaml`
- Create: `matrix-stack/linkedin/config.yaml`
- Modify: `matrix-stack/synapse/homeserver.yaml:122-123`
- Create: `matrix-stack/setup-bridges.sh`

- [ ] **Step 1: Add PostgreSQL databases for new bridges**

In `matrix-stack/docker-compose.yml`, the existing `postgres-mautrix` service (line 61) uses a single DB `mautrix_whatsapp`. Add init script to create additional databases. Replace the postgres-mautrix environment section:

```yaml
  postgres-mautrix:
    image: postgres:16
    container_name: grot-postgres-mautrix
    restart: unless-stopped
    network_mode: host
    environment:
      POSTGRES_USER: mautrix
      POSTGRES_PASSWORD: ${POSTGRES_MAUTRIX_PASSWORD}
      POSTGRES_DB: mautrix_whatsapp
    volumes:
      - postgres-mautrix-data:/var/lib/postgresql/data
      - ./init-mautrix-dbs.sql:/docker-entrypoint-initdb.d/init-extra-dbs.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mautrix"]
      interval: 5s
      timeout: 5s
      retries: 5
```

Create `matrix-stack/init-mautrix-dbs.sql`:

```sql
CREATE DATABASE mautrix_meta_facebook;
CREATE DATABASE mautrix_meta_instagram;
CREATE DATABASE mautrix_linkedin;
```

- [ ] **Step 2: Add mautrix-meta-facebook service**

Append to `matrix-stack/docker-compose.yml` after the mautrix-whatsapp service (after line 117):

```yaml
  mautrix-meta-facebook:
    image: dock.mau.dev/mautrix/meta:latest
    container_name: grot-mautrix-meta-facebook
    restart: unless-stopped
    network_mode: host
    depends_on:
      postgres-mautrix:
        condition: service_healthy
    environment:
      POSTGRES_MAUTRIX_PASSWORD: ${POSTGRES_MAUTRIX_PASSWORD}
    volumes:
      - ./meta-facebook:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:29319/_matrix/provision/v3/whoami || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

- [ ] **Step 3: Add mautrix-meta-instagram service**

Append to `matrix-stack/docker-compose.yml`:

```yaml
  mautrix-meta-instagram:
    image: dock.mau.dev/mautrix/meta:latest
    container_name: grot-mautrix-meta-instagram
    restart: unless-stopped
    network_mode: host
    depends_on:
      postgres-mautrix:
        condition: service_healthy
    environment:
      POSTGRES_MAUTRIX_PASSWORD: ${POSTGRES_MAUTRIX_PASSWORD}
    volumes:
      - ./meta-instagram:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:29320/_matrix/provision/v3/whoami || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

- [ ] **Step 4: Add mautrix-linkedin service**

Append to `matrix-stack/docker-compose.yml`:

```yaml
  mautrix-linkedin:
    image: dock.mau.dev/mautrix/linkedin:latest
    container_name: grot-mautrix-linkedin
    restart: unless-stopped
    network_mode: host
    depends_on:
      postgres-mautrix:
        condition: service_healthy
    environment:
      POSTGRES_MAUTRIX_PASSWORD: ${POSTGRES_MAUTRIX_PASSWORD}
    volumes:
      - ./linkedin:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:29321/_matrix/provision/v3/whoami || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

- [ ] **Step 5: Create mautrix-meta-facebook config**

Create `matrix-stack/meta-facebook/config.yaml`:

```yaml
homeserver:
    address: http://localhost:8008
    domain: grot.de

appservice:
    address: http://localhost:29319
    port: 29319
    database:
        type: postgres
        uri: postgres://mautrix:${POSTGRES_MAUTRIX_PASSWORD}@localhost:5433/mautrix_meta_facebook

meta:
    mode: facebook

bridge:
    permissions:
        "grot.de": user
        "@admin:grot.de": admin
    provisioning:
        shared_secret: generate

logging:
    min_level: info
    writers:
        - type: stdout
          format: pretty-colored
```

- [ ] **Step 6: Create mautrix-meta-instagram config**

Create `matrix-stack/meta-instagram/config.yaml`:

```yaml
homeserver:
    address: http://localhost:8008
    domain: grot.de

appservice:
    address: http://localhost:29320
    port: 29320
    database:
        type: postgres
        uri: postgres://mautrix:${POSTGRES_MAUTRIX_PASSWORD}@localhost:5433/mautrix_meta_instagram

meta:
    mode: instagram

bridge:
    permissions:
        "grot.de": user
        "@admin:grot.de": admin
    provisioning:
        shared_secret: generate

logging:
    min_level: info
    writers:
        - type: stdout
          format: pretty-colored
```

- [ ] **Step 7: Create mautrix-linkedin config**

Create `matrix-stack/linkedin/config.yaml`:

```yaml
homeserver:
    address: http://localhost:8008
    domain: grot.de

appservice:
    address: http://localhost:29321
    port: 29321
    database:
        type: postgres
        uri: postgres://mautrix:${POSTGRES_MAUTRIX_PASSWORD}@localhost:5433/mautrix_linkedin

bridge:
    permissions:
        "grot.de": user
        "@admin:grot.de": admin
    provisioning:
        shared_secret: generate

logging:
    min_level: info
    writers:
        - type: stdout
          format: pretty-colored
```

- [ ] **Step 8: Update Synapse homeserver.yaml**

In `matrix-stack/synapse/homeserver.yaml`, update line 122-123:

```yaml
app_service_config_files:
    - /data/whatsapp-registration.yaml
    - /data/meta-facebook-registration.yaml
    - /data/meta-instagram-registration.yaml
    - /data/linkedin-registration.yaml
```

- [ ] **Step 9: Create setup-bridges.sh**

Create `matrix-stack/setup-bridges.sh`:

```bash
#!/bin/bash
set -e

BRIDGES=("mautrix-whatsapp:whatsapp" "mautrix-meta-facebook:meta-facebook" "mautrix-meta-instagram:meta-instagram" "mautrix-linkedin:linkedin")

for entry in "${BRIDGES[@]}"; do
    IFS=':' read -r container name <<< "$entry"
    SRC="./${container}/registration.yaml"
    DST="./synapse/${name}-registration.yaml"

    if [ ! -f "$SRC" ]; then
        echo "WARNING: $SRC not found. Start $container first to generate it."
        continue
    fi

    cp "$SRC" "$DST"
    echo "Copied $SRC -> $DST"
done

echo ""
echo "Done. Now restart Synapse: docker compose restart synapse"
```

- [ ] **Step 10: Commit infrastructure changes**

```bash
git add matrix-stack/docker-compose.yml matrix-stack/init-mautrix-dbs.sql \
  matrix-stack/meta-facebook/config.yaml matrix-stack/meta-instagram/config.yaml \
  matrix-stack/linkedin/config.yaml matrix-stack/synapse/homeserver.yaml \
  matrix-stack/setup-bridges.sh
git commit -m "infra: add mautrix-meta and mautrix-linkedin bridge containers"
```

---

## Task 2: Backend Models — BridgeConfig + ClientBridgeConnection

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/models_bridge.py`
- Create: `p004_ai_nexelin/MASTER/clients/migrations/0058_bridge_config_models.py`
- Modify: `p004_ai_nexelin/MASTER/clients/models.py` (import in `__init__` if needed)

- [ ] **Step 1: Write tests for BridgeConfig model**

Create `p004_ai_nexelin/MASTER/clients/tests/test_bridge_models.py`:

```python
import pytest
from django.test import TestCase
from MASTER.clients.models_bridge import BridgeConfig, ClientBridgeConnection


class BridgeConfigTest(TestCase):
    def test_create_bridge_config(self):
        config = BridgeConfig.objects.create(
            bridge_type='meta-facebook',
            is_enabled=True,
            provisioning_url='http://localhost:29319',
            provisioning_secret='test-secret',
            bot_username='@facebookbot:grot.de',
            auth_flow='cookies',
            default_scopes=['assistant', 'manager'],
            display_name='Facebook Messenger',
            icon='facebook',
        )
        assert config.bridge_type == 'meta-facebook'
        assert config.auth_flow == 'cookies'

    def test_bridge_type_unique(self):
        BridgeConfig.objects.create(
            bridge_type='meta-facebook',
            provisioning_url='http://localhost:29319',
            provisioning_secret='s',
            bot_username='@facebookbot:grot.de',
            auth_flow='cookies',
            default_scopes=[],
            display_name='FB',
            icon='fb',
        )
        with self.assertRaises(Exception):
            BridgeConfig.objects.create(
                bridge_type='meta-facebook',
                provisioning_url='http://localhost:29320',
                provisioning_secret='s',
                bot_username='@facebookbot2:grot.de',
                auth_flow='cookies',
                default_scopes=[],
                display_name='FB2',
                icon='fb',
            )


class ClientBridgeConnectionTest(TestCase):
    fixtures = ['test_client']  # assumes a fixture with a Client

    def test_create_connection(self):
        from MASTER.clients.models import Client
        client = Client.objects.first()
        config = BridgeConfig.objects.create(
            bridge_type='meta-instagram',
            is_enabled=True,
            provisioning_url='http://localhost:29320',
            provisioning_secret='secret',
            bot_username='@instagrambot:grot.de',
            auth_flow='cookies',
            default_scopes=['assistant', 'manager'],
            display_name='Instagram DM',
            icon='instagram',
        )
        conn = ClientBridgeConnection.objects.create(
            client=client,
            bridge_config=config,
            matrix_user_id='@nexelin_client_1:grot.de',
            matrix_access_token='token123',
            status='disconnected',
        )
        assert conn.status == 'disconnected'
        assert conn.remote_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py test MASTER.clients.tests.test_bridge_models -v 2
```

Expected: FAIL — `models_bridge` module not found.

- [ ] **Step 3: Create BridgeConfig and ClientBridgeConnection models**

Create `p004_ai_nexelin/MASTER/clients/models_bridge.py`:

```python
from django.db import models
from django.utils import timezone


class BridgeConfig(models.Model):
    """Global config for each bridge type. One row per bridge."""

    BRIDGE_TYPES = [
        ('whatsapp', 'WhatsApp'),
        ('meta-facebook', 'Facebook Messenger'),
        ('meta-instagram', 'Instagram DM'),
        ('linkedin', 'LinkedIn Messages'),
    ]

    AUTH_FLOWS = [
        ('qr_code', 'QR Code'),
        ('cookies', 'Browser Cookies'),
    ]

    bridge_type = models.CharField(max_length=30, unique=True, choices=BRIDGE_TYPES)
    is_enabled = models.BooleanField(default=False)
    provisioning_url = models.URLField(
        help_text='mautrix provisioning API base URL, e.g. http://mautrix-meta-facebook:29319'
    )
    provisioning_secret = models.CharField(max_length=255)
    bot_username = models.CharField(
        max_length=255,
        help_text='Matrix bot user, e.g. @facebookbot:grot.de'
    )
    auth_flow = models.CharField(max_length=20, choices=AUTH_FLOWS)
    default_scopes = models.JSONField(
        default=list,
        help_text='Default targets: ["assistant","manager"] or ["leads"]'
    )
    display_name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50)
    popup_url = models.URLField(
        blank=True,
        help_text='Login URL for cookie auth, e.g. https://instagram.com'
    )
    cookie_domains = models.JSONField(
        default=list,
        help_text='Domains to extract cookies from, e.g. [".instagram.com"]'
    )
    required_cookies = models.JSONField(
        default=list,
        help_text='Cookie names required, e.g. ["sessionid","csrftoken"]'
    )

    class Meta:
        app_label = 'clients'
        verbose_name = 'Bridge Config'
        verbose_name_plural = 'Bridge Configs'

    def __str__(self):
        return f'{self.display_name} ({self.bridge_type})'


class ClientBridgeConnection(models.Model):
    """Per-client connection state for a specific bridge."""

    STATUS_CHOICES = [
        ('disconnected', 'Disconnected'),
        ('pending', 'Pending'),
        ('connected', 'Connected'),
        ('expired', 'Expired'),
        ('error', 'Error'),
    ]

    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE, related_name='bridge_connections'
    )
    bridge_config = models.ForeignKey(
        BridgeConfig, on_delete=models.CASCADE, related_name='connections'
    )
    matrix_user_id = models.CharField(max_length=255, blank=True)
    matrix_access_token = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')
    remote_id = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Phone for WhatsApp, profile ID for Meta/LinkedIn'
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    # Provisioning API v3 login state (transient, used during login flow)
    login_process_id = models.CharField(max_length=255, blank=True)
    login_step_id = models.CharField(max_length=255, blank=True)
    login_flow_id = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'clients'
        unique_together = [('client', 'bridge_config')]
        verbose_name = 'Client Bridge Connection'

    def __str__(self):
        return f'{self.client} — {self.bridge_config.bridge_type} ({self.status})'

    def mark_connected(self, remote_id=None):
        self.status = 'connected'
        self.connected_at = timezone.now()
        self.error = ''
        self.login_process_id = ''
        self.login_step_id = ''
        if remote_id:
            self.remote_id = remote_id
        self.save()

    def mark_error(self, error_msg):
        self.status = 'error'
        self.error = error_msg
        self.save()

    def mark_expired(self):
        self.status = 'expired'
        self.save()

    def mark_disconnected(self):
        self.status = 'disconnected'
        self.remote_id = None
        self.connected_at = None
        self.error = ''
        self.login_process_id = ''
        self.login_step_id = ''
        self.save()
```

- [ ] **Step 4: Create migration**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py makemigrations clients --name bridge_config_models
```

Expected output: `Migrations for 'clients': MASTER/clients/migrations/0058_bridge_config_models.py`

- [ ] **Step 5: Run migration**

```bash
python manage.py migrate clients
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python manage.py test MASTER.clients.tests.test_bridge_models -v 2
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models_bridge.py \
  p004_ai_nexelin/MASTER/clients/migrations/0058_bridge_config_models.py \
  p004_ai_nexelin/MASTER/clients/tests/test_bridge_models.py
git commit -m "feat(bridges): add BridgeConfig and ClientBridgeConnection models"
```

---

## Task 3: Universal Bridge Service

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/services/bridge_service.py`
- Test: `p004_ai_nexelin/MASTER/clients/tests/test_bridge_service.py`
- Reference: `p004_ai_nexelin/MASTER/clients/services/whatsapp_bridge.py` (existing pattern)

- [ ] **Step 1: Write tests for bridge service**

Create `p004_ai_nexelin/MASTER/clients/tests/test_bridge_service.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
from django.test import TestCase
from MASTER.clients.models_bridge import BridgeConfig, ClientBridgeConnection


class BridgeServiceTest(TestCase):
    fixtures = ['test_client']

    def setUp(self):
        from MASTER.clients.models import Client
        self.client = Client.objects.first()
        self.config = BridgeConfig.objects.create(
            bridge_type='meta-instagram',
            is_enabled=True,
            provisioning_url='http://localhost:29320',
            provisioning_secret='test-secret',
            bot_username='@instagrambot:grot.de',
            auth_flow='cookies',
            default_scopes=['assistant', 'manager'],
            display_name='Instagram DM',
            icon='instagram',
            popup_url='https://www.instagram.com/',
            cookie_domains=['.instagram.com'],
            required_cookies=['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
        )

    @patch('MASTER.clients.services.bridge_service.httpx.AsyncClient')
    async def test_start_login_cookies_flow(self, mock_httpx):
        from MASTER.clients.services.bridge_service import BridgeService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'type': 'cookies',
            'step_id': 'step-1',
            'process_id': 'proc-1',
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client

        service = BridgeService()
        result = await service.start_login(self.client, 'meta-instagram')

        assert result['auth_flow'] == 'cookies'
        assert result['popup_url'] == 'https://www.instagram.com/'
        assert 'process_id' in result

    @patch('MASTER.clients.services.bridge_service.httpx.AsyncClient')
    async def test_submit_cookies(self, mock_httpx):
        from MASTER.clients.services.bridge_service import BridgeService

        conn = ClientBridgeConnection.objects.create(
            client=self.client,
            bridge_config=self.config,
            matrix_user_id='@nexelin_client_1:grot.de',
            matrix_access_token='token',
            status='pending',
            login_process_id='proc-1',
            login_step_id='step-1',
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'type': 'complete',
            'user_login_id': 'login-123',
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client

        service = BridgeService()
        result = await service.submit_cookies(
            self.client, 'meta-instagram',
            {'sessionid': 'abc', 'csrftoken': 'xyz'}
        )

        assert result['status'] == 'connected'
        conn.refresh_from_db()
        assert conn.status == 'connected'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py test MASTER.clients.tests.test_bridge_service -v 2
```

Expected: FAIL — `bridge_service` module not found.

- [ ] **Step 3: Implement BridgeService**

Create `p004_ai_nexelin/MASTER/clients/services/bridge_service.py`:

```python
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
        try:
            config = BridgeConfig.objects.get(bridge_type=bridge_type)
        except BridgeConfig.DoesNotExist:
            raise BridgeServiceError(f'Bridge config not found: {bridge_type}')
        if not config.is_enabled:
            raise BridgeServiceError(f'Bridge disabled: {bridge_type}')
        return config

    def _provision_headers(self, matrix_access_token: str) -> dict:
        return {
            'Authorization': f'Bearer {matrix_access_token}',
            'Content-Type': 'application/json',
        }

    def _provision_url(self, config: BridgeConfig, path: str) -> str:
        base = config.provisioning_url.rstrip('/')
        return f'{base}/_matrix/provision{path}'

    async def _get_or_create_connection(
        self, client, config: BridgeConfig
    ) -> ClientBridgeConnection:
        conn, created = await sync_to_async(
            ClientBridgeConnection.objects.get_or_create
        )(
            client=client,
            bridge_config=config,
            defaults={
                'status': 'disconnected',
            },
        )
        return conn

    async def _ensure_matrix_user(self, client, conn: ClientBridgeConnection):
        """Create or reuse Matrix user for client. Reuses existing whatsapp_bridge logic."""
        if conn.matrix_user_id and conn.matrix_access_token:
            return  # already have credentials

        # Import existing function that handles Matrix user creation
        from MASTER.clients.services.whatsapp_bridge import create_matrix_user
        result = await sync_to_async(create_matrix_user)(client)

        conn.matrix_user_id = client.whatsapp_bridge_matrix_user_id
        conn.matrix_access_token = client.whatsapp_bridge_matrix_access_token
        await sync_to_async(conn.save)(
            update_fields=['matrix_user_id', 'matrix_access_token']
        )

    async def start_login(self, client, bridge_type: str) -> dict:
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)
        await self._ensure_matrix_user(client, conn)

        # Get available login flows
        url = self._provision_url(config, '/v3/login/flows')
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                url, headers=self._provision_headers(conn.matrix_access_token)
            )
            if resp.status_code != 200:
                raise BridgeServiceError(
                    f'Failed to get login flows: {resp.status_code} {resp.text}'
                )
            flows = resp.json()

        if not flows:
            raise BridgeServiceError(f'No login flows available for {bridge_type}')

        # Start first available flow
        flow_id = flows[0].get('id', flows[0].get('flow_id', ''))
        url = self._provision_url(config, f'/v3/login/start/{flow_id}')
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                url, headers=self._provision_headers(conn.matrix_access_token)
            )
            if resp.status_code != 200:
                raise BridgeServiceError(
                    f'Failed to start login: {resp.status_code} {resp.text}'
                )
            step = resp.json()

        step_type = step.get('type', '')
        process_id = step.get('process_id', '')
        step_id = step.get('step_id', '')

        # Store login state
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
            # QR code flow (WhatsApp)
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

    async def submit_cookies(
        self, client, bridge_type: str, cookies: dict
    ) -> dict:
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)

        if not conn.login_process_id or not conn.login_step_id:
            raise BridgeServiceError('No active login session. Call start_login first.')

        url = self._provision_url(
            config,
            f'/v3/login/step/{conn.login_process_id}/{conn.login_step_id}/cookies'
        )
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                url,
                headers=self._provision_headers(conn.matrix_access_token),
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
            # Need additional input (e.g., 2FA code)
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
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)

        if not conn.matrix_access_token:
            return {'status': conn.status, 'bridge_type': bridge_type}

        url = self._provision_url(config, '/v3/logins')
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(
                    url, headers=self._provision_headers(conn.matrix_access_token)
                )
            if resp.status_code == 200:
                logins = resp.json()
                if logins:
                    return {
                        'status': 'connected',
                        'bridge_type': bridge_type,
                        'remote_id': conn.remote_id,
                        'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
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
        config = await sync_to_async(self._get_config)(bridge_type)
        conn = await self._get_or_create_connection(client, config)

        if conn.matrix_access_token:
            url = self._provision_url(config, '/v3/logout/all')
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    await http.post(
                        url, headers=self._provision_headers(conn.matrix_access_token)
                    )
            except Exception as e:
                logger.warning(f'Bridge logout API failed for {bridge_type}: {e}')

        await sync_to_async(conn.mark_disconnected)()
        return {'status': 'disconnected', 'bridge_type': bridge_type}

    async def list_connections(self, client) -> list:
        connections = await sync_to_async(list)(
            ClientBridgeConnection.objects.filter(client=client)
            .select_related('bridge_config')
        )
        result = []
        for conn in connections:
            result.append({
                'bridge_type': conn.bridge_config.bridge_type,
                'display_name': conn.bridge_config.display_name,
                'status': conn.status,
                'remote_id': conn.remote_id,
                'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
            })
        return result


bridge_service = BridgeService()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py test MASTER.clients.tests.test_bridge_service -v 2
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/services/bridge_service.py \
  p004_ai_nexelin/MASTER/clients/tests/test_bridge_service.py
git commit -m "feat(bridges): add universal BridgeService with provisioning API v3"
```

---

## Task 4: Bridge API Endpoints

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/views_bridge.py`
- Create: `p004_ai_nexelin/MASTER/clients/urls_bridge.py`
- Modify: `p004_ai_nexelin/MASTER/clients/urls.py:1-50`

- [ ] **Step 1: Create bridge views**

Create `p004_ai_nexelin/MASTER/clients/views_bridge.py`:

```python
import logging

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from MASTER.clients.models_bridge import BridgeConfig
from MASTER.clients.services.bridge_service import bridge_service, BridgeServiceError

logger = logging.getLogger(__name__)


def _get_client(request):
    client = getattr(request, 'client', None)
    if not client:
        return None
    return client


class BridgeListView(APIView):
    """GET /api/bridges/ — list available bridge configs."""

    def get(self, request):
        configs = BridgeConfig.objects.filter(is_enabled=True).values(
            'bridge_type', 'display_name', 'icon', 'auth_flow', 'default_scopes'
        )
        return Response(list(configs))


class BridgeStatusView(APIView):
    """GET /api/bridges/{type}/status/ — connection status for current client."""

    def get(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.check_status)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLoginStartView(APIView):
    """POST /api/bridges/{type}/login/start/ — initiate login."""

    def post(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.start_login)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLoginCookiesView(APIView):
    """POST /api/bridges/{type}/login/cookies/ — submit cookies from extension."""

    def post(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        cookies = request.data.get('cookies', {})
        if not cookies:
            return Response(
                {'error': 'cookies field is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = async_to_sync(bridge_service.submit_cookies)(client, bridge_type, cookies)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLoginStatusView(APIView):
    """GET /api/bridges/{type}/login/status/ — poll login progress."""

    def get(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.check_status)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLogoutView(APIView):
    """POST /api/bridges/{type}/logout/ — disconnect."""

    def post(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.logout)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeMessageView(APIView):
    """POST /api/bridges/message/ — universal incoming message from Integration Service."""
    permission_classes = []

    def post(self, request):
        from django.conf import settings

        # Verify service token
        token = request.headers.get('X-Service-Token', '')
        if token != getattr(settings, 'INTEGRATION_SERVICE_TOKEN', ''):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        client_id = request.data.get('client_id')
        bridge_type = request.data.get('bridge_type')
        sender_id = request.data.get('sender_id', '')
        message_text = request.data.get('message_text', '')
        room_id = request.data.get('room_id', '')

        if not client_id or not bridge_type:
            return Response(
                {'error': 'client_id and bridge_type required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from MASTER.clients.models import Client
        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        # Determine scope from bridge_type and ToolConnection target
        from MASTER.tools.models import ToolConnection, ToolCard
        try:
            tool_card = ToolCard.objects.get(slug=bridge_type)
            conn = ToolConnection.objects.filter(
                client=client, tool_card=tool_card, status='connected'
            ).first()
            scope = conn.target if conn else 'assistant'
        except ToolCard.DoesNotExist:
            scope = 'assistant'

        # Route to orchestrator (same pattern as WhatsAppBridgeMessageView)
        from MASTER.agents.orchestrator import AgentOrchestrator
        try:
            orchestrator = AgentOrchestrator(client=client, scope=scope)
            response = async_to_sync(orchestrator.process)(message_text)
            return Response({
                'response': response,
                'bridge_type': bridge_type,
                'scope': scope,
            })
        except Exception as e:
            logger.error(f'Bridge message processing error: {e}', exc_info=True)
            return Response({'error': 'Processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

- [ ] **Step 2: Create URL routing**

Create `p004_ai_nexelin/MASTER/clients/urls_bridge.py`:

```python
from django.urls import path
from MASTER.clients import views_bridge

urlpatterns = [
    path('', views_bridge.BridgeListView.as_view(), name='bridge-list'),
    path('message/', views_bridge.BridgeMessageView.as_view(), name='bridge-message'),
    path('<str:bridge_type>/status/', views_bridge.BridgeStatusView.as_view(), name='bridge-status'),
    path('<str:bridge_type>/login/start/', views_bridge.BridgeLoginStartView.as_view(), name='bridge-login-start'),
    path('<str:bridge_type>/login/cookies/', views_bridge.BridgeLoginCookiesView.as_view(), name='bridge-login-cookies'),
    path('<str:bridge_type>/login/status/', views_bridge.BridgeLoginStatusView.as_view(), name='bridge-login-status'),
    path('<str:bridge_type>/logout/', views_bridge.BridgeLogoutView.as_view(), name='bridge-logout'),
]
```

- [ ] **Step 3: Include bridge URLs in main clients urls**

In `p004_ai_nexelin/MASTER/clients/urls.py`, add this include alongside existing patterns:

```python
from django.urls import path, include

# Add to urlpatterns:
path('bridges/', include('MASTER.clients.urls_bridge')),
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views_bridge.py \
  p004_ai_nexelin/MASTER/clients/urls_bridge.py \
  p004_ai_nexelin/MASTER/clients/urls.py
git commit -m "feat(bridges): add universal bridge API endpoints"
```

---

## Task 5: MCP Builtin Tools for Oleg

**Files:**
- Create: `p004_ai_nexelin/MASTER/mcp_hub/builtin/bridge_tools.py`
- Test: `p004_ai_nexelin/MASTER/mcp_hub/tests/test_bridge_tools.py`

- [ ] **Step 1: Write tests for bridge tools**

Create `p004_ai_nexelin/MASTER/mcp_hub/tests/test_bridge_tools.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
from django.test import TestCase


class BridgeToolsTest(TestCase):
    fixtures = ['test_client']

    def setUp(self):
        from MASTER.clients.models import Client
        from MASTER.clients.models_bridge import BridgeConfig
        self.client = Client.objects.first()
        self.config = BridgeConfig.objects.create(
            bridge_type='meta-instagram',
            is_enabled=True,
            provisioning_url='http://localhost:29320',
            provisioning_secret='secret',
            bot_username='@instagrambot:grot.de',
            auth_flow='cookies',
            default_scopes=['assistant', 'manager'],
            display_name='Instagram DM',
            icon='instagram',
            popup_url='https://www.instagram.com/',
            cookie_domains=['.instagram.com'],
            required_cookies=['sessionid', 'csrftoken'],
        )

    @patch('MASTER.mcp_hub.builtin.bridge_tools.bridge_service')
    async def test_bridge_start_connection(self, mock_service):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        mock_conn = MagicMock()
        mock_conn.client = self.client
        mock_service.start_login = AsyncMock(return_value={
            'auth_flow': 'cookies',
            'popup_url': 'https://www.instagram.com/',
            'bridge_type': 'meta-instagram',
        })

        result = await bridge_tools(
            connection=mock_conn,
            tool_name='bridge_start_connection',
            bridge_type='meta-instagram',
        )

        assert result['type'] == 'auth_popup'
        assert result['popup_url'] == 'https://www.instagram.com/'

    @patch('MASTER.mcp_hub.builtin.bridge_tools.bridge_service')
    async def test_canvas_list_connections(self, mock_service):
        from MASTER.mcp_hub.builtin.bridge_tools import bridge_tools

        mock_conn = MagicMock()
        mock_conn.client = self.client
        mock_service.list_connections = AsyncMock(return_value=[
            {'bridge_type': 'meta-instagram', 'status': 'connected'}
        ])

        result = await bridge_tools(
            connection=mock_conn,
            tool_name='canvas_list_connections',
        )

        assert len(result['connections']) == 1
        assert result['connections'][0]['bridge_type'] == 'meta-instagram'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py test MASTER.mcp_hub.tests.test_bridge_tools -v 2
```

Expected: FAIL — `bridge_tools` module not found.

- [ ] **Step 3: Implement bridge tools**

Create `p004_ai_nexelin/MASTER/mcp_hub/builtin/bridge_tools.py`:

```python
"""
MCP builtin tools for Oleg to manage bridge connections and canvas nodes.

Tools:
- bridge_start_connection: Initiate bridge auth (QR or cookies)
- bridge_check_status: Check bridge connection status
- canvas_add_tool_connection: Create ToolConnection + canvas node
- canvas_remove_tool_connection: Remove ToolConnection
- canvas_list_connections: List all bridge connections
"""

import logging

from asgiref.sync import sync_to_async
from django.utils import timezone

from MASTER.clients.services.bridge_service import bridge_service, BridgeServiceError

logger = logging.getLogger(__name__)


async def bridge_tools(connection, tool_name, **kwargs):
    """Dispatcher for bridge-related MCP tools."""
    client = connection.client

    handlers = {
        'bridge_start_connection': _bridge_start_connection,
        'bridge_check_status': _bridge_check_status,
        'canvas_add_tool_connection': _canvas_add_tool_connection,
        'canvas_remove_tool_connection': _canvas_remove_tool_connection,
        'canvas_list_connections': _canvas_list_connections,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return {'error': f'Unknown tool: {tool_name}'}

    try:
        return await handler(client, **kwargs)
    except BridgeServiceError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.error(f'Bridge tool {tool_name} error: {e}', exc_info=True)
        return {'error': f'Internal error: {str(e)}'}


async def _bridge_start_connection(client, bridge_type=None, **kwargs):
    if not bridge_type:
        return {'error': 'bridge_type is required'}

    result = await bridge_service.start_login(client, bridge_type)

    if result['auth_flow'] == 'cookies':
        return {
            'type': 'auth_popup',
            'auth_flow': 'cookies',
            'popup_url': result.get('popup_url', ''),
            'bridge_type': bridge_type,
            'cookie_domains': result.get('cookie_domains', []),
            'required_cookies': result.get('required_cookies', []),
            'process_id': result.get('process_id', ''),
            'step_id': result.get('step_id', ''),
        }
    elif result['auth_flow'] == 'qr_code':
        return {
            'type': 'qr_code',
            'qr': result.get('qr', ''),
            'bridge_type': bridge_type,
            'process_id': result.get('process_id', ''),
        }
    else:
        return result


async def _bridge_check_status(client, bridge_type=None, **kwargs):
    if not bridge_type:
        # Return all connections
        connections = await bridge_service.list_connections(client)
        return {'type': 'status_card', 'connections': connections}

    result = await bridge_service.check_status(client, bridge_type)
    return {
        'type': 'status_card',
        'bridge_type': bridge_type,
        'status': result.get('status', 'disconnected'),
        'remote_id': result.get('remote_id'),
        'connected_at': result.get('connected_at'),
        'error': result.get('error', ''),
    }


async def _canvas_add_tool_connection(client, bridge_type=None, targets=None, **kwargs):
    if not bridge_type:
        return {'error': 'bridge_type is required'}

    from MASTER.tools.models import ToolCard, ToolConnection
    from MASTER.clients.models_bridge import BridgeConfig

    try:
        tool_card = await sync_to_async(ToolCard.objects.get)(slug=bridge_type)
    except ToolCard.DoesNotExist:
        return {'error': f'ToolCard not found for {bridge_type}'}

    # Use provided targets or defaults from BridgeConfig
    if not targets:
        try:
            config = await sync_to_async(BridgeConfig.objects.get)(bridge_type=bridge_type)
            targets = config.default_scopes
        except BridgeConfig.DoesNotExist:
            targets = ['assistant']

    nodes_created = []
    for target in targets:
        conn, created = await sync_to_async(ToolConnection.objects.update_or_create)(
            client=client,
            tool_card=tool_card,
            target=target,
            defaults={
                'status': 'connected',
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            },
        )
        nodes_created.append(f'{target}-{bridge_type}')

    return {
        'type': 'connection_created',
        'bridge_type': bridge_type,
        'targets': targets,
        'nodes_created': nodes_created,
    }


async def _canvas_remove_tool_connection(client, connection_id=None, bridge_type=None, **kwargs):
    from MASTER.tools.models import ToolConnection

    if connection_id:
        try:
            conn = await sync_to_async(ToolConnection.objects.get)(
                pk=connection_id, client=client
            )
            await sync_to_async(conn.delete)()
            return {'type': 'connection_removed', 'connection_id': connection_id}
        except ToolConnection.DoesNotExist:
            return {'error': f'Connection {connection_id} not found'}

    if bridge_type:
        from MASTER.tools.models import ToolCard
        try:
            tool_card = await sync_to_async(ToolCard.objects.get)(slug=bridge_type)
        except ToolCard.DoesNotExist:
            return {'error': f'ToolCard not found for {bridge_type}'}

        deleted, _ = await sync_to_async(
            ToolConnection.objects.filter(client=client, tool_card=tool_card).delete
        )()
        return {'type': 'connection_removed', 'bridge_type': bridge_type, 'deleted_count': deleted}

    return {'error': 'connection_id or bridge_type required'}


async def _canvas_list_connections(client, **kwargs):
    from MASTER.tools.models import ToolConnection

    connections = await sync_to_async(list)(
        ToolConnection.objects.filter(client=client)
        .select_related('tool_card')
        .values(
            'id', 'tool_card__slug', 'tool_card__name', 'status',
            'target', 'connected_at', 'enabled'
        )
    )

    bridge_connections = await bridge_service.list_connections(client)

    return {
        'canvas_connections': connections,
        'bridge_connections': bridge_connections,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py test MASTER.mcp_hub.tests.test_bridge_tools -v 2
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/mcp_hub/builtin/bridge_tools.py \
  p004_ai_nexelin/MASTER/mcp_hub/tests/test_bridge_tools.py
git commit -m "feat(bridges): add MCP builtin bridge tools for Oleg"
```

---

## Task 6: Seed ToolCards for New Bridges

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/seed_data.py`
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0016_seed_meta_linkedin_tools.py`

- [ ] **Step 1: Add new ToolCard entries to seed_data.py**

In `p004_ai_nexelin/MASTER/tools/seed_data.py`, add to the TOOL_CARDS list:

```python
{
    'slug': 'meta-facebook',
    'name': 'Facebook Messenger',
    'tagline': 'Bridge Facebook Messenger conversations',
    'description': 'Connect Facebook Messenger to receive and respond to messages through the mautrix bridge.',
    'icon': 'facebook',
    'color': '#1877F2',
    'category': 'communication',
    'transport_type': 'builtin',
    'is_builtin': True,
    'builtin_handler': 'mcp_hub.builtin.bridge_tools',
    'auth_type': 'cookies',
    'auth_config': {
        'popup_url': 'https://www.messenger.com/',
        'cookie_domains': ['.facebook.com', '.messenger.com'],
        'required_cookies': ['c_user', 'xs', 'datr', 'sb'],
    },
    'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    'is_active': True,
    'is_featured': False,
    'is_system': False,
    'tools_schema': [
        {
            'name': 'bridge_start_connection',
            'description': 'Start Facebook Messenger bridge connection',
            'parameters': {'type': 'object', 'properties': {'bridge_type': {'type': 'string', 'const': 'meta-facebook'}}},
        },
        {
            'name': 'bridge_check_status',
            'description': 'Check Facebook Messenger bridge status',
            'parameters': {'type': 'object', 'properties': {'bridge_type': {'type': 'string', 'const': 'meta-facebook'}}},
        },
    ],
},
{
    'slug': 'meta-instagram',
    'name': 'Instagram DM',
    'tagline': 'Bridge Instagram Direct Messages',
    'description': 'Connect Instagram DM to receive and respond to messages through the mautrix bridge.',
    'icon': 'instagram',
    'color': '#E4405F',
    'category': 'communication',
    'transport_type': 'builtin',
    'is_builtin': True,
    'builtin_handler': 'mcp_hub.builtin.bridge_tools',
    'auth_type': 'cookies',
    'auth_config': {
        'popup_url': 'https://www.instagram.com/',
        'cookie_domains': ['.instagram.com'],
        'required_cookies': ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
    },
    'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    'is_active': True,
    'is_featured': False,
    'is_system': False,
    'tools_schema': [
        {
            'name': 'bridge_start_connection',
            'description': 'Start Instagram DM bridge connection',
            'parameters': {'type': 'object', 'properties': {'bridge_type': {'type': 'string', 'const': 'meta-instagram'}}},
        },
        {
            'name': 'bridge_check_status',
            'description': 'Check Instagram DM bridge status',
            'parameters': {'type': 'object', 'properties': {'bridge_type': {'type': 'string', 'const': 'meta-instagram'}}},
        },
    ],
},
{
    'slug': 'linkedin',
    'name': 'LinkedIn Messages',
    'tagline': 'Bridge LinkedIn Messages for lead generation',
    'description': 'Connect LinkedIn Messages to receive and respond to messages through the mautrix bridge.',
    'icon': 'linkedin',
    'color': '#0A66C2',
    'category': 'communication',
    'transport_type': 'builtin',
    'is_builtin': True,
    'builtin_handler': 'mcp_hub.builtin.bridge_tools',
    'auth_type': 'cookies',
    'auth_config': {
        'popup_url': 'https://www.linkedin.com/',
        'cookie_domains': ['.linkedin.com'],
        'required_cookies': ['li_at', 'JSESSIONID', 'lidc'],
    },
    'skill_scopes': {'scopes': ['leads'], 'bidirectional': True},
    'is_active': True,
    'is_featured': False,
    'is_system': False,
    'tools_schema': [
        {
            'name': 'bridge_start_connection',
            'description': 'Start LinkedIn Messages bridge connection',
            'parameters': {'type': 'object', 'properties': {'bridge_type': {'type': 'string', 'const': 'linkedin'}}},
        },
        {
            'name': 'bridge_check_status',
            'description': 'Check LinkedIn Messages bridge status',
            'parameters': {'type': 'object', 'properties': {'bridge_type': {'type': 'string', 'const': 'linkedin'}}},
        },
    ],
},
```

- [ ] **Step 2: Create seed migration**

Create `p004_ai_nexelin/MASTER/tools/migrations/0016_seed_meta_linkedin_tools.py`:

```python
from django.db import migrations


def seed_bridge_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')

    bridges = [
        {
            'slug': 'meta-facebook',
            'name': 'Facebook Messenger',
            'tagline': 'Bridge Facebook Messenger conversations',
            'description': 'Connect Facebook Messenger via mautrix bridge.',
            'icon': 'facebook',
            'color': '#1877F2',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.bridge_tools',
            'auth_type': 'cookies',
            'auth_config': {
                'popup_url': 'https://www.messenger.com/',
                'cookie_domains': ['.facebook.com', '.messenger.com'],
                'required_cookies': ['c_user', 'xs', 'datr', 'sb'],
            },
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
            'is_active': True,
        },
        {
            'slug': 'meta-instagram',
            'name': 'Instagram DM',
            'tagline': 'Bridge Instagram Direct Messages',
            'description': 'Connect Instagram DM via mautrix bridge.',
            'icon': 'instagram',
            'color': '#E4405F',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.bridge_tools',
            'auth_type': 'cookies',
            'auth_config': {
                'popup_url': 'https://www.instagram.com/',
                'cookie_domains': ['.instagram.com'],
                'required_cookies': ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
            },
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
            'is_active': True,
        },
        {
            'slug': 'linkedin',
            'name': 'LinkedIn Messages',
            'tagline': 'Bridge LinkedIn Messages for lead generation',
            'description': 'Connect LinkedIn Messages via mautrix bridge.',
            'icon': 'linkedin',
            'color': '#0A66C2',
            'category': 'communication',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.bridge_tools',
            'auth_type': 'cookies',
            'auth_config': {
                'popup_url': 'https://www.linkedin.com/',
                'cookie_domains': ['.linkedin.com'],
                'required_cookies': ['li_at', 'JSESSIONID', 'lidc'],
            },
            'skill_scopes': {'scopes': ['leads'], 'bidirectional': True},
            'is_active': True,
        },
    ]

    for data in bridges:
        ToolCard.objects.get_or_create(slug=data['slug'], defaults=data)


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug__in=['meta-facebook', 'meta-instagram', 'linkedin']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0015_system_xlsx_coaching'),
    ]

    operations = [
        migrations.RunPython(seed_bridge_tools, reverse),
    ]
```

- [ ] **Step 3: Run migration**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py migrate tools
```

- [ ] **Step 4: Verify seed data**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py shell -c "from MASTER.tools.models import ToolCard; print(ToolCard.objects.filter(slug__in=['meta-facebook','meta-instagram','linkedin']).values_list('slug','name'))"
```

Expected: `[('meta-facebook', 'Facebook Messenger'), ('meta-instagram', 'Instagram DM'), ('linkedin', 'LinkedIn Messages')]`

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/seed_data.py \
  p004_ai_nexelin/MASTER/tools/migrations/0016_seed_meta_linkedin_tools.py
git commit -m "feat(bridges): seed Meta FB, Meta IG, LinkedIn ToolCards"
```

---

## Task 7: Seed BridgeConfig Data

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/migrations/0059_seed_bridge_configs.py`

- [ ] **Step 1: Create BridgeConfig seed migration**

Create `p004_ai_nexelin/MASTER/clients/migrations/0059_seed_bridge_configs.py`:

```python
from django.db import migrations


def seed_bridge_configs(apps, schema_editor):
    BridgeConfig = apps.get_model('clients', 'BridgeConfig')

    configs = [
        {
            'bridge_type': 'meta-facebook',
            'is_enabled': False,
            'provisioning_url': 'http://localhost:29319',
            'provisioning_secret': '',
            'bot_username': '@facebookbot:grot.de',
            'auth_flow': 'cookies',
            'default_scopes': ['assistant', 'manager'],
            'display_name': 'Facebook Messenger',
            'icon': 'facebook',
            'popup_url': 'https://www.messenger.com/',
            'cookie_domains': ['.facebook.com', '.messenger.com'],
            'required_cookies': ['c_user', 'xs', 'datr', 'sb'],
        },
        {
            'bridge_type': 'meta-instagram',
            'is_enabled': False,
            'provisioning_url': 'http://localhost:29320',
            'provisioning_secret': '',
            'bot_username': '@instagrambot:grot.de',
            'auth_flow': 'cookies',
            'default_scopes': ['assistant', 'manager'],
            'display_name': 'Instagram DM',
            'icon': 'instagram',
            'popup_url': 'https://www.instagram.com/',
            'cookie_domains': ['.instagram.com'],
            'required_cookies': ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
        },
        {
            'bridge_type': 'linkedin',
            'is_enabled': False,
            'provisioning_url': 'http://localhost:29321',
            'provisioning_secret': '',
            'bot_username': '@linkedinbot:grot.de',
            'auth_flow': 'cookies',
            'default_scopes': ['leads'],
            'display_name': 'LinkedIn Messages',
            'icon': 'linkedin',
            'popup_url': 'https://www.linkedin.com/',
            'cookie_domains': ['.linkedin.com'],
            'required_cookies': ['li_at', 'JSESSIONID', 'lidc'],
        },
    ]

    for data in configs:
        BridgeConfig.objects.get_or_create(bridge_type=data['bridge_type'], defaults=data)


def reverse(apps, schema_editor):
    BridgeConfig = apps.get_model('clients', 'BridgeConfig')
    BridgeConfig.objects.filter(
        bridge_type__in=['meta-facebook', 'meta-instagram', 'linkedin']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('clients', '0058_bridge_config_models'),
    ]

    operations = [
        migrations.RunPython(seed_bridge_configs, reverse),
    ]
```

- [ ] **Step 2: Run migration**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py migrate clients
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/migrations/0059_seed_bridge_configs.py
git commit -m "feat(bridges): seed BridgeConfig for Meta FB, Meta IG, LinkedIn"
```

---

## Task 8: Chrome Extension — Cookie Extraction Module

**Files:**
- Create: `p004_ai_nexelin/chrome_extension/content/cookie-extractor.js`
- Modify: `p004_ai_nexelin/chrome_extension/manifest.json`
- Modify: `p004_ai_nexelin/chrome_extension/background/service-worker.js`

- [ ] **Step 1: Update manifest.json with cookie permissions**

In `p004_ai_nexelin/chrome_extension/manifest.json`, update permissions and host_permissions:

```json
{
  "manifest_version": 3,
  "name": "Nexelin Assistant",
  "version": "0.3.0",
  "description": "Nexelin browser assistant with cookie extraction for bridge connections",
  "permissions": ["storage", "activeTab", "scripting", "cookies"],
  "host_permissions": [
    "*://*/",
    "*://*.facebook.com/*",
    "*://*.messenger.com/*",
    "*://*.instagram.com/*",
    "*://*.linkedin.com/*"
  ],
  "background": {
    "service_worker": "background/service-worker.js",
    "type": "module"
  },
  "action": {
    "default_popup": "popup.html"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["contentScript.js", "content/behaviour-tracker.js"],
      "run_at": "document_idle"
    }
  ],
  "externally_connectable": {
    "matches": ["*://localhost/*", "*://*.nexelin.com/*", "*://*.grot.de/*"]
  }
}
```

- [ ] **Step 2: Create cookie extractor module**

Create `p004_ai_nexelin/chrome_extension/content/cookie-extractor.js`:

```javascript
/**
 * Cookie extraction module for mautrix bridge authentication.
 * Listens for messages from Nexelin frontend, extracts cookies via
 * chrome.cookies API, and sends them to the backend.
 */

const BRIDGE_COOKIE_CONFIG = {
  'meta-facebook': {
    domains: ['.facebook.com', '.messenger.com'],
    required: ['c_user', 'xs', 'datr', 'sb'],
    loginUrl: 'https://www.messenger.com/',
  },
  'meta-instagram': {
    domains: ['.instagram.com'],
    required: ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
    loginUrl: 'https://www.instagram.com/',
  },
  'linkedin': {
    domains: ['.linkedin.com'],
    required: ['li_at', 'JSESSIONID', 'lidc'],
    loginUrl: 'https://www.linkedin.com/',
  },
};

/**
 * Extract cookies for a given bridge type.
 * @param {string} bridgeType - e.g. 'meta-instagram'
 * @returns {Promise<Object>} - { cookies: {name: value}, missing: [names] }
 */
async function extractCookies(bridgeType) {
  const config = BRIDGE_COOKIE_CONFIG[bridgeType];
  if (!config) {
    return { error: `Unknown bridge type: ${bridgeType}` };
  }

  const allCookies = {};
  for (const domain of config.domains) {
    const cookies = await chrome.cookies.getAll({ domain });
    for (const cookie of cookies) {
      allCookies[cookie.name] = cookie.value;
    }
  }

  const result = {};
  const missing = [];
  for (const name of config.required) {
    if (allCookies[name]) {
      result[name] = allCookies[name];
    } else {
      missing.push(name);
    }
  }

  if (missing.length > 0) {
    return { cookies: result, missing, complete: false };
  }

  return { cookies: result, missing: [], complete: true };
}

/**
 * Open login popup for bridge auth.
 * @param {string} bridgeType
 * @returns {Promise<number>} - tab ID of opened popup
 */
async function openLoginPopup(bridgeType) {
  const config = BRIDGE_COOKIE_CONFIG[bridgeType];
  if (!config) return null;

  const tab = await chrome.tabs.create({
    url: config.loginUrl,
    active: true,
  });
  return tab.id;
}

/**
 * Poll for cookies after popup opened. Checks every 3s for up to 2 minutes.
 * @param {string} bridgeType
 * @param {number} tabId - popup tab to close on success
 * @returns {Promise<Object>}
 */
async function pollForCookies(bridgeType, tabId) {
  const maxAttempts = 40;
  const interval = 3000;

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, interval));

    const result = await extractCookies(bridgeType);
    if (result.complete) {
      // Close the login tab
      try {
        await chrome.tabs.remove(tabId);
      } catch (e) {
        // Tab may already be closed
      }
      return result;
    }
  }

  return { error: 'Timeout waiting for login', complete: false };
}

// Export for use in service-worker.js
if (typeof globalThis !== 'undefined') {
  globalThis.nexelinCookieExtractor = {
    extractCookies,
    openLoginPopup,
    pollForCookies,
    BRIDGE_COOKIE_CONFIG,
  };
}
```

- [ ] **Step 3: Add message handler to service-worker.js**

Add to the end of `p004_ai_nexelin/chrome_extension/background/service-worker.js`:

```javascript
// ===== Bridge Cookie Extraction =====
importScripts('../content/cookie-extractor.js');

chrome.runtime.onMessageExternal.addListener(
  (message, sender, sendResponse) => {
    if (message.action === 'nexelin_bridge_auth') {
      const { bridgeType, apiBaseUrl, authToken } = message;

      (async () => {
        try {
          // Open login popup
          const tabId = await globalThis.nexelinCookieExtractor.openLoginPopup(bridgeType);
          if (!tabId) {
            sendResponse({ error: 'Failed to open login tab' });
            return;
          }

          // Poll for cookies
          const result = await globalThis.nexelinCookieExtractor.pollForCookies(bridgeType, tabId);

          if (result.complete) {
            // Send cookies to backend
            const resp = await fetch(`${apiBaseUrl}/clients/bridges/${bridgeType}/login/cookies/`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`,
              },
              body: JSON.stringify({ cookies: result.cookies }),
            });

            const data = await resp.json();
            sendResponse({ success: true, status: data.status });
          } else {
            sendResponse({ error: result.error || 'Cookie extraction failed', missing: result.missing });
          }
        } catch (e) {
          sendResponse({ error: e.message });
        }
      })();

      return true; // async sendResponse
    }

    if (message.action === 'nexelin_check_extension') {
      sendResponse({ installed: true, version: chrome.runtime.getManifest().version });
      return;
    }
  }
);
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/chrome_extension/manifest.json \
  p004_ai_nexelin/chrome_extension/content/cookie-extractor.js \
  p004_ai_nexelin/chrome_extension/background/service-worker.js
git commit -m "feat(extension): add cookie extraction for Meta and LinkedIn bridges"
```

---

## Task 9: Frontend — Rich Message Cards in Chat

**Files:**
- Create: `nextlen/src/components/sandbox/chat/RichMessageCard.jsx`
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx:565-685`

- [ ] **Step 1: Create RichMessageCard component**

Create `nextlen/src/components/sandbox/chat/RichMessageCard.jsx`:

```jsx
import React, { useState, useCallback } from 'react';
import { Facebook, Instagram, Linkedin, Loader2, CheckCircle2, XCircle, Wifi } from 'lucide-react';

const EXTENSION_ID = import.meta.env.VITE_NEXELIN_EXTENSION_ID || '';
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

const BRIDGE_ICONS = {
  'meta-facebook': Facebook,
  'meta-instagram': Instagram,
  'linkedin': Linkedin,
};

const BRIDGE_COLORS = {
  'meta-facebook': '#1877F2',
  'meta-instagram': '#E4405F',
  'linkedin': '#0A66C2',
};

const BRIDGE_NAMES = {
  'meta-facebook': 'Facebook Messenger',
  'meta-instagram': 'Instagram DM',
  'linkedin': 'LinkedIn Messages',
};

function AuthPopupCard({ data, onComplete }) {
  const [status, setStatus] = useState('idle'); // idle, loading, success, error
  const [error, setError] = useState('');
  const Icon = BRIDGE_ICONS[data.bridge_type] || Wifi;
  const color = BRIDGE_COLORS[data.bridge_type] || '#6B7280';
  const name = BRIDGE_NAMES[data.bridge_type] || data.bridge_type;

  const handleClick = useCallback(async () => {
    setStatus('loading');
    setError('');

    // Check extension installed
    if (!EXTENSION_ID) {
      setError('Extension ID not configured');
      setStatus('error');
      return;
    }

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          EXTENSION_ID,
          {
            action: 'nexelin_bridge_auth',
            bridgeType: data.bridge_type,
            apiBaseUrl: API_BASE,
            authToken: localStorage.getItem('access_token') || '',
          },
          (resp) => {
            if (chrome.runtime.lastError) {
              reject(new Error('Extension not found. Please install the Nexelin extension.'));
            } else if (resp?.error) {
              reject(new Error(resp.error));
            } else {
              resolve(resp);
            }
          }
        );
      });

      setStatus('success');
      if (onComplete) onComplete(data.bridge_type);
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  }, [data.bridge_type, onComplete]);

  return (
    <div
      className="flex items-center gap-3 p-4 rounded-xl border"
      style={{ borderColor: color + '33', background: color + '08' }}
    >
      <div className="p-2 rounded-lg" style={{ background: color + '15' }}>
        <Icon size={24} style={{ color }} />
      </div>
      <div className="flex-1">
        <div className="font-medium text-sm">{name}</div>
        {status === 'error' && (
          <div className="text-xs text-red-500 mt-1">{error}</div>
        )}
        {status === 'success' && (
          <div className="text-xs text-green-600 mt-1">Connected successfully</div>
        )}
      </div>
      {status === 'idle' && (
        <button
          onClick={handleClick}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium hover:opacity-90 transition-opacity"
          style={{ background: color }}
        >
          Sign in
        </button>
      )}
      {status === 'loading' && <Loader2 size={20} className="animate-spin" style={{ color }} />}
      {status === 'success' && <CheckCircle2 size={20} className="text-green-600" />}
      {status === 'error' && (
        <button
          onClick={handleClick}
          className="px-3 py-1.5 rounded-lg text-xs border border-red-200 text-red-600 hover:bg-red-50"
        >
          Retry
        </button>
      )}
    </div>
  );
}

function QRCodeCard({ data }) {
  return (
    <div className="flex flex-col items-center gap-3 p-4 rounded-xl border border-gray-200 bg-white">
      <div className="text-sm font-medium">Scan QR code with WhatsApp</div>
      {data.qr ? (
        <img src={`data:image/png;base64,${data.qr}`} alt="QR Code" className="w-48 h-48" />
      ) : (
        <Loader2 size={32} className="animate-spin text-gray-400" />
      )}
      <div className="text-xs text-gray-500">Waiting for scan...</div>
    </div>
  );
}

function ConnectionStatusCard({ data }) {
  const Icon = BRIDGE_ICONS[data.bridge_type] || Wifi;
  const color = BRIDGE_COLORS[data.bridge_type] || '#6B7280';
  const name = BRIDGE_NAMES[data.bridge_type] || data.bridge_type;
  const isConnected = data.status === 'connected';

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-gray-200">
      <Icon size={20} style={{ color }} />
      <div className="flex-1">
        <div className="text-sm font-medium">{name}</div>
        <div className={`text-xs ${isConnected ? 'text-green-600' : 'text-gray-500'}`}>
          {data.status}
          {data.remote_id && ` — ${data.remote_id}`}
        </div>
      </div>
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
    </div>
  );
}

function TargetSelectorCard({ data, onSelect }) {
  const targets = data.targets || ['assistant', 'manager', 'leads'];
  const defaults = data.defaults || [];

  return (
    <div className="flex flex-col gap-2 p-4 rounded-xl border border-gray-200">
      <div className="text-sm font-medium">Where to connect?</div>
      <div className="flex gap-2 flex-wrap">
        {targets.map((target) => (
          <button
            key={target}
            onClick={() => onSelect && onSelect(target)}
            className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
              defaults.includes(target)
                ? 'border-blue-300 bg-blue-50 text-blue-700 font-medium'
                : 'border-gray-200 hover:border-gray-300 text-gray-700'
            }`}
          >
            {target.charAt(0).toUpperCase() + target.slice(1)}
          </button>
        ))}
        {targets.length > 1 && (
          <button
            onClick={() => onSelect && onSelect(targets.join(','))}
            className="px-3 py-1.5 rounded-lg text-sm border border-gray-200 hover:border-gray-300 text-gray-700"
          >
            All
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Main rich message renderer. Dispatches based on data.type.
 */
export default function RichMessageCard({ data, onAction }) {
  if (!data || !data.type) return null;

  switch (data.type) {
    case 'auth_popup':
      return <AuthPopupCard data={data} onComplete={(bt) => onAction?.('auth_complete', bt)} />;
    case 'qr_code':
      return <QRCodeCard data={data} />;
    case 'status_card':
      return <ConnectionStatusCard data={data} />;
    case 'target_selector':
      return <TargetSelectorCard data={data} onSelect={(t) => onAction?.('target_selected', t)} />;
    case 'connection_created':
      return (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-green-200 bg-green-50">
          <CheckCircle2 size={16} className="text-green-600" />
          <span className="text-sm text-green-700">
            Added to canvas: {data.nodes_created?.join(', ')}
          </span>
        </div>
      );
    case 'connection_removed':
      return (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-gray-200 bg-gray-50">
          <XCircle size={16} className="text-gray-500" />
          <span className="text-sm text-gray-600">Connection removed from canvas</span>
        </div>
      );
    default:
      return null;
  }
}
```

- [ ] **Step 2: Integrate RichMessageCard into ChatWindow**

In `nextlen/src/components/sandbox/ChatWindow.jsx`, add import at the top (around line 7):

```javascript
import RichMessageCard from './chat/RichMessageCard';
```

In the message rendering loop (around line 591-630 where AI messages render), after the ReactMarkdown block, add rich message rendering. Find where `msg.sender === 'ai'` messages are rendered and add:

```jsx
{msg.toolData?.type && (
  <RichMessageCard
    data={msg.toolData}
    onAction={(action, value) => {
      if (action === 'target_selected') {
        // Send target selection as user message
        handleSend(value);
      }
    }}
  />
)}
```

- [ ] **Step 3: Update handleToolEvent to capture rich message data**

In `ChatWindow.jsx` around line 114-200 (handleToolEvent function), add handling for bridge tool results:

```javascript
// Inside handleToolEvent, after existing tool_result handling:
if (event.type === 'tool_result' && event.data?.type) {
  // Bridge tool returned a rich message type
  const richTypes = ['auth_popup', 'qr_code', 'status_card', 'target_selector',
                     'connection_created', 'connection_removed'];
  if (richTypes.includes(event.data.type)) {
    // Attach to the next AI message as toolData
    setCurrentToolData(event.data);
  }
}
```

Add state for tool data (near other useState declarations around line 14):

```javascript
const [currentToolData, setCurrentToolData] = useState(null);
```

When building AI message objects, include `toolData: currentToolData` and reset it after.

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/components/sandbox/chat/RichMessageCard.jsx \
  nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(chat): add rich message cards for bridge auth in Oleg chat"
```

---

## Task 10: Frontend — Canvas Real-time Updates

**Files:**
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx`

- [ ] **Step 1: Add WebSocket listener for tool connection events**

In `nextlen/src/components/tools/FlowCanvas.jsx`, add a useEffect that listens for connection events. Insert after existing useEffect hooks (around line 145-150):

```jsx
// Real-time canvas updates from Oleg's bridge tools
useEffect(() => {
  const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/canvas/`;
  let ws;

  try {
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.event === 'tool_connection_created') {
        // Refresh connections from API
        refreshConnections();
      } else if (data.event === 'tool_connection_removed') {
        refreshConnections();
      } else if (data.event === 'tool_connection_status_changed') {
        refreshConnections();
      }
    };

    ws.onerror = () => {
      // WebSocket not available, fall back to polling
    };
  } catch (e) {
    // WebSocket not supported in this environment
  }

  return () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
  };
}, []);
```

Add a `refreshConnections` function that re-fetches the connections list:

```jsx
const refreshConnections = useCallback(async () => {
  try {
    const res = await api.get('/tools/connections/');
    if (res.data) {
      setConnections(res.data);
    }
  } catch (e) {
    // Silently fail
  }
}, []);
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/FlowCanvas.jsx
git commit -m "feat(canvas): add real-time WebSocket updates for bridge connections"
```

---

## Task 11: Integration Service — Bridge Type Routing

**Files:**
- Modify: `services/integration-service/internal/hitl/bridge.go:8-20`
- Modify: `services/integration-service/internal/hitl/orchestrator.go`

- [ ] **Step 1: Add BridgeType to ConversationMapping**

In `services/integration-service/internal/hitl/bridge.go`, update the `ConversationMapping` struct (line 14-20):

```go
type ConversationMapping struct {
	ConversationID int64
	RoomID         string
	Channel        string // "telegram", "whatsapp", "web"
	ClientID       int64
	BridgeType     string // "whatsapp", "meta-facebook", "meta-instagram", "linkedin"
}
```

- [ ] **Step 2: Add bot-to-bridge-type mapping in orchestrator**

In `services/integration-service/internal/hitl/orchestrator.go`, add a function to determine bridge type from room members:

```go
var botToBridgeType = map[string]string{
	"whatsappbot":  "whatsapp",
	"facebookbot":  "meta-facebook",
	"instagrambot": "meta-instagram",
	"linkedinbot":  "linkedin",
}

func (o *Orchestrator) detectBridgeType(roomID string) string {
	// Check room members for known bot users
	members, err := o.matrixClient.GetRoomMembers(roomID)
	if err != nil {
		return "whatsapp" // default fallback
	}

	for _, member := range members {
		// Extract localpart from @botname:domain
		localpart := strings.Split(strings.TrimPrefix(member, "@"), ":")[0]
		if bt, ok := botToBridgeType[localpart]; ok {
			return bt
		}
	}

	return "whatsapp"
}
```

- [ ] **Step 3: Update message forwarding to include bridge_type**

In the orchestrator's message handling function, when calling the Django API, include `bridge_type`:

```go
// When building the request body for Django API:
body := map[string]interface{}{
	"client_id":    mapping.ClientID,
	"bridge_type":  mapping.BridgeType,
	"sender_id":    senderID,
	"message_text": messageText,
	"room_id":      roomID,
}
```

Update the Django API URL from `/clients/whatsapp/bridge/message/` to `/clients/bridges/message/`.

- [ ] **Step 4: Commit**

```bash
cd /home/dchuprina/nexelin_web/services/integration-service
git add internal/hitl/bridge.go internal/hitl/orchestrator.go
git commit -m "feat(integration): add bridge_type routing for multi-bridge support"
```

---

## Task 12: Register Bridge Tools in Orchestrator

**Files:**
- Modify: `p004_ai_nexelin/MASTER/agents/orchestrator.py:32-55`

- [ ] **Step 1: Add bridge tools to assistant system prompt**

In `p004_ai_nexelin/MASTER/agents/orchestrator.py`, update `DEFAULT_ASSISTANT_PROMPT` (line 32-55) to inform Oleg about bridge tools:

Add this paragraph to the assistant prompt:

```python
"""
You have bridge management tools available:
- bridge_start_connection: Start connecting a messaging platform (meta-facebook, meta-instagram, linkedin, whatsapp)
- bridge_check_status: Check if a bridge is connected
- canvas_add_tool_connection: Add a connected bridge to the flow canvas with chosen targets
- canvas_remove_tool_connection: Remove a bridge from the canvas
- canvas_list_connections: List all current bridge connections

When a user asks to connect a platform, use bridge_start_connection first, then after successful auth,
ask which targets (assistant, manager, leads) to connect to, and use canvas_add_tool_connection.
Default targets: LinkedIn → leads, Facebook/Instagram → assistant + manager.
"""
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/agents/orchestrator.py
git commit -m "feat(orchestrator): add bridge tools to Oleg's system prompt"
```

---

## Task 13: ConnectModal — Support Cookies Auth Type

**Files:**
- Modify: `nextlen/src/components/tools/ConnectModal.jsx:45-69`

- [ ] **Step 1: Add cookies auth handling in ConnectModal**

In `nextlen/src/components/tools/ConnectModal.jsx`, in the `handleSubmit` function (line 45-69), add a branch for `cookies` auth type:

```jsx
// After the existing qr_code check (around line 55):
if (tool.auth_type === 'cookies' && data.status === 'pending') {
  // Trigger extension cookie extraction
  const extensionId = import.meta.env.VITE_NEXELIN_EXTENSION_ID;
  if (!extensionId) {
    setError('Nexelin extension is required for this connection');
    return;
  }

  try {
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        extensionId,
        {
          action: 'nexelin_bridge_auth',
          bridgeType: tool.slug,
          apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
          authToken: localStorage.getItem('access_token') || '',
        },
        (resp) => {
          if (chrome.runtime.lastError) {
            reject(new Error('Extension not found'));
          } else if (resp?.error) {
            reject(new Error(resp.error));
          } else {
            resolve(resp);
          }
        }
      );
    });

    if (response.success) {
      onConnected(tool.slug);
      onClose();
    }
  } catch (e) {
    setError(e.message);
  }
  return;
}
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ConnectModal.jsx
git commit -m "feat(tools): add cookies auth type support in ConnectModal"
```

---

## Task 14: End-to-End Verification

- [ ] **Step 1: Verify Docker services start**

```bash
cd /home/dchuprina/nexelin_web/matrix-stack
docker compose config --services | sort
```

Expected: Should list `mautrix-meta-facebook`, `mautrix-meta-instagram`, `mautrix-linkedin` alongside existing services.

- [ ] **Step 2: Verify Django migrations**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py showmigrations clients | tail -5
python manage.py showmigrations tools | tail -5
```

Expected: All migrations applied (marked with `[X]`).

- [ ] **Step 3: Verify ToolCards seeded**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py shell -c "
from MASTER.tools.models import ToolCard
for t in ToolCard.objects.filter(slug__in=['meta-facebook','meta-instagram','linkedin','whatsapp-bridge']):
    print(f'{t.slug}: auth={t.auth_type}, transport={t.transport_type}, handler={t.builtin_handler}')
"
```

Expected:
```
meta-facebook: auth=cookies, transport=builtin, handler=mcp_hub.builtin.bridge_tools
meta-instagram: auth=cookies, transport=builtin, handler=mcp_hub.builtin.bridge_tools
linkedin: auth=cookies, transport=builtin, handler=mcp_hub.builtin.bridge_tools
whatsapp-bridge: auth=qr_code, transport=builtin, handler=...
```

- [ ] **Step 4: Verify BridgeConfig seeded**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py shell -c "
from MASTER.clients.models_bridge import BridgeConfig
for c in BridgeConfig.objects.all():
    print(f'{c.bridge_type}: enabled={c.is_enabled}, auth={c.auth_flow}, url={c.provisioning_url}')
"
```

Expected: Three configs listed (meta-facebook, meta-instagram, linkedin), all `enabled=False` (need manual enable after Docker setup).

- [ ] **Step 5: Verify API endpoints respond**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python manage.py test MASTER.clients.tests.test_bridge_models MASTER.clients.tests.test_bridge_service MASTER.mcp_hub.tests.test_bridge_tools -v 2
```

Expected: All tests PASS.

- [ ] **Step 6: Final commit with all remaining changes**

```bash
git add -A
git status
# Review, then:
git commit -m "feat(bridges): complete multi-bridge integration with Oleg dynamic connections"
```
