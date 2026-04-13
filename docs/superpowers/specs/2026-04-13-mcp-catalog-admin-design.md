# MCP Catalog Admin — Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Branch:** feature/admin-foundation

## Goal

Add an owner-facing admin page for managing MCP servers (ToolCards). Owner pastes a URL, the system auto-discovers available tools, validates connectivity, creates a ToolCard, and auto-connects it to all existing and future clients.

## Decisions

| Question | Answer |
|---|---|
| Auto-connect scope | All existing + new clients (option A) |
| Discovery | Auto on save + manual Refresh button (option A) |
| Default targets | Owner picks via checkboxes: assistant, manager, leads (option C) |
| URL validation | Block save if URL unreachable or list_tools() fails (option A) |
| Approach | Minimal CRUD + URL discovery (approach 1) |

---

## 1. Backend API

### 1.1 ViewSet: `ToolCardOwnerViewSet`

File: `backend/Jeeves/tools/views_owner.py` (new)

Mixin: `_OwnerOnlyMixin` (JWTAuthentication + IsOwner), same pattern as `EmbeddingModel/views_owner.py`.

| Endpoint | Method | Action |
|---|---|---|
| `GET /owner/tools/` | list | All ToolCards, annotated with `connections_count` |
| `GET /owner/tools/:id/` | retrieve | Single ToolCard detail |
| `POST /owner/tools/` | create | Manual ToolCard creation (builtin tools) |
| `POST /owner/tools/discover/` | discover | URL in → connect via MCP SDK → return server_name, tools list. Does NOT save. |
| `POST /owner/tools/from-url/` | create_from_url | URL + owner metadata → discover → validate → create ToolCard → auto-connect all clients |
| `PUT /owner/tools/:id/` | update | Update ToolCard metadata |
| `POST /owner/tools/:id/refresh/` | refresh | Re-connect to MCP server, update tools_schema |
| `DELETE /owner/tools/:id/` | destroy | Delete ToolCard + cascade ToolConnections |

### 1.2 Discovery Flow

```
POST /owner/tools/discover/
Body: { "url": "https://mcp-server.example.com/sse" }

1. Determine transport: if URL ends with /sse → sse, else → streamable_http
2. Connect: sse_client(url) or streamable_http_client(url)
3. ClientSession → initialize() → list_tools()
4. Return: {
     "server_name": "...",
     "tools": [{"name": "...", "description": "...", "inputSchema": {...}}]
   }
5. On failure (timeout, connection refused, invalid response) → 400 with error message
```

Uses existing `mcp` Python SDK already in the project (see `mcp_hub/executor.py`).

### 1.3 Auto-Connect on Create

After ToolCard is saved via `from-url`:

```python
from django.utils import timezone

now = timezone.now()
clients = Client.objects.filter(is_active=True)  # or all()
targets = request.data.get('targets', ['assistant'])

for client in clients:
    for target in targets:
        ToolConnection.objects.get_or_create(
            client=client,
            tool_card=tool_card,
            target=target,
            defaults={'status': 'connected', 'enabled': True, 'connected_at': now},
        )
```

The existing `auto_connect_system_tools` signal handles new clients created after the ToolCard exists (for `is_system=True` cards). External MCP servers added via URL will also be marked `is_system=True` so the signal covers them.

### 1.4 Serializer: `ToolCardOwnerSerializer`

File: `backend/Jeeves/tools/serializers.py` (append)

Fields:
- `id`, `name`, `slug`, `tagline`, `tagline_i18n`, `description`
- `icon`, `color`, `category`
- `mcp_server_url`, `transport_type`, `is_builtin`, `builtin_handler`
- `tools_schema`, `scope_schema`, `skill_scopes`
- `auth_type`, `auth_config`
- `is_active`, `is_featured`, `is_system`
- `sort_order`
- `connections_count` (read-only, annotated)
- `created_at`, `updated_at`

`slug` auto-generated from `name` on create if not provided.

### 1.5 URL Registration

File: `backend/Jeeves/concierge_platform/urls.py` (append router registration)

```python
router.register(r'owner/tools', tools_owner_views.ToolCardOwnerViewSet, basename='owner-tool')
```

Plus manual paths for `discover` and `from-url` custom actions.

---

## 2. Frontend

### 2.1 API Client

File: `frontend/src/api/owner.js` (append)

```javascript
export const mcpServersAPI = {
  list: () => api.get('/owner/tools/'),
  detail: (id) => api.get(`/owner/tools/${id}/`),
  create: (data) => api.post('/owner/tools/', data),
  update: (id, data) => api.put(`/owner/tools/${id}/`, data),
  delete: (id) => api.delete(`/owner/tools/${id}/`),
  discover: (url) => api.post('/owner/tools/discover/', { url }),
  createFromUrl: (data) => api.post('/owner/tools/from-url/', data),
  refresh: (id) => api.post(`/owner/tools/${id}/refresh/`),
};
```

### 2.2 MCPServersPage

File: `frontend/src/pages/owner/MCPServersPage.jsx`
Route: `/owner/mcp-servers`

Table columns:
- **Name** — ToolCard name
- **Category** — badge (communication, productivity, etc.)
- **Transport** — builtin / sse / streamable_http
- **Tools** — count from tools_schema array length
- **Connections** — connections_count / total clients
- **Active** — yes/no
- **Actions** — Edit link, Delete button (disabled for builtin)

Header: "+ Add MCP Server" button.

Empty state: "No MCP servers configured. Add your first one."

Follows exact same pattern as `LLMProvidersPage.jsx`.

### 2.3 MCPServerEditPage

File: `frontend/src/pages/owner/MCPServerEditPage.jsx`
Routes: `/owner/mcp-servers/new`, `/owner/mcp-servers/:id`

**New server flow:**
1. Input field: "MCP Server URL"
2. Button: "Discover" → calls `mcpServersAPI.discover(url)`
3. On success: shows preview card with server name + list of tools (name, description)
4. Form fields appear: icon (text input), color (color picker), category (select), targets (checkboxes: assistant, manager, leads)
5. "Save & Connect All Clients" button → calls `mcpServersAPI.createFromUrl({url, icon, color, category, targets, ...})`

**Edit existing flow:**
1. Standard form with all metadata fields
2. "Refresh Tools" button → calls `mcpServersAPI.refresh(id)` → updates tools_schema display
3. Read-only section: "Available Tools" — renders tools_schema as a list

Follows pattern of `LLMProviderEditPage.jsx`.

### 2.4 Sidebar

File: `frontend/src/components/owner/OwnerSidebar.jsx`

Add `{ to: '/owner/mcp-servers', label: 'MCP Servers' }` between "Clients" and "AI Providers" in NAV array.

### 2.5 Routes

File: `frontend/src/App.jsx`

```jsx
<Route path="mcp-servers" element={<MCPServersPage />} />
<Route path="mcp-servers/new" element={<MCPServerEditPage />} />
<Route path="mcp-servers/:id" element={<MCPServerEditPage />} />
```

---

## 3. Seed Builtin MCP Servers

Data migration: `tools/migrations/XXXX_seed_builtin_tools.py`

Creates ToolCards for the 8 existing MCP servers:

| Name | Slug | Category | Builtin Handler | System |
|---|---|---|---|---|
| RAG Knowledge Search | rag | ai | mcp_servers.rag.server | Yes |
| Escalation | escalation | communication | mcp_servers.escalation.server | Yes |
| Lead Management | leads | crm | mcp_servers.leads.server | Yes |
| Email | email | communication | mcp_servers.email.server | Yes |
| Coaching | coaching | ai | mcp_servers.coaching.server | No |
| Sales Intelligence | sales-intel | analytics | mcp_servers.sales_intel.server | No |
| Memory | memory | ai | mcp_servers.memory.server | Yes |
| XLSX Export | xlsx | productivity | mcp_servers.xlsx.server | No |

All with `transport_type='builtin'`, `is_builtin=True`, `is_active=True`.

System tools (rag, escalation, leads, email, memory) auto-connect to all clients. Non-system tools (coaching, sales-intel, xlsx) appear in catalog but clients connect manually.

The migration also creates ToolConnections for all existing clients for system tools.

---

## 4. Implementation Notes

- `MCPExecutor._call_mcp()` currently only supports SSE transport. The `from-url` endpoint should default `transport_type` to `'sse'`. Streamable HTTP support can be added later when the MCP SDK stabilizes it.
- Discovery timeout: 10 seconds max for connecting + list_tools(). Prevents hanging on unresponsive servers.
- Slug auto-generation: `django.utils.text.slugify(name)` with uniqueness check (append `-2`, `-3` etc. if taken).

## 5. Out of Scope

- ToolCard marketplace / import-export between instances
- OAuth2 flow for external MCP servers (auth_type stays 'none' for now)
- Per-client enable/disable of specific MCP tools from owner panel (existing client portal handles this)
- EdgeMiddleware management from owner panel
- MCP server health monitoring / uptime checks
