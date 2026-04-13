# MCP Catalog Admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Owner can manage MCP servers from the frontend admin — add external MCP via URL with auto-discovery, see builtin tools, auto-connect to all clients.

**Architecture:** New `ToolCardOwnerViewSet` (DRF ModelViewSet) with custom `discover` and `from_url` actions. Two new React pages following existing LLMProviders pattern. Data migration seeds 8 builtin MCP servers.

**Tech Stack:** Django REST Framework, MCP Python SDK 1.26.0 (sse_client), React 18, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-04-13-mcp-catalog-admin-design.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `backend/Jeeves/tools/views_owner.py` | Owner ViewSet + discover/from_url actions |
| Create | `backend/Jeeves/tools/serializers_owner.py` | ToolCardOwnerSerializer |
| Create | `backend/Jeeves/tools/mcp_discovery.py` | MCP discovery helper (connect + list_tools) |
| Modify | `backend/Jeeves/concierge_platform/urls.py` | Register owner tools routes |
| Create | `backend/Jeeves/tools/migrations/XXXX_seed_builtin_tools.py` | Seed 8 builtin ToolCards |
| Modify | `frontend/src/api/owner.js` | Add mcpServersAPI |
| Create | `frontend/src/pages/owner/MCPServersPage.jsx` | List page |
| Create | `frontend/src/pages/owner/MCPServerEditPage.jsx` | Edit/create page with discovery |
| Modify | `frontend/src/components/owner/OwnerSidebar.jsx` | Add MCP Servers nav item |
| Modify | `frontend/src/App.jsx` | Add routes |

---

### Task 1: MCP Discovery Helper

**Files:**
- Create: `backend/Jeeves/tools/mcp_discovery.py`

- [ ] **Step 1: Create the discovery module**

```python
# backend/Jeeves/tools/mcp_discovery.py
import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10  # seconds


@dataclass
class DiscoveryResult:
    server_name: str
    tools: list  # [{"name": ..., "description": ..., "inputSchema": ...}]


class DiscoveryError(Exception):
    pass


async def _discover_sse(url: str) -> DiscoveryResult:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in result.tools
            ]
            server_name = getattr(session, "server_name", "") or ""
            return DiscoveryResult(server_name=server_name, tools=tools)


def discover_mcp_server(url: str) -> DiscoveryResult:
    """Connect to an MCP server via SSE, list its tools, return result.

    Raises DiscoveryError on any failure (timeout, connection, protocol).
    """
    try:
        result = asyncio.run(
            asyncio.wait_for(_discover_sse(url), timeout=DISCOVERY_TIMEOUT)
        )
        if not result.tools:
            raise DiscoveryError("Server returned zero tools.")
        return result
    except DiscoveryError:
        raise
    except asyncio.TimeoutError:
        raise DiscoveryError(f"Connection timed out after {DISCOVERY_TIMEOUT}s.")
    except Exception as e:
        raise DiscoveryError(f"Failed to connect: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/Jeeves/tools/mcp_discovery.py
git commit -m "feat(tools): add MCP discovery helper for SSE servers"
```

---

### Task 2: Owner Serializer

**Files:**
- Create: `backend/Jeeves/tools/serializers_owner.py`

- [ ] **Step 1: Create the owner serializer**

```python
# backend/Jeeves/tools/serializers_owner.py
from django.utils.text import slugify
from rest_framework import serializers

from .models import ToolCard


class ToolCardOwnerSerializer(serializers.ModelSerializer):
    connections_count = serializers.IntegerField(read_only=True, default=0)
    tools_count = serializers.SerializerMethodField()

    class Meta:
        model = ToolCard
        fields = [
            'id', 'name', 'slug', 'tagline', 'tagline_i18n', 'description',
            'icon', 'color', 'category',
            'mcp_server_url', 'transport_type', 'is_builtin', 'builtin_handler',
            'tools_schema', 'scope_schema', 'skill_scopes',
            'auth_type', 'auth_config',
            'is_active', 'is_featured', 'is_system',
            'sort_order',
            'connections_count', 'tools_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'connections_count', 'tools_count',
            'created_at', 'updated_at',
        ]

    def get_tools_count(self, obj):
        schema = obj.tools_schema
        if isinstance(schema, list):
            return len(schema)
        return 0

    def validate_slug(self, value):
        return value  # allow explicit slug

    def create(self, validated_data):
        if not validated_data.get('slug'):
            base = slugify(validated_data.get('name', ''))
            slug = base
            counter = 2
            while ToolCard.objects.filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            validated_data['slug'] = slug
        return super().create(validated_data)


class DiscoverRequestSerializer(serializers.Serializer):
    url = serializers.URLField()


class FromUrlRequestSerializer(serializers.Serializer):
    url = serializers.URLField()
    name = serializers.CharField(max_length=100, required=False, default='')
    icon = serializers.CharField(max_length=50, required=False, default='puzzle')
    color = serializers.CharField(max_length=7, required=False, default='#6366f1')
    category = serializers.ChoiceField(
        choices=ToolCard.CATEGORY_CHOICES, required=False, default='custom',
    )
    targets = serializers.ListField(
        child=serializers.ChoiceField(choices=['assistant', 'manager', 'leads']),
        required=False, default=['assistant'],
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/Jeeves/tools/serializers_owner.py
git commit -m "feat(tools): add ToolCardOwnerSerializer and request serializers"
```

---

### Task 3: Owner ViewSet

**Files:**
- Create: `backend/Jeeves/tools/views_owner.py`

- [ ] **Step 1: Create the owner ViewSet with CRUD + custom actions**

```python
# backend/Jeeves/tools/views_owner.py
import logging

from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from .models import ToolCard, ToolConnection
from .mcp_discovery import discover_mcp_server, DiscoveryError
from .serializers_owner import (
    ToolCardOwnerSerializer,
    DiscoverRequestSerializer,
    FromUrlRequestSerializer,
)

logger = logging.getLogger(__name__)


class ToolCardOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = ToolCardOwnerSerializer

    def get_queryset(self):
        return ToolCard.objects.annotate(
            connections_count=Count('connections'),
        ).order_by('sort_order', 'name')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_builtin:
            return Response(
                {'error': 'Cannot delete built-in tools.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def discover(self, request):
        """Connect to MCP server URL, return available tools. Does not save."""
        ser = DiscoverRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        url = ser.validated_data['url']

        try:
            result = discover_mcp_server(url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'server_name': result.server_name,
            'tools': result.tools,
        })

    @action(detail=False, methods=['post'], url_path='from-url')
    def from_url(self, request):
        """Discover + create ToolCard + auto-connect to all clients."""
        ser = FromUrlRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # 1. Discover
        try:
            result = discover_mcp_server(data['url'])
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Create ToolCard
        name = data['name'] or result.server_name or 'Unnamed MCP Server'
        tool_data = {
            'name': name,
            'tagline': f"External MCP server with {len(result.tools)} tools",
            'description': ', '.join(t['name'] for t in result.tools),
            'icon': data['icon'],
            'color': data['color'],
            'category': data['category'],
            'mcp_server_url': data['url'],
            'transport_type': 'sse',
            'is_builtin': False,
            'tools_schema': result.tools,
            'auth_type': 'none',
            'is_active': True,
            'is_system': True,
            'skill_scopes': {'scopes': data['targets']},
        }
        card_ser = ToolCardOwnerSerializer(data=tool_data)
        card_ser.is_valid(raise_exception=True)
        tool_card = card_ser.save()

        # 3. Auto-connect all clients
        now = timezone.now()
        clients = Client.objects.all()
        connections = []
        for client in clients:
            for target in data['targets']:
                connections.append(ToolConnection(
                    client=client,
                    tool_card=tool_card,
                    target=target,
                    status='connected',
                    enabled=True,
                    connected_at=now,
                ))
        ToolConnection.objects.bulk_create(connections, ignore_conflicts=True)

        # Re-fetch with annotation
        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(
            ToolCardOwnerSerializer(tool_card).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Re-discover tools from existing MCP server URL."""
        tool_card = self.get_object()
        if not tool_card.mcp_server_url:
            return Response(
                {'error': 'No MCP server URL configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = discover_mcp_server(tool_card.mcp_server_url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool_card.tools_schema = result.tools
        tool_card.save(update_fields=['tools_schema', 'updated_at'])

        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(ToolCardOwnerSerializer(tool_card).data)
```

- [ ] **Step 2: Commit**

```bash
git add backend/Jeeves/tools/views_owner.py
git commit -m "feat(tools): add ToolCardOwnerViewSet with discover/from-url/refresh"
```

---

### Task 4: URL Registration

**Files:**
- Modify: `backend/Jeeves/concierge_platform/urls.py`

- [ ] **Step 1: Register the owner tools ViewSet in the router**

Add to the imports at the top of `backend/Jeeves/concierge_platform/urls.py`:

```python
from Jeeves.tools import views_owner as tools_owner_views
```

Add after the existing `router.register` calls (after `model-pair`):

```python
router.register(
    r'owner/tools',
    tools_owner_views.ToolCardOwnerViewSet,
    basename='owner-tool',
)
```

- [ ] **Step 2: Commit**

```bash
git add backend/Jeeves/concierge_platform/urls.py
git commit -m "feat(urls): register owner tools ViewSet"
```

---

### Task 5: Seed Builtin MCP Servers Migration

**Files:**
- Create: `backend/Jeeves/tools/migrations/XXXX_seed_builtin_tools.py`

- [ ] **Step 1: Create the data migration**

Run:
```bash
cd /home/dchuprina/jeevs/backend && python manage.py makemigrations tools --empty -n seed_builtin_tools
```

- [ ] **Step 2: Fill in the migration**

Replace the generated migration content with:

```python
from django.db import migrations


BUILTIN_TOOLS = [
    {
        'name': 'RAG Knowledge Search',
        'slug': 'rag',
        'tagline': 'Search knowledge base with semantic retrieval',
        'description': 'RAG pipeline — vector search, context building, reranking.',
        'icon': 'search',
        'color': '#3b82f6',
        'category': 'ai',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.rag.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 10,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
    {
        'name': 'Escalation',
        'slug': 'escalation',
        'tagline': 'Escalate conversations to human managers',
        'description': 'HITL manager escalation with availability checks.',
        'icon': 'arrow-up-right',
        'color': '#ef4444',
        'category': 'communication',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.escalation.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 20,
        'skill_scopes': {'scopes': ['assistant']},
    },
    {
        'name': 'Lead Management',
        'slug': 'leads',
        'tagline': 'Capture and score leads from conversations',
        'description': 'Save leads with contact info, scoring, and session tracking.',
        'icon': 'user-plus',
        'color': '#10b981',
        'category': 'crm',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.leads.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 30,
        'skill_scopes': {'scopes': ['assistant']},
    },
    {
        'name': 'Email',
        'slug': 'email',
        'tagline': 'Send emails from conversations',
        'description': 'Email integration for agent-driven communications.',
        'icon': 'mail',
        'color': '#8b5cf6',
        'category': 'communication',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.email.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 40,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
    {
        'name': 'Memory',
        'slug': 'memory',
        'tagline': 'Conversation memory and context persistence',
        'description': 'Store and retrieve conversation memory across sessions.',
        'icon': 'brain',
        'color': '#f59e0b',
        'category': 'ai',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.memory.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 50,
        'skill_scopes': {'scopes': ['assistant']},
    },
    {
        'name': 'Coaching',
        'slug': 'coaching',
        'tagline': 'AI coaching for conversation improvement',
        'description': 'Review conversations, find gaps, suggest knowledge base updates.',
        'icon': 'graduation-cap',
        'color': '#06b6d4',
        'category': 'ai',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.coaching.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 60,
        'skill_scopes': {'scopes': ['manager']},
    },
    {
        'name': 'Sales Intelligence',
        'slug': 'sales-intel',
        'tagline': 'Sales insights and analytics',
        'description': 'Sales intelligence tools for conversation analysis.',
        'icon': 'chart-bar',
        'color': '#ec4899',
        'category': 'analytics',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.sales_intel.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 70,
        'skill_scopes': {'scopes': ['manager']},
    },
    {
        'name': 'XLSX Export',
        'slug': 'xlsx',
        'tagline': 'Generate Excel spreadsheets',
        'description': 'Create and export XLSX spreadsheets from conversation data.',
        'icon': 'table',
        'color': '#22c55e',
        'category': 'productivity',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.xlsx.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 80,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
]


def seed_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    for tool_data in BUILTIN_TOOLS:
        ToolCard.objects.update_or_create(
            slug=tool_data['slug'],
            defaults=tool_data,
        )


def unseed_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    slugs = [t['slug'] for t in BUILTIN_TOOLS]
    ToolCard.objects.filter(slug__in=slugs, is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_tools, unseed_tools),
    ]
```

Note: Check the actual latest migration name in `backend/Jeeves/tools/migrations/` and set the correct dependency.

- [ ] **Step 3: Run the migration**

```bash
cd /home/dchuprina/jeevs/backend && python manage.py migrate tools
```

- [ ] **Step 4: Commit**

```bash
git add backend/Jeeves/tools/migrations/
git commit -m "feat(tools): seed 8 builtin MCP server ToolCards"
```

---

### Task 6: Frontend API Client

**Files:**
- Modify: `frontend/src/api/owner.js`

- [ ] **Step 1: Add mcpServersAPI to owner.js**

Append at the end of `frontend/src/api/owner.js`:

```javascript
// MCP Servers (ToolCards)
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

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/owner.js
git commit -m "feat(frontend): add mcpServersAPI to owner API client"
```

---

### Task 7: MCPServersPage (List)

**Files:**
- Create: `frontend/src/pages/owner/MCPServersPage.jsx`

- [ ] **Step 1: Create the list page**

```jsx
// frontend/src/pages/owner/MCPServersPage.jsx
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { mcpServersAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';

const CATEGORY_LABELS = {
  communication: 'Communication',
  productivity: 'Productivity',
  analytics: 'Analytics',
  ai: 'AI & Knowledge',
  crm: 'CRM & Sales',
  custom: 'Custom',
};

const TRANSPORT_LABELS = {
  builtin: 'Built-in',
  sse: 'SSE',
  streamable_http: 'HTTP',
};

const MCPServersPage = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const refresh = () => {
    setLoading(true);
    mcpServersAPI
      .list()
      .then(({ data }) => {
        setRows(Array.isArray(data) ? data : data.results || []);
        setError('');
      })
      .catch((e) => setError(e?.response?.data?.detail || 'Failed to load'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete "${row.name}"?`)) return;
    try {
      await mcpServersAPI.delete(row.id);
      refresh();
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-ink">MCP Servers</h1>
        <button
          className={buttonClass}
          onClick={() => navigate('/owner/mcp-servers/new')}
        >
          + Add MCP Server
        </button>
      </div>

      {loading && <p className="text-sm text-ink/60">Loading...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && rows.length === 0 && (
        <div className="border border-dashed border-ink/20 rounded-sm p-8 text-center">
          <p className="text-ink/70">No MCP servers configured yet.</p>
          <Link
            to="/owner/mcp-servers/new"
            className="text-ink underline mt-2 inline-block"
          >
            Add your first one
          </Link>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <table className="w-full text-sm border border-ink/10 rounded-sm overflow-hidden">
          <thead className="bg-ink/5 text-left">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Transport</th>
              <th className="px-3 py-2">Tools</th>
              <th className="px-3 py-2">Connections</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-ink/10">
                <td className="px-3 py-2 font-medium">
                  {row.name}
                  {row.is_builtin && (
                    <span className="ml-2 text-xs bg-ink/10 text-ink/60 px-1.5 py-0.5 rounded-sm">
                      built-in
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs">
                  {CATEGORY_LABELS[row.category] || row.category}
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {TRANSPORT_LABELS[row.transport_type] || row.transport_type}
                </td>
                <td className="px-3 py-2">{row.tools_count ?? 0}</td>
                <td className="px-3 py-2">{row.connections_count ?? 0}</td>
                <td className="px-3 py-2">{row.is_active ? 'yes' : 'no'}</td>
                <td className="px-3 py-2 text-right space-x-2">
                  <Link
                    to={`/owner/mcp-servers/${row.id}`}
                    className="text-ink underline text-xs"
                  >
                    Edit
                  </Link>
                  {!row.is_builtin && (
                    <button
                      onClick={() => handleDelete(row)}
                      className="text-red-600 text-xs"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default MCPServersPage;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/MCPServersPage.jsx
git commit -m "feat(frontend): add MCPServersPage list view"
```

---

### Task 8: MCPServerEditPage (Create/Edit with Discovery)

**Files:**
- Create: `frontend/src/pages/owner/MCPServerEditPage.jsx`

- [ ] **Step 1: Create the edit page**

```jsx
// frontend/src/pages/owner/MCPServerEditPage.jsx
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { mcpServersAPI } from '../../api/owner';

const CATEGORIES = [
  { value: 'communication', label: 'Communication' },
  { value: 'productivity', label: 'Productivity' },
  { value: 'analytics', label: 'Analytics' },
  { value: 'ai', label: 'AI & Knowledge' },
  { value: 'crm', label: 'CRM & Sales' },
  { value: 'custom', label: 'Custom' },
];

const TARGETS = [
  { value: 'assistant', label: 'AI Assistant' },
  { value: 'manager', label: 'Client Manager' },
  { value: 'leads', label: 'Leads' },
];

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 disabled:opacity-50 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const MCPServerEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';

  // Discovery state (new server flow)
  const [url, setUrl] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState(null); // {server_name, tools}
  const [discoverError, setDiscoverError] = useState('');

  // Form state
  const [form, setForm] = useState({
    name: '',
    icon: 'puzzle',
    color: '#6366f1',
    category: 'custom',
    targets: ['assistant'],
  });
  const [existing, setExisting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!isEdit) return;
    mcpServersAPI.detail(id).then(({ data }) => {
      setExisting(data);
      setForm({
        name: data.name || '',
        icon: data.icon || 'puzzle',
        color: data.color || '#6366f1',
        category: data.category || 'custom',
        targets: data.skill_scopes?.scopes || ['assistant'],
      });
      setDiscovered({ server_name: data.name, tools: data.tools_schema || [] });
    });
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const toggleTarget = (target) => {
    setForm((f) => {
      const targets = f.targets.includes(target)
        ? f.targets.filter((t) => t !== target)
        : [...f.targets, target];
      return { ...f, targets: targets.length ? targets : f.targets };
    });
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    setDiscoverError('');
    setDiscovered(null);
    try {
      const { data } = await mcpServersAPI.discover(url);
      setDiscovered(data);
      if (data.server_name && !form.name) {
        set('name', data.server_name);
      }
    } catch (e) {
      setDiscoverError(e?.response?.data?.error || 'Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      if (isEdit) {
        await mcpServersAPI.update(id, {
          name: form.name,
          icon: form.icon,
          color: form.color,
          category: form.category,
          skill_scopes: { scopes: form.targets },
        });
      } else {
        await mcpServersAPI.createFromUrl({
          url,
          name: form.name,
          icon: form.icon,
          color: form.color,
          category: form.category,
          targets: form.targets,
        });
      }
      navigate('/owner/mcp-servers');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleRefresh = async () => {
    setBusy(true);
    try {
      const { data } = await mcpServersAPI.refresh(id);
      setDiscovered({ server_name: data.name, tools: data.tools_schema || [] });
      setExisting(data);
    } catch (e) {
      alert(e?.response?.data?.error || 'Refresh failed');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${form.name}"?`)) return;
    try {
      await mcpServersAPI.delete(id);
      navigate('/owner/mcp-servers');
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit ${existing?.name || ''}` : 'New MCP Server'}
      </h1>

      {/* Discovery section — only for new */}
      {!isEdit && (
        <div className="space-y-3 p-4 border border-ink/10 rounded-sm">
          <Field label="MCP Server URL">
            <div className="flex gap-2">
              <input
                className={inputClass}
                placeholder="https://mcp-server.example.com/sse"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <button
                className={secondaryClass}
                onClick={handleDiscover}
                disabled={discovering || !url}
              >
                {discovering ? 'Discovering...' : 'Discover'}
              </button>
            </div>
          </Field>
          {discoverError && (
            <p className="text-sm text-red-600">{discoverError}</p>
          )}
        </div>
      )}

      {/* Discovered tools preview */}
      {discovered && (
        <div className="space-y-3">
          <div className="p-4 border border-ink/10 rounded-sm bg-ink/[0.02]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-ink">
                Available Tools ({discovered.tools.length})
              </h3>
              {isEdit && !existing?.is_builtin && (
                <button
                  className={secondaryClass}
                  onClick={handleRefresh}
                  disabled={busy}
                >
                  Refresh Tools
                </button>
              )}
            </div>
            <div className="space-y-1">
              {discovered.tools.map((tool, i) => (
                <div key={i} className="text-sm py-1 border-b border-ink/5 last:border-0">
                  <span className="font-mono text-xs text-ink/80">{tool.name}</span>
                  {tool.description && (
                    <span className="ml-2 text-ink/50">{tool.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Metadata form */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Name" error={errors.name}>
              <input
                className={inputClass}
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                disabled={isEdit && existing?.is_builtin}
              />
            </Field>
            <Field label="Category">
              <select
                className={inputClass}
                value={form.category}
                onChange={(e) => set('category', e.target.value)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Icon (name)">
              <input
                className={inputClass}
                value={form.icon}
                onChange={(e) => set('icon', e.target.value)}
              />
            </Field>
            <Field label="Color">
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                  className="w-10 h-10 border border-ink/20 rounded-sm cursor-pointer"
                />
                <input
                  className={inputClass}
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                  maxLength={7}
                />
              </div>
            </Field>
          </div>

          {/* Target checkboxes */}
          <div className="space-y-2">
            <span className="text-xs label-mono text-ink/60">Connect to targets</span>
            <div className="flex gap-4">
              {TARGETS.map((t) => (
                <label key={t.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.targets.includes(t.value)}
                    onChange={() => toggleTarget(t.value)}
                    disabled={isEdit && existing?.is_builtin}
                  />
                  {t.label}
                </label>
              ))}
            </div>
          </div>

          {/* Errors */}
          {errors.detail && (
            <p className="text-sm text-red-600">{String(errors.detail)}</p>
          )}
          {errors.error && (
            <p className="text-sm text-red-600">{String(errors.error)}</p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            {!(isEdit && existing?.is_builtin) && (
              <button className={buttonClass} onClick={handleSave} disabled={busy}>
                {isEdit ? 'Save' : 'Save & Connect All Clients'}
              </button>
            )}
            <button
              className={secondaryClass}
              onClick={() => navigate('/owner/mcp-servers')}
            >
              {isEdit && existing?.is_builtin ? 'Back' : 'Cancel'}
            </button>
            {isEdit && !existing?.is_builtin && (
              <button
                className="ml-auto px-4 py-2 border border-red-600 text-red-600 rounded-sm text-sm"
                onClick={handleDelete}
              >
                Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MCPServerEditPage;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/MCPServerEditPage.jsx
git commit -m "feat(frontend): add MCPServerEditPage with discovery flow"
```

---

### Task 9: Routes and Sidebar

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/owner/OwnerSidebar.jsx`

- [ ] **Step 1: Add imports to App.jsx**

At the end of the owner admin imports block (after `import PlatformDefaultsPage`), add:

```javascript
import MCPServersPage from './pages/owner/MCPServersPage';
import MCPServerEditPage from './pages/owner/MCPServerEditPage';
```

- [ ] **Step 2: Add routes to App.jsx**

Inside the `<Route path="/owner" ...>` block, after the `clients` route and before `ai-providers`, add:

```jsx
<Route path="mcp-servers" element={<MCPServersPage />} />
<Route path="mcp-servers/new" element={<MCPServerEditPage />} />
<Route path="mcp-servers/:id" element={<MCPServerEditPage />} />
```

- [ ] **Step 3: Add sidebar item to OwnerSidebar.jsx**

In the `NAV` array, after `{ to: '/owner/clients', label: 'Clients' }` and before the AI Providers group, add:

```javascript
{ to: '/owner/mcp-servers', label: 'MCP Servers' },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/owner/OwnerSidebar.jsx
git commit -m "feat(frontend): wire MCP servers routes and sidebar navigation"
```

---

### Task 10: Smoke Test

- [ ] **Step 1: Start backend and verify API**

```bash
cd /home/dchuprina/jeevs/backend && python manage.py migrate
```

Then start the server and test:
```bash
# Get JWT token (use existing test/owner credentials)
# GET /api/owner/tools/ should return the 8 seeded builtin tools
```

- [ ] **Step 2: Start frontend and verify pages**

```bash
cd /home/dchuprina/jeevs/frontend && npm run dev
```

Navigate to `/owner/mcp-servers` — should see the 8 builtin tools in the table.
Click "Edit" on one — should show tools list and metadata form (read-only for builtin).
Click "+ Add MCP Server" — should show URL input with Discover button.

- [ ] **Step 3: Final commit if any fixes needed**
