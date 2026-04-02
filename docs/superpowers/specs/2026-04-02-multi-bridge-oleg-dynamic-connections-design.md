# Multi-Bridge Integration + Oleg Dynamic Connections

**Date:** 2026-04-02
**Status:** Approved
**Scope:** Meta (Facebook Messenger + Instagram DM) + LinkedIn bridges via mautrix, Oleg as full connection controller

---

## 1. Overview

Extend the existing WhatsApp bridge pattern to support three new messaging platforms — Facebook Messenger, Instagram DM, and LinkedIn Messages — using the mautrix bridge ecosystem. Additionally, give Oleg (the AI assistant) the ability to fully manage bridge connections through chat: initiating auth, showing popups/QR codes, creating ToolConnections, and placing nodes on the Flow Canvas in real-time.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| iMessage | Excluded | Requires physical macOS, no Docker, impractical for VPS B2B |
| Auth method | Popup + Chrome extension cookie extraction | Extension already exists, httpOnly cookies require `chrome.cookies` API |
| Meta ToolCards | Two separate (FB + IG) | Simpler UX, not everyone needs both, separate cookies domains |
| Container scaling | One container per bridge type | Megabridge API v3 designed for multi-user, scale later when needed |
| WhatsApp migration | Last, after new bridges proven stable | Zero risk to existing production flow |
| Oleg's role | Full controller — auth, scope selection, canvas manipulation | Best UX, leverages MCP tool architecture |
| Rich messages | Typed JSON responses rendered as interactive cards | Extensible, fits existing tool response pattern |
| Default scopes | LinkedIn → `["leads"]`, Meta → `["assistant", "manager"]` | Matches business intent per platform |

---

## 2. Infrastructure Layer

### 2.1 New Docker Services (matrix-stack/docker-compose.yml)

Three new containers alongside existing `mautrix-whatsapp`:

```yaml
mautrix-meta-facebook:
  image: dock.mau.dev/mautrix/meta:latest
  restart: unless-stopped
  volumes:
    - ./meta-facebook:/data
  # config.yaml: meta.mode = "facebook"
  # Port: 29319
  # Dedicated PostgreSQL database

mautrix-meta-instagram:
  image: dock.mau.dev/mautrix/meta:latest
  restart: unless-stopped
  volumes:
    - ./meta-instagram:/data
  # config.yaml: meta.mode = "instagram"
  # Port: 29320
  # Dedicated PostgreSQL database

mautrix-linkedin:
  image: dock.mau.dev/mautrix/linkedin:latest
  restart: unless-stopped
  volumes:
    - ./linkedin:/data
  # Port: 29321
  # Dedicated PostgreSQL database
```

Each bridge registers with Synapse via `registration.yaml` (same pattern as WhatsApp).

Health checks + `restart: unless-stopped` for resilience.

### 2.2 Synapse Registration

Each bridge gets its own `registration.yaml` with unique:
- `id`: `mautrix-meta-facebook`, `mautrix-meta-instagram`, `mautrix-linkedin`
- `sender_localpart`: `facebookbot`, `instagrambot`, `linkedinbot`
- `namespaces.users`: `@facebook_.*`, `@instagram_.*`, `@linkedin_.*`

All registered in `homeserver.yaml` → `app_service_config_files`.

### 2.3 Provisioning API v3 (Megabridge)

All Go bridges share the same API spec:

| Endpoint | Purpose |
|----------|---------|
| `POST /v3/login/start/{flowID}` | Initiate login (returns first LoginStep) |
| `POST /v3/login/step/{processID}/{stepID}/cookies` | Submit cookies (Meta, LinkedIn) |
| `POST /v3/login/step/{processID}/{stepID}/display_and_wait` | Confirm QR display (WhatsApp) |
| `GET /v3/logins` | Current login status |
| `POST /v3/logout/{loginID}` | Disconnect |
| `GET /v3/whoami` | Bridge info + user logins |

Auth: Matrix bearer token (`Authorization: Bearer <matrix_access_token>`).

---

## 3. Backend — Universal Bridge Service

### 3.1 New Models

**`BridgeConfig`** — replaces singleton `WhatsAppBridgeConfig`, one row per bridge type:

| Field | Type | Example |
|-------|------|---------|
| `bridge_type` | CharField (unique) | `"whatsapp"`, `"meta-facebook"`, `"meta-instagram"`, `"linkedin"` |
| `is_enabled` | BooleanField | `True` |
| `provisioning_url` | URLField | `http://mautrix-meta-facebook:29319` |
| `provisioning_secret` | CharField | shared secret |
| `bot_username` | CharField | `@facebookbot:domain` |
| `auth_flow` | CharField | `"qr_code"` or `"cookies"` |
| `default_scopes` | JSONField | `["assistant", "manager"]` or `["leads"]` |
| `display_name` | CharField | `"Facebook Messenger"` |
| `icon` | CharField | icon identifier for frontend |

**`ClientBridgeConnection`** — replaces per-client `whatsapp_bridge_*` fields on Client model:

| Field | Type | Description |
|-------|------|-------------|
| `client` | ForeignKey(Client) | |
| `bridge_config` | ForeignKey(BridgeConfig) | |
| `matrix_user_id` | CharField | `@nexelin_client_42:domain` |
| `matrix_access_token` | CharField | |
| `status` | CharField | `disconnected`, `pending`, `connected`, `expired`, `error` |
| `remote_id` | CharField(null) | phone for WA, profile ID for Meta/LinkedIn |
| `connected_at` | DateTimeField(null) | |
| `error` | TextField(null) | |

Unique constraint: `(client, bridge_config)`.

### 3.2 Universal Bridge Service (`services/bridge_service.py`)

Single service class operating through Provisioning API v3:

```python
class BridgeService:
    def create_matrix_user(client, bridge_config) -> ClientBridgeConnection
    def start_login(client, bridge_type) -> dict  # returns {auth_flow, popup_url/qr, login_id, process_id, step_id}
    def submit_cookies(client, bridge_type, cookies: dict) -> dict  # sends to provisioning API
    def check_login_status(client, bridge_type) -> dict  # polls provisioning API
    def logout(client, bridge_type) -> dict
    def get_status(client, bridge_type) -> dict
```

Key logic in `start_login()`:
- Calls `POST /v3/login/start/{flowID}`
- If step type is `display_and_wait` → return QR data (WhatsApp)
- If step type is `cookies` → return `{auth_flow: "cookies", popup_url: "https://instagram.com"}` (Meta, LinkedIn)
- Stores `process_id` + `step_id` in `ClientBridgeConnection` for subsequent `submit_cookies()`

### 3.3 Migration Strategy for WhatsApp

1. New `BridgeService` built alongside existing `whatsapp_bridge.py`
2. Meta + LinkedIn use new service from day one
3. WhatsApp migrates to universal service **last**, only after Meta/LinkedIn proven stable
4. Old `whatsapp_bridge.py` kept as fallback until migration verified
5. Data migration: existing `Client.whatsapp_bridge_*` fields → `ClientBridgeConnection` rows

### 3.4 API Endpoints

New universal endpoints (replace hardcoded WhatsApp ones):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/bridges/` | List available bridge configs |
| GET | `/api/bridges/{type}/status/` | Connection status for current client |
| POST | `/api/bridges/{type}/login/start/` | Initiate login |
| POST | `/api/bridges/{type}/login/cookies/` | Submit cookies from extension |
| GET | `/api/bridges/{type}/login/status/` | Poll login progress |
| POST | `/api/bridges/{type}/logout/` | Disconnect |
| POST | `/api/bridges/message/` | Universal incoming message endpoint (from Integration Service) |

---

## 4. Chrome Extension — Cookie Extraction

### 4.1 New Module in Existing Extension

Add cookie extraction capability to the existing Nexelin Chrome extension.

**Required cookies per platform:**

| Platform | Cookies | Domain |
|----------|---------|--------|
| Facebook | `c_user`, `xs`, `datr`, `sb` | `.facebook.com`, `.messenger.com` |
| Instagram | `sessionid`, `csrftoken`, `mid`, `ig_did`, `ds_user_id` | `.instagram.com` |
| LinkedIn | `li_at`, `JSESSIONID`, `lidc` | `.linkedin.com` |

### 4.2 Flow

1. Nexelin frontend sends message to extension: `{ action: "start_bridge_auth", bridge_type: "meta-instagram", popup_url: "https://instagram.com" }`
2. Extension opens popup tab with `popup_url`
3. Content script on target domain monitors for successful login (presence of key cookies)
4. On login detected: `chrome.cookies.getAll({ domain })` extracts all cookies including httpOnly
5. Extension sends cookies to backend: `POST /api/bridges/{type}/login/cookies/`
6. Extension closes popup tab
7. Extension notifies Nexelin frontend: `{ action: "bridge_auth_complete", bridge_type: "meta-instagram" }`

### 4.3 Manifest.json Additions

```json
{
  "permissions": ["cookies"],
  "host_permissions": [
    "*://*.facebook.com/*",
    "*://*.messenger.com/*",
    "*://*.instagram.com/*",
    "*://*.linkedin.com/*"
  ]
}
```

### 4.4 Extension Not Installed Fallback

Frontend checks extension presence via `chrome.runtime.sendMessage()` before opening popup. If extension not found → show message "Install Nexelin Extension" with Chrome Web Store link.

---

## 5. MCP Tools for Oleg

### 5.1 New Builtin Tools (scope: `assistant`)

**`bridge_start_connection`**

```
Input:  { bridge_type: "meta-instagram" | "meta-facebook" | "linkedin" | "whatsapp" }
Output: { type: "auth_popup", auth_flow: "cookies", popup_url: "https://instagram.com", bridge_type: "meta-instagram" }
     or { type: "qr_code", qr: "base64...", login_id: "xxx" }  (WhatsApp)
```

Frontend chat renders output as interactive card (AuthPopupCard or QRCodeCard).

**`bridge_check_status`**

```
Input:  { bridge_type: "meta-instagram" }
Output: { type: "status_card", status: "connected", remote_id: "user123", connected_at: "2026-04-02T..." }
     or { type: "status_card", status: "disconnected" }
```

**`canvas_add_tool_connection`**

```
Input:  { bridge_type: "meta-instagram", targets: ["assistant", "manager"] }
Output: { type: "connection_created", connection_id: 42, nodes_created: ["assistant-meta-instagram", "manager-meta-instagram"] }
```

Creates `ToolConnection` records in DB, emits WebSocket event. Frontend canvas adds nodes in real-time.

**`canvas_remove_tool_connection`**

```
Input:  { connection_id: 42 }
Output: { type: "connection_removed", connection_id: 42 }
```

**`canvas_list_connections`**

```
Input:  {}
Output: { connections: [{ bridge_type: "whatsapp", status: "connected", targets: ["assistant"], remote_id: "+380..." }, ...] }
```

Oleg uses this to understand current state before making recommendations.

### 5.2 Example Dialog

```
User: "Хочу підключити інсту"

Oleg: [calls canvas_list_connections] → Instagram not connected
Oleg: [calls bridge_start_connection({ bridge_type: "meta-instagram" })]
Oleg: "Давай підключимо Instagram! Натисни кнопку нижче і залогінся у свій акаунт."
      + [AuthPopupCard: icon=instagram, button="Увійти в Instagram"]

... user clicks → popup opens instagram.com → logs in → extension extracts cookies → backend connects ...

Oleg: "Instagram підключено! Рекомендую додати до assistant і manager — для клієнтської комунікації. Або можеш вибрати інше:"
      + [TargetSelectorCard: buttons="Assistant", "Manager", "Обидва", "Leads"]

User clicks: "Обидва"

Oleg: [calls canvas_add_tool_connection({ bridge_type: "meta-instagram", targets: ["assistant", "manager"] })]
Oleg: "Готово! Instagram додано на canvas для assistant і manager."
      + [Canvas updates in real-time with new nodes]
```

### 5.3 Rich Message Protocol

Tool responses with `type` field are rendered as interactive components in chat:

| type | Frontend Component | Description |
|------|-------------------|-------------|
| `auth_popup` | `AuthPopupCard` | Platform icon + "Sign in" button → opens popup |
| `qr_code` | `QRCodeCard` | QR image + polling indicator |
| `connection_created` | animation trigger | Canvas node appears with animation |
| `connection_removed` | animation trigger | Canvas node removed with animation |
| `status_card` | `ConnectionStatusCard` | Bridge status + disconnect button |
| `target_selector` | `TargetSelectorCard` | Buttons for scope selection |

---

## 6. Frontend Changes

### 6.1 Chat — Rich Message Components

New components in Oleg's chat, rendered when tool response contains `type` field:

- **`AuthPopupCard`** — platform icon, name, "Sign in" button. Click → message to extension → popup. After cookies received → card changes to "Connected".
- **`QRCodeCard`** — inline QR code with polling (reuse from ConnectModal). For WhatsApp.
- **`ConnectionStatusCard`** — bridge status display with disconnect button.
- **`TargetSelectorCard`** — scope selection buttons. Click sends choice back as user message to Oleg.

### 6.2 Canvas — Real-time Updates via WebSocket

Backend emits events on ToolConnection changes:

```json
{ "event": "tool_connection_created", "data": { "id": 42, "tool_slug": "meta-instagram", "targets": ["assistant", "manager"] } }
{ "event": "tool_connection_removed", "data": { "id": 42 } }
{ "event": "tool_connection_status_changed", "data": { "id": 42, "status": "connected" } }
```

Canvas component subscribes and updates nodes/edges with animation.

### 6.3 New ToolCard Seed Data

Three new ToolCard records (via migration):

| slug | name | auth_type | transport | default_scopes |
|------|------|-----------|-----------|----------------|
| `meta-facebook` | Facebook Messenger | `cookies` | `builtin` | `["assistant", "manager"]` |
| `meta-instagram` | Instagram DM | `cookies` | `builtin` | `["assistant", "manager"]` |
| `linkedin` | LinkedIn Messages | `cookies` | `builtin` | `["leads"]` |

---

## 7. Integration Service (Go) — Changes

### 7.1 Room → Bridge Type Mapping

Currently hardcoded for WhatsApp. Change to dynamic routing:

- Store mapping `room_id → bridge_type` based on bot user presence in room:
  - `@whatsappbot:domain` → `whatsapp`
  - `@facebookbot:domain` → `meta-facebook`
  - `@instagrambot:domain` → `meta-instagram`
  - `@linkedinbot:domain` → `linkedin`

### 7.2 Universal Message Endpoint

Replace `POST /clients/whatsapp/bridge/message/` with `POST /api/bridges/message/`:

```json
{
  "client_id": 42,
  "bridge_type": "meta-instagram",
  "sender_id": "user123",
  "message_text": "Hello",
  "room_id": "!abc:domain"
}
```

Django routes to appropriate orchestrator scope based on `bridge_type` + `ToolConnection.target`.

---

## 8. Error Handling

| Error | Detection | Response |
|-------|-----------|----------|
| **Cookies expired** | Bridge sends Matrix "logged out" event | `status: 'expired'`. Oleg proactively offers re-auth on next interaction |
| **Bridge container down** | Docker health check fails | Auto-restart. After 3 failures → `status: 'error'` for all connections, admin alert |
| **Cookies rejected** | Provisioning API returns error on `/v3/login/step/.../cookies` | Oleg: "Failed to connect, try logging in again" |
| **LinkedIn rate limit/ban** | Bridge logs warning | `status: 'error'` with details. Oleg warns user |
| **Extension not installed** | `chrome.runtime.sendMessage()` fails | Show "Install Nexelin Extension" with link |
| **Matrix user creation fails** | API error | Retry 3x → `status: 'error'` → Oleg: "Technical issue, try later" |

### Session Expiry Expectations

| Platform | Cookie Lifetime | Expire Trigger |
|----------|----------------|----------------|
| WhatsApp | Months | Phone offline >14 days |
| Facebook | Weeks-months | Password change, security alert |
| Instagram | Weeks | Password change, new location |
| LinkedIn | Days-weeks | Aggressive session rotation |

LinkedIn is most problematic — Oleg should proactively check and offer re-auth.

---

## 9. Out of Scope

- iMessage bridge (requires physical macOS)
- Telegram bridge (not requested, can be added later with same pattern)
- WhatsApp migration to universal service (happens after Meta/LinkedIn stable)
- Meta Business API integration (separate from mautrix bridge, already exists)
- Browser extension for non-Chrome browsers
- End-to-end encryption for bridge messages
