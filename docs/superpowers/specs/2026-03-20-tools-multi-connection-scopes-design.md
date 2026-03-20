# Tools Multi-Connection & Scopes — Design Spec

## Problem

Currently `ToolConnection` has `unique_together = ['client', 'tool_card']` — one tool can only connect to ONE core node. Real-world need: rag-search should connect to BOTH Assistant (Oleg) and Manager (Vasya) with **different scopes** (Oleg has full knowledge, Vasya only B2C). Same for email, telegram, etc.

## Architecture Decision

### ToolConnection: single-target → multi-target

Change `unique_together` from `['client', 'tool_card']` to `['client', 'tool_card', 'target']`.

Each connection = one tool + one target + specific scope/permissions.

### New field: `scope` on ToolConnection

```python
class ToolConnection(models.Model):
    # ... existing fields ...
    scope = models.JSONField(
        default=dict, blank=True,
        help_text='Per-target permissions/scope for this connection')
```

Scope structure (examples):

```json
// rag-search → assistant (Oleg): full knowledge access
{
  "knowledge": "all",
  "description": "Full access to all knowledge blocks"
}

// rag-search → manager (Vasya): B2C knowledge only
{
  "knowledge": "b2c_only",
  "tags": ["b2c", "sales", "pricing"],
  "description": "Only B2C-relevant knowledge blocks"
}

// email → assistant (Oleg): full email access
{
  "can_read": true,
  "can_send": true,
  "can_analyze": true,
  "description": "Read, send, analyze all emails"
}

// email → manager (Vasya): limited B2C sending only
{
  "can_read": false,
  "can_send": true,
  "can_analyze": false,
  "send_scope": "b2c_only",
  "requires_client_request": true,
  "description": "Send B2C emails only when client requests"
}

// telegram → assistant: full messaging
{
  "can_receive": true,
  "can_send": true,
  "description": "Full Telegram messaging"
}

// telegram → manager: notify + escalation only
{
  "can_receive": true,
  "can_send": true,
  "send_scope": "escalation_only",
  "description": "Receive messages, send only escalation responses"
}
```

Scope is **freeform JSON per tool** — each tool/skill defines its own scope schema. The admin (Dasha) configures scopes manually per client. In the future, `ToolCard` can define a `scope_schema` field describing available scope options.

### ToolCard: scope_schema (future-ready)

Add optional field to ToolCard for documenting available scope options:

```python
scope_schema = models.JSONField(
    default=dict, blank=True,
    help_text='Available scope options for this tool')
```

Example:
```json
// email-smtp scope_schema
{
  "fields": [
    {"name": "can_read", "type": "boolean", "label": "Can read emails", "default": true},
    {"name": "can_send", "type": "boolean", "label": "Can send emails", "default": true},
    {"name": "can_analyze", "type": "boolean", "label": "Can analyze email content", "default": true},
    {"name": "send_scope", "type": "select", "label": "Send scope", "options": ["all", "b2c_only", "internal_only"]},
    {"name": "requires_client_request", "type": "boolean", "label": "Only send when client requests", "default": false}
  ]
}
```

This is NOT enforced by backend — it's metadata for UI to render scope configuration forms in the future.

---

## Backend Changes

### 1. Model: ToolConnection

```python
class ToolConnection(models.Model):
    # ... existing fields unchanged ...
    scope = models.JSONField(default=dict, blank=True,
        help_text='Per-target permissions/scope for this connection')

    class Meta:
        unique_together = ['client', 'tool_card', 'target']  # WAS: ['client', 'tool_card']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['tool_card', 'status']),
        ]
```

### 2. Model: ToolCard

Add:
```python
scope_schema = models.JSONField(default=dict, blank=True,
    help_text='Available scope options for UI rendering')
```

### 3. Migration

- Change unique_together
- Add `scope` field to ToolConnection
- Add `scope_schema` field to ToolCard
- Data migration: existing connections keep their current target, no scope changes needed

### 4. ToolCatalogView

Currently returns single `connection: {...}` per tool. Change to `connections: [...]`:

```python
# Before
'connection': { 'id': conn.pk, 'status': ..., 'target': ... } if conn else None

# After
'connections': [
    {
        'id': conn.pk,
        'status': conn.status,
        'enabled': conn.enabled,
        'target': conn.target,
        'scope': conn.scope,
        'connected_at': ...,
        'middlewares': [...],
    }
    for conn in tool_connections
]
```

Where `tool_connections` is a list (not single object). Build connections dict as `{tool_card_id: [conn1, conn2, ...]}`.

### 5. ToolConnectView

Currently `update_or_create(client=client, tool_card=tool_card)`. Change to include `target`:

```python
conn, _ = ToolConnection.objects.update_or_create(
    client=client, tool_card=tool_card, target=target,
    defaults={...})
```

### 6. ToolDisconnectView

Currently disconnects ALL connections for a tool. Change to accept optional `target` param:

```python
def post(self, request, slug):
    target = request.data.get('target')  # optional
    qs = ToolConnection.objects.filter(client=client, tool_card__slug=slug)
    if target:
        qs = qs.filter(target=target)
    updated = qs.update(status='disconnected', enabled=False)
```

### 7. FlowConnectionsView.post

Same — include target in `update_or_create`:

```python
conn, created = ToolConnection.objects.update_or_create(
    client=client, tool_card=tool_card, target=target,
    defaults={...})
```

### 8. FlowConnectionDetailView.patch

When changing target: this now means creating a NEW connection (new target) and deleting the old one. Or just updating target field — but then unique constraint might conflict. Simplest: PATCH only updates scope/position/enabled, NOT target. To change target = delete old + create new.

### 9. API for scope management

```
PATCH /api/tools/flow/connections/{id}/  — update scope, position, enabled (existing endpoint)
```

Add `scope` to FlowConnectionUpdateSerializer:
```python
class FlowConnectionUpdateSerializer(serializers.Serializer):
    target = serializers.ChoiceField(choices=..., required=False)  # REMOVE this
    position_x = serializers.FloatField(required=False, allow_null=True)
    position_y = serializers.FloatField(required=False, allow_null=True)
    enabled = serializers.BooleanField(required=False)
    scope = serializers.JSONField(required=False)  # ADD this
```

---

## Frontend Changes

### 1. Data model adaptation

Tool object from catalog API changes:

```js
// Before
tool.connection = { id, status, enabled, target, middlewares } | null

// After
tool.connections = [
  { id, status, enabled, target, scope, middlewares },
  { id, status, enabled, target, scope, middlewares },
]  // can be empty array
```

### 2. FlowCanvas: getEffectiveTargets

```js
const getEffectiveTargets = useCallback((tool) => {
  const conns = tool.connections?.filter(c => c.status === 'connected' && c.enabled) || [];
  if (conns.length > 0) return conns.map(c => c.target);
  return getToolTargets(tool.slug);  // fallback for unconnected tools
}, []);
```

### 3. FlowCanvas: connectedTools

```js
const connectedTools = useMemo(
  () => tools.filter(t => t.connections?.some(c => c.status === 'connected' && c.enabled)),
  [tools]
);
```

### 4. ToolsPage: handleConnect

Always creates new connection (not update):

```js
const handleConnect = useCallback(async (slug, target) => {
  const tool = tools.find(t => t.slug === slug);
  if (!tool) return;

  // Check if already connected to THIS target
  const existingConn = tool.connections?.find(
    c => c.target === target && c.status === 'connected' && c.enabled
  );
  if (existingConn) return; // already connected to this target

  if (tool.auth_type === 'none') {
    await toolsAPI.createFlowConnection(slug, target);
  } else {
    // Check if tool has ANY active connection (credentials exist)
    const anyConn = tool.connections?.find(c => c.status === 'connected');
    if (anyConn) {
      // Credentials already exist — just create new connection to different target
      await toolsAPI.createFlowConnection(slug, target);
    } else {
      showToast('...', 'Connect tool first via card');
      return;
    }
  }
  loadTools();
}, [tools, showToast]);
```

### 5. ToolsPage: handleDisconnect

Disconnect specific target:

```js
const handleDisconnect = useCallback(async (slug, target) => {
  await toolsAPI.disconnect(slug, target);  // pass target
  loadTools();
}, []);
```

### 6. toolsAPI.disconnect

```js
disconnect: (slug, target) => api.post(`/tools/${slug}/disconnect/`, { target }),
```

### 7. CanvasToolNode: scope chips

Show all connected targets:

```js
const targets = tool.connections
  ?.filter(c => c.status === 'connected' && c.enabled)
  .map(c => c.target) || [];
```

### 8. ToolPopover: disconnect specific connection

Show each connection with its target + scope, with individual disconnect button:

```jsx
{tool.connections?.filter(c => c.status === 'connected').map(conn => (
  <div key={conn.id}>
    <span>{conn.target}</span>
    <span className="text-xs text-gray-400">{conn.scope?.description || ''}</span>
    <button onClick={() => onDisconnect(tool.slug, conn.target)}>Disconnect</button>
  </div>
))}
```

### 9. FlowCanvas: handleDeleteEdge

Pass target to disconnect:

```js
const handleDeleteEdge = useCallback((edgeId) => {
  const conn = connections.find(c => c.id === edgeId);
  if (!conn || conn.target === 'escalation' || !conn.toolSlug) return;
  if (window.confirm('Disconnect this tool?')) {
    onDisconnect?.(conn.toolSlug, conn.target);  // pass target
  }
  setSelectedEdge(null);
  setContextMenu(null);
}, [connections, onDisconnect]);
```

### 10. EdgeMiddleware: connection ID lookup

Middleware is per-connection. When tool has multiple connections, need correct connection ID:

```js
const handleMiddlewareAttach = useCallback(async (conn, skillSlug) => {
  // conn already has toolSlug and target from connections array
  const tool = tools.find(t => t.slug === conn.toolSlug);
  const toolConn = tool?.connections?.find(c => c.target === conn.target && c.status === 'connected');
  if (!toolConn?.id) return;
  await toolsAPI.attachMiddleware(toolConn.id, skillSlug);
  loadTools();
}, [tools]);
```

---

## What stays the same

- EdgeMiddleware model — unchanged (FK to ToolConnection, works with multi-connections)
- skill_scopes on ToolCard — unchanged
- Flow canvas visual layout — unchanged (just shows more edges per tool now)
- Auth flow (FlipToolCard) — first connection still goes through auth, subsequent connections to other targets reuse credentials
- MCP executor — reads ToolConnection per target, already filtered by client+enabled

---

## Scope Definitions Per Tool (confirmed by Dasha 2026-03-20)

### RAG Search (Knowledge Base)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | Повний доступ: всі знання (all + assistant + manager) |
| **Vasya (Manager)** | Обмежений: тільки all + manager знання |
| **Leads** | ❌ Немає доступу |

### Email (email-smtp)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | `can_read: true, can_send: true, can_analyze: true` — повний доступ |
| **Vasya (Manager)** | `can_read: false, can_send: true, send_scope: "b2c", requires_oleg_instruction: true` — тільки B2C відправка за вказівкою Олега |
| **Leads** | `can_send: true, send_scope: "owner_only", send_type: "leads_excel"` — відправка Excel таблиць з лідами тільки на мейл юзера (власника), не стороннім |

### Telegram Bot
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | `can_receive: true, can_read: true, can_send: true, can_analyze: true` — повний доступ |
| **Vasya (Manager)** | `can_receive: true, can_send: true, role: "sales", uses_rag: true, can_escalate: true` — продажник з RAG або ескалація (два різних боти) |
| **Leads** | `can_detect_leads: true, sources: ["bot", "personal"]` — детекція лідів з ботів і персональних Telegram |

### WhatsApp Business (Meta API)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | `can_receive: true, can_read: true, can_send: true, can_analyze: true` — повний доступ |
| **Vasya (Manager)** | `can_receive: true, can_send: true, role: "sales", uses_rag: true, can_escalate: true` — продажник/RAG/ескалація |
| **Leads** | `can_detect_leads: true` — детекція лідів |

### WhatsApp Personal (Bridge)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | Повний доступ (як WhatsApp Business) |
| **Vasya (Manager)** | Продажник/RAG/ескалація (як WhatsApp Business) |
| **Leads** | Детекція лідів (як WhatsApp Business) |

### Web Chat (Widget)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | `can_receive: true, can_send: true, can_analyze: true` — повний доступ |
| **Vasya (Manager)** | `can_receive: true, can_send: true, role: "sales", uses_rag: true, can_escalate: true` — продажник/RAG/ескалація |
| **Leads** | `can_detect_leads: true` — детекція лідів з веб-чату |

### Live Manager (HITL Matrix)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | ❌ Не стосується |
| **Vasya (Manager)** | `can_escalate: true` — шле ескалацію в Matrix, живий менеджер відповідає через Matrix, Вася передає відповідь клієнту |
| **Leads** | ❌ Не стосується |

### Translation (Auto Translation)
| Target | Scopes |
|--------|--------|
| **Oleg (Assistant)** | `bidirectional: true` — переклад в обидва боки (клієнт ↔ AI) |
| **Vasya (Manager)** | `bidirectional: true` — переклад в обидва боки |
| **Leads** | ❌ Не стосується |

---

## Open questions (still TODO)

1. **Scope UI**: should scopes be configurable from the canvas (popup on edge click) or from a separate settings page?
2. **Credentials sharing**: when email is connected to both Oleg and Vasya, do they share the same SMTP credentials? Does Vasya have his own "from_name" or "from_address"?

---

## Migration plan

1. Add `scope` field + `scope_schema` field (non-breaking)
2. Change `unique_together` (migration handles existing data — no duplicates exist)
3. Update backend views (backward-compatible: `connections` array, old `connection` field kept temporarily)
4. Update frontend to read `connections[]`
5. Remove old `connection` singular field after frontend migration
