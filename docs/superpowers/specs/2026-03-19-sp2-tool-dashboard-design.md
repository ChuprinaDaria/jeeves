# SP2: Tool Dashboard — Design Spec

> Beautiful visual tool cards on dashboard. Client connects tools with one click.
> No "MCP" in UI. Non-tech descriptions. shadcn/ui components. Feature-flagged.

---

## Overview

Replace the current `IntegrationsPage` (hardcoded per-integration modals, 30+ state variables) with a dynamic Tool Dashboard that reads from the `ToolCard` / `ToolConnection` backend (SP1).

Clients see beautiful cards like "WhatsApp Business — дозвольте асистенту відповідати вашим клієнтам". Click → fill credentials → connected. No technical jargon.

**Gated by:** `FeatureFlag('mcp_tools_dashboard')` — only `srtyh` sees new UI, everyone else sees old IntegrationsPage.

---

## What Changes

| Current | New |
|---------|-----|
| `IntegrationsPage.jsx` — 6 hardcoded integrations, 30+ useState | `ToolsPage.jsx` — dynamic from API, minimal state |
| `IntegrationCard.jsx` — static props | `ToolCard.jsx` — renders from `GET /api/tools/catalog/` |
| Per-integration modals (WhatsAppSetup, TelegramSetup...) | Universal `ConnectModal.jsx` — dynamic form from `auth_config` |
| Dashboard has no tools | Dashboard shows connected tools summary strip |

---

## Tech Stack

- React 19 (existing)
- Tailwind CSS 3.4 (existing)
- Lucide React icons (existing)
- No new UI library — keep existing Tailwind component system (`.card`, `.btn-primary`)
- i18next for translations (existing)

Why no shadcn/ui: project already has its own Tailwind design system with dark mode, custom components, mobile-first approach. Adding shadcn/ui would create two competing systems. Better to extend what exists.

---

## New API Client

```javascript
// src/api/tools.js

import api from './axios';

export const toolsAPI = {
  getCatalog: () => api.get('/tools/catalog/'),
  connect: (slug, credentials) => api.post(`/tools/${slug}/connect/`, { credentials }),
  disconnect: (slug) => api.post(`/tools/${slug}/disconnect/`),
  getStatus: (slug) => api.get(`/tools/${slug}/status/`),
  getMyTools: () => api.get('/tools/my/'),
};
```

---

## Components

### 1. ToolsPage.jsx (replaces IntegrationsPage)

Full page with tool catalog. Categories as filter tabs.

```
┌─────────────────────────────────────────────┐
│  Tools & Integrations              [search] │
│                                             │
│  [All] [Communication] [AI] [Productivity]  │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 💬       │ │ ✈️       │ │ 📧       │   │
│  │ WhatsApp │ │ Telegram │ │ Email    │   │
│  │ Business │ │ Bot      │ │          │   │
│  │          │ │          │ │          │   │
│  │ Дозволь- │ │ Підклю-  │ │ Асистент │   │
│  │ те асис- │ │ чіть Tg  │ │ надсила- │   │
│  │ тенту... │ │ бота...  │ │ тиме...  │   │
│  │          │ │          │ │          │   │
│  │ ● Connected│ ○ Setup  │ │ ● Connected│  │
│  └──────────┘ └──────────┘ └──────────┘   │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 📱       │ │ 💬       │ │ 👥       │   │
│  │ WhatsApp │ │ Web Chat │ │ Live     │   │
│  │ Personal │ │          │ │ Manager  │   │
│  │ ...      │ │ ...      │ │ ...      │   │
│  └──────────┘ └──────────┘ └──────────┘   │
│                                             │
│  ┌──────────┐                               │
│  │ 📖       │                               │
│  │ Knowledge│                               │
│  │ Base     │                               │
│  │ ...      │                               │
│  └──────────┘                               │
└─────────────────────────────────────────────┘
```

**Data flow:**
1. `useEffect` → `toolsAPI.getCatalog()`
2. Response contains tools + connection status per tool
3. Filter by category tab
4. Click card → if connected: show status. If not: open `ConnectModal`

### 2. ToolCard.jsx (replaces IntegrationCard)

Single tool card. Renders from API data, not hardcoded props.

```jsx
// Props: { tool } where tool = catalog item from API
// tool.slug, tool.name, tool.tagline, tool.icon, tool.color
// tool.category, tool.auth_type, tool.connection (null or {status, enabled, connected_at})
```

Visual states:
- **Not connected** — muted card, "Connect" button
- **Connected** — accent border (tool.color), green dot, "Connected" badge, "Configure" button
- **Error** — red border, error icon, "Retry" button
- **Pending** — pulsing border, spinner, "Connecting..." text

### 3. ConnectModal.jsx (universal, replaces all per-integration modals)

Dynamic form generated from `tool.auth_config.fields`:

```
┌──────────────────────────────────┐
│  Connect WhatsApp Business    ✕  │
│                                  │
│  Дозвольте асистенту відповідати │
│  вашим клієнтам у WhatsApp       │
│                                  │
│  WABA ID                         │
│  ┌────────────────────────────┐  │
│  │                            │  │
│  └────────────────────────────┘  │
│                                  │
│  App ID                          │
│  ┌────────────────────────────┐  │
│  │                            │  │
│  └────────────────────────────┘  │
│                                  │
│  App Secret                      │
│  ┌────────────────────────────┐  │
│  │ ••••••••••                 │  │
│  └────────────────────────────┘  │
│                                  │
│  [Cancel]            [Connect]   │
└──────────────────────────────────┘
```

Field types from `auth_config.fields[].type`:
- `text` (default) → `<input type="text">`
- `password` → `<input type="password">` with show/hide toggle
- `checkbox` → toggle switch
- `tags` → multi-value input (for Matrix manager IDs)

For `auth_type === 'none'` → connect immediately, no modal.
For `auth_type === 'qr_code'` → show QR code flow (reuse existing WhatsApp QR logic).
For `auth_type === 'oauth2'` → redirect to `auth_url` from API response.

### 4. ToolStatusBadge.jsx

Inline status component for connected tools:

```jsx
// Connected: green dot + "Connected" + time ago
// Error: red dot + "Error" + retry link
// Pending: yellow dot + "Connecting..."
```

### 5. DashboardToolsStrip.jsx (on Dashboard page)

Horizontal strip showing connected tools on the main dashboard:

```
Connected Tools (4)
[💬 WhatsApp ✓] [✈️ Telegram ✓] [📧 Email ✓] [📖 Knowledge ✓]  [+ Add more]
```

Click on tool → navigates to ToolsPage. Click "+ Add more" → navigates to ToolsPage.

---

## Feature Flag Gating

### In React (routing level)

```jsx
// App.jsx — route level switch
{client?.feature_flags?.mcp_tools_dashboard ? (
  <Route path="tools" element={<ToolsPage />} />
) : (
  <Route path="integrations" element={<IntegrationsPage />} />
)}
```

### Backend API for flags

Add endpoint to expose client's feature flags:

```python
# In existing /api/clients/me/ response, add:
{
  ...existing_fields,
  "feature_flags": {
    "mcp_tools_dashboard": true/false,
    "mcp_sse_streaming": true/false,
  }
}
```

One query to `FeatureFlag.is_enabled()` per flag. Cached 60s.

---

## Sidebar Navigation

Current sidebar has "Integrations" link. For flagged clients, change to "Tools":

```jsx
// Sidebar.jsx
{featureFlags.mcp_tools_dashboard ? (
  <NavItem to="tools" icon={Puzzle} label="Tools" />
) : (
  <NavItem to="integrations" icon={Plug} label="Integrations" />
)}
```

---

## File Structure

```
src/
├── api/
│   └── tools.js                    # NEW — tools API client
├── pages/
│   ├── IntegrationsPage.jsx        # KEEP — old code for non-flagged clients
│   └── ToolsPage.jsx               # NEW — dynamic tool catalog
├── components/
│   ├── integrations/               # KEEP — old components
│   └── tools/                      # NEW
│       ├── ToolCard.jsx            # Single tool card
│       ├── ConnectModal.jsx        # Universal connect dialog
│       ├── ToolStatusBadge.jsx     # Status indicator
│       ├── DashboardToolsStrip.jsx # Dashboard summary strip
│       └── CategoryFilter.jsx      # Tab filter for categories
├── App.jsx                         # MODIFY — add conditional route
└── components/layout/
    └── Sidebar.jsx                 # MODIFY — conditional nav item
```

---

## i18n Keys

```json
{
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
    "modal": {
      "connect": "Connect",
      "cancel": "Cancel",
      "disconnectConfirm": "Are you sure you want to disconnect?"
    },
    "categories": {
      "communication": "Communication",
      "productivity": "Productivity",
      "analytics": "Analytics",
      "ai": "AI & Knowledge",
      "crm": "CRM & Sales",
      "custom": "Custom"
    }
  }
}
```

Add to all 7 locales (en, de, fr, es, it, nl, da).

---

## Backend Changes

### 1. Feature flags in /api/clients/me/

Add to existing `ClientDetailSerializer`:

```python
feature_flags = serializers.SerializerMethodField()

def get_feature_flags(self, obj):
    return {
        'mcp_tools_dashboard': FeatureFlag.is_enabled('mcp_tools_dashboard', obj),
        'mcp_sse_streaming': FeatureFlag.is_enabled('mcp_sse_streaming', obj),
    }
```

### 2. CSRF exemption for tools API

Tools views use DRF `APIView` — CSRF handled by DRF auth. No changes needed if client uses `X-API-Key` or `Authorization` header (already configured).

---

## Dark Mode

All new components support dark mode via existing Tailwind `dark:` variants. Tool card colors use the `tool.color` hex as accent — render as border-left or top gradient strip, not full background (keeps readability in both modes).

---

## Mobile

Cards stack in single column on mobile (existing `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` pattern from IntegrationsPage). ConnectModal is full-screen on mobile (`fixed inset-0` with safe-area padding).

---

## What SP2 Does NOT Include

- SSE streaming chat (SP3)
- Personal Assistant mode (SP3)
- Agent config editing from frontend (SP3)
- RAG pipeline changes (SP4)
- OAuth2 provider implementation (just redirects to URL from API)
- Deletion of old IntegrationsPage (kept for non-flagged clients)
