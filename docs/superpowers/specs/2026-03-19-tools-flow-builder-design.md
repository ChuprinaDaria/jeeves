# Tools Flow Builder — Design Spec

**Date:** 2026-03-19
**Branch:** `feature/sp1-mcp-core-engine`
**Replaces:** Current `ToolsPage` grid layout

## Overview

Visual flow builder page where clients see their AI Assistant and Client Manager as central nodes, with MCP tools around them connected by animated bezier lines. Tools are authenticated via flip-card interaction and auto-positioned on the canvas once connected.

## Page Layout

```
+------------------------------------------------------------------+
|  [ Tool Card ] [ Tool Card ] [ Tool Card ] ... (horizontal scroll)|
+------------------------------------------------------------------+
|                                                                    |
|     [WhatsApp]---bezier--→  ┌──────────┐                          |
|     [Telegram]---bezier--→  │    AI     │  escalation   ┌────────┐|
|     [Knowledge]--bezier--→  │ Assistant │ ··········→    │ Client │|
|                             └──────────┘                │Manager │|
|                                          [Calendar]--→  └────────┘|
|                                          [HITL]------→            |
|                                                                    |
+------------------------------------------------------------------+
```

### Top: Tool Catalog Strip

- Horizontal scrollable row of all available tools from `toolsAPI.getCatalog()`
- Cards are ~160px wide, compact
- **Disconnected** cards: `opacity-60`, dashed border, greyed icon
- **Connected** cards: `opacity-100`, solid border with category color left stripe, green dot
- Horizontal scroll with subtle fade masks on edges

### Center: Canvas Area

- Full width, min-height `max(60vh, 400px)`, grows to fit content: `max(60vh, connectedToolsCount * 80px + 200px)`
- **Dark mode:** `bg-gray-900`, dot grid pattern (radial gradient dots)
- **Light mode:** `bg-gray-50`, clean background without dots
- Two immovable core nodes, auto-positioned center-left and center-right
- Connected tool nodes auto-positioned around their core node
- SVG overlay layer for bezier connections

## Core Nodes

### AI Assistant
- Lucide icon: `Bot`
- Color: `primary-500` (#6366f1) — indigo
- Glow: `box-shadow: 0 0 40px rgba(99,102,241,0.15)` (dark), soft shadow (light)
- Label: "AI Assistant"
- Subtitle: "Central AI engine"
- Left-side ports (small circles) for tool connections

### Client Manager
- Lucide icon: `UserCircle`
- Color: `green-500` (#22c55e) — emerald
- Glow: `box-shadow: 0 0 40px rgba(34,197,94,0.15)` (dark), soft shadow (light)
- Label: "Client Manager"
- Subtitle: "HITL escalation"
- Left-side ports for tool connections

### Escalation Link
- Thin dashed line between Assistant and Manager
- Label "escalation" in the middle
- Always visible

## Tool Cards (Flip Interaction)

### Front Face (default)
- Lucide icon matching tool (from icon field or mapped)
- Tool name + short tagline
- Category color indicator (left stripe)
- **Disconnected:** dashed border, `opacity-60`, hover shows hint tooltip
- **Connected:** solid border, `opacity-100`, green status dot, category color stripe

### Back Face (auth form) — shown on click of disconnected card
- 3D CSS `rotateY(180deg)` flip animation, `perspective: 1000px`
- Content depends on `tool.auth_type`:
  - `none` — card does NOT flip. Instead: brief loading spinner overlay on front face, auto-connect API call, on success card transitions to connected state with a pulse animation. No back face needed.
  - `qr_code` — QR image + "Waiting for scan..." spinner, polling via `tool.auth_config.initiate_url` (falls back to `/clients/whatsapp/bridge/login/`). Status polling via `tool.auth_config.status_url` (falls back to `/clients/whatsapp/bridge/login/status/`). This keeps QR flow generic for future QR-based tools.
  - Text fields (API key, token, password) — compact form with submit
  - OAuth — "Connect with..." button, redirects to `auth_url` from connect response
- "Cancel" button to flip back to front
- On successful connect: flip back with bounce, card becomes active, bezier appears

### Error Handling on Back Face
- API errors show inline on the back face (red text below the form, same pattern as existing `ConnectModal`)
- Card stays flipped until user either fixes the error and retries, or clicks "Cancel"
- Network timeout (10s): show "Connection timed out. Please try again." on back face
- QR polling timeout (120s): show "QR code expired" with "Try again" button that restarts the QR flow
- After any error, card does NOT auto-flip — user stays in control

### Card Category Colors
- `communication` — green (`#22c55e`)
- `ai` — indigo (`#6366f1`)
- `productivity` — orange (`#f97316`)
- `analytics` — blue (`#3b82f6`)
- `crm` — pink (`#ec4899`)
- `custom` — gray (`#6b7280`)

## Tool-to-Node Assignment

### Strategy: Frontend Hardcoded Mapping

The backend API (`/tools/catalog/`) does **not** return `targets` or `connected_to` fields. These are **not** added to the backend — the frontend owns the mapping via a constant:

```js
// src/components/tools/toolTargets.js
export const TOOL_TARGETS = {
  'whatsapp-meta':   ['assistant'],
  'whatsapp-bridge': ['assistant'],
  'telegram':        ['assistant'],
  'instagram':       ['assistant'],
  'email-smtp':      ['assistant'],
  'web-widget':      ['assistant'],
  'rag-search':      ['assistant'],
  'translation':     ['assistant'],
  'hitl-matrix':     ['manager'],
  'calendar':        ['manager'],
  'crm':             ['assistant', 'manager'],
  'analytics':       ['assistant', 'manager'],
};

// Fallback for unknown tools: default to ['assistant']
export const getToolTargets = (slug) => TOOL_TARGETS[slug] || ['assistant'];
```

This avoids a backend migration and keeps the visual layout as a pure frontend concern. If the backend later adds a `targets` field, the frontend can switch to reading it from the API response.

### Layout Rules
- Tools targeting only assistant — positioned left of Assistant node
- Tools targeting only manager — positioned right of Manager node
- Tools targeting both — positioned above center, two bezier lines
- Connection lines only attach to valid targets (dragging to an invalid node does nothing)

### Default Target Mapping
| Tool | Targets |
|------|---------|
| WhatsApp (Meta) | assistant |
| WhatsApp Bridge | assistant |
| Telegram | assistant |
| Instagram | assistant |
| Email SMTP | assistant |
| Web Chat | assistant |
| Knowledge Base | assistant |
| Translation | assistant |
| HITL Matrix | manager |
| Calendar | manager |
| CRM | both |
| Analytics | both |

## SVG Connections

### Bezier Lines
- SVG `<path>` with cubic bezier from tool card to core node port
- Two layers per connection:
  1. Background path: thick (6px), low opacity (0.08), gradient fill
  2. Foreground path: thin (2px), animated dash (`stroke-dasharray: 8 4`, `stroke-dashoffset` animation)
- Gradient: indigo for assistant connections, emerald for manager connections

### SVG Gradients
```xml
<linearGradient id="grad-assistant">
  <stop offset="0%" stop-color="#6366f1" stop-opacity="0.6"/>
  <stop offset="100%" stop-color="#818cf8" stop-opacity="0.3"/>
</linearGradient>
<linearGradient id="grad-manager">
  <stop offset="0%" stop-color="#22c55e" stop-opacity="0.6"/>
  <stop offset="100%" stop-color="#4ade80" stop-opacity="0.3"/>
</linearGradient>
```

### Particles
- 3 small circles per connection that travel along the path
- Primary: CSS `offset-path` with `offset-distance` animation
- Fallback (Safari < 16): SVG `<animateMotion>` along the same path — detected via `CSS.supports('offset-path', 'path("")')` at runtime
- Duration: 2-3s, staggered delays (0, 0.8s, 1.6s)
- Color matches gradient (indigo dot for assistant, green for manager)

### Appearance Animation
- On page load: core nodes fadeIn + scale (0.3s)
- Then connections "grow" one by one with 200ms stagger (stroke-dashoffset from 100% to 0)
- Particles start after line is fully drawn

## Hover & Interaction Effects

### Disconnected Card Hover
- `opacity-60` → `opacity-80`
- Tooltip: tool description + "Click to connect"

### Connected Card Hover
- Its bezier line brightens (opacity 0.3 → 0.8)
- Other lines dim (opacity → 0.04)
- Tooltip: "Connected to AI Assistant" / "Connected to Client Manager"

### Connected Card Click
- Small popover (not modal): Configure / Disconnect buttons
- Disconnect: confirmation → API call → card returns to disconnected state, bezier fades out

### Core Node Hover
- Tooltip with description:
  - Assistant: "Handles automated responses, RAG search, and customer conversations"
  - Manager: "Receives escalated conversations that need human attention"

### SVG Path Hover
- Path brightens, tooltip with tool name + status

## Loading & Error States

### Loading
- Full canvas area shows skeleton: two blurred core node placeholders + 3 shimmer card placeholders in the strip
- Same pattern as current ToolsPage spinner but integrated into layout

### API Error
- Canvas still renders core nodes (they are static, no API needed)
- Tool strip shows inline error banner: "Failed to load tools. [Retry]" with retry button
- No crash, graceful degradation

## Onboarding (Zero-State)

When 0 tools are connected:
- Canvas shows core nodes with a pulsing arrow from the tool strip down
- Text: "Click a tool to get started"
- Disappears after first successful connection

## Toast Notifications

- Bottom-right, slide up animation
- On connect: "WhatsApp connected to AI Assistant"
- On disconnect: "WhatsApp disconnected"
- Auto-dismiss after 2.5s

## Dark / Light Theme

| Element | Dark | Light |
|---------|------|-------|
| Canvas bg | `gray-900` | `gray-50` |
| Dot grid | visible (rgba white 0.03) | hidden |
| Core node bg | `gray-800` | `white` |
| Core node border | colored, 40% opacity | colored, 20% opacity |
| Glow | colored box-shadow | soft neutral shadow |
| Card bg | `gray-800` | `white` |
| Card border | `gray-700` | `gray-200` |
| SVG lines | brighter gradients | softer gradients |
| Particles | full brightness | 70% opacity |
| Text | `gray-100` / `gray-400` | `gray-900` / `gray-500` |

## Component Structure

```
ToolsPage.jsx (rewritten)
├── ToolCatalogStrip.jsx
│   └── FlipToolCard.jsx (front/back, flip animation, auth form)
├── FlowCanvas.jsx
│   ├── CoreNode.jsx (AI Assistant / Client Manager)
│   ├── CanvasToolNode.jsx (connected tool on canvas)
│   ├── ConnectionsLayer.jsx (SVG bezier + particles)
│   └── OnboardingHint.jsx (zero-state)
├── ToolPopover.jsx (configure/disconnect on click)
└── FlowToast.jsx (notifications)
```

## API Integration

### Data Loading
```js
// On mount
const catalog = await toolsAPI.getCatalog();
// catalog[i].connection?.status === 'connected'
// catalog[i].connection?.connected_to === 'assistant' | 'manager'
// catalog[i].targets === ['assistant'] | ['manager'] | ['assistant', 'manager']
```

### Connect Flow
```js
// 1. User clicks disconnected card → flip to back
// 2. Auth form submits
const res = await toolsAPI.connect(slug, credentials);
// 3. If res.status === 'connected' → flip back, draw bezier
// 4. If QR flow → start polling
```

### Disconnect Flow
```js
// 1. User clicks connected card → popover
// 2. Clicks "Disconnect" → confirm
await toolsAPI.disconnect(slug);
// 3. Card returns to disconnected, bezier fades out
```

## Auto-Layout Algorithm

Connected tools are positioned automatically around their core node:

1. Collect tools by target into 3 groups: assistant-only (left), manager-only (right), both (top-center)
2. Each group distributes vertically with equal spacing. Available vertical space = canvas height minus padding (40px top/bottom)
3. If a group has 0 tools, its side is simply empty — core nodes stay in their fixed positions
4. If a group has many tools (8+), vertical spacing compresses but never below 60px per tool. If it would go below, canvas height grows (see min-height formula above)
5. "Both" tools are placed in a horizontal row above the two core nodes, centered. Max 4 in a row, then wraps to second row
6. Canvas tool nodes are ~150px wide, positioned 200px from core node horizontally
7. Recalculate on window resize (debounced 150ms)
8. No manual drag — positions are computed

```
  [Tool1]                              [Tool4]
  [Tool2]  ──→  [Assistant]  ···→  [Manager]  ←──  [Tool5]
  [Tool3]                              [Tool6]

              [BothTool1]  (two lines, one to each)
```

## Existing Components Reuse

- **ConnectModal logic** — auth form logic (QR polling, field rendering) extracted into `FlipToolCard` back face
- **ToolStatusBadge** — reused for status dots on cards
- **toolsAPI** — unchanged, all endpoints stay the same
- **i18n keys** — extend existing `tools.*` namespace

## Files Changed

| File | Action |
|------|--------|
| `src/pages/ToolsPage.jsx` | **Rewrite** — new flow builder layout |
| `src/components/tools/ToolCatalogStrip.jsx` | **New** — horizontal card strip |
| `src/components/tools/FlipToolCard.jsx` | **New** — flip card with auth |
| `src/components/tools/FlowCanvas.jsx` | **New** — canvas with core nodes + SVG |
| `src/components/tools/CoreNode.jsx` | **New** — assistant/manager node |
| `src/components/tools/CanvasToolNode.jsx` | **New** — tool node on canvas |
| `src/components/tools/ConnectionsLayer.jsx` | **New** — SVG bezier + particles |
| `src/components/tools/OnboardingHint.jsx` | **New** — zero-state hint |
| `src/components/tools/ToolPopover.jsx` | **New** — configure/disconnect |
| `src/components/tools/FlowToast.jsx` | **New** — toast notifications |
| `src/components/tools/ToolCard.jsx` | **Keep** — used by DashboardToolsStrip |
| `src/components/tools/ConnectModal.jsx` | **Keep** — logic extracted, component stays for other uses |
| `src/components/tools/CategoryFilter.jsx` | **Remove** — only imported by ToolsPage, safe to delete |
| `src/components/tools/toolTargets.js` | **New** — hardcoded tool→target mapping constant |
| `src/locales/en/translation.json` | **Extend** — new tooltip/hint keys |
| `src/index.css` | **Extend** — flip animation, particle keyframes |

## Notes

- **No global toast system exists** — `FlowToast` is self-contained. If a global toast is added later, migrate.
- **Popover positioning** — `ToolPopover` uses a portal (`createPortal`) and auto-flips to stay within viewport bounds (check available space above/below/left/right).
- **Accessibility** — tracked as follow-up: keyboard triggers for flip cards, `aria-hidden` on SVG decorative elements, focus trapping in popovers. Not blocking for MVP.
