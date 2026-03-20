# SP2: Tool Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded IntegrationsPage with a dynamic Tool Dashboard that reads tools from the SP1 backend API, gated by feature flag.

**Architecture:** Feature-flagged new UI (ToolsPage) alongside old IntegrationsPage. Backend adds `feature_flags` to `/api/clients/me/` response. Frontend creates tools API client, 5 new components (ToolsPage, ToolCard, ConnectModal, ToolStatusBadge, DashboardToolsStrip), conditional routing in App.jsx, conditional nav in Sidebar.jsx. All new components use existing Tailwind design system with dark mode.

**Tech Stack:** React 19, Tailwind CSS 3.4, Lucide React, i18next, Axios, Django REST Framework

**Spec:** `docs/superpowers/specs/2026-03-19-sp2-tool-dashboard-design.md`

---

## File Structure

```
BACKEND (p004_ai_nexelin/MASTER/):
├── clients/serializers.py          MODIFY — add feature_flags to ClientSerializer
├── clients/views.py:1091-1114      MODIFY — no change needed, serializer handles it

FRONTEND (nextlen/src/):
├── api/tools.js                    CREATE — tools API client
├── components/tools/ToolCard.jsx           CREATE — single tool card
├── components/tools/ConnectModal.jsx       CREATE — universal connect dialog
├── components/tools/ToolStatusBadge.jsx    CREATE — status indicator
├── components/tools/DashboardToolsStrip.jsx CREATE — dashboard strip
├── components/tools/CategoryFilter.jsx     CREATE — category tabs
├── pages/ToolsPage.jsx                     CREATE — main tools page
├── App.jsx                                 MODIFY — conditional routing
├── components/layout/Sidebar.jsx           MODIFY — conditional nav item
├── pages/DashboardPage.jsx                 MODIFY — add DashboardToolsStrip
├── locales/en/translation.json             MODIFY — add tools.* keys
```

---

### Task 1: Backend — Add feature_flags to ClientSerializer

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py:16-73`

- [ ] **Step 1: Add feature_flags field to ClientSerializer**

In `p004_ai_nexelin/MASTER/clients/serializers.py`, add the import at top and the SerializerMethodField:

```python
# Add import at top of file (after existing imports):
from MASTER.nexelin_platform.models import FeatureFlag
```

Add to `ClientSerializer` class — add `feature_flags` to `fields` list (after `'updated_at'`) and add the method:

```python
    feature_flags = serializers.SerializerMethodField()

    # Add 'feature_flags' to the fields list in Meta class
    # After 'updated_at' in the list

    def get_feature_flags(self, obj):
        return {
            'mcp_tools_dashboard': FeatureFlag.is_enabled('mcp_tools_dashboard', obj),
            'mcp_sse_streaming': FeatureFlag.is_enabled('mcp_sse_streaming', obj),
        }
```

- [ ] **Step 2: Verify manually**

Start Django shell and test:
```bash
cd p004_ai_nexelin && python manage.py shell -c "
from MASTER.clients.models import Client
from MASTER.clients.serializers import ClientSerializer
c = Client.objects.first()
print(ClientSerializer(c).data.get('feature_flags'))
"
```

Expected: `{'mcp_tools_dashboard': False}` (flag doesn't exist yet → defaults to False)

- [ ] **Step 3: Create the feature flag in DB**

```bash
cd p004_ai_nexelin && python manage.py shell -c "
from MASTER.nexelin_platform.models import FeatureFlag
from MASTER.clients.models import Client
flag, created = FeatureFlag.objects.get_or_create(
    key='mcp_tools_dashboard',
    defaults={'description': 'Show new Tool Dashboard instead of IntegrationsPage', 'rollout': 'selected'}
)
srtyh = Client.objects.filter(tag='srtyh').first()
if srtyh:
    flag.enabled_clients.add(srtyh)
    print(f'Enabled for srtyh (pk={srtyh.pk})')
print(f'Flag: {flag.key} rollout={flag.rollout}')
"
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/serializers.py
git commit -m "feat(clients): add feature_flags to ClientSerializer for SP2 tool dashboard"
```

---

### Task 2: Frontend — Tools API Client

**Files:**
- Create: `nextlen/src/api/tools.js`

- [ ] **Step 1: Create tools API client**

Create `nextlen/src/api/tools.js`:

```javascript
import api from './axios';

export const toolsAPI = {
  getCatalog: () => api.get('/tools/catalog/'),
  connect: (slug, credentials) => api.post(`/tools/${slug}/connect/`, { credentials }),
  disconnect: (slug) => api.post(`/tools/${slug}/disconnect/`),
  getStatus: (slug) => api.get(`/tools/${slug}/status/`),
  getMyTools: () => api.get('/tools/my/'),
};
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/api/tools.js
git commit -m "feat(tools): add tools API client for SP2"
```

---

### Task 3: Frontend — i18n Keys

**Files:**
- Modify: `nextlen/src/locales/en/translation.json`

- [ ] **Step 1: Add tools i18n keys to English locale**

Add the `"tools"` block to `nextlen/src/locales/en/translation.json` (at root level, after existing sections):

```json
  "tools": {
    "title": "Tools & Integrations",
    "subtitle": "Connect tools to enhance your AI assistant",
    "search": "Search tools...",
    "allCategories": "All",
    "connect": "Connect",
    "configure": "Configure",
    "disconnect": "Disconnect",
    "connected": "Connected",
    "notConnected": "Not connected",
    "connecting": "Connecting...",
    "error": "Connection error",
    "retry": "Retry",
    "connectedTools": "Connected Tools",
    "addMore": "Add more",
    "noTools": "No tools found",
    "confirmDisconnect": "Are you sure you want to disconnect this tool?",
    "categories": {
      "communication": "Communication",
      "productivity": "Productivity",
      "analytics": "Analytics",
      "ai": "AI & Knowledge",
      "crm": "CRM & Sales",
      "custom": "Custom"
    }
  }
```

Also add `"tools": "Tools"` to the `"nav"` section.

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/locales/en/translation.json
git commit -m "feat(i18n): add tools dashboard translation keys"
```

---

### Task 4: Frontend — ToolStatusBadge Component

**Files:**
- Create: `nextlen/src/components/tools/ToolStatusBadge.jsx`

- [ ] **Step 1: Create ToolStatusBadge**

Create `nextlen/src/components/tools/ToolStatusBadge.jsx`:

```jsx
import { useTranslation } from 'react-i18next';

const STATUS_CONFIG = {
  connected: {
    dot: 'bg-green-500',
    text: 'text-green-700 dark:text-green-400',
    key: 'tools.connected',
  },
  pending: {
    dot: 'bg-yellow-500 animate-pulse',
    text: 'text-yellow-700 dark:text-yellow-400',
    key: 'tools.connecting',
  },
  error: {
    dot: 'bg-red-500',
    text: 'text-red-700 dark:text-red-400',
    key: 'tools.error',
  },
  disconnected: {
    dot: 'bg-gray-400',
    text: 'text-gray-500 dark:text-gray-400',
    key: 'tools.notConnected',
  },
};

const ToolStatusBadge = ({ status }) => {
  const { t } = useTranslation();
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.disconnected;

  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${config.dot}`} />
      <span className={`text-xs font-medium ${config.text}`}>
        {t(config.key)}
      </span>
    </div>
  );
};

export default ToolStatusBadge;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ToolStatusBadge.jsx
git commit -m "feat(tools): add ToolStatusBadge component"
```

---

### Task 5: Frontend — CategoryFilter Component

**Files:**
- Create: `nextlen/src/components/tools/CategoryFilter.jsx`

- [ ] **Step 1: Create CategoryFilter**

Create `nextlen/src/components/tools/CategoryFilter.jsx`:

```jsx
import { useTranslation } from 'react-i18next';

const CATEGORIES = [
  { key: 'all', labelKey: 'tools.allCategories' },
  { key: 'communication', labelKey: 'tools.categories.communication' },
  { key: 'ai', labelKey: 'tools.categories.ai' },
  { key: 'productivity', labelKey: 'tools.categories.productivity' },
  { key: 'analytics', labelKey: 'tools.categories.analytics' },
  { key: 'crm', labelKey: 'tools.categories.crm' },
  { key: 'custom', labelKey: 'tools.categories.custom' },
];

const CategoryFilter = ({ active, onChange }) => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap gap-2">
      {CATEGORIES.map(({ key, labelKey }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            active === key
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          {t(labelKey)}
        </button>
      ))}
    </div>
  );
};

export default CategoryFilter;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/CategoryFilter.jsx
git commit -m "feat(tools): add CategoryFilter component"
```

---

### Task 6: Frontend — ToolCard Component

**Files:**
- Create: `nextlen/src/components/tools/ToolCard.jsx`

- [ ] **Step 1: Create ToolCard**

Create `nextlen/src/components/tools/ToolCard.jsx`:

```jsx
import { useTranslation } from 'react-i18next';
import ToolStatusBadge from './ToolStatusBadge';

const ToolCard = ({ tool, onConnect, onConfigure }) => {
  const { t } = useTranslation();
  const conn = tool.connection;
  const isConnected = conn?.status === 'connected' && conn?.enabled;
  const isError = conn?.status === 'error';
  const isPending = conn?.status === 'pending';

  return (
    <div
      className={`relative bg-white dark:bg-gray-800 rounded-xl border p-5 transition-all hover:shadow-md ${
        isConnected
          ? 'border-l-4'
          : isError
          ? 'border-red-300 dark:border-red-700'
          : isPending
          ? 'border-yellow-300 dark:border-yellow-700 animate-pulse'
          : 'border-gray-200 dark:border-gray-700 opacity-80 hover:opacity-100'
      }`}
      style={isConnected ? { borderLeftColor: tool.color || '#6366f1' } : undefined}
    >
      {/* Icon + Name */}
      <div className="flex items-start gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-lg shrink-0"
          style={{ backgroundColor: `${tool.color || '#6366f1'}20` }}
        >
          {tool.icon || '🔧'}
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
            {tool.name}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mt-0.5">
            {tool.tagline}
          </p>
        </div>
      </div>

      {/* Status */}
      <div className="mb-4">
        <ToolStatusBadge status={conn?.status || 'disconnected'} />
      </div>

      {/* Action */}
      {isConnected ? (
        <button
          onClick={() => onConfigure(tool)}
          className="w-full py-2 px-4 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          {t('tools.configure')}
        </button>
      ) : (
        <button
          onClick={() => onConnect(tool)}
          disabled={isPending}
          className="w-full py-2 px-4 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {isPending ? t('tools.connecting') : isError ? t('tools.retry') : t('tools.connect')}
        </button>
      )}
    </div>
  );
};

export default ToolCard;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ToolCard.jsx
git commit -m "feat(tools): add ToolCard component with status states"
```

---

### Task 7: Frontend — ConnectModal Component

**Files:**
- Create: `nextlen/src/components/tools/ConnectModal.jsx`

This is the most complex component — dynamic form from `auth_config.fields`, support for text/password/checkbox field types, QR code flow reuse.

- [ ] **Step 1: Create ConnectModal**

Create `nextlen/src/components/tools/ConnectModal.jsx`:

```jsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Eye, EyeOff, Loader2 } from 'lucide-react';
import { toolsAPI } from '../../api/tools';
import api from '../../api/axios';

const ConnectModal = ({ tool, onClose, onConnected }) => {
  const { t } = useTranslation();
  const [credentials, setCredentials] = useState({});
  const [showPasswords, setShowPasswords] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // QR code state
  const [qrData, setQrData] = useState(null);
  const [loginId, setLoginId] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    // Initialize default values from auth_config fields
    const defaults = {};
    (tool.auth_config?.fields || []).forEach((field) => {
      if (field.type === 'checkbox') {
        defaults[field.name] = field.default || false;
      } else if (field.type === 'tags') {
        defaults[field.name] = field.default || [];
      } else {
        defaults[field.name] = field.default || '';
      }
    });
    setCredentials(defaults);
  }, [tool]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleChange = (name, value) => {
    setCredentials((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await toolsAPI.connect(tool.slug, credentials);
      const data = res.data;

      if (data.status === 'connected') {
        onConnected(tool.slug);
        onClose();
      } else if (data.status === 'pending' && tool.auth_type === 'qr_code') {
        // Start QR flow
        startQrFlow(data.initiate_url);
      } else if (data.auth_url) {
        // OAuth2 redirect
        window.location.href = data.auth_url;
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  const startQrFlow = async (initiateUrl) => {
    try {
      const res = await api.post(initiateUrl || '/clients/whatsapp/bridge/login/');
      if (res.data.qr) {
        setQrData(res.data.qr);
        setLoginId(res.data.login_id);
        startPolling(res.data.login_id);
      }
    } catch (err) {
      setError('Failed to start QR login');
    }
  };

  const startPolling = (id) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/clients/whatsapp/bridge/login/status/?login_id=${id}`);
        const data = res.data;
        if (data.status === 'connected') {
          clearInterval(pollRef.current);
          onConnected(tool.slug);
          onClose();
        } else if (data.qr) {
          setQrData(data.qr);
        }
      } catch {
        // Ignore polling errors
      }
    }, 2500);
  };

  const handleNoAuthConnect = useCallback(async () => {
    setLoading(true);
    try {
      await toolsAPI.connect(tool.slug, {});
      onConnected(tool.slug);
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  }, [tool.slug, onConnected, onClose]);

  // For auth_type === 'none', connect immediately
  useEffect(() => {
    if (tool.auth_type === 'none') {
      handleNoAuthConnect();
    }
  }, [tool.auth_type, handleNoAuthConnect]);

  const fields = tool.auth_config?.fields || [];

  // QR code view
  if (qrData) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {tool.name}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
              <X size={20} />
            </button>
          </div>
          <div className="flex flex-col items-center gap-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
              Scan this QR code with your WhatsApp app
            </p>
            <div className="bg-white p-4 rounded-lg">
              <img
                src={`data:image/png;base64,${qrData}`}
                alt="QR Code"
                className="w-64 h-64"
              />
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Waiting for scan...
            </div>
          </div>
        </div>
      </div>
    );
  }

  // auth_type === 'none' shows loading
  if (tool.auth_type === 'none') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-8">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600 mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t('tools.connect')} {tool.name}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {tool.tagline}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {fields.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {field.label || field.name}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>

              {field.type === 'password' ? (
                <div className="relative">
                  <input
                    type={showPasswords[field.name] ? 'text' : 'password'}
                    value={credentials[field.name] || ''}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    required={field.required}
                    placeholder={field.placeholder || ''}
                    className="input w-full pr-10"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowPasswords((p) => ({ ...p, [field.name]: !p[field.name] }))
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPasswords[field.name] ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              ) : field.type === 'checkbox' ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={credentials[field.name] || false}
                    onChange={(e) => handleChange(field.name, e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {field.description || ''}
                  </span>
                </label>
              ) : field.type === 'tags' ? (
                <input
                  type="text"
                  value={(credentials[field.name] || []).join(', ')}
                  onChange={(e) =>
                    handleChange(
                      field.name,
                      e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                    )
                  }
                  placeholder={field.placeholder || 'value1, value2, value3'}
                  className="input w-full"
                />
              ) : (
                <input
                  type="text"
                  value={credentials[field.name] || ''}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  required={field.required}
                  placeholder={field.placeholder || ''}
                  className="input w-full"
                />
              )}

              {field.hint && (
                <p className="text-xs text-gray-400 mt-1">{field.hint}</p>
              )}
            </div>
          ))}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary flex-1"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {t('tools.connect')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ConnectModal;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ConnectModal.jsx
git commit -m "feat(tools): add ConnectModal with dynamic form and QR code support"
```

---

### Task 8: Frontend — ToolsPage

**Files:**
- Create: `nextlen/src/pages/ToolsPage.jsx`

- [ ] **Step 1: Create ToolsPage**

Create `nextlen/src/pages/ToolsPage.jsx`:

```jsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Loader2 } from 'lucide-react';
import { toolsAPI } from '../api/tools';
import ToolCard from '../components/tools/ToolCard';
import CategoryFilter from '../components/tools/CategoryFilter';
import ConnectModal from '../components/tools/ConnectModal';

const ToolsPage = () => {
  const { t } = useTranslation();
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const [connectTool, setConnectTool] = useState(null);
  const [configureTool, setConfigureTool] = useState(null);

  const loadTools = async () => {
    try {
      const res = await toolsAPI.getCatalog();
      setTools(res.data);
      setError('');
    } catch (err) {
      setError('Failed to load tools');
      console.error('Tools catalog error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTools();
  }, []);

  const handleConnect = (tool) => {
    setConnectTool(tool);
  };

  const handleConfigure = (tool) => {
    setConfigureTool(tool);
  };

  const handleConnected = () => {
    loadTools(); // Refresh catalog
  };

  const handleDisconnect = async (slug) => {
    if (!window.confirm(t('tools.confirmDisconnect'))) return;
    try {
      await toolsAPI.disconnect(slug);
      setConfigureTool(null);
      loadTools();
    } catch (err) {
      console.error('Disconnect error:', err);
    }
  };

  const filtered = tools.filter((tool) => {
    if (category !== 'all' && tool.category !== category) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        tool.name.toLowerCase().includes(q) ||
        tool.tagline.toLowerCase().includes(q)
      );
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {t('tools.title')}
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            {t('tools.subtitle')}
          </p>
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder={t('tools.search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input w-full pl-9"
          />
        </div>
      </div>

      {/* Category Filter */}
      <CategoryFilter active={category} onChange={setCategory} />

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          {t('tools.noTools')}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((tool) => (
            <ToolCard
              key={tool.slug}
              tool={tool}
              onConnect={handleConnect}
              onConfigure={handleConfigure}
            />
          ))}
        </div>
      )}

      {/* Connect Modal */}
      {connectTool && (
        <ConnectModal
          tool={connectTool}
          onClose={() => setConnectTool(null)}
          onConnected={handleConnected}
        />
      )}

      {/* Configure Modal (simple disconnect for now) */}
      {configureTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              {configureTool.name}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {t('tools.connected')} {configureTool.connection?.connected_at
                ? new Date(configureTool.connection.connected_at).toLocaleDateString()
                : ''}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfigureTool(null)}
                className="btn-secondary flex-1"
              >
                {t('common.close')}
              </button>
              <button
                onClick={() => handleDisconnect(configureTool.slug)}
                className="flex-1 py-2 px-4 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                {t('tools.disconnect')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolsPage;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(tools): add ToolsPage with catalog, search, and category filter"
```

---

### Task 9: Frontend — DashboardToolsStrip

**Files:**
- Create: `nextlen/src/components/tools/DashboardToolsStrip.jsx`
- Modify: `nextlen/src/pages/DashboardPage.jsx:109-141`

- [ ] **Step 1: Create DashboardToolsStrip**

Create `nextlen/src/components/tools/DashboardToolsStrip.jsx`:

```jsx
import { useState, useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, CheckCircle } from 'lucide-react';
import { toolsAPI } from '../../api/tools';

const DashboardToolsStrip = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tag: routeTag } = useParams();
  const [searchParams] = useSearchParams();
  const [tools, setTools] = useState([]);

  const tag = routeTag || searchParams.get('tag');

  useEffect(() => {
    toolsAPI.getMyTools()
      .then((res) => setTools(res.data))
      .catch(() => {}); // Silent fail — strip is optional
  }, []);

  if (tools.length === 0) return null;

  const toolsPath = routeTag ? `/l/${routeTag}/tools` : (tag ? `/tools?tag=${tag}` : '/tools');

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          {t('tools.connectedTools')} ({tools.length})
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {tools.map((conn) => (
          <button
            key={conn.tool.slug}
            onClick={() => navigate(toolsPath)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-sm"
          >
            <span>{conn.tool.icon || '🔧'}</span>
            <span className="text-gray-700 dark:text-gray-300">{conn.tool.name}</span>
            <CheckCircle className="w-3.5 h-3.5 text-green-500" />
          </button>
        ))}
        <button
          onClick={() => navigate(toolsPath)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors text-sm text-gray-500 dark:text-gray-400"
        >
          <Plus className="w-3.5 h-3.5" />
          {t('tools.addMore')}
        </button>
      </div>
    </div>
  );
};

export default DashboardToolsStrip;
```

- [ ] **Step 2: Add DashboardToolsStrip to DashboardPage**

In `nextlen/src/pages/DashboardPage.jsx`:

Add import after existing imports (line 7):
```javascript
import DashboardToolsStrip from '../components/tools/DashboardToolsStrip';
```

Add the strip between PixelDashboard and stats grid. After the `{user?.pixel_dashboard_enabled && ...}` block (after line 120), add:

```jsx
      <DashboardToolsStrip />
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/tools/DashboardToolsStrip.jsx nextlen/src/pages/DashboardPage.jsx
git commit -m "feat(tools): add DashboardToolsStrip to dashboard page"
```

---

### Task 10: Frontend — Conditional Routing & Navigation

**Files:**
- Modify: `nextlen/src/App.jsx:1-70`
- Modify: `nextlen/src/components/layout/Sidebar.jsx:1-248`

- [ ] **Step 1: Add ToolsPage route to App.jsx**

In `nextlen/src/App.jsx`:

Add import (after line 13):
```javascript
import ToolsPage from './pages/ToolsPage';
```

Add tools route after the integrations routes. In the `/l/:tag` section (after line 37), add:
```jsx
            <Route path="tools" element={<ToolsPage />} />
```

In the Layout section (after line 54), add:
```jsx
              <Route path="/tools" element={<ToolsPage />} />
```

Note: Both `/integrations` and `/tools` routes exist simultaneously. Sidebar determines which link is shown based on feature flag. This is simpler than conditional Route rendering and allows direct URL access.

- [ ] **Step 2: Update Sidebar to conditionally show Tools vs Integrations**

In `nextlen/src/components/layout/Sidebar.jsx`:

Add `Puzzle` to the lucide-react imports (line 3):
```javascript
import {
  LayoutDashboard,
  GraduationCap,
  FlaskConical,
  Plug2,
  Puzzle,
  MessageSquare,
  BookOpen,
  Settings,
  CreditCard,
  Menu,
  X,
  Users
} from 'lucide-react';
```

In the navItems array (line 73-82), replace the integrations line:
```javascript
    // Old:
    // { to: '/integrations', icon: Plug2, label: t('nav.integrations') },
    // New: conditional based on feature flag
    ...(user?.feature_flags?.mcp_tools_dashboard
      ? [{ to: '/tools', icon: Puzzle, label: t('nav.tools') || 'Tools' }]
      : [{ to: '/integrations', icon: Plug2, label: t('nav.integrations') }]),
```

- [ ] **Step 3: Verify feature_flags reaches user context**

The `user` object in AuthContext comes from `clientAPI.getMe()` which uses `ClientSerializer`. After Task 1, `feature_flags` will be in the response → available via `useAuth().user.feature_flags`.

No changes needed in AuthContext — it already stores the full response: `setUser(data)` (line 55 of AuthContext.jsx).

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/App.jsx nextlen/src/components/layout/Sidebar.jsx
git commit -m "feat(tools): add conditional routing and navigation for tool dashboard"
```

---

### Task 11: Manual Integration Testing

- [ ] **Step 1: Start backend and frontend**

```bash
# Terminal 1: backend
cd p004_ai_nexelin && python manage.py runserver 0.0.0.0:8000

# Terminal 2: frontend
cd nextlen && npm run dev
```

- [ ] **Step 2: Test as srtyh (flagged client)**

1. Open browser → login as srtyh client
2. Verify sidebar shows "Tools" (Puzzle icon), not "Integrations"
3. Click "Tools" → ToolsPage loads with cards from `/api/tools/catalog/`
4. Verify category filter works
5. Verify search works
6. Click "Connect" on a tool → ConnectModal opens with dynamic form
7. Verify Dashboard shows DashboardToolsStrip (if tools are connected)

- [ ] **Step 3: Test as non-flagged client**

1. Login as any other client (not srtyh)
2. Verify sidebar shows "Integrations" (Plug icon)
3. Click "Integrations" → old IntegrationsPage loads
4. Verify `/tools` URL still works if accessed directly (page loads, just not in nav)

- [ ] **Step 4: Test dark mode**

1. Toggle dark mode
2. Verify all new components render correctly in dark mode
3. Check ToolCard accent colors are visible in dark mode

- [ ] **Step 5: Test mobile**

1. Resize browser to mobile width
2. Verify cards stack in single column
3. Verify ConnectModal is usable on mobile
4. Verify DashboardToolsStrip wraps properly

---

### Task 12: Final Commit & Cleanup

- [ ] **Step 1: Run linter**

```bash
cd nextlen && npx eslint src/pages/ToolsPage.jsx src/components/tools/ src/api/tools.js --fix
```

- [ ] **Step 2: Verify no console.logs left in new code**

```bash
grep -rn "console.log" nextlen/src/components/tools/ nextlen/src/pages/ToolsPage.jsx nextlen/src/api/tools.js
```

- [ ] **Step 3: Final commit if any fixes**

```bash
git add nextlen/src/pages/ToolsPage.jsx nextlen/src/components/tools/ nextlen/src/api/tools.js
git commit -m "fix(tools): lint fixes and cleanup for SP2 tool dashboard"
```
