# Multi-Connection & Scopes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable tools to connect to multiple core nodes (Assistant, Manager, Leads) simultaneously with per-connection scopes, gated by feature flag.

**Architecture:** Change `ToolConnection.unique_together` from `['client', 'tool_card']` to `['client', 'tool_card', 'target']`. Add `scope` JSONField to ToolConnection, `scope_schema` to ToolCard. Catalog API returns `connections: [...]` array instead of single `connection`. Frontend adapts to multi-connection data model. All gated by `mcp_tools_multi_connection` feature flag.

**Tech Stack:** Django 5.x, DRF, PostgreSQL, React 18, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-20-tools-multi-connection-scopes-design.md`

**CRITICAL RULE:** All new code paths gated by `FeatureFlag.is_enabled('mcp_tools_multi_connection', client)`. When flag is off — old single-connection behavior unchanged.

---

## File Structure

### Backend (modify)
- `p004_ai_nexelin/MASTER/tools/models.py` — add `scope` to ToolConnection, `scope_schema` to ToolCard, change unique_together
- `p004_ai_nexelin/MASTER/tools/serializers.py` — add `scope` to serializers, update FlowConnectionUpdateSerializer
- `p004_ai_nexelin/MASTER/tools/views.py` — multi-connection catalog response, connect/disconnect per target
- `p004_ai_nexelin/MASTER/tools/admin.py` — show scope fields
- `p004_ai_nexelin/MASTER/clients/serializers.py` — add flag to get_feature_flags

### Backend (create)
- `p004_ai_nexelin/MASTER/tools/migrations/XXXX_multi_connection_scopes.py`

### Frontend (modify)
- `nextlen/src/api/tools.js` — disconnect accepts target
- `nextlen/src/pages/ToolsPage.jsx` — adapt handlers to multi-connection
- `nextlen/src/components/tools/FlowCanvas.jsx` — connectedTools/getEffectiveTargets use connections[]
- `nextlen/src/components/tools/ToolPopover.jsx` — show per-connection disconnect
- `nextlen/src/locales/en/translation.json` — scope-related keys

---

## Task 1: Backend — Add scope + scope_schema fields, change unique_together

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/models.py:50-52,91-113`

- [ ] **Step 1: Add scope_schema to ToolCard**

After `skill_scopes` field (line 52), add:
```python
    scope_schema = models.JSONField(
        default=dict, blank=True,
        help_text='Available scope options for UI rendering')
```

- [ ] **Step 2: Add scope to ToolConnection**

After `config` field (line 93), add:
```python
    scope = models.JSONField(
        default=dict, blank=True,
        help_text='Per-target permissions/scope for this connection')
```

- [ ] **Step 3: Change unique_together**

Replace line 109:
```python
# BEFORE
unique_together = ['client', 'tool_card']

# AFTER
unique_together = ['client', 'tool_card', 'target']
```

- [ ] **Step 4: Create and run migration**

```bash
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py makemigrations tools -n "multi_connection_scopes"
python p004_ai_nexelin/manage.py migrate tools
```

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/models.py p004_ai_nexelin/MASTER/tools/migrations/
git commit -m "feat(tools): add scope fields, change unique_together for multi-connection"
```

---

## Task 2: Backend — Update serializers

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/serializers.py`

- [ ] **Step 1: Add scope to FlowConnectionSerializer**

In `FlowConnectionSerializer.Meta.fields` (line 52-54), add `'scope'`:
```python
        fields = ['id', 'slug', 'name', 'icon', 'color', 'category',
                  'status', 'target', 'scope', 'enabled',
                  'position_x', 'position_y', 'connected_at', 'middlewares']
```

- [ ] **Step 2: Update FlowConnectionUpdateSerializer — replace target with scope**

Replace `FlowConnectionUpdateSerializer` (lines 57-63):
```python
class FlowConnectionUpdateSerializer(serializers.Serializer):
    """For PATCH — update scope, position, or enabled. NOT target (delete+create instead)."""
    position_x = serializers.FloatField(required=False, allow_null=True)
    position_y = serializers.FloatField(required=False, allow_null=True)
    enabled = serializers.BooleanField(required=False)
    scope = serializers.JSONField(required=False)
```

- [ ] **Step 3: Update ToolCatalogItemSerializer — change connection to connections**

Replace line 79:
```python
# BEFORE
connection = serializers.DictField(allow_null=True)

# AFTER
connections = serializers.ListField(child=serializers.DictField(), default=list)
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/serializers.py
git commit -m "feat(tools): add scope to serializers, connections[] in catalog"
```

---

## Task 3: Backend — Update views for multi-connection

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/views.py`

- [ ] **Step 1: Update ToolCatalogView — connections as list**

Replace the connections dict building (lines 23-28) and the item building (lines 38-71):

```python
class ToolCatalogView(APIView):
    """GET /api/tools/catalog/ — all available tools with connection status."""

    def get(self, request):
        client = getattr(request, 'client', None)
        lang = request.query_params.get('lang') or request.headers.get(
            'Accept-Language', '')[:2] or 'en'
        tools = ToolCard.objects.filter(is_active=True).order_by('sort_order', 'name')

        # Build connections: {tool_card_id: [conn1, conn2, ...]}
        from collections import defaultdict
        connections = defaultdict(list)
        if client:
            conns_qs = ToolConnection.objects.filter(
                client=client
            ).prefetch_related('middlewares__skill_card')
            for tc in conns_qs:
                connections[tc.tool_card_id].append(tc)

        from MASTER.nexelin_platform.models import FeatureFlag
        multi_conn = client and FeatureFlag.is_enabled('mcp_tools_multi_connection', client)

        result = []
        for tool in tools:
            tool_conns = connections.get(tool.pk, [])
            tagline = tool.tagline
            if tool.tagline_i18n and lang in tool.tagline_i18n:
                tagline = tool.tagline_i18n[lang]

            def _serialize_conn(conn):
                return {
                    'id': conn.pk,
                    'status': conn.status,
                    'enabled': conn.enabled,
                    'target': conn.target,
                    'scope': conn.scope,
                    'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
                    'last_used_at': conn.last_used_at.isoformat() if conn.last_used_at else None,
                    'middlewares': [
                        {
                            'id': mw.pk,
                            'skill_slug': mw.skill_card.slug,
                            'skill_name': mw.skill_card.name,
                            'skill_icon': mw.skill_card.icon,
                            'skill_color': mw.skill_card.color,
                            'order': mw.order,
                            'enabled': mw.enabled,
                        }
                        for mw in conn.middlewares.all()
                    ],
                }

            item = {
                'slug': tool.slug,
                'name': tool.name,
                'tagline': tagline,
                'tagline_i18n': tool.tagline_i18n,
                'description': tool.description,
                'icon': tool.icon,
                'color': tool.color,
                'category': tool.category,
                'is_featured': tool.is_featured,
                'auth_type': tool.auth_type,
                'auth_config': tool.auth_config if not tool_conns else None,
                'skill_scopes': tool.skill_scopes,
                'scope_schema': tool.scope_schema,
            }

            if multi_conn:
                item['connections'] = [_serialize_conn(c) for c in tool_conns]
                # backward compat: also include single connection
                first_conn = next((c for c in tool_conns if c.status == 'connected' and c.enabled), None)
                item['connection'] = _serialize_conn(first_conn) if first_conn else None
            else:
                conn = next((c for c in tool_conns), None)
                item['connection'] = _serialize_conn(conn) if conn else None

            result.append(item)

        return Response(result)
```

- [ ] **Step 2: Update ToolConnectView — include target in update_or_create**

In `ToolConnectView.post()`, change all `update_or_create` calls to include `target`:

Line 111-113 (qr_code):
```python
            conn, _ = ToolConnection.objects.update_or_create(
                client=client, tool_card=tool_card, target=target,
                defaults={'status': 'pending'})
```

Lines 118-128 (api_key, credentials, none):
```python
        conn, _ = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card, target=target,
            defaults={
                'credentials': credentials,
                'status': 'connected',
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            })
```

- [ ] **Step 3: Update ToolDisconnectView — accept optional target**

Replace lines 135-146:
```python
    def post(self, request, slug):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        target = request.data.get('target')  # optional
        qs = ToolConnection.objects.filter(client=client, tool_card__slug=slug)
        if target:
            qs = qs.filter(target=target)
        updated = qs.update(status='disconnected', enabled=False)

        if not updated:
            return Response({'error': 'Connection not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'status': 'disconnected'})
```

- [ ] **Step 4: Update FlowConnectionsView.post — include target in update_or_create**

Lines 223-232:
```python
        conn, created = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card, target=target,
            defaults={
                'status': 'connected',
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            })
```

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/views.py
git commit -m "feat(tools): multi-connection catalog, connect/disconnect per target"
```

---

## Task 4: Backend — Admin + feature flag

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/admin.py`
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py:98-102`

- [ ] **Step 1: Add scope to ToolConnectionAdmin**

In `ToolConnectionAdmin.list_display` add `'target'` and `'scope'` (if not already there).

- [ ] **Step 2: Add scope_schema to ToolCardAdmin fieldsets**

In `ToolCardAdmin` fieldsets, add `'scope_schema'` to the MCP Connection section alongside `tools_schema`.

- [ ] **Step 3: Add feature flag**

In `get_feature_flags` (clients/serializers.py line 98-102):
```python
    def get_feature_flags(self, obj):
        return {
            'mcp_tools_dashboard': FeatureFlag.is_enabled('mcp_tools_dashboard', obj),
            'mcp_sse_streaming': FeatureFlag.is_enabled('mcp_sse_streaming', obj),
            'mcp_knowledge_split': FeatureFlag.is_enabled('mcp_knowledge_split', obj),
            'mcp_tools_multi_connection': FeatureFlag.is_enabled('mcp_tools_multi_connection', obj),
        }
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/admin.py p004_ai_nexelin/MASTER/clients/serializers.py
git commit -m "feat(tools): admin scope fields, mcp_tools_multi_connection flag"
```

---

## Task 5: Backend — Create feature flag in DB

- [ ] **Step 1: Create flag for srtyh**

```bash
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py shell -c "
from MASTER.nexelin_platform.models import FeatureFlag
from MASTER.clients.models import Client
flag, created = FeatureFlag.objects.get_or_create(
    key='mcp_tools_multi_connection',
    defaults={'description': 'Multi-target tool connections with per-connection scopes', 'rollout': 'selected'}
)
srtyh = Client.objects.filter(tag='srtyh').first()
if srtyh:
    flag.enabled_clients.add(srtyh)
    print(f'Enabled for srtyh (pk={srtyh.pk})')
print(f'Flag: {flag.key} rollout={flag.rollout} created={created}')
"
```

---

## Task 6: Frontend — Update tools API client

**Files:**
- Modify: `nextlen/src/api/tools.js`

- [ ] **Step 1: Update disconnect to accept optional target**

```js
disconnect: (slug, target) => api.post(`/tools/${slug}/disconnect/`, target ? { target } : {}),
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/api/tools.js
git commit -m "feat(tools): disconnect API accepts optional target param"
```

---

## Task 7: Frontend — ToolsPage multi-connection handlers

**Files:**
- Modify: `nextlen/src/pages/ToolsPage.jsx`

- [ ] **Step 1: Import useAuth and get feature flag**

```js
import { useAuth } from '../context/AuthContext';

// Inside component:
const { user } = useAuth();
const multiConn = user?.feature_flags?.mcp_tools_multi_connection;
```

- [ ] **Step 2: Update connectedCount to work with both data models**

```js
const connectedCount = tools.filter(t => {
  if (multiConn && t.connections) {
    return t.connections.some(c => c.status === 'connected' && c.enabled);
  }
  return t.connection?.status === 'connected' && t.connection?.enabled;
}).length;
```

- [ ] **Step 3: Update handleDisconnect to pass target**

```js
const handleDisconnect = useCallback(async (slug, target) => {
  try {
    await toolsAPI.disconnect(slug, target);
    const tool = tools.find(t => t.slug === slug);
    showToast('🔌', `${tool?.name || slug} ${t('tools.flow.disconnected')}`);
    loadTools();
  } catch (err) {
    console.error('Disconnect error:', err);
  }
}, [tools, showToast, t]);
```

- [ ] **Step 4: Update handleConnect for multi-connection**

```js
const handleConnect = useCallback(async (slug, target) => {
  const tool = tools.find(t => t.slug === slug);
  if (!tool) return;

  if (multiConn && tool.connections) {
    // Check if already connected to THIS target
    const existing = tool.connections.find(
      c => c.target === target && c.status === 'connected' && c.enabled
    );
    if (existing) return;

    // Check if tool has ANY active connection (credentials exist)
    const anyConn = tool.connections.find(c => c.status === 'connected');
    if (tool.auth_type === 'none' || anyConn) {
      await toolsAPI.createFlowConnection(slug, target);
    } else {
      showToast('💡', t('tools.flow.clickToConnect'));
      return;
    }
  } else {
    // Old single-connection logic
    const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
    if (isConnected && tool.connection?.id) {
      await toolsAPI.updateFlowConnection(tool.connection.id, { target });
    } else if (tool.auth_type === 'none') {
      await toolsAPI.createFlowConnection(slug, target);
    } else {
      showToast('💡', t('tools.flow.clickToConnect'));
      return;
    }
  }
  showToast('🔗', `${tool?.name || slug} → ${target}`);
  loadTools();
}, [tools, showToast, t, multiConn]);
```

- [ ] **Step 5: Update handleMiddlewareRemove/Attach for multi-connection**

```js
const handleMiddlewareRemove = useCallback(async (conn, middlewareId) => {
  try {
    const tool = tools.find(t => t.slug === conn.toolSlug);
    let connId;
    if (multiConn && tool?.connections) {
      const toolConn = tool.connections.find(c => c.target === conn.target && c.status === 'connected');
      connId = toolConn?.id;
    } else {
      connId = tool?.connection?.id;
    }
    if (!connId) return;
    await toolsAPI.detachMiddleware(connId, middlewareId);
    showToast('🔧', 'Middleware removed');
    loadTools();
  } catch (err) {
    console.error('Remove middleware error:', err);
  }
}, [tools, showToast, multiConn]);

const handleMiddlewareAttach = useCallback(async (conn, skillSlug) => {
  try {
    const tool = tools.find(t => t.slug === conn.toolSlug);
    let connId;
    if (multiConn && tool?.connections) {
      const toolConn = tool.connections.find(c => c.target === conn.target && c.status === 'connected');
      connId = toolConn?.id;
    } else {
      connId = tool?.connection?.id;
    }
    if (!connId) return;
    await toolsAPI.attachMiddleware(connId, skillSlug);
    const skill = tools.find(t => t.slug === skillSlug);
    showToast('🧩', `${skill?.name || skillSlug} attached`);
    loadTools();
  } catch (err) {
    console.error('Attach middleware error:', err);
    showToast('⚠️', err.response?.data?.error || 'Failed to attach skill');
  }
}, [tools, showToast, multiConn]);
```

- [ ] **Step 6: Commit**

```bash
git add nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(tools): ToolsPage multi-connection handlers (flag-gated)"
```

---

## Task 8: Frontend — FlowCanvas multi-connection support

**Files:**
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:57-84`

- [ ] **Step 1: Update connectedTools to work with both data models**

Replace lines 62-65:
```js
  const connectedTools = useMemo(
    () => tools.filter(t => {
      if (t.connections) {
        return t.connections.some(c => c.status === 'connected' && c.enabled);
      }
      return t.connection?.status === 'connected' && t.connection?.enabled;
    }),
    [tools]
  );
```

- [ ] **Step 2: Update getEffectiveTargets**

Replace lines 68-72:
```js
  const getEffectiveTargets = useCallback((tool) => {
    if (tool.connections?.length) {
      const targets = tool.connections
        .filter(c => c.status === 'connected' && c.enabled)
        .map(c => c.target);
      return targets.length ? targets : getToolTargets(tool.slug);
    }
    const connTarget = tool.connection?.target;
    if (connTarget) return [connTarget];
    return getToolTargets(tool.slug);
  }, []);
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/tools/FlowCanvas.jsx
git commit -m "feat(tools): FlowCanvas multi-connection support"
```

---

## Task 9: Frontend — ToolPopover per-connection disconnect

**Files:**
- Modify: `nextlen/src/components/tools/ToolPopover.jsx`

- [ ] **Step 1: Show each connection with individual disconnect**

Find the disconnect button section. Add multi-connection rendering:
```jsx
{/* When tool.connections exists, show each connection */}
{tool.connections?.filter(c => c.status === 'connected').map(conn => (
  <div key={conn.id} className="flex items-center justify-between py-1">
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">{conn.target}</span>
      {conn.scope?.description && (
        <span className="text-xs text-gray-400">{conn.scope.description}</span>
      )}
    </div>
    <button
      onClick={() => onDisconnect(tool.slug, conn.target)}
      className="text-xs text-red-500 hover:text-red-700"
    >
      {t('tools.flow.disconnect') || 'Disconnect'}
    </button>
  </div>
))}
```

Keep existing single-connection disconnect as fallback when `tool.connections` is undefined.

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ToolPopover.jsx
git commit -m "feat(tools): ToolPopover per-connection disconnect"
```

---

## Summary of changes

| # | Task | Type | Files |
|---|------|------|-------|
| 1 | scope + scope_schema fields, unique_together | model + migration | 1 backend |
| 2 | Serializers update | backend | 1 |
| 3 | Views multi-connection | backend | 1 |
| 4 | Admin + feature flag | backend | 2 |
| 5 | Create flag in DB | data | shell |
| 6 | API client update | frontend | 1 |
| 7 | ToolsPage handlers | frontend | 1 |
| 8 | FlowCanvas multi-connection | frontend | 1 |
| 9 | ToolPopover per-connection | frontend | 1 |
