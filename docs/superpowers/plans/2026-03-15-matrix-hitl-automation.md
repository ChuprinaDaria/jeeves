# Matrix HITL Automation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-server Integration Service containers with a single dynamic instance. MatrixServer model in Django admin with auto bot registration. No rebuilds.

**Architecture:** New `MatrixServer` Django model stores homeserver credentials. Django signals trigger Celery bot registration via Synapse Admin API. Integration Service refactored to fetch server configs from Django API at startup + poll for changes. Escalation flow updated to pass dynamic credentials per request.

**Tech Stack:** Django 5, Celery, PostgreSQL, Go (gin + gomatrix), Synapse Admin API, django-fernet-fields

**Spec:** `docs/superpowers/specs/2026-03-15-whitelabel-matrix-hitl-automation-design.md` (Part 2)

---

## File Structure

### Django (create)
- `MASTER/clients/models_matrix.py` — MatrixServer model
- `MASTER/clients/signals_matrix.py` — post_save signal for bot registration
- `MASTER/clients/tasks_matrix.py` — Celery task: register_matrix_bot
- `MASTER/clients/views_matrix.py` — API endpoints for Integration Service
- `MASTER/clients/migrations/0048_matrixserver.py` — MatrixServer + Client.matrix_server FK
- `tests/clients/test_matrix_server.py` — model + registration tests

### Django (modify)
- `MASTER/clients/models.py:274-288` — add matrix_server FK, remove matrix_homeserver_url
- `MASTER/clients/admin.py:176-190` — update HITL fieldset with MatrixServer dropdown
- `MASTER/clients/apps.py:8-9` — register matrix signals
- `MASTER/clients/tasks.py:3131-3210` — update send_matrix_escalation to use MatrixServer
- `MASTER/clients/urls.py` — add matrix server API routes
- `MASTER/settings.py` — add FERNET_KEY setting

### Integration Service Go (modify)
- `cmd/server/main.go` — refactor init to fetch servers from Django API
- `internal/hitl/orchestrator.go` — accept dynamic credentials per escalation
- `internal/matrix/client.go` — support multiple Matrix clients
- `internal/matrix/sync.go` — manage multiple sync loops
- `internal/api/handlers.go` — accept credentials in escalation request
- `pkg/models/escalation.go` — add homeserver/token fields to EscalationRequest

### Frontend (modify)
- `nextlen/src/components/integrations/HITLSetup.jsx` — add Matrix server selector

---

## Chunk 1: MatrixServer Model + Migration

### Task 1: Create MatrixServer model

**Files:**
- Create: `MASTER/clients/models_matrix.py`

- [ ] **Step 1: Install django-fernet-fields**

```bash
pip install django-fernet-fields
```

Add to `requirements.txt`:
```
django-fernet-fields==0.6
```

- [ ] **Step 2: Add FERNET_KEY to settings**

File: `MASTER/settings.py` — after line 309 (BOOTSTRAP_SECRET)

```python
# Encryption key for sensitive model fields (MatrixServer secrets)
FERNET_KEY = env("FERNET_KEY", default="")
if not FERNET_KEY:
    # Generate deterministic key from SECRET_KEY for dev convenience
    import hashlib, base64
    FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
```

- [ ] **Step 3: Write MatrixServer model**

File: `MASTER/clients/models_matrix.py`

```python
"""
MatrixServer model — stores Matrix homeserver configs with encrypted secrets.
Managed via Django admin. Bot registration happens automatically via Celery.
"""
from django.db import models
from fernet_fields import EncryptedCharField, EncryptedTextField


class MatrixServer(models.Model):
    """A Matrix homeserver in our federation with auto-registered bot."""

    name = models.CharField(max_length=100, help_text="Display name, e.g. 'Grot.de Production'")
    homeserver_url = models.URLField(help_text="Synapse URL, e.g. https://matrix.grot.de")
    domain = models.CharField(max_length=255, unique=True, help_text="Matrix domain, e.g. grot.de")
    registration_shared_secret = EncryptedCharField(
        max_length=500,
        help_text="Synapse registration_shared_secret (encrypted at rest)"
    )

    # Auto-filled after bot registration
    bot_user_id = models.CharField(max_length=255, blank=True)
    bot_access_token = EncryptedTextField(blank=True)
    bot_password = EncryptedCharField(max_length=255, blank=True)

    BOT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('registering', 'Registering...'),
        ('registered', 'Registered'),
        ('error', 'Error'),
    ]
    bot_status = models.CharField(max_length=20, choices=BOT_STATUS_CHOICES, default='pending')
    bot_error = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Matrix Server'
        verbose_name_plural = 'Matrix Servers'

    def __str__(self):
        status = self.get_bot_status_display()
        return f"{self.name} ({self.domain}) — {status}"
```

- [ ] **Step 4: Add matrix_server FK to Client model**

File: `MASTER/clients/models.py` — after line 288 (matrix_homeserver_url)

Add import at top:
```python
from MASTER.clients.models_matrix import MatrixServer
```

Add field after `matrix_homeserver_url`:
```python
matrix_server = models.ForeignKey(
    'clients.MatrixServer',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    help_text="Matrix server for HITL escalations (select from registered servers)"
)
```

- [ ] **Step 5: Create migration**

File: `MASTER/clients/migrations/0048_matrixserver.py`

```bash
# Generate:
python manage.py makemigrations clients --name matrixserver
# Or write manually with dependency on 0047_whatsappbridgeconfig_mautrix_db_password
```

Migration should:
1. CreateModel `MatrixServer`
2. AddField `Client.matrix_server` (FK, null=True)

- [ ] **Step 6: Register model in admin**

File: `MASTER/clients/admin.py` — add import and admin class:

```python
from .models_matrix import MatrixServer

@admin.register(MatrixServer)
class MatrixServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'bot_status', 'is_active']
    list_filter = ['bot_status', 'is_active']
    readonly_fields = ['bot_user_id', 'bot_status', 'bot_error', 'created_at', 'updated_at']

    fieldsets = (
        ('Server Config', {
            'fields': ('name', 'homeserver_url', 'domain', 'registration_shared_secret'),
        }),
        ('Bot Status', {
            'fields': ('bot_user_id', 'bot_status', 'bot_error'),
            'description': 'Auto-filled after bot registration. Do not edit manually.',
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at'),
        }),
    )

    def has_module_permission(self, request):
        return request.user.is_superuser
```

Update Client admin fieldset (replace lines 176-190):
```python
('Matrix.org HITL (Unified Interface)', {
    'fields': ('matrix_server', 'matrix_hitl_enabled', 'matrix_manager_user_ids'),
    'classes': ('collapse',),
    'description': 'Select Matrix server, enable HITL, add manager Matrix IDs.'
}),
```

- [ ] **Step 7: Run migration locally and verify**

```bash
python manage.py migrate clients
python manage.py shell -c "from MASTER.clients.models_matrix import MatrixServer; print('OK')"
```

- [ ] **Step 8: Commit**

```bash
git add MASTER/clients/models_matrix.py MASTER/clients/migrations/0048_* MASTER/clients/admin.py MASTER/clients/models.py MASTER/settings.py requirements.txt
git commit -m "feat: add MatrixServer model with encrypted secrets and admin"
```

---

## Chunk 2: Bot Auto-Registration via Celery

### Task 2: Celery task for bot registration

**Files:**
- Create: `MASTER/clients/tasks_matrix.py`
- Create: `MASTER/clients/signals_matrix.py`
- Modify: `MASTER/clients/apps.py`

- [ ] **Step 1: Write register_matrix_bot Celery task**

File: `MASTER/clients/tasks_matrix.py`

```python
"""
Celery tasks for Matrix server management.
Auto-registers nexelin-bot on Synapse via Admin API.
"""
import hashlib
import hmac
import logging
import uuid

import httpx
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def register_matrix_bot(self, server_id: int):
    """Register @nexelin-bot on a Synapse homeserver using shared-secret registration."""
    from MASTER.clients.models_matrix import MatrixServer

    try:
        server = MatrixServer.objects.get(id=server_id)
    except MatrixServer.DoesNotExist:
        logger.error(f"MatrixServer {server_id} not found")
        return

    server.bot_status = 'registering'
    server.bot_error = ''
    server.save(update_fields=['bot_status', 'bot_error'])

    username = 'nexelin-bot'
    password = f"nexelin_bot_{server.id}_{uuid.uuid4().hex[:8]}"

    try:
        # Step 1: Get nonce
        nonce_url = f"{server.homeserver_url}/_synapse/admin/v1/register"
        nonce_resp = httpx.get(nonce_url, timeout=10.0)
        if nonce_resp.status_code != 200:
            raise Exception(f"Nonce request failed: {nonce_resp.status_code}")
        nonce = nonce_resp.json()["nonce"]

        # Step 2: HMAC
        mac_msg = f"{nonce}\0{username}\0{password}\0notadmin"
        mac = hmac.new(
            server.registration_shared_secret.encode(),
            mac_msg.encode(),
            hashlib.sha1,
        ).hexdigest()

        # Step 3: Register
        reg_resp = httpx.post(nonce_url, json={
            "nonce": nonce,
            "username": username,
            "password": password,
            "admin": False,
            "mac": mac,
        }, timeout=10.0)

        if reg_resp.status_code == 200:
            data = reg_resp.json()
            server.bot_user_id = data.get("user_id", f"@{username}:{server.domain}")
            server.bot_access_token = data["access_token"]
            server.bot_password = password
            server.bot_status = 'registered'
            server.bot_error = ''
            logger.info(f"Bot registered: {server.bot_user_id} on {server.domain}")

        elif reg_resp.status_code == 400 and "User ID already taken" in reg_resp.text:
            # Bot exists — login
            login_resp = httpx.post(
                f"{server.homeserver_url}/_matrix/client/v3/login",
                json={
                    "type": "m.login.password",
                    "identifier": {"type": "m.id.user", "user": username},
                    "password": password,
                },
                timeout=10.0,
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                server.bot_user_id = data.get("user_id", f"@{username}:{server.domain}")
                server.bot_access_token = data["access_token"]
                server.bot_password = password
                server.bot_status = 'registered'
                server.bot_error = ''
                logger.info(f"Bot logged in: {server.bot_user_id} on {server.domain}")
            else:
                # Try with old password from DB if exists
                if server.bot_password:
                    login_resp2 = httpx.post(
                        f"{server.homeserver_url}/_matrix/client/v3/login",
                        json={
                            "type": "m.login.password",
                            "identifier": {"type": "m.id.user", "user": username},
                            "password": server.bot_password,
                        },
                        timeout=10.0,
                    )
                    if login_resp2.status_code == 200:
                        data = login_resp2.json()
                        server.bot_user_id = data.get("user_id", f"@{username}:{server.domain}")
                        server.bot_access_token = data["access_token"]
                        server.bot_status = 'registered'
                        server.bot_error = ''
                        logger.info(f"Bot re-logged in with stored password on {server.domain}")
                    else:
                        raise Exception(f"Bot exists but login failed: {login_resp2.text}")
                else:
                    raise Exception(f"Bot exists but login failed: {login_resp.text}")
        else:
            raise Exception(f"Registration failed: {reg_resp.status_code} {reg_resp.text}")

        server.save(update_fields=[
            'bot_user_id', 'bot_access_token', 'bot_password',
            'bot_status', 'bot_error',
        ])

    except Exception as e:
        logger.error(f"Bot registration failed on {server.domain}: {e}", exc_info=True)
        server.bot_status = 'error'
        server.bot_error = str(e)[:500]
        server.save(update_fields=['bot_status', 'bot_error'])
        raise self.retry(exc=e)
```

- [ ] **Step 2: Write post_save signal**

File: `MASTER/clients/signals_matrix.py`

```python
"""Signal: auto-register bot when MatrixServer is created."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='clients.MatrixServer')
def auto_register_bot(sender, instance, created, **kwargs):
    """Trigger bot registration on new server or when secret changes."""
    if created or instance.bot_status == 'pending':
        from MASTER.clients.tasks_matrix import register_matrix_bot
        register_matrix_bot.delay(instance.id)
        logger.info(f"Bot registration queued for {instance.domain}")
```

- [ ] **Step 3: Register signal in apps.py**

File: `MASTER/clients/apps.py` — update ready():

```python
def ready(self):
    import MASTER.clients.signals
    import MASTER.rag.qdrant_sync  # noqa
    import MASTER.clients.signals_matrix  # noqa — auto-register Matrix bots
```

- [ ] **Step 4: Commit**

```bash
git add MASTER/clients/tasks_matrix.py MASTER/clients/signals_matrix.py MASTER/clients/apps.py
git commit -m "feat: auto-register Matrix bot via Celery on server creation"
```

---

## Chunk 3: Django API for Integration Service

### Task 3: API endpoints for dynamic server config

**Files:**
- Create: `MASTER/clients/views_matrix.py`
- Modify: `MASTER/clients/urls.py`
- Modify: `MASTER/clients/tasks.py:3131-3210`

- [ ] **Step 1: Create API views for Integration Service**

File: `MASTER/clients/views_matrix.py`

```python
"""
API endpoints consumed by Integration Service.
- GET /api/clients/matrix/servers/ — list active servers with bot credentials
- POST /api/clients/matrix/test/ — test Matrix connection for a client
"""
import logging
from rest_framework.response import Response
from rest_framework.views import APIView
from .models_matrix import MatrixServer
from .views import get_client_from_request

logger = logging.getLogger(__name__)


class MatrixActiveServersView(APIView):
    """GET — returns all registered Matrix servers for Integration Service."""
    permission_classes = []

    def get(self, request):
        # Auth: check internal service token
        from django.conf import settings
        token = request.headers.get('X-Service-Token', '')
        expected = getattr(settings, 'INTEGRATION_SERVICE_TOKEN', '')
        if expected and token != expected:
            return Response({'error': 'Unauthorized'}, status=403)

        servers = MatrixServer.objects.filter(
            is_active=True,
            bot_status='registered',
        )
        return Response([{
            'id': s.id,
            'homeserver_url': s.homeserver_url,
            'domain': s.domain,
            'bot_user_id': s.bot_user_id,
            'bot_access_token': s.bot_access_token,
        } for s in servers])


class MatrixTestConnectionView(APIView):
    """POST — test Matrix HITL connection for a client."""
    permission_classes = []

    def post(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        if not client.matrix_server:
            return Response({'error': 'No Matrix server assigned'}, status=400)

        server = client.matrix_server
        if server.bot_status != 'registered':
            return Response({
                'error': f'Bot not registered on {server.domain}',
                'bot_status': server.bot_status,
                'bot_error': server.bot_error,
            }, status=400)

        # Test: create room, send message, verify
        import httpx
        results = []
        try:
            headers = {"Authorization": f"Bearer {server.bot_access_token}"}

            # Test 1: whoami
            resp = httpx.get(
                f"{server.homeserver_url}/_matrix/client/v3/account/whoami",
                headers=headers, timeout=10.0,
            )
            if resp.status_code == 200:
                results.append({'test': 'bot_auth', 'status': 'ok'})
            else:
                results.append({'test': 'bot_auth', 'status': 'fail', 'error': resp.text})
                return Response({'results': results, 'overall': 'fail'})

            # Test 2: create test room
            resp = httpx.post(
                f"{server.homeserver_url}/_matrix/client/v3/createRoom",
                headers=headers, timeout=10.0,
                json={
                    "name": f"Test: {client.company_name or client.tag}",
                    "preset": "private_chat",
                },
            )
            if resp.status_code == 200:
                room_id = resp.json()['room_id']
                results.append({'test': 'create_room', 'status': 'ok', 'room_id': room_id})
            else:
                results.append({'test': 'create_room', 'status': 'fail', 'error': resp.text})
                return Response({'results': results, 'overall': 'fail'})

            # Test 3: send message
            resp = httpx.put(
                f"{server.homeserver_url}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/test1",
                headers=headers, timeout=10.0,
                json={"msgtype": "m.text", "body": "HITL test message 1"},
            )
            results.append({
                'test': 'send_message',
                'status': 'ok' if resp.status_code == 200 else 'fail',
            })

            # Test 4: send SECOND message to SAME room (dedup check)
            resp = httpx.put(
                f"{server.homeserver_url}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/test2",
                headers=headers, timeout=10.0,
                json={"msgtype": "m.text", "body": "HITL test message 2 (same room)"},
            )
            results.append({
                'test': 'same_room_reuse',
                'status': 'ok' if resp.status_code == 200 else 'fail',
            })

            # Test 5: invite managers
            for mgr_id in (client.matrix_manager_user_ids or []):
                resp = httpx.post(
                    f"{server.homeserver_url}/_matrix/client/v3/rooms/{room_id}/invite",
                    headers=headers, timeout=10.0,
                    json={"user_id": mgr_id},
                )
                results.append({
                    'test': f'invite_{mgr_id}',
                    'status': 'ok' if resp.status_code in (200, 403) else 'fail',
                })

            # Cleanup: leave test room
            httpx.post(
                f"{server.homeserver_url}/_matrix/client/v3/rooms/{room_id}/leave",
                headers=headers, timeout=5.0,
            )

            overall = 'ok' if all(r['status'] == 'ok' for r in results) else 'partial'
            return Response({'results': results, 'overall': overall})

        except Exception as e:
            results.append({'test': 'connection', 'status': 'fail', 'error': str(e)})
            return Response({'results': results, 'overall': 'fail'})
```

- [ ] **Step 2: Add URL routes**

File: `MASTER/clients/urls.py` — add:

```python
from .views_matrix import MatrixActiveServersView, MatrixTestConnectionView

# In urlpatterns:
path('matrix/servers/', MatrixActiveServersView.as_view(), name='matrix-active-servers'),
path('matrix/test/', MatrixTestConnectionView.as_view(), name='matrix-test-connection'),
```

- [ ] **Step 3: Update send_matrix_escalation to use MatrixServer**

File: `MASTER/clients/tasks.py` — replace lines 3131-3210

Key changes:
- Get credentials from `client.matrix_server` instead of env vars
- Add `select_for_update()` lock on conversation
- Pass `homeserver_url`, `bot_access_token`, `existing_room_id` to Integration Service
- Determine Integration Service URL from settings (single instance)

```python
def send_matrix_escalation(client, conversation, question, context_text, language='en'):
    """Send escalation to Matrix via Integration Service with dynamic server credentials."""
    if not client.matrix_hitl_enabled or not client.matrix_server:
        logger.warning(f"Matrix HITL not configured for client {client.id}")
        return False

    server = client.matrix_server
    if server.bot_status != 'registered':
        logger.error(f"Bot not registered on {server.domain} for client {client.id}")
        return False

    from django.db import transaction
    from MASTER.clients.models import ClientWhatsAppConversation

    # Lock conversation to prevent duplicate room creation
    with transaction.atomic():
        conv = ClientWhatsAppConversation.objects.select_for_update().get(id=conversation.id)
        existing_room_id = conv.matrix_room_id or None

    manager_ids = client.matrix_manager_user_ids or []
    if not manager_ids:
        logger.warning(f"No manager IDs for client {client.id}")
        return False

    integration_url = getattr(settings, 'INTEGRATION_SERVICE_URL',
                              'http://ai_nexelin_integration_service:8080')

    payload = {
        'conversation_id': conversation.id,
        'client_id': client.id,
        'client_name': client.company_name or client.user,
        'homeserver_url': server.homeserver_url,
        'bot_user_id': server.bot_user_id,
        'bot_access_token': server.bot_access_token,
        'manager_user_ids': manager_ids,
        'existing_room_id': existing_room_id,
        'customer_name': getattr(conversation, 'customer_phone', '') or 'Customer',
        'channel': conversation.context_metadata.get('platform', 'web') if conversation.context_metadata else 'web',
        'question': question[:2000],
        'context': context_text[:3000],
        'language': language,
    }

    try:
        import httpx
        resp = httpx.post(
            f"{integration_url}/api/v1/hitl/escalate",
            json=payload,
            timeout=15.0,
        )
        if resp.status_code == 200:
            logger.info(f"Matrix escalation sent for conversation {conversation.id}")
            return True
        else:
            logger.error(f"Matrix escalation failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Matrix escalation request failed: {e}", exc_info=True)
        return False
```

- [ ] **Step 4: Commit**

```bash
git add MASTER/clients/views_matrix.py MASTER/clients/urls.py MASTER/clients/tasks.py
git commit -m "feat: dynamic Matrix HITL — API endpoints and escalation with select_for_update"
```

---

## Chunk 4: Integration Service Refactor (Go)

### Task 4: Make Integration Service dynamic

**Files:**
- Modify: `services/integration-service/cmd/server/main.go`
- Modify: `services/integration-service/internal/hitl/orchestrator.go`
- Modify: `services/integration-service/internal/matrix/client.go`
- Modify: `services/integration-service/internal/matrix/sync.go`
- Modify: `services/integration-service/internal/api/handlers.go`
- Modify: `services/integration-service/pkg/models/escalation.go`

- [ ] **Step 1: Update EscalationRequest model**

File: `pkg/models/escalation.go` — add fields:

```go
type EscalationRequest struct {
    ConversationID int      `json:"conversation_id"`
    ClientID       int      `json:"client_id"`
    ClientName     string   `json:"client_name"`
    HomeserverURL  string   `json:"homeserver_url"`      // NEW — dynamic
    BotUserID      string   `json:"bot_user_id"`         // NEW — dynamic
    BotAccessToken string   `json:"bot_access_token"`    // NEW — dynamic
    ManagerUserIDs []string `json:"manager_user_ids"`
    ExistingRoomID string   `json:"existing_room_id"`    // NEW — room reuse
    CustomerName   string   `json:"customer_name"`
    Channel        string   `json:"channel"`
    Question       string   `json:"question"`
    Context        string   `json:"context"`
    Language       string   `json:"language"`
}
```

- [ ] **Step 2: Refactor Matrix client to support multiple servers**

File: `internal/matrix/client.go` — make `NewClient` accept params:

```go
func NewClient(homeserverURL, userID, accessToken string) (*Client, error) {
    matrixClient, err := gomatrix.NewClient(homeserverURL, userID, accessToken)
    if err != nil {
        return nil, err
    }
    return &Client{client: matrixClient}, nil
}
```

- [ ] **Step 3: Refactor orchestrator to use per-request credentials**

File: `internal/hitl/orchestrator.go`

Key change in `HandleEscalation()`:
- Create Matrix client from request credentials (not from stored env vars)
- Check `ExistingRoomID` — if set, use existing room
- If not set, create new room

```go
func (o *Orchestrator) HandleEscalation(req models.EscalationRequest) (*models.Escalation, error) {
    // Create client from request credentials
    matrixClient, err := matrix.NewClient(req.HomeserverURL, req.BotUserID, req.BotAccessToken)
    if err != nil {
        return nil, fmt.Errorf("matrix client init failed: %w", err)
    }

    var roomID string
    if req.ExistingRoomID != "" {
        // Reuse existing room
        roomID = req.ExistingRoomID
    } else {
        // Create new room
        roomName := fmt.Sprintf("Escalation: %s - %s", req.ClientName, req.Channel)
        roomID, err = matrixClient.CreateRoom(roomName)
        if err != nil {
            return nil, fmt.Errorf("create room failed: %w", err)
        }
        // Invite managers
        for _, mgrID := range req.ManagerUserIDs {
            matrixClient.InviteUser(roomID, mgrID)
        }
        // Store room in Django
        o.storeEscalationRoom(req.ConversationID, roomID)
    }

    // Send escalation message
    msg := formatEscalationMessage(req)
    matrixClient.SendFormattedMessage(roomID, msg)

    // Register in bridge for response tracking
    o.bridge.RegisterConversation(roomID, req.ConversationID)

    return &models.Escalation{
        RoomID:         roomID,
        ConversationID: req.ConversationID,
    }, nil
}
```

- [ ] **Step 4: Add multi-server sync management**

File: `internal/matrix/sync.go` — add `SyncManager`:

```go
type SyncManager struct {
    syncs    map[string]*SyncHandler  // domain → sync
    mu       sync.RWMutex
    djangoURL string
}

func (m *SyncManager) UpdateServers(servers []ServerConfig) {
    m.mu.Lock()
    defer m.mu.Unlock()

    active := make(map[string]bool)
    for _, s := range servers {
        active[s.Domain] = true
        if _, exists := m.syncs[s.Domain]; !exists {
            // Start new sync
            handler := NewSyncHandler(s.HomeserverURL, s.BotUserID, s.BotAccessToken)
            go handler.Start()
            m.syncs[s.Domain] = handler
        }
    }
    // Stop removed servers
    for domain, handler := range m.syncs {
        if !active[domain] {
            handler.Stop()
            delete(m.syncs, domain)
        }
    }
}
```

- [ ] **Step 5: Refactor main.go — poll Django for servers**

File: `cmd/server/main.go`

```go
func main() {
    djangoURL := os.Getenv("DJANGO_API_URL")
    serviceToken := os.Getenv("DJANGO_API_TOKEN")

    syncManager := matrix.NewSyncManager(djangoURL)

    // Poll for server configs every 15 seconds
    go func() {
        for {
            servers := fetchActiveServers(djangoURL, serviceToken)
            syncManager.UpdateServers(servers)
            time.Sleep(15 * time.Second)
        }
    }()

    // Start HTTP server (same as before)
    router := gin.Default()
    api.SetupRoutes(router, orchestrator)
    router.Run(":" + port)
}

func fetchActiveServers(djangoURL, token string) []matrix.ServerConfig {
    url := djangoURL + "/clients/matrix/servers/"
    req, _ := http.NewRequest("GET", url, nil)
    req.Header.Set("X-Service-Token", token)
    resp, err := http.DefaultClient.Do(req)
    // parse JSON into []ServerConfig
    // ...
}
```

- [ ] **Step 6: Rebuild Integration Service**

```bash
cd services/integration-service
docker build -t nexelin-integration:latest .
```

- [ ] **Step 7: Commit**

```bash
git add services/integration-service/
git commit -m "feat: Integration Service dynamic multi-server support"
```

---

## Chunk 5: Deploy and Test

### Task 5: Deploy to production

- [ ] **Step 1: Deploy Django changes**

```bash
scp MASTER/clients/models_matrix.py server:/opt/.../MASTER/clients/
scp MASTER/clients/tasks_matrix.py server:/opt/.../MASTER/clients/
scp MASTER/clients/signals_matrix.py server:/opt/.../MASTER/clients/
scp MASTER/clients/views_matrix.py server:/opt/.../MASTER/clients/
scp MASTER/clients/apps.py server:/opt/.../MASTER/clients/
scp MASTER/clients/admin.py server:/opt/.../MASTER/clients/
scp MASTER/clients/tasks.py server:/opt/.../MASTER/clients/
scp MASTER/clients/urls.py server:/opt/.../MASTER/clients/
scp MASTER/clients/migrations/0048_* server:/opt/.../MASTER/clients/migrations/
scp MASTER/settings.py server:/opt/.../MASTER/
```

- [ ] **Step 2: Run migration on server**

```bash
docker exec ai_nexelin_web pip install django-fernet-fields
docker exec ai_nexelin_web python manage.py migrate clients
```

- [ ] **Step 3: Add FERNET_KEY to .env**

```bash
echo "FERNET_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env
```

- [ ] **Step 4: Create MatrixServer records for existing servers**

In Django admin:
1. Add MatrixServer "Grot.de" — homeserver_url=https://matrix.grot.de, domain=grot.de, secret from homeserver.yaml
2. Add MatrixServer "Bytekraft" — homeserver_url=https://matrix.bytekraft.eu, domain=bytekraft.eu, secret from their config
3. Bot registration should happen automatically via Celery signal

- [ ] **Step 5: Assign MatrixServer to existing clients**

In Django admin — for each client with matrix_hitl_enabled=True:
- Set matrix_server from dropdown

- [ ] **Step 6: Rebuild and deploy Integration Service**

```bash
cd /opt/p004_ai_nexelin/services/integration-service
docker build -t nexelin-integration:latest .
cd /opt/p004_ai_nexelin/p004_ai_nexelin
docker compose down integration-service integration-service-bytekraft
# Remove bytekraft container from docker-compose (no longer needed)
docker compose up -d
```

- [ ] **Step 7: Test end-to-end**

1. Send message that triggers escalation to bytekraft client
2. Verify: room created on correct Matrix server
3. Verify: manager receives invite
4. Verify: manager reply reaches customer
5. Verify: second escalation reuses existing room

- [ ] **Step 8: Commit deploy config**

```bash
git commit -m "deploy: Matrix HITL automation — single Integration Service"
```
