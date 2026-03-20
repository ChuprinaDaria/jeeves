# White Label Domain + Matrix HITL Automation — Design Spec

## Problem

Two manual processes block scalability:

1. **White label domains** — adding a new client domain requires manual nginx config, certbot, CORS/CSRF updates in settings.py, and container rebuild.
2. **Matrix HITL** — each Matrix homeserver needs a separate Integration Service container with hardcoded env vars. Adding a client to HITL requires manual bot registration, config changes, and restart.

## Goal

Everything through Django admin, zero rebuilds:
- Add Matrix server → bot auto-registers
- Enable HITL for client → select server from dropdown, works immediately
- Set white label domain → SSL auto-provisions, CORS auto-allowed

## Architecture Overview

```
Django Admin
    │
    ├── MatrixServer (CRUD)
    │   └── save() → Celery: register bot on Synapse via Admin API
    │
    ├── Client
    │   ├── matrix_server: FK → MatrixServer (dropdown)
    │   ├── matrix_hitl_enabled: checkbox
    │   ├── matrix_manager_user_ids: ["@mgr:grot.de"]
    │   ├── [Test Connection] button
    │   │
    │   ├── webchat_domain: "ai.client.de"
    │   ├── ssl_status: auto (dns_pending/active/error)
    │   └── save() → Celery: DNS check → nginx conf → certbot → CORS
    │
    ▼
Integration Service (single instance, semi-stateful)
    │
    ├── Startup: GET /api/integration/active-servers/ → sync loop per server
    ├── Escalation: check room in Django DB → reuse or create
    ├── Hot reload: new server → new sync loop, no restart
    └── Manager reply: sync → forward → Django → user channel

    ▼
Nginx (dynamic config generation)
    │
    ├── api.nexelin.com → Django backend
    ├── app.nexelin.com → React build (single build, all clients)
    ├── ai.client1.de  → React build (auto-generated config)
    └── SSL: certbot per domain, auto-renew via Celery beat
```

---

## Part 1: Data Models

### New model: MatrixServer

```python
class MatrixServer(models.Model):
    name = CharField(max_length=100)  # "Grot.de Production"
    homeserver_url = URLField()  # "https://matrix.grot.de"
    domain = CharField(max_length=255, unique=True)  # "grot.de"
    registration_shared_secret = EncryptedCharField(max_length=500)  # encrypted at rest

    # Auto-filled after bot registration
    bot_user_id = CharField(max_length=255, blank=True)  # "@nexelin-bot:grot.de"
    bot_access_token = EncryptedTextField(blank=True)  # encrypted at rest
    bot_password = EncryptedCharField(max_length=255, blank=True)  # for re-login if token expires
    bot_status = CharField(choices=[
        ('pending', 'Pending'),
        ('registered', 'Registered'),
        ('error', 'Error'),
    ], default='pending')
    bot_error = TextField(blank=True)

    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Encryption:** Use `django-fernet-fields` or `django-encrypted-model-fields` for `registration_shared_secret`, `bot_access_token`, and `bot_password`. These are never displayed in admin after initial save — admin shows `***` for existing values.

**Bot password:** Stored encrypted to allow re-login if token expires. Generated deterministically as `f"nexelin_bot_{server.id}_{domain}"` or random UUID.

### Client model changes

```python
# NEW field
matrix_server = ForeignKey(MatrixServer, null=True, blank=True, on_delete=SET_NULL)

# EXISTING fields (keep)
matrix_hitl_enabled = BooleanField(default=False)
matrix_manager_user_ids = JSONField(default=list)

# REMOVE
matrix_homeserver_url  # → replaced by matrix_server.homeserver_url

# NEW SSL fields
ssl_status = CharField(choices=[
    ('none', 'None'),
    ('dns_pending', 'DNS Pending'),
    ('provisioning', 'Provisioning'),
    ('active', 'Active'),
    ('error', 'Error'),
], default='none')
ssl_expires_at = DateTimeField(null=True, blank=True)
ssl_error = TextField(blank=True)
ssl_first_requested_at = DateTimeField(null=True, blank=True)  # for DNS timeout tracking
ssl_last_certbot_at = DateTimeField(null=True, blank=True)  # rate limit: min 1h between attempts
```

---

## Part 2: Matrix HITL Automation

### Flow: Admin adds Matrix server

1. Admin creates MatrixServer in Django admin with name, homeserver_url, domain, registration_shared_secret
2. `post_save` signal triggers Celery task `register_matrix_bot(server_id)`
3. Task calls Synapse Admin API:
   - `GET /_synapse/admin/v1/register` → get nonce
   - HMAC-SHA1 sign: `nonce\0nexelin-bot\0password\0notadmin`
   - `POST /_synapse/admin/v1/register` → register @nexelin-bot:{domain}
4. On success: save bot_user_id + bot_access_token, set bot_status="registered"
5. On failure: set bot_status="error", bot_error=message
6. If user already exists: login with password, get access_token

### Flow: Admin enables HITL for client

1. Admin selects matrix_server from dropdown (only servers with bot_status="registered")
2. Checks matrix_hitl_enabled
3. Enters manager Matrix IDs
4. Clicks [Test Connection] → AJAX call tests:
   - Bot can connect to homeserver
   - Room creation works
   - Manager invites work
   - Second message goes to SAME room (no duplicate)
   - Sync is active
5. Save — no rebuild needed

### Flow: Escalation at runtime

1. RAG detects `[[ESCALATE_TO_MANAGER]]`
2. Django task `notify_manager_of_escalation()`:
   - Gets `client.matrix_server` → homeserver_url, bot_access_token
   - Gets `conversation.matrix_room_id` — if exists, reuse
   - Calls Integration Service: `POST /api/v1/hitl/escalate`
     ```json
     {
       "client_id": 42,
       "conversation_id": 123,
       "homeserver_url": "https://matrix.grot.de",
       "bot_access_token": "syt_...",
       "manager_user_ids": ["@mgr1:grot.de"],
       "existing_room_id": "!abc:grot.de",  // or null
       "message": "Customer asks about...",
       "context": { ... }
     }
     ```

3. Integration Service:
   - If `existing_room_id` → send message to existing room
   - If null → create room, save room_id back to Django via `POST /api/v1/integration/update-room`
   - **NEVER** create room without checking Django DB first

### Room deduplication guarantee

1. **Source of truth**: PostgreSQL `conversation.matrix_room_id`
2. **DB lock in send_matrix_escalation():**
   ```python
   with transaction.atomic():
       conv = ClientWhatsAppConversation.objects.select_for_update().get(id=conversation_id)
       if conv.matrix_room_id:
           existing_room_id = conv.matrix_room_id
       else:
           existing_room_id = None
       # Call Integration Service with existing_room_id
       # If IS creates new room → update-room callback saves room_id
   ```
   Two concurrent escalations for the same conversation: second one waits for lock, sees room_id already set.
3. **Integration Service**: always receives existing_room_id from Django, never decides independently
4. After IS restart: Django still has room mapping, no data loss

**Required changes to `send_matrix_escalation` in tasks.py:**
- Add `select_for_update()` lock (currently missing)
- Add `homeserver_url` and `bot_access_token` from `client.matrix_server` to payload
- Add `existing_room_id` from `conversation.matrix_room_id` to payload

### Integration Service changes

Current: two containers with hardcoded env vars per Matrix server.
After: single container, dynamic configuration.

**Startup:**
1. `GET /api/integration/active-servers/` from Django
2. For each MatrixServer with bot_status="registered": start goroutine with `/sync` loop
3. Listen for manager replies in real-time

**Hot reload (new server added):**
Strategy: **poll with short interval** (simpler, no webhook failure handling needed).
1. IS polls `GET /api/integration/active-servers/` every 15 seconds
2. Compares current sync loops with server list
3. New server → start sync loop. Removed server → stop sync loop.
4. 15s max latency is acceptable for admin operations (adding a server is rare)

**Manager reply flow:**
1. `/sync` receives new message in escalation room
2. IS checks: is this from a manager (not the bot)?
3. If yes: `POST /api/v1/integration/forward-message` to Django
4. Django routes reply to original channel (Telegram/WhatsApp/Web)

---

## Part 3: White Label SSL Automation

### Flow: Admin sets white label domain

1. Admin sets `webchat_domain = "ai.clientname.de"` on Client
2. `post_save` signal triggers Celery task `provision_ssl_certificate(client_id)`

**Step 1: DNS verification**
- `dig ai.clientname.de` — check if CNAME/A points to our server IP
- NO → `ssl_status = "dns_pending"`, `ssl_error = "DNS not pointing to 188.34.143.153"`
- Celery beat retries every 15 minutes, max 48 hours (192 attempts)
- After 48h without resolution → `ssl_status = "error"`, `ssl_error = "DNS not configured after 48h. Check CNAME/A record."`
- Track with `ssl_first_requested_at` timestamp on Client model

**Step 2: Generate nginx config (HTTP only first)**
- Template: `server_name ai.clientname.de` + `proxy_pass` to React build
- Write to `/etc/nginx/conf.d/whitelabel_{client_id}.conf`
- `nginx -s reload`

**Step 3: Certbot**
- `certbot certonly --webroot -w /var/www/certbot -d ai.clientname.de --non-interactive --agree-tos`
- Success → `ssl_status = "active"`, `ssl_expires_at = expiry date`
- Failure → `ssl_status = "error"`, `ssl_error = certbot output`

**Step 4: Update nginx config with SSL**
- Add `listen 443 ssl`, `ssl_certificate`, `ssl_certificate_key`
- Add HTTP→HTTPS redirect
- `nginx -s reload`

### Docker orchestration for nginx + certbot

Celery workers run inside Django container but need to write nginx configs and run certbot. Approach: **shared volumes + nginx-reload sidecar**.

```
Docker volumes:
  nginx_dynamic_conf → mounted in both Django/Celery and nginx containers
  certbot_webroot → mounted in nginx (read) and Celery (write)
  letsencrypt → mounted in nginx (read) and Celery (write)

Flow:
  1. Celery writes config to nginx_dynamic_conf/whitelabel_{id}.conf
  2. Celery runs certbot (certbot binary installed in Django image)
  3. Celery writes a trigger file: nginx_dynamic_conf/.reload
  4. nginx-reload sidecar (inotifywait loop) detects .reload → nginx -s reload
```

Alternative: install `certbot` in the Django Docker image and mount `/etc/letsencrypt` as shared volume. The nginx container reads certs from the same volume. For nginx reload, use a lightweight sidecar container that watches for config changes.

```yaml
# docker-compose addition
nginx-reload:
  image: alpine
  command: >
    sh -c "apk add inotify-tools &&
    while inotifywait -e modify,create,delete /etc/nginx/conf.d/dynamic/; do
      docker exec ai_nexelin_nginx nginx -s reload 2>/dev/null || true;
      sleep 1;
    done"
  volumes:
    - nginx_dynamic_conf:/etc/nginx/conf.d/dynamic/:ro
    - /var/run/docker.sock:/var/run/docker.sock
```

### HTTP-only template (before certbot)

```nginx
# Used in Step 2, before SSL is provisioned
server {
    listen 80;
    server_name {domain};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Full SSL template (after certbot succeeds)

```nginx
# /etc/nginx/conf.d/whitelabel_{client_id}.conf
# Auto-generated — do not edit manually

server {
    listen 80;
    server_name {domain};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Auto-renewal

Celery beat task `renew_ssl_certificates()` runs daily:
- Query all Clients where `ssl_status="active"` and `ssl_expires_at < now + 30 days`
- Run `certbot renew --cert-name {domain}`
- Update `ssl_expires_at`

### Domain removal

When `webchat_domain` is cleared or client deactivated:
- Remove `/etc/nginx/conf.d/whitelabel_{client_id}.conf`
- `nginx -s reload`
- Optionally: `certbot delete --cert-name {domain}`

---

## Part 4: Dynamic CORS without rebuild

### Current problem

CORS allowed origins are hardcoded in `settings.py` and `CORS_EXTRA_ORIGINS` env var. Adding a new white label domain requires rebuild.

### Solution: Custom CORS middleware

Replace static CORS origin list with dynamic check:

```python
class DynamicCORSMiddleware:
    def __call__(self, request):
        origin = request.headers.get('Origin')
        if origin and self._is_allowed_origin(origin):
            # Set CORS headers

    def _is_allowed_origin(self, origin):
        domain = urlparse(origin).hostname
        # 1. Check static list (nexelin.com, localhost)
        # 2. Check Redis cache
        # 3. If not cached: query Client.objects.filter(
        #        webchat_domain__contains=domain, is_active=True
        #    ).exists()
        # 4. Cache result in Redis for 5 minutes
```

This **fully replaces** `django-cors-headers`. Remove `corsheaders.middleware.CorsMiddleware` from MIDDLEWARE. The custom middleware handles both static origins (nexelin.com, localhost) and dynamic white-label origins from DB.

### CSRF trusted origins

Same dynamic approach for `CSRF_TRUSTED_ORIGINS`. Override `CsrfViewMiddleware` or add a custom middleware that checks white-label domains against DB before CSRF validation:

```python
class DynamicCSRFMiddleware(CsrfViewMiddleware):
    def _origin_verified(self, request):
        # Check static list first, then DB for white-label domains
        if super()._origin_verified(request):
            return True
        origin = request.META.get('HTTP_ORIGIN')
        if origin:
            domain = urlparse(origin).hostname
            return self._is_whitelabel_domain(domain)  # same Redis-cached DB check
        return False
```

---

## Part 5: Admin UI

### MatrixServer admin

```
list_display: [name, domain, bot_status, is_active]
fieldsets:
  - Server Config: name, homeserver_url, domain, registration_shared_secret
  - Bot Status (readonly): bot_user_id, bot_access_token, bot_status, bot_error
  - [Register Bot] button (if bot_status != "registered")
```

### Client admin changes

```
fieldset "Matrix HITL":
  - matrix_server: dropdown (MatrixServer, filter: bot_status="registered")
  - matrix_hitl_enabled: checkbox
  - matrix_manager_user_ids: JSON
  - [Test Connection] button

fieldset "White Label":
  - webchat_domain: text
  - ssl_status (readonly): badge (green/yellow/red)
  - ssl_expires_at (readonly)
  - ssl_error (readonly)
```

---

## What does NOT require rebuild

| Action | Before | After |
|--------|--------|-------|
| Add Matrix server | New container + env vars + restart | Record in Django admin |
| Enable HITL for client | Manual config + restart IS | Checkbox + dropdown |
| Add white label domain | Manual nginx + certbot + CORS in settings.py + rebuild | webchat_domain field in admin |
| Renew SSL | Manual certbot renew | Celery beat automatic |
| Allow CORS for domain | Rebuild with new env vars | Automatic from DB |
| Add managers to HITL | Edit env + restart IS | JSON field in admin |

---

## Key constraints

- All Matrix servers are self-hosted Synapse in one federation — we have admin access and registration_shared_secret
- Frontend is one React build for all white label clients — branding loaded from API by tag
- Integration Service must maintain persistent /sync connections for real-time manager replies
- Room deduplication is guaranteed by PostgreSQL (conversation.matrix_room_id) + select_for_update lock
- Certbot requires DNS to point to our server before SSL provisioning
- nginx runs inside Docker — config generation via shared volume, reload via sidecar
- Let's Encrypt rate limits: 50 certs/week per domain, min 1 hour between certbot retries for same domain
- Secrets (registration_shared_secret, bot_access_token) encrypted at rest in PostgreSQL
- Manager Matrix IDs are not validated against server domain — federation allows cross-server invites

---

## Part 6: Search Engine Upgrade (Qdrant + Cohere Rerank)

### Status: DEPLOYED

Qdrant deployed on production server (188.34.143.153), 12,870 embeddings migrated, dual-write active.

### Architecture

```
User query
    ↓
EmbeddingService.create_embedding(query)  → OpenAI text-embedding-3-small (1536d)
    ↓
QdrantSearchService.search()
    ↓ payload filter: client_id + embedding_model_id
    ↓ retrieve 20 candidates (cosine similarity)
    ↓
Cohere Rerank (rerank-multilingual-v3.0)
    ↓ rerank by semantic relevance to query
    ↓ return top 5
    ↓
ContextBuilder → LLMClient → Response
```

### Qdrant setup

- **Container**: `ai_nexelin_qdrant` in docker-compose, `qdrant_data` named volume
- **Collection**: `nexelin_embeddings` — single collection for all clients
- **Vectors**: size=1536, distance=Cosine
- **Payload indexes**: `client_id` (integer), `embedding_model_id` (integer)
- **Multi-tenancy**: payload filtering by `client_id` (recommended Qdrant approach for this scale)

### Dual-write (qdrant_sync.py)

Django signals on `ClientEmbedding`:
- `post_save` → upsert point to Qdrant
- `post_delete` → delete point from Qdrant
- Registered in `clients/apps.py` → `ready()`
- Fail-open: if Qdrant is unreachable, pgvector still works

### Search service (qdrant_search.py)

`QdrantSearchService` — drop-in replacement for `VectorSearchService`:
- Same `search()` interface, returns same `SearchResult` objects
- Added `query_text` param for Cohere reranking
- Retrieves 20 candidates from Qdrant, reranks to top 5 via Cohere
- Without Cohere key: returns top 5 by cosine similarity (same as pgvector)

### Response generator integration

`ResponseGenerator.__init__()` auto-selects backend:
1. If `USE_QDRANT=True` and `qdrant-client` installed → `QdrantSearchService`
2. If Qdrant init fails → fallback to `VectorSearchService` (pgvector)
3. `settings.USE_QDRANT` flag for manual override

### Cohere Rerank

- Model: `rerank-multilingual-v3.0` (optimized for DE/FR/ES/IT/NL/DA)
- Activated by setting `COHERE_API_KEY` in `.env`
- Without key: reranking skipped, pure cosine similarity
- Rerank scores stored in `metadata['rerank_score']` for debugging

### Settings

```python
USE_QDRANT = env.bool("USE_QDRANT", default=True)
QDRANT_HOST = env("QDRANT_HOST", default="ai_nexelin_qdrant")
QDRANT_PORT = env.int("QDRANT_PORT", default=6333)
QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="nexelin_embeddings")
COHERE_API_KEY = env("COHERE_API_KEY", default="")
COHERE_RERANK_MODEL = env("COHERE_RERANK_MODEL", default="rerank-multilingual-v3.0")
```

### Future: embedding model upgrade

Current: OpenAI `text-embedding-3-small` (1536d)
Planned: Cohere `embed-multilingual-v3.0` (1024d) for better DE/FR/ES/IT/NL/DA support.
Migration path:
1. Add new EmbeddingModel record in Django admin
2. Re-embed all documents via Celery task
3. Create new Qdrant collection with size=1024
4. Switch clients to new model
5. Delete old collection
