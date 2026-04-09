# Tools Canvas: Bug Fixes + Edge Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix canvas edge/disconnect backend integration, implement skill-as-middleware on edges, and fix category grouping.

**Architecture:** Backend gets new `EdgeMiddleware` model linking skills to connections. Frontend wires up existing TODO stubs to real API calls and renders skill badges on bezier edges. Skills become draggable middleware that intercept data flow on specific connections.

**Tech Stack:** Django 5.x, DRF, PostgreSQL, React 18, Tailwind CSS, SVG

---

## File Structure

### Backend (create)
- `p004_ai_nexelin/MASTER/tools/migrations/0004_edgemiddleware_toolcard_skill_scopes.py` — migration for new model + field
- (no new files needed — extend existing models.py, views.py, serializers.py, urls.py)

### Backend (modify)
- `p004_ai_nexelin/MASTER/tools/models.py` — add `EdgeMiddleware` model + `skill_scopes` field on `ToolCard`
- `p004_ai_nexelin/MASTER/tools/serializers.py` — add `EdgeMiddlewareSerializer`, update `FlowConnectionSerializer`
- `p004_ai_nexelin/MASTER/tools/views.py` — add `EdgeMiddlewareView`, `EdgeMiddlewareDetailView`
- `p004_ai_nexelin/MASTER/tools/urls.py` — add middleware endpoints
- `p004_ai_nexelin/MASTER/tools/admin.py` — register EdgeMiddleware

### Frontend (modify)
- `nextlen/src/components/tools/FlowCanvas.jsx` — wire handleDeleteEdge, handlePortPointerUp, handleDrop to API; add middleware state
- `nextlen/src/components/tools/ConnectionsLayer.jsx` — render skill badges on edges
- `nextlen/src/components/tools/ToolCatalogStrip.jsx` — move rag-search to servers
- `nextlen/src/pages/ToolsPage.jsx` — pass disconnect/connect callbacks to FlowCanvas; load middleware data
- `nextlen/src/api/tools.js` — add middleware API calls + flow connection endpoints

### Frontend (create)
- `nextlen/src/components/tools/EdgeSkillBadge.jsx` — skill circle rendered on bezier path

---

## Task 1: Fix `rag-search` category grouping

**Files:**
- Modify: `nextlen/src/components/tools/ToolCatalogStrip.jsx:7`

- [ ] **Step 1: Change rag-search from skills to servers**

In `SLUG_TO_GROUP` at line 7, change:
```js
// BEFORE
'rag-search':      'skills',

// AFTER
'rag-search':      'servers',
```

- [ ] **Step 2: Verify visually**

Run dev server, check Tools page — rag-search should now appear under "Servers" tab.

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/tools/ToolCatalogStrip.jsx
git commit -m "fix(tools): move rag-search from skills to servers category"
```

---

## Task 2: Wire handleDeleteEdge to backend

**Files:**
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:350-357`
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:56` (add onDisconnect prop)

- [ ] **Step 1: Add onDisconnect prop to FlowCanvas**

FlowCanvas component signature at line 56:
```js
// BEFORE
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop }) => {

// AFTER
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop, onDisconnect }) => {
```

- [ ] **Step 2: Replace handleDeleteEdge stub with real API call**

Replace lines 350-357:
```js
const handleDeleteEdge = useCallback((edgeId) => {
  const conn = connections.find(c => c.id === edgeId);
  if (!conn || conn.target === 'escalation' || !conn.toolSlug) return;

  if (window.confirm('Disconnect this tool?')) {
    onDisconnect?.(conn.toolSlug);
  }
  setSelectedEdge(null);
  setContextMenu(null);
}, [connections, onDisconnect]);
```

- [ ] **Step 3: Pass onDisconnect from ToolsPage**

In `nextlen/src/pages/ToolsPage.jsx` line 140-145:
```jsx
<FlowCanvas
  tools={tools}
  onToolClick={handleCanvasToolClick}
  highlightedTool={highlightedTool}
  onToolDrop={handleToolDrop}
  onDisconnect={handleDisconnect}
/>
```

- [ ] **Step 4: Verify**

On canvas, right-click an edge > "Remove connection" > confirm > should call API and refresh tools list.

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/components/tools/FlowCanvas.jsx nextlen/src/pages/ToolsPage.jsx
git commit -m "fix(tools): wire edge deletion to backend disconnect API"
```

---

## Task 3: Wire handlePortPointerUp to backend (edge creation via port drag)

**Files:**
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:284-291`
- Modify: `nextlen/src/api/tools.js`
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:56` (add onConnect prop)

- [ ] **Step 1: Add flow connection API methods**

In `nextlen/src/api/tools.js`:
```js
import api from './axios';

export const toolsAPI = {
  getCatalog: () => api.get('/tools/catalog/'),
  connect: (slug, credentials, config) => api.post(`/tools/${slug}/connect/`, { credentials }, config),
  disconnect: (slug) => api.post(`/tools/${slug}/disconnect/`),
  getStatus: (slug) => api.get(`/tools/${slug}/status/`),
  getMyTools: () => api.get('/tools/my/'),

  // Flow canvas
  getFlowConnections: () => api.get('/tools/flow/connections/'),
  createFlowConnection: (slug, target) => api.post('/tools/flow/connections/', { slug, target }),
  updateFlowConnection: (id, data) => api.patch(`/tools/flow/connections/${id}/`, data),
  deleteFlowConnection: (id) => api.delete(`/tools/flow/connections/${id}/`),

  // Edge middleware
  getEdgeMiddleware: (connectionId) => api.get(`/tools/flow/edges/${connectionId}/middleware/`),
  attachMiddleware: (connectionId, skillSlug) => api.post(`/tools/flow/edges/${connectionId}/middleware/`, { skill_slug: skillSlug }),
  detachMiddleware: (connectionId, middlewareId) => api.delete(`/tools/flow/edges/${connectionId}/middleware/${middlewareId}/`),
};
```

- [ ] **Step 2: Add onConnect prop and wire handlePortPointerUp**

Add `onConnect` to FlowCanvas props:
```js
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop, onDisconnect, onConnect }) => {
```

Replace handlePortPointerUp (lines 284-291):
```js
const handlePortPointerUp = useCallback((nodeId, portIndex) => {
  if (!edgeDrag) return;

  const { sourceNode } = edgeDrag;
  setEdgeDrag(null);
  setGhostEdge(null);

  // Determine tool slug and target core node
  const sourceIsCore = sourceNode.startsWith('__');
  const targetIsCore = nodeId.startsWith('__');

  // Only allow tool-to-core or core-to-tool connections
  if (sourceIsCore === targetIsCore) return;

  const toolSlug = sourceIsCore ? nodeId : sourceNode;
  const coreNodeId = sourceIsCore ? sourceNode : nodeId;

  // Don't create edges for core-only nodes (e.g. tool slug starting with __)
  if (toolSlug.startsWith('__')) return;

  const target = coreNodeId.slice(2); // '__assistant' -> 'assistant'
  onConnect?.(toolSlug, target);
}, [edgeDrag, onConnect]);
```

- [ ] **Step 3: Add handleConnect in ToolsPage and pass it**

In `nextlen/src/pages/ToolsPage.jsx`, after handleDisconnect:
```js
const handleConnect = useCallback(async (slug, target) => {
  const tool = tools.find(t => t.slug === slug);
  if (!tool) return;

  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;

  try {
    if (isConnected && tool.connection?.id) {
      // Already connected — update target via flow API
      await toolsAPI.updateFlowConnection(tool.connection.id, { target });
    } else if (tool.auth_type === 'none') {
      // Not connected, no auth needed — create connection
      await toolsAPI.createFlowConnection(slug, target);
    } else {
      showToast('💡', t('tools.flow.clickToConnect'));
      return;
    }
    const targetName = t(`tools.flow.connectedTo${target.charAt(0).toUpperCase() + target.slice(1)}`);
    showToast('🔗', `${tool?.name || slug} ${targetName}`);
    loadTools();
  } catch (err) {
    console.error('Connect error:', err);
  }
}, [tools, showToast, t]);
```

Pass to FlowCanvas:
```jsx
<FlowCanvas
  tools={tools}
  onToolClick={handleCanvasToolClick}
  highlightedTool={highlightedTool}
  onToolDrop={handleToolDrop}
  onDisconnect={handleDisconnect}
  onConnect={handleConnect}
/>
```

- [ ] **Step 4: Verify**

Drag from a tool port to a core node port — should create/update connection via API.

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/api/tools.js nextlen/src/components/tools/FlowCanvas.jsx nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(tools): wire port-to-port edge creation to backend API"
```

---

## Task 4: Backend — EdgeMiddleware model + skill_scopes on ToolCard

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/models.py`

- [ ] **Step 1: Add skill_scopes field to ToolCard**

After `auth_config` field (line 49):
```python
skill_scopes = models.JSONField(
    default=dict, blank=True,
    help_text='{"scopes": ["assistant","manager","escalation"], "bidirectional": true}')
```

- [ ] **Step 2: Add EdgeMiddleware model**

After ToolConnection class:
```python
class EdgeMiddleware(models.Model):
    """Skill attached to a connection edge as middleware/filter."""

    connection = models.ForeignKey(
        ToolConnection, on_delete=models.CASCADE,
        related_name='middlewares',
        help_text='The edge this skill is attached to')
    skill_card = models.ForeignKey(
        ToolCard, on_delete=models.CASCADE,
        related_name='middleware_usages',
        help_text='The skill acting as middleware')
    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE,
        related_name='edge_middlewares')
    order = models.IntegerField(default=0, help_text='Execution order on this edge')
    enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True,
        help_text='Per-edge config overrides for this skill')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        unique_together = ['connection', 'skill_card']
        indexes = [
            models.Index(fields=['client', 'connection']),
        ]

    def __str__(self):
        return f'{self.skill_card.name} on {self.connection}'
```

- [ ] **Step 3: Create migration**

```bash
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py makemigrations tools -n "edgemiddleware_toolcard_skill_scopes"
```

- [ ] **Step 4: Run migration**

```bash
python p004_ai_nexelin/manage.py migrate tools
```

- [ ] **Step 5: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/models.py p004_ai_nexelin/MASTER/tools/migrations/
git commit -m "feat(tools): add EdgeMiddleware model and skill_scopes field"
```

---

## Task 5: Backend — Serializers + Views + URLs for EdgeMiddleware

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/serializers.py`
- Modify: `p004_ai_nexelin/MASTER/tools/views.py`
- Modify: `p004_ai_nexelin/MASTER/tools/urls.py`
- Modify: `p004_ai_nexelin/MASTER/tools/admin.py`

- [ ] **Step 1: Add EdgeMiddleware serializer**

In `serializers.py`, add after FlowConnectionUpdateSerializer:
```python
from .models import ToolCard, ToolConnection, EdgeMiddleware


class EdgeMiddlewareSerializer(serializers.ModelSerializer):
    skill_slug = serializers.CharField(source='skill_card.slug', read_only=True)
    skill_name = serializers.CharField(source='skill_card.name', read_only=True)
    skill_icon = serializers.CharField(source='skill_card.icon', read_only=True)
    skill_color = serializers.CharField(source='skill_card.color', read_only=True)

    class Meta:
        model = EdgeMiddleware
        fields = ['id', 'skill_slug', 'skill_name', 'skill_icon', 'skill_color',
                  'order', 'enabled', 'config', 'created_at']


class EdgeMiddlewareCreateSerializer(serializers.Serializer):
    skill_slug = serializers.SlugField()
    order = serializers.IntegerField(required=False, default=0)
    config = serializers.JSONField(required=False, default=dict)
```

- [ ] **Step 2: Update FlowConnectionSerializer to include middlewares**

```python
class FlowConnectionSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source='tool_card.slug', read_only=True)
    name = serializers.CharField(source='tool_card.name', read_only=True)
    icon = serializers.CharField(source='tool_card.icon', read_only=True)
    color = serializers.CharField(source='tool_card.color', read_only=True)
    category = serializers.CharField(source='tool_card.category', read_only=True)
    middlewares = EdgeMiddlewareSerializer(many=True, read_only=True)

    class Meta:
        model = ToolConnection
        fields = ['id', 'slug', 'name', 'icon', 'color', 'category',
                  'status', 'target', 'enabled',
                  'position_x', 'position_y', 'connected_at', 'middlewares']
```

- [ ] **Step 3: Add EdgeMiddleware views**

In `views.py`, add after FlowConnectionDetailView:
```python
from .models import ToolCard, ToolConnection, EdgeMiddleware
from .serializers import (
    ToolCatalogItemSerializer, ToolConnectionSerializer,
    FlowConnectionSerializer, FlowConnectionUpdateSerializer,
    EdgeMiddlewareSerializer, EdgeMiddlewareCreateSerializer,
)


class EdgeMiddlewareView(APIView):
    """
    GET  /api/tools/flow/edges/<connection_id>/middleware/
    POST /api/tools/flow/edges/<connection_id>/middleware/
    """

    def _get_connection(self, request, connection_id):
        client = getattr(request, 'client', None)
        if not client:
            return None, Response(
                {'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            conn = ToolConnection.objects.get(pk=connection_id, client=client)
            return conn, None
        except ToolConnection.DoesNotExist:
            return None, Response(
                {'error': 'Connection not found'}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, connection_id):
        conn, err = self._get_connection(request, connection_id)
        if err:
            return err
        middlewares = conn.middlewares.select_related('skill_card').all()
        return Response(EdgeMiddlewareSerializer(middlewares, many=True).data)

    def post(self, request, connection_id):
        conn, err = self._get_connection(request, connection_id)
        if err:
            return err

        ser = EdgeMiddlewareCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        skill_slug = ser.validated_data['skill_slug']
        try:
            skill_card = ToolCard.objects.get(slug=skill_slug, is_active=True)
        except ToolCard.DoesNotExist:
            return Response(
                {'error': 'Skill not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if skill supports this edge's target
        scopes = skill_card.skill_scopes.get('scopes', [])
        if scopes and conn.target not in scopes:
            return Response(
                {'error': f'Skill does not support target "{conn.target}"'},
                status=status.HTTP_400_BAD_REQUEST)

        middleware, created = EdgeMiddleware.objects.get_or_create(
            connection=conn,
            skill_card=skill_card,
            client=conn.client,
            defaults={
                'order': ser.validated_data.get('order', 0),
                'config': ser.validated_data.get('config', {}),
            })

        return Response(
            EdgeMiddlewareSerializer(middleware).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class EdgeMiddlewareDetailView(APIView):
    """DELETE /api/tools/flow/edges/<connection_id>/middleware/<pk>/"""

    def delete(self, request, connection_id, pk):
        client = getattr(request, 'client', None)
        if not client:
            return Response(
                {'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        deleted, _ = EdgeMiddleware.objects.filter(
            pk=pk, connection_id=connection_id, client=client
        ).delete()
        if not deleted:
            return Response(
                {'error': 'Middleware not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Add URL patterns**

In `urls.py`, add:
```python
# Edge middleware
path('flow/edges/<int:connection_id>/middleware/',
     views.EdgeMiddlewareView.as_view(), name='edge-middleware'),
path('flow/edges/<int:connection_id>/middleware/<int:pk>/',
     views.EdgeMiddlewareDetailView.as_view(), name='edge-middleware-detail'),
```

- [ ] **Step 5: Register in admin**

In `admin.py`, add:
```python
from .models import ToolCard, ToolConnection, EdgeMiddleware

@admin.register(EdgeMiddleware)
class EdgeMiddlewareAdmin(admin.ModelAdmin):
    list_display = ['skill_card', 'connection', 'client', 'order', 'enabled', 'created_at']
    list_filter = ['enabled', 'skill_card']
    raw_id_fields = ['connection', 'skill_card', 'client']
```

- [ ] **Step 6: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/serializers.py p004_ai_nexelin/MASTER/tools/views.py p004_ai_nexelin/MASTER/tools/urls.py p004_ai_nexelin/MASTER/tools/admin.py
git commit -m "feat(tools): add EdgeMiddleware API endpoints and serializers"
```

---

## Task 6: Backend — Add middleware data to catalog API response

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/views.py:13-60` (ToolCatalogView)

- [ ] **Step 1: Include middlewares in catalog connection data**

In `ToolCatalogView.get()`, update the connections query to prefetch middlewares:

After line 25 (`connections` dict), change to:
```python
connections = {}
if client:
    conns_qs = ToolConnection.objects.filter(client=client).prefetch_related(
        'middlewares__skill_card'
    )
    connections = {tc.tool_card_id: tc for tc in conns_qs}
```

In the connection dict (around line 49), add middlewares:
```python
'connection': {
    'id': conn.pk,
    'status': conn.status,
    'enabled': conn.enabled,
    'target': conn.target,
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
} if conn else None,
```

Also add `skill_scopes` to the tool item dict:
```python
'skill_scopes': tool.skill_scopes,
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/views.py
git commit -m "feat(tools): include middleware data in catalog API response"
```

---

## Task 7: Frontend — EdgeSkillBadge component

**Files:**
- Create: `nextlen/src/components/tools/EdgeSkillBadge.jsx`

- [ ] **Step 1: Create EdgeSkillBadge component**

```jsx
import ToolIcon from './ToolIcon';

const EdgeSkillBadge = ({ middleware, pathD, position = 0.5, onRemove }) => {
  // Calculate point on bezier at given position (0-1)
  const getPointOnPath = (d, t) => {
    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.setAttribute('d', d);
    const len = pathEl.getTotalLength();
    return pathEl.getPointAtLength(t * len);
  };

  const pt = getPointOnPath(pathD, position);

  return (
    <div
      className="absolute flex items-center justify-center group"
      style={{
        left: pt.x,
        top: pt.y,
        transform: 'translate(-50%, -50%)',
        zIndex: 5,
      }}
    >
      {/* Badge circle */}
      <div
        className={`w-7 h-7 rounded-full border-2 border-white dark:border-gray-800 bg-white dark:bg-gray-800
          shadow-md flex items-center justify-center transition-transform group-hover:scale-125 cursor-default`}
        title={middleware.skill_name}
      >
        <ToolIcon name={middleware.skill_icon} className="w-3.5 h-3.5 text-primary-500" />
      </div>

      {/* Remove button on hover */}
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(middleware.id);
          }}
          className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-500 text-white
            flex items-center justify-center text-[9px] font-bold
            opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer
            hover:bg-red-600"
          title="Remove"
        >
          x
        </button>
      )}
    </div>
  );
};

export default EdgeSkillBadge;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/EdgeSkillBadge.jsx
git commit -m "feat(tools): create EdgeSkillBadge component for skill circles on edges"
```

---

## Task 8: Frontend — Render middleware badges on canvas edges

**Files:**
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx`
- Modify: `nextlen/src/pages/ToolsPage.jsx`

- [ ] **Step 1: Extract middleware map from tools data in FlowCanvas**

In FlowCanvas, after the `connections` useMemo (around line 243), add:
```js
/* -- Middleware on edges -- */
const middlewareByEdge = useMemo(() => {
  const map = {};
  connectedTools.forEach(tool => {
    const mws = tool.connection?.middlewares;
    if (!mws?.length) return;
    const targets = getToolTargets(tool.slug);
    targets.forEach(target => {
      const edgeId = `${tool.slug}-${target}`;
      map[edgeId] = mws;
    });
  });
  return map;
}, [connectedTools]);
```

- [ ] **Step 2: Import and render EdgeSkillBadge inside the transform layer**

Add import at top:
```js
import EdgeSkillBadge from './EdgeSkillBadge';
```

After the connected tool nodes block (after line 747), before closing `</div>` of innerRef:
```jsx
{/* Middleware badges on edges */}
{connections.map(conn => {
  const mws = middlewareByEdge[conn.id];
  if (!mws?.length || conn.target === 'escalation') return null;
  return mws.map((mw, i) => {
    const count = mws.length;
    const position = count === 1 ? 0.5 : (i + 1) / (count + 1);
    return (
      <EdgeSkillBadge
        key={`${conn.id}-${mw.id}`}
        middleware={mw}
        pathD={conn.pathD}
        position={position}
        onRemove={(mwId) => onMiddlewareRemove?.(conn, mwId)}
      />
    );
  });
})}
```

- [ ] **Step 3: Add onMiddlewareRemove prop**

Update FlowCanvas signature:
```js
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop, onDisconnect, onConnect, onMiddlewareRemove }) => {
```

- [ ] **Step 4: Add middleware handlers in ToolsPage**

In `ToolsPage.jsx`, add after handleConnect:
```js
const handleMiddlewareRemove = useCallback(async (conn, middlewareId) => {
  try {
    // Find connection ID from tool slug
    const tool = tools.find(t => t.slug === conn.toolSlug);
    if (!tool?.connection?.id) return;
    await toolsAPI.detachMiddleware(tool.connection.id, middlewareId);
    showToast('🔧', t('tools.flow.middlewareRemoved'));
    loadTools();
  } catch (err) {
    console.error('Remove middleware error:', err);
  }
}, [tools, showToast, t]);
```

Pass to FlowCanvas:
```jsx
<FlowCanvas
  tools={tools}
  onToolClick={handleCanvasToolClick}
  highlightedTool={highlightedTool}
  onToolDrop={handleToolDrop}
  onDisconnect={handleDisconnect}
  onConnect={handleConnect}
  onMiddlewareRemove={handleMiddlewareRemove}
/>
```

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/components/tools/FlowCanvas.jsx nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(tools): render middleware skill badges on canvas edges"
```

---

## Task 9: Frontend — Wire edge drop to attach middleware

**Files:**
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:576-594` (handleDrop)
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx:56` (add onMiddlewareAttach prop)
- Modify: `nextlen/src/pages/ToolsPage.jsx`

- [ ] **Step 1: Add onMiddlewareAttach prop to FlowCanvas**

Update signature:
```js
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop, onDisconnect, onConnect, onMiddlewareRemove, onMiddlewareAttach }) => {
```

- [ ] **Step 2: Wire handleDrop edge attachment**

Replace the edge-drop section in handleDrop (lines 583-589):
```js
if (dragOverEdgeId) {
  const conn = connections.find(c => c.id === dragOverEdgeId);
  if (conn && conn.toolSlug) {
    onMiddlewareAttach?.(conn, slug);
  }
  setDragOverEdgeId(null);
  return;
}
```

- [ ] **Step 3: Add handleMiddlewareAttach in ToolsPage**

After handleMiddlewareRemove:
```js
const handleMiddlewareAttach = useCallback(async (conn, skillSlug) => {
  try {
    const tool = tools.find(t => t.slug === conn.toolSlug);
    if (!tool?.connection?.id) return;
    await toolsAPI.attachMiddleware(tool.connection.id, skillSlug);
    const skill = tools.find(t => t.slug === skillSlug);
    showToast('🧩', `${skill?.name || skillSlug} ${t('tools.flow.middlewareAttached')}`);
    loadTools();
  } catch (err) {
    console.error('Attach middleware error:', err);
    showToast('⚠️', err.response?.data?.error || 'Failed to attach skill');
  }
}, [tools, showToast, t]);
```

Pass to FlowCanvas:
```jsx
<FlowCanvas
  tools={tools}
  onToolClick={handleCanvasToolClick}
  highlightedTool={highlightedTool}
  onToolDrop={handleToolDrop}
  onDisconnect={handleDisconnect}
  onConnect={handleConnect}
  onMiddlewareRemove={handleMiddlewareRemove}
  onMiddlewareAttach={handleMiddlewareAttach}
/>
```

- [ ] **Step 4: Verify end-to-end**

1. Drag `translation` card from catalog strip onto edge between telegram and assistant
2. Edge should glow (dragOverEdgeId already works)
3. On drop: API call, toast, reload shows circle on edge
4. Hover circle: shows name + remove button
5. Click remove: API call, toast, circle disappears

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/components/tools/FlowCanvas.jsx nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(tools): wire skill drag-on-edge to middleware API"
```

---

## Task 10: Backend — Seed skill_scopes for existing tools

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/seed_data.py`

- [ ] **Step 1: Add skill_scopes to existing skill ToolCards**

For `translation` and `rag-search` entries in seed_data.py, add:

```python
# translation
'skill_scopes': {
    'scopes': ['assistant', 'manager', 'escalation'],
    'bidirectional': True,
},

# rag-search
'skill_scopes': {
    'scopes': ['assistant'],
    'bidirectional': False,
},
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/seed_data.py
git commit -m "feat(tools): add skill_scopes to seed data for translation and rag-search"
```

---

## Summary of changes

| # | Task | Type | Files changed |
|---|------|------|---------------|
| 1 | Fix rag-search category | bugfix | 1 frontend |
| 2 | Wire edge delete to API | bugfix | 2 frontend |
| 3 | Wire port drag to API | bugfix | 3 frontend |
| 4 | EdgeMiddleware model | feature | 1 backend + migration |
| 5 | Middleware API endpoints | feature | 4 backend |
| 6 | Middleware in catalog response | feature | 1 backend |
| 7 | EdgeSkillBadge component | feature | 1 frontend (new) |
| 8 | Render badges on edges | feature | 2 frontend |
| 9 | Wire edge drop to middleware | feature | 2 frontend |
| 10 | Seed skill_scopes | data | 1 backend |
