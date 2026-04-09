# Chat "WOW" Features — Flow Diagram Visual Transfer

**Date:** 2026-03-23
**Approach:** C — Frontend-first with progressive enhancement
**Scope:** Full-stack (SSE protocol + React components + CSS animations)

---

## 1. SSE Protocol Extension (Backend)

### New event types in orchestrator SSE stream

```
event: tool_start
data: {"tool": "send-email", "params": {"to": "user@mail.com", "subject": "Report"}, "call_id": "tc_123"}

event: tool_result
data: {"call_id": "tc_123", "status": "success", "summary": "Email sent", "data": {...}}

event: tool_error
data: {"call_id": "tc_123", "error": "SMTP timeout"}
```

**Files:** `orchestrator.py` (add `on_event` callback in tool_calls loop), `views.py` (proxy via `yield self._sse(...)`)

**Backward compat:** Old clients ignore unknown event types.

---

## 2. Component Architecture

New files in `nextlen/src/components/sandbox/chat/`:

| File | Purpose | Lines |
|------|---------|-------|
| `ToolExecutionNode.jsx` | Tool call card (running/success/error) | ~120 |
| `DataCard.jsx` | Structured cards for leads/emails/files/KB | ~100 |
| `QuickActions.jsx` | Contextual action chips | ~60 |
| `ThinkingPipeline.jsx` | Flow-style thinking indicator | ~80 |
| `LiveStatus.jsx` | Connected tools status | ~40 |

**ChatWindow.jsx changes:**
- New state: `toolCalls` array `{id, tool, params, status, result}`
- SSE handler extended for `tool_start` / `tool_result` / `tool_error`
- Tool nodes rendered between user message and bot response
- QuickActions after bot message
- ThinkingPipeline replaces bouncing dots
- LiveStatus under header

---

## 3. Tool Execution Nodes

Visual: compact card, full message-area width, flow diagram node style.

**Styles:**
- Background: `bg-gray-800/90` dark / `bg-white/90` light
- Left border 4px by tool type:
  - `#00d9a3` green — channel tools (email, telegram)
  - `#a29bfe` purple — AI operations (KB search, generate)
  - `#fbbf24` amber — lead management
  - `#6b7280` gray — unknown/other
- Border: `border border-gray-700/50` dark / `border-gray-200` light
- Rounded: `rounded-xl`

**Three states:**
1. Running — pulsing dot + "Processing..." + skeleton shimmer
2. Success — green check + summary + expanded params
3. Error — red X + error message

**Animation:** `flow-node-enter` (scale 0.85->1, 0.4s)

**Tool type mapping:**
```js
const TOOL_MAP = {
  'send-email':    { icon: Mail,      label: 'Email',          color: 'green' },
  'rag-search':    { icon: Search,    label: 'Knowledge Base', color: 'purple' },
  'lead-search':   { icon: Users,     label: 'Leads',          color: 'amber' },
  'lead-create':   { icon: UserPlus,  label: 'Create Lead',    color: 'amber' },
  'web-research':  { icon: Globe,     label: 'Web Research',   color: 'purple' },
  'generate-file': { icon: FileDown,  label: 'Generate File',  color: 'green' },
};
```

**Fallback:** regex parse markdown when SSE not available.

---

## 4. Message Animations

Replace uniform `animate-in` with per-type animations:

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| User message | slide from right + scale | 0.3s | ease-out |
| Bot message | fade + slide up | 0.4s | cubic-bezier(0.16,1,0.3,1) |
| Tool node | `flow-node-enter` (reuse) | 0.4s | cubic-bezier(0.16,1,0.3,1) |
| Quick chips | scale overshoot | 0.35s | cubic-bezier(0.34,1.56,0.64,1) |
| Sequential | +100ms delay per element | — | — |

`prefers-reduced-motion`: all animations become instant opacity-only.

---

## 5. Structured Data Cards

**Lead Card:** status pill (colored), heat stars, name, contact, quick actions (View, Change Status)
- Left border: `border-l-4 border-amber-400`

**File Card:** file type icon, name, size, download button with gradient bg
**Email Preview:** to, subject, truncated body, success/error indicator
**KB Search Results:** document list with relevance scores, expand/collapse

Detection: SSE `tool_result.data` first, regex fallback on markdown.
Animation: `flow-node-enter`, sequential delay 100ms.

---

## 6. Quick Action Chips

2-4 contextual chips after bot response:

| Context | Chips |
|---------|-------|
| After email | Resend, Edit & Resend, View in History |
| After leads | Show Details, Export CSV, Change Status |
| After KB | Search Again, Save Answer, More Results |
| Default | Tell me more, Start over |

Style: `rounded-full px-3 py-1.5 text-xs`, gradient border, hover `bg-{color}-500/10`
Animation: `chat-chip-pop` with 50ms sequential delay
Click: inserts prompt into input and auto-sends

---

## 7. Thinking Pipeline

Replaces bouncing dots + ToolCallBadge. Horizontal step chain:

```
Your message -> [AI Processing ...] -> [Knowledge Base] -> ...
```

- Steps connected by thin gradient line with `flow-dash` animation
- Active step: pulsing dot + bold
- Completed steps: dim + checkmark
- New step added on `tool_start` SSE event
- Compact mode (>3 steps): `Step 3/5: Searching leads...`

---

## 8. Live Status Indicator

Under "Chat Test" header:

```
* AI Assistant active . Knowledge Base connected . 3 tools ready
```

- Green pulsing dot (`animate-pulse`)
- Text: `text-xs text-gray-400`
- Data: fetch `/tools/connections/` on mount

---

## 9. CSS Architecture

All in `index.css` under `/* Chat — tool execution & animations */` section.

**New keyframes:** `chat-msg-user`, `chat-msg-bot`, `chat-chip-pop`, `chat-shimmer`
**Reused:** `flow-node-enter`, `flow-dash`, `animate-pulse`

**Tool color tokens in `:root`:**
```css
--tool-green: #00d9a3;
--tool-purple: #a29bfe;
--tool-amber: #fbbf24;
--tool-gray: #6b7280;
```

---

## Priority

| # | Feature | Priority |
|---|---------|----------|
| 1 | Tool Execution Nodes | P0 |
| 2 | Message enter animations | P0 |
| 3 | Structured Data Cards | P1 |
| 4 | Quick-action chips | P1 |
| 5 | Thinking Pipeline | P1 |
| 6 | Live Status | P2 |
| 7 | SSE protocol extension | P0 (enables real data) |

**Total:** ~600 lines new code, ~80 lines changes in existing files.
