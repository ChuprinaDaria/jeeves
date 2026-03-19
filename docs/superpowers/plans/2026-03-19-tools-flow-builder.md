# Tools Flow Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ToolsPage grid with a visual flow builder showing AI Assistant and Client Manager as central nodes, with connected tools linked by animated SVG bezier lines and flip-card authentication.

**Architecture:** Pure React + SVG canvas approach. Top horizontal strip for tool catalog with flip-card auth. Center canvas with auto-positioned core nodes and connected tool nodes. SVG overlay for bezier connections with particle animations. No external graph libraries.

**Tech Stack:** React 18, Tailwind CSS, Lucide React icons, SVG for connections, CSS transforms for flip animation.

**Spec:** `docs/superpowers/specs/2026-03-19-tools-flow-builder-design.md`

**Note:** `toolsAPI.connect` needs to accept optional axios config for timeout. Update `nextlen/src/api/tools.js`:
```js
connect: (slug, credentials, config) => api.post(`/tools/${slug}/connect/`, { credentials }, config),
```

---

### Task 1: Tool Targets Mapping + CSS Foundations

**Files:**
- Create: `nextlen/src/components/tools/toolTargets.js`
- Modify: `nextlen/src/index.css`

- [ ] **Step 1: Create tool targets mapping**

Create `nextlen/src/components/tools/toolTargets.js`:

```js
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

export const getToolTargets = (slug) => TOOL_TARGETS[slug] || ['assistant'];
```

- [ ] **Step 2: Add CSS keyframes and utilities to index.css**

Append to `nextlen/src/index.css` inside `@layer utilities`:

```css
/* Flow Builder — flip card */
.perspective-1000 {
  perspective: 1000px;
}
.backface-hidden {
  backface-visibility: hidden;
}
.rotate-y-180 {
  transform: rotateY(180deg);
}

/* Flow Builder — dot grid (dark mode only) */
.dot-grid {
  background-image: radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 30px 30px;
}

/* Flow Builder — connection line dash animation */
@keyframes flow-dash {
  to { stroke-dashoffset: -20; }
}
.flow-line-animated {
  stroke-dasharray: 8 4;
  animation: flow-dash 1s linear infinite;
}

/* Flow Builder — particle along path (CSS offset-path) */
@keyframes flow-particle {
  0%   { offset-distance: 0%;   opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { offset-distance: 100%; opacity: 0; }
}
.flow-particle {
  offset-rotate: 0deg;
  animation: flow-particle var(--particle-duration, 2.5s) linear infinite;
  animation-delay: var(--particle-delay, 0s);
}

/* Flow Builder — line grow-in */
@keyframes flow-line-grow {
  from { stroke-dashoffset: var(--path-length); }
  to   { stroke-dashoffset: 0; }
}

/* Flow Builder — node entrance */
@keyframes flow-node-enter {
  from { opacity: 0; transform: scale(0.85); }
  to   { opacity: 1; transform: scale(1); }
}
.flow-node-enter {
  animation: flow-node-enter 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* Flow Builder — toast slide */
@keyframes flow-toast-in {
  from { transform: translateY(80px); opacity: 0; }
  to   { transform: translateY(0); opacity: 1; }
}
@keyframes flow-toast-out {
  from { transform: translateY(0); opacity: 1; }
  to   { transform: translateY(80px); opacity: 0; }
}

/* Flow Builder — card flip bounce */
@keyframes flow-flip-bounce {
  0%   { transform: rotateY(180deg); }
  60%  { transform: rotateY(-10deg); }
  80%  { transform: rotateY(5deg); }
  100% { transform: rotateY(0deg); }
}

/* Flow Builder — pulse for onboarding */
@keyframes flow-pulse-arrow {
  0%, 100% { opacity: 0.4; transform: translateY(0); }
  50%      { opacity: 1;   transform: translateY(8px); }
}
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/tools/toolTargets.js nextlen/src/index.css
git commit -m "feat(tools): add tool targets mapping and flow builder CSS keyframes"
```

---

### Task 2: FlowToast Component

**Files:**
- Create: `nextlen/src/components/tools/FlowToast.jsx`

- [ ] **Step 1: Create FlowToast**

Create `nextlen/src/components/tools/FlowToast.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';

const FlowToast = ({ message, icon, visible, onHide }) => {
  useEffect(() => {
    if (!visible) return;
    const t = setTimeout(() => onHide(), 2500);
    return () => clearTimeout(t);
  }, [visible, onHide]);

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3.5 rounded-xl
        bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
        shadow-lg dark:shadow-2xl text-sm font-medium text-gray-900 dark:text-gray-100
        transition-all duration-400
        ${visible
          ? 'translate-y-0 opacity-100'
          : 'translate-y-20 opacity-0 pointer-events-none'
        }`}
      style={{ transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}
    >
      {icon && <span className="text-lg">{icon}</span>}
      <span>{message}</span>
    </div>
  );
};

export default FlowToast;

// Hook for easy usage
export const useFlowToast = () => {
  const [toast, setToast] = useState({ message: '', icon: '', visible: false });

  const showToast = useCallback((icon, message) => {
    setToast({ icon, message, visible: true });
  }, []);

  const hideToast = useCallback(() => {
    setToast(prev => ({ ...prev, visible: false }));
  }, []);

  return { toast, showToast, hideToast };
};
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/FlowToast.jsx
git commit -m "feat(tools): add FlowToast notification component"
```

---

### Task 3: CoreNode Component

**Files:**
- Create: `nextlen/src/components/tools/CoreNode.jsx`

- [ ] **Step 1: Create CoreNode**

Create `nextlen/src/components/tools/CoreNode.jsx`:

```jsx
import { forwardRef } from 'react';
import { Bot, UserCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const VARIANTS = {
  assistant: {
    Icon: Bot,
    label: 'tools.flow.aiAssistant',
    subtitle: 'tools.flow.centralEngine',
    tooltip: 'tools.flow.assistantTooltip',
    color: 'primary',
    borderClass: 'border-primary-500/40 dark:border-primary-500/40',
    glowClass: 'shadow-[0_0_40px_rgba(99,102,241,0.08)] dark:shadow-[0_0_40px_rgba(99,102,241,0.15)]',
    iconBg: 'bg-primary-500/10 dark:bg-primary-500/20 border border-primary-500/20 dark:border-primary-500/30',
    iconColor: 'text-primary-500',
  },
  manager: {
    Icon: UserCircle,
    label: 'tools.flow.clientManager',
    subtitle: 'tools.flow.hitlEscalation',
    tooltip: 'tools.flow.managerTooltip',
    color: 'green',
    borderClass: 'border-green-500/40 dark:border-green-500/40',
    glowClass: 'shadow-[0_0_40px_rgba(34,197,94,0.08)] dark:shadow-[0_0_40px_rgba(34,197,94,0.15)]',
    iconBg: 'bg-green-500/10 dark:bg-green-500/20 border border-green-500/20 dark:border-green-500/30',
    iconColor: 'text-green-500',
  },
};

const CoreNode = forwardRef(({ variant, connectedCount = 0, style }, ref) => {
  const { t } = useTranslation();
  const v = VARIANTS[variant];
  const { Icon } = v;

  return (
    <div
      ref={ref}
      className={`flow-node-enter absolute w-[200px] bg-white dark:bg-gray-800 border-[1.5px] rounded-2xl p-5 text-center
        ${v.borderClass} ${v.glowClass}`}
      style={style}
      title={t(v.tooltip)}
    >
      {/* Ports on left side */}
      <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-center gap-2 -translate-x-[6px]">
        {Array.from({ length: Math.max(connectedCount, 1) }).map((_, i) => (
          <div
            key={i}
            className={`w-3 h-3 rounded-full border-2 transition-all
              ${i < connectedCount
                ? 'border-green-500 bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
                : 'border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-800'
              }`}
          />
        ))}
      </div>

      <div className={`w-12 h-12 rounded-[14px] mx-auto mb-3 flex items-center justify-center ${v.iconBg}`}>
        <Icon className={`w-6 h-6 ${v.iconColor}`} />
      </div>
      <div className="font-semibold text-[15px] text-gray-900 dark:text-gray-100 mb-1">
        {t(v.label)}
      </div>
      <div className="text-[11px] text-gray-500 dark:text-gray-400">
        {t(v.subtitle)}
      </div>
    </div>
  );
});

CoreNode.displayName = 'CoreNode';
export default CoreNode;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/CoreNode.jsx
git commit -m "feat(tools): add CoreNode component for assistant/manager"
```

---

### Task 4: CanvasToolNode Component

**Files:**
- Create: `nextlen/src/components/tools/CanvasToolNode.jsx`

- [ ] **Step 1: Create CanvasToolNode**

Create `nextlen/src/components/tools/CanvasToolNode.jsx`:

```jsx
import { forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import ToolStatusBadge from './ToolStatusBadge';

const CAT_COLORS = {
  communication: { bg: 'bg-green-500/10 dark:bg-green-500/15', text: 'text-green-500', border: 'border-green-500/30' },
  ai:            { bg: 'bg-primary-500/10 dark:bg-primary-500/15', text: 'text-primary-500', border: 'border-primary-500/30' },
  productivity:  { bg: 'bg-orange-500/10 dark:bg-orange-500/15', text: 'text-orange-500', border: 'border-orange-500/30' },
  analytics:     { bg: 'bg-blue-500/10 dark:bg-blue-500/15', text: 'text-blue-500', border: 'border-blue-500/30' },
  crm:           { bg: 'bg-pink-500/10 dark:bg-pink-500/15', text: 'text-pink-500', border: 'border-pink-500/30' },
  custom:        { bg: 'bg-gray-500/10 dark:bg-gray-500/15', text: 'text-gray-500', border: 'border-gray-500/30' },
};

const CanvasToolNode = forwardRef(({ tool, onClick, isHighlighted, style }, ref) => {
  const { t } = useTranslation();
  const cat = CAT_COLORS[tool.category] || CAT_COLORS.custom;
  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;

  return (
    <div
      ref={ref}
      id={`canvas-tool-${tool.slug}`}
      className={`flow-node-enter absolute w-[160px] bg-white dark:bg-gray-800 border rounded-[14px] p-3.5 cursor-pointer
        transition-all duration-300
        ${isConnected ? `${cat.border} border-opacity-100` : 'border-gray-200 dark:border-gray-700'}
        ${isHighlighted === false ? 'opacity-30' : isHighlighted === true ? 'opacity-100' : 'opacity-100'}
        hover:shadow-md dark:hover:shadow-lg`}
      style={style}
      onClick={(e) => onClick?.(tool, e)}
    >
      {/* Connect port on right */}
      <div
        className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-[6px] w-3 h-3 rounded-full border-2 transition-all
          ${isConnected
            ? 'border-green-500 bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
            : 'border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-800'
          }`}
      />

      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0 ${cat.bg} ${cat.text}`}>
          {tool.icon || '🔧'}
        </div>
        <div className="text-[13px] font-medium text-gray-900 dark:text-gray-100 truncate">
          {tool.name}
        </div>
      </div>

      <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
    </div>
  );
});

CanvasToolNode.displayName = 'CanvasToolNode';
export default CanvasToolNode;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/CanvasToolNode.jsx
git commit -m "feat(tools): add CanvasToolNode for connected tools on canvas"
```

---

### Task 5: ConnectionsLayer (SVG Bezier + Particles)

**Files:**
- Create: `nextlen/src/components/tools/ConnectionsLayer.jsx`

- [ ] **Step 1: Create ConnectionsLayer**

Create `nextlen/src/components/tools/ConnectionsLayer.jsx`:

```jsx
import { useMemo } from 'react';

const supportsOffsetPath = typeof CSS !== 'undefined' && CSS.supports?.('offset-path', 'path("")');

const ConnectionsLayer = ({ connections, highlightedTool }) => {
  // connections = [{ id, pathD, target: 'assistant'|'manager', toolSlug }]

  const gradients = useMemo(() => (
    <>
      <linearGradient id="grad-assistant" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#6366f1" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#818cf8" stopOpacity="0.3" />
      </linearGradient>
      <linearGradient id="grad-manager" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#22c55e" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#4ade80" stopOpacity="0.3" />
      </linearGradient>
      <linearGradient id="grad-escalation" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#6b7280" stopOpacity="0.3" />
        <stop offset="100%" stopColor="#6b7280" stopOpacity="0.1" />
      </linearGradient>
    </>
  ), []);

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: 1 }}
    >
      <defs>{gradients}</defs>

      {connections.map((conn, i) => {
        const gradId = conn.target === 'escalation'
          ? 'grad-escalation'
          : conn.target === 'assistant' ? 'grad-assistant' : 'grad-manager';
        const dotColor = conn.target === 'assistant' ? '#818cf8' : '#4ade80';

        const isHighlighted = highlightedTool === null
          ? true
          : highlightedTool === conn.toolSlug;
        const opacity = isHighlighted ? 1 : 0.08;

        return (
          <g
            key={conn.id}
            className="transition-opacity duration-300"
            style={{ opacity, animationDelay: `${i * 200}ms` }}
          >
            {/* Background glow line */}
            <path
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth="6"
              opacity="0.08"
            />

            {/* Animated foreground line */}
            <path
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth="2"
              className="flow-line-animated"
            />

            {/* Particles */}
            {conn.target !== 'escalation' && [0, 1, 2].map(p => (
              supportsOffsetPath ? (
                <circle
                  key={p}
                  r="3"
                  fill={dotColor}
                  className="flow-particle"
                  style={{
                    offsetPath: `path("${conn.pathD}")`,
                    '--particle-duration': `${2 + Math.random() * 0.5}s`,
                    '--particle-delay': `${p * 0.8}s`,
                  }}
                />
              ) : (
                <circle key={p} r="3" fill={dotColor} opacity="0">
                  <animateMotion
                    dur={`${2 + Math.random() * 0.5}s`}
                    repeatCount="indefinite"
                    begin={`${p * 0.8}s`}
                    path={conn.pathD}
                  />
                  <animate
                    attributeName="opacity"
                    values="0;1;1;0"
                    keyTimes="0;0.1;0.9;1"
                    dur={`${2 + Math.random() * 0.5}s`}
                    repeatCount="indefinite"
                    begin={`${p * 0.8}s`}
                  />
                </circle>
              )
            ))}
          </g>
        );
      })}
    </svg>
  );
};

export default ConnectionsLayer;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ConnectionsLayer.jsx
git commit -m "feat(tools): add ConnectionsLayer with SVG bezier and particles"
```

---

### Task 6: OnboardingHint Component

**Files:**
- Create: `nextlen/src/components/tools/OnboardingHint.jsx`

- [ ] **Step 1: Create OnboardingHint**

Create `nextlen/src/components/tools/OnboardingHint.jsx`:

```jsx
import { ArrowDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const OnboardingHint = () => {
  const { t } = useTranslation();

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-start pt-8 pointer-events-none z-10">
      <div className="flex flex-col items-center gap-2">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
          {t('tools.flow.onboarding')}
        </p>
        <ArrowDown
          className="w-6 h-6 text-primary-400 dark:text-primary-500"
          style={{ animation: 'flow-pulse-arrow 2s ease-in-out infinite' }}
        />
      </div>
    </div>
  );
};

export default OnboardingHint;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/OnboardingHint.jsx
git commit -m "feat(tools): add OnboardingHint for zero-state"
```

---

### Task 7: ToolPopover Component

**Files:**
- Create: `nextlen/src/components/tools/ToolPopover.jsx`

- [ ] **Step 1: Create ToolPopover**

Create `nextlen/src/components/tools/ToolPopover.jsx`:

```jsx
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Unplug } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const ToolPopover = ({ tool, anchorRect, onDisconnect, onClose }) => {
  const { t } = useTranslation();
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (!anchorRect) return null;

  // Position: prefer below, flip above if no space
  const top = anchorRect.bottom + 8;
  const left = anchorRect.left + anchorRect.width / 2;
  const flipAbove = top + 120 > window.innerHeight;

  const style = {
    position: 'fixed',
    left: `${left}px`,
    transform: 'translateX(-50%)',
    ...(flipAbove
      ? { bottom: `${window.innerHeight - anchorRect.top + 8}px` }
      : { top: `${top}px` }),
    zIndex: 60,
  };

  return createPortal(
    <div ref={ref} style={style}
      className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-3 w-48"
    >
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2 truncate">
        {tool.name}
      </div>
      <div className="text-xs text-green-600 dark:text-green-400 mb-3 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
        {t('tools.connected')}
      </div>
      <button
        onClick={() => {
          if (window.confirm(t('tools.confirmDisconnect'))) {
            onDisconnect(tool.slug);
            onClose();
          }
        }}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
      >
        <Unplug className="w-4 h-4" />
        {t('tools.disconnect')}
      </button>
    </div>,
    document.body
  );
};

export default ToolPopover;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ToolPopover.jsx
git commit -m "feat(tools): add ToolPopover for connected tool actions"
```

---

### Task 8: FlipToolCard Component

**Files:**
- Create: `nextlen/src/components/tools/FlipToolCard.jsx`

This is the most complex component — flip animation + auth form on back face. Auth logic is adapted from existing `ConnectModal.jsx`.

- [ ] **Step 1: Create FlipToolCard**

Create `nextlen/src/components/tools/FlipToolCard.jsx`:

```jsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Eye, EyeOff, Loader2 } from 'lucide-react';
import { toolsAPI } from '../../api/tools';
import api from '../../api/axios';
import ToolStatusBadge from './ToolStatusBadge';

const CAT_COLORS = {
  communication: { stripe: 'border-l-green-500',   iconBg: 'bg-green-500/10',   iconText: 'text-green-500' },
  ai:            { stripe: 'border-l-primary-500',  iconBg: 'bg-primary-500/10',  iconText: 'text-primary-500' },
  productivity:  { stripe: 'border-l-orange-500',   iconBg: 'bg-orange-500/10',   iconText: 'text-orange-500' },
  analytics:     { stripe: 'border-l-blue-500',     iconBg: 'bg-blue-500/10',     iconText: 'text-blue-500' },
  crm:           { stripe: 'border-l-pink-500',     iconBg: 'bg-pink-500/10',     iconText: 'text-pink-500' },
  custom:        { stripe: 'border-l-gray-500',     iconBg: 'bg-gray-500/10',     iconText: 'text-gray-500' },
};

const FlipToolCard = ({ tool, onConnected }) => {
  const { t } = useTranslation();
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [credentials, setCredentials] = useState({});
  const [showPasswords, setShowPasswords] = useState({});
  const [qrData, setQrData] = useState(null);
  const pollRef = useRef(null);

  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
  const cat = CAT_COLORS[tool.category] || CAT_COLORS.custom;
  const fields = tool.auth_config?.fields || [];

  // Initialize defaults for fields
  useEffect(() => {
    const defaults = {};
    fields.forEach((f) => {
      if (f.type === 'checkbox') defaults[f.name] = f.default || false;
      else if (f.type === 'tags') defaults[f.name] = f.default || [];
      else defaults[f.name] = f.default || '';
    });
    setCredentials(defaults);
  }, [tool.slug]);

  // Cleanup polling
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleClick = () => {
    if (isConnected) return; // Connected cards handled by popover
    if (tool.auth_type === 'none') {
      handleNoAuth();
    } else {
      setFlipped(true);
    }
  };

  const handleNoAuth = async () => {
    setLoading(true);
    try {
      await toolsAPI.connect(tool.slug, {});
      onConnected(tool.slug);
    } catch (err) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await toolsAPI.connect(tool.slug, credentials, { timeout: 10000 });
      if (res.data.status === 'connected') {
        setFlipped(false);
        onConnected(tool.slug);
      } else if (res.data.status === 'pending' && tool.auth_type === 'qr_code') {
        startQrFlow(res.data.initiate_url);
      } else if (res.data.auth_url) {
        window.location.href = res.data.auth_url;
      }
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        setError('Connection timed out. Please try again.');
      } else {
        setError(err.response?.data?.error || 'Connection failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const startQrFlow = async (initiateUrl) => {
    try {
      const url = initiateUrl || tool.auth_config?.initiate_url || '/clients/whatsapp/bridge/login/';
      const res = await api.post(url);
      if (res.data.qr) {
        setQrData(res.data.qr);
        startPolling(res.data.login_id);
      }
    } catch {
      setError('Failed to start QR login');
    }
  };

  const startPolling = (id) => {
    let retries = 0;
    const statusUrl = tool.auth_config?.status_url || '/clients/whatsapp/bridge/login/status/';
    pollRef.current = setInterval(async () => {
      retries++;
      if (retries > 48) {
        clearInterval(pollRef.current);
        setQrData(null);
        setError(t('tools.flow.qrExpired'));
        return;
      }
      try {
        const res = await api.get(`${statusUrl}?login_id=${id}`);
        if (res.data.status === 'connected') {
          clearInterval(pollRef.current);
          setFlipped(false);
          onConnected(tool.slug);
        } else if (res.data.qr) {
          setQrData(res.data.qr);
        }
      } catch { /* ignore polling errors */ }
    }, 2500);
  };

  const handleCancel = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setFlipped(false);
    setError('');
    setQrData(null);
  };

  const handleChange = (name, value) => {
    setCredentials(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="perspective-1000 w-[160px] shrink-0" style={{ minHeight: '100px' }}>
      <div
        className={`relative w-full transition-transform duration-500 ${flipped ? 'rotate-y-180' : ''}`}
        style={{ transformStyle: 'preserve-3d', minHeight: flipped ? '180px' : '100px' }}
      >
        {/* FRONT */}
        <div
          className={`backface-hidden absolute inset-0 rounded-xl border p-3 cursor-pointer transition-all
            ${isConnected
              ? `border-l-4 ${cat.stripe} border-gray-200 dark:border-gray-700 opacity-100`
              : 'border-dashed border-gray-300 dark:border-gray-600 opacity-60 hover:opacity-80'
            }
            bg-white dark:bg-gray-800`}
          onClick={handleClick}
          title={isConnected ? t('tools.connected') : tool.tagline + ' — ' + t('tools.flow.clickToConnect')}
        >
          {loading && tool.auth_type === 'none' && (
            <div className="absolute inset-0 bg-white/80 dark:bg-gray-800/80 rounded-xl flex items-center justify-center z-10">
              <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
            </div>
          )}
          <div className="flex items-center gap-2 mb-1.5">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0 ${cat.iconBg} ${cat.iconText}`}>
              {tool.icon || '🔧'}
            </div>
            <div className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate leading-tight">
              {tool.name}
            </div>
          </div>
          <div className="text-[10px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-snug mb-1">
            {tool.tagline}
          </div>
          <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
        </div>

        {/* BACK */}
        <div
          className="backface-hidden rotate-y-180 absolute inset-0 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 overflow-y-auto"
          style={{ transformStyle: 'preserve-3d' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-900 dark:text-gray-100 truncate">{tool.name}</span>
            <button onClick={handleCancel} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 min-h-0 min-w-0 p-0.5">
              <X size={14} />
            </button>
          </div>

          {error && (
            <div className="text-[10px] text-red-600 dark:text-red-400 mb-2 leading-snug">{error}</div>
          )}

          {qrData ? (
            <div className="flex flex-col items-center gap-1">
              <div className="bg-white p-1 rounded">
                <img src={`data:image/png;base64,${qrData}`} alt="QR" className="w-24 h-24" />
              </div>
              <div className="flex items-center gap-1 text-[10px] text-gray-500">
                <Loader2 className="w-3 h-3 animate-spin" />
                {t('tools.connecting')}
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-1.5">
              {fields.map(field => (
                <div key={field.name}>
                  {field.type === 'password' ? (
                    <div className="relative">
                      <input
                        type={showPasswords[field.name] ? 'text' : 'password'}
                        value={credentials[field.name] || ''}
                        onChange={(e) => handleChange(field.name, e.target.value)}
                        required={field.required}
                        placeholder={field.label || field.name}
                        className="w-full px-2 py-1 text-[11px] border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 outline-none focus:ring-1 focus:ring-primary-500 min-h-0"
                      />
                      <button type="button"
                        onClick={() => setShowPasswords(p => ({ ...p, [field.name]: !p[field.name] }))}
                        className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 min-h-0 min-w-0 p-0"
                      >
                        {showPasswords[field.name] ? <EyeOff size={12} /> : <Eye size={12} />}
                      </button>
                    </div>
                  ) : field.type === 'checkbox' ? (
                    <label className="flex items-center gap-1.5 text-[11px] text-gray-600 dark:text-gray-400 cursor-pointer">
                      <input type="checkbox" checked={credentials[field.name] || false}
                        onChange={(e) => handleChange(field.name, e.target.checked)}
                        className="w-3 h-3 rounded border-gray-300 text-primary-600 min-h-0 min-w-0"
                      />
                      {field.label || field.name}
                    </label>
                  ) : (
                    <input
                      type="text"
                      value={credentials[field.name] || ''}
                      onChange={(e) => handleChange(field.name, e.target.value)}
                      required={field.required}
                      placeholder={field.label || field.name}
                      className="w-full px-2 py-1 text-[11px] border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 outline-none focus:ring-1 focus:ring-primary-500 min-h-0"
                    />
                  )}
                </div>
              ))}
              <button type="submit" disabled={loading}
                className="w-full py-1 text-[11px] font-medium rounded bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-1 min-h-0"
              >
                {loading && <Loader2 className="w-3 h-3 animate-spin" />}
                {tool.auth_type === 'qr_code' ? t('tools.flow.startQr') : t('tools.connect')}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default FlipToolCard;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/FlipToolCard.jsx
git commit -m "feat(tools): add FlipToolCard with 3D flip animation and auth form"
```

---

### Task 9: ToolCatalogStrip Component

**Files:**
- Create: `nextlen/src/components/tools/ToolCatalogStrip.jsx`

- [ ] **Step 1: Create ToolCatalogStrip**

Create `nextlen/src/components/tools/ToolCatalogStrip.jsx`:

```jsx
import { useRef, useState, useEffect } from 'react';
import FlipToolCard from './FlipToolCard';

const ToolCatalogStrip = ({ tools, onConnected, onToolHover, onToolHoverEnd }) => {
  const scrollRef = useRef(null);
  const [showLeftFade, setShowLeftFade] = useState(false);
  const [showRightFade, setShowRightFade] = useState(false);

  const updateFades = () => {
    const el = scrollRef.current;
    if (!el) return;
    setShowLeftFade(el.scrollLeft > 10);
    setShowRightFade(el.scrollLeft < el.scrollWidth - el.clientWidth - 10);
  };

  useEffect(() => {
    updateFades();
    const el = scrollRef.current;
    el?.addEventListener('scroll', updateFades);
    window.addEventListener('resize', updateFades);
    return () => {
      el?.removeEventListener('scroll', updateFades);
      window.removeEventListener('resize', updateFades);
    };
  }, [tools]);

  return (
    <div className="relative">
      {/* Left fade */}
      {showLeftFade && (
        <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-gray-50 dark:from-gray-900 to-transparent z-10 pointer-events-none" />
      )}
      {/* Right fade */}
      {showRightFade && (
        <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-gray-50 dark:from-gray-900 to-transparent z-10 pointer-events-none" />
      )}

      <div
        ref={scrollRef}
        className="flex gap-3 overflow-x-auto pb-2 px-1 scrollbar-hide"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {tools.map(tool => (
          <FlipToolCard
            key={tool.slug}
            tool={tool}
            onConnected={onConnected}
          />
        ))}
      </div>
    </div>
  );
};

export default ToolCatalogStrip;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/ToolCatalogStrip.jsx
git commit -m "feat(tools): add ToolCatalogStrip with horizontal scroll and fade masks"
```

---

### Task 10: FlowCanvas Component (layout engine)

**Files:**
- Create: `nextlen/src/components/tools/FlowCanvas.jsx`

This is the main canvas component that positions core nodes, connected tool nodes, and computes bezier paths.

- [ ] **Step 1: Create FlowCanvas**

Create `nextlen/src/components/tools/FlowCanvas.jsx`:

```jsx
import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import CoreNode from './CoreNode';
import CanvasToolNode from './CanvasToolNode';
import ConnectionsLayer from './ConnectionsLayer';
import OnboardingHint from './OnboardingHint';
import { getToolTargets } from './toolTargets';

const FlowCanvas = ({ tools, onToolClick, highlightedTool }) => {
  const canvasRef = useRef(null);
  const assistantRef = useRef(null);
  const managerRef = useRef(null);
  const toolRefs = useRef({});
  const [connections, setConnections] = useState([]);
  const [, setTick] = useState(0); // force re-render for ref reads

  const connectedTools = useMemo(
    () => tools.filter(t => t.connection?.status === 'connected' && t.connection?.enabled),
    [tools]
  );

  const groups = useMemo(() => {
    const left = [];    // assistant only
    const right = [];   // manager only
    const both = [];    // both

    connectedTools.forEach(tool => {
      const targets = getToolTargets(tool.slug);
      if (targets.includes('assistant') && targets.includes('manager')) both.push(tool);
      else if (targets.includes('manager')) right.push(tool);
      else left.push(tool);
    });

    return { left, right, both };
  }, [connectedTools]);

  // Canvas min-height: max(60vh, 400px, content-based)
  const maxGroupSize = Math.max(groups.left.length, groups.right.length, 1);
  const contentHeight = maxGroupSize * 80 + 200;
  // 60vh is applied via CSS, this is the pixel minimum
  const canvasMinHeight = Math.max(400, contentHeight);

  // Compute positions and bezier paths
  const computeConnections = useCallback(() => {
    const canvas = canvasRef.current;
    const aNode = assistantRef.current;
    const mNode = managerRef.current;
    if (!canvas || !aNode || !mNode) return;

    const canvasRect = canvas.getBoundingClientRect();
    const newConns = [];

    const getCenter = (el) => {
      const r = el.getBoundingClientRect();
      return {
        x: r.left + r.width / 2 - canvasRect.left,
        y: r.top + r.height / 2 - canvasRect.top,
      };
    };

    const getPort = (el, side) => {
      const r = el.getBoundingClientRect();
      return {
        x: (side === 'left' ? r.left : r.right) - canvasRect.left,
        y: r.top + r.height / 2 - canvasRect.top,
      };
    };

    // Escalation link between assistant and manager
    const aCenter = getCenter(aNode);
    const mCenter = getCenter(mNode);
    const aRight = getPort(aNode, 'right');
    const mLeft = getPort(mNode, 'left');
    const escCpX = aRight.x + (mLeft.x - aRight.x) * 0.5;
    newConns.push({
      id: 'escalation',
      pathD: `M${aRight.x},${aRight.y} C${escCpX},${aRight.y} ${escCpX},${mLeft.y} ${mLeft.x},${mLeft.y}`,
      target: 'escalation',
      toolSlug: null,
    });

    // Tool connections
    const addToolConn = (toolSlug, sourceEl, targetEl, target) => {
      if (!sourceEl || !targetEl) return;
      const src = getPort(sourceEl, 'right');
      const tgt = getPort(targetEl, 'left');
      const cpX = src.x + (tgt.x - src.x) * 0.55;
      newConns.push({
        id: `${toolSlug}-${target}`,
        pathD: `M${src.x},${src.y} C${cpX},${src.y} ${cpX},${tgt.y} ${tgt.x},${tgt.y}`,
        target,
        toolSlug,
      });
    };

    connectedTools.forEach(tool => {
      const ref = toolRefs.current[tool.slug];
      if (!ref) return;
      const targets = getToolTargets(tool.slug);
      if (targets.includes('assistant')) addToolConn(tool.slug, ref, aNode, 'assistant');
      if (targets.includes('manager')) addToolConn(tool.slug, ref, mNode, 'manager');
    });

    setConnections(newConns);
  }, [connectedTools]);

  // Recompute on mount, resize, and tool changes
  useEffect(() => {
    // Wait for refs to be set
    const t = setTimeout(() => {
      setTick(n => n + 1);
      computeConnections();
    }, 100);
    return () => clearTimeout(t);
  }, [connectedTools, computeConnections]);

  useEffect(() => {
    let timeout;
    const handleResize = () => {
      clearTimeout(timeout);
      timeout = setTimeout(computeConnections, 150);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timeout);
    };
  }, [computeConnections]);

  // Auto-layout: position tool nodes
  const getToolStyle = (tool, group, index, total) => {
    const canvasH = canvasMinHeight;
    const padding = 40;
    const usableH = canvasH - padding * 2;
    const spacing = total > 1 ? usableH / (total - 1) : 0;
    const yStart = total > 1 ? padding : canvasH / 2 - 30;
    const y = yStart + index * spacing;

    if (group === 'left') return { top: `${y}px`, left: '40px' };
    if (group === 'right') return { top: `${y}px`, right: '40px' };
    // both: horizontal row above center
    const xCenter = 50; // percent
    const offset = (index - (total - 1) / 2) * 180;
    return { top: `${padding}px`, left: `calc(${xCenter}% + ${offset}px)`, transform: 'translateX(-50%)' };
  };

  return (
    <div
      ref={canvasRef}
      className="relative w-full bg-gray-50 dark:bg-gray-900 rounded-xl overflow-hidden"
      style={{ minHeight: `max(60vh, ${canvasMinHeight}px)` }}
    >
      {/* Dot grid (dark only) */}
      <div className="absolute inset-0 dot-grid hidden dark:block" />

      {/* Onboarding hint */}
      {connectedTools.length === 0 && <OnboardingHint />}

      {/* SVG connections */}
      <ConnectionsLayer connections={connections} highlightedTool={highlightedTool} />

      {/* Core nodes */}
      <CoreNode
        ref={assistantRef}
        variant="assistant"
        connectedCount={groups.left.length + groups.both.length}
        style={{ top: '50%', left: '35%', transform: 'translate(-50%, -50%)' }}
      />
      <CoreNode
        ref={managerRef}
        variant="manager"
        connectedCount={groups.right.length + groups.both.length}
        style={{ top: '50%', left: '65%', transform: 'translate(-50%, -50%)' }}
      />

      {/* Escalation label */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] text-gray-400 dark:text-gray-500 font-medium tracking-wider uppercase pointer-events-none">
        escalation
      </div>

      {/* Connected tool nodes */}
      {groups.left.map((tool, i) => (
        <CanvasToolNode
          key={tool.slug}
          ref={el => { toolRefs.current[tool.slug] = el; }}
          tool={tool}
          onClick={onToolClick}
          isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
          style={getToolStyle(tool, 'left', i, groups.left.length)}
        />
      ))}
      {groups.right.map((tool, i) => (
        <CanvasToolNode
          key={tool.slug}
          ref={el => { toolRefs.current[tool.slug] = el; }}
          tool={tool}
          onClick={onToolClick}
          isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
          style={getToolStyle(tool, 'right', i, groups.right.length)}
        />
      ))}
      {groups.both.map((tool, i) => (
        <CanvasToolNode
          key={tool.slug}
          ref={el => { toolRefs.current[tool.slug] = el; }}
          tool={tool}
          onClick={onToolClick}
          isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
          style={getToolStyle(tool, 'both', i, groups.both.length)}
        />
      ))}
    </div>
  );
};

export default FlowCanvas;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/FlowCanvas.jsx
git commit -m "feat(tools): add FlowCanvas with auto-layout and bezier computation"
```

---

### Task 11: Rewrite ToolsPage + i18n Keys

**Files:**
- Modify: `nextlen/src/pages/ToolsPage.jsx` (full rewrite)
- Modify: `nextlen/src/locales/en/translation.json` (extend tools section)
- Delete: `nextlen/src/components/tools/CategoryFilter.jsx`

- [ ] **Step 1: Add i18n keys**

Add to `tools` object in `nextlen/src/locales/en/translation.json`:

```json
"flow": {
  "title": "Nexelin",
  "titleAccent": "Flow",
  "aiAssistant": "AI Assistant",
  "centralEngine": "Central AI engine",
  "clientManager": "Client Manager",
  "hitlEscalation": "HITL escalation",
  "assistantTooltip": "Handles automated responses, RAG search, and customer conversations",
  "managerTooltip": "Receives escalated conversations that need human attention",
  "clickToConnect": "Click to connect",
  "connectedTo": "Connected to",
  "onboarding": "Click a tool to get started",
  "qrExpired": "QR code expired. Try again.",
  "startQr": "Start QR scan",
  "connectedToAssistant": "connected to AI Assistant",
  "connectedToManager": "connected to Client Manager",
  "disconnected": "disconnected",
  "loadError": "Failed to load tools.",
  "statsConnected": "connected",
  "statsAvailable": "available"
}
```

- [ ] **Step 2: Rewrite ToolsPage**

Rewrite `nextlen/src/pages/ToolsPage.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw } from 'lucide-react';
import { toolsAPI } from '../api/tools';
import ToolCatalogStrip from '../components/tools/ToolCatalogStrip';
import FlowCanvas from '../components/tools/FlowCanvas';
import ToolPopover from '../components/tools/ToolPopover';
import FlowToast, { useFlowToast } from '../components/tools/FlowToast';
import { getToolTargets } from '../components/tools/toolTargets';

const ToolsPage = () => {
  const { t } = useTranslation();
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [highlightedTool, setHighlightedTool] = useState(null);
  const [popover, setPopover] = useState(null); // { tool, rect }
  const { toast, showToast, hideToast } = useFlowToast();

  const loadTools = async () => {
    try {
      const res = await toolsAPI.getCatalog();
      setTools(res.data);
      setError('');
    } catch {
      setError(t('tools.flow.loadError'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTools(); }, []);

  const handleConnected = useCallback((slug) => {
    const tool = tools.find(t => t.slug === slug);
    const targets = getToolTargets(slug);
    const targetName = targets.includes('assistant')
      ? t('tools.flow.connectedToAssistant')
      : t('tools.flow.connectedToManager');
    showToast('🔗', `${tool?.name || slug} ${targetName}`);
    loadTools();
  }, [tools, showToast, t]);

  const handleDisconnect = useCallback(async (slug) => {
    try {
      await toolsAPI.disconnect(slug);
      const tool = tools.find(t => t.slug === slug);
      showToast('🔌', `${tool?.name || slug} ${t('tools.flow.disconnected')}`);
      loadTools();
    } catch (err) {
      console.error('Disconnect error:', err);
    }
  }, [tools, showToast, t]);

  const handleCanvasToolClick = useCallback((tool, e) => {
    const el = e?.currentTarget || document.getElementById(`canvas-tool-${tool.slug}`);
    if (el) {
      setPopover({ tool, rect: el.getBoundingClientRect() });
    }
  }, []);

  const connectedCount = tools.filter(t => t.connection?.status === 'connected' && t.connection?.enabled).length;
  const availableCount = tools.length - connectedCount;

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Skeleton strip */}
        <div className="flex gap-3 overflow-hidden">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="w-[160px] h-[100px] rounded-xl bg-gray-200 dark:bg-gray-700 animate-pulse shrink-0" />
          ))}
        </div>
        {/* Skeleton canvas with blurred core node placeholders */}
        <div className="relative w-full rounded-xl bg-gray-100 dark:bg-gray-800 overflow-hidden" style={{ minHeight: 'max(60vh, 400px)' }}>
          <div className="absolute top-1/2 left-[35%] -translate-x-1/2 -translate-y-1/2 w-[200px] h-[140px] rounded-2xl bg-gray-200 dark:bg-gray-700 animate-pulse blur-[2px]" />
          <div className="absolute top-1/2 left-[65%] -translate-x-1/2 -translate-y-1/2 w-[200px] h-[140px] rounded-2xl bg-gray-200 dark:bg-gray-700 animate-pulse blur-[2px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {t('tools.flow.title')} <span className="text-primary-500">{t('tools.flow.titleAccent')}</span>
          </h1>
        </div>
        <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.6)]" />
            {connectedCount} {t('tools.flow.statsConnected')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
            {availableCount} {t('tools.flow.statsAvailable')}
          </span>
        </div>
      </div>

      {/* Tool Catalog Strip */}
      {error ? (
        <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
          <span className="text-sm text-red-700 dark:text-red-400">{error}</span>
          <button onClick={() => { setLoading(true); loadTools(); }}
            className="flex items-center gap-1 text-sm font-medium text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 min-h-0">
            <RefreshCw className="w-3.5 h-3.5" /> {t('tools.retry')}
          </button>
        </div>
      ) : (
        <ToolCatalogStrip tools={tools} onConnected={handleConnected} />
      )}

      {/* Flow Canvas */}
      <FlowCanvas
        tools={tools}
        onToolClick={handleCanvasToolClick}
        highlightedTool={highlightedTool}
      />

      {/* Popover */}
      {popover && (
        <ToolPopover
          tool={popover.tool}
          anchorRect={popover.rect}
          onDisconnect={handleDisconnect}
          onClose={() => setPopover(null)}
        />
      )}

      {/* Toast */}
      <FlowToast
        message={toast.message}
        icon={toast.icon}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
};

export default ToolsPage;
```

- [ ] **Step 3: Delete CategoryFilter**

```bash
rm nextlen/src/components/tools/CategoryFilter.jsx
```

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/pages/ToolsPage.jsx nextlen/src/locales/en/translation.json
git add -u nextlen/src/components/tools/CategoryFilter.jsx
git commit -m "feat(tools): rewrite ToolsPage as visual flow builder with flip cards and SVG connections"
```

---

### Task 12: Hover Highlight Interaction

**Files:**
- Modify: `nextlen/src/components/tools/FlipToolCard.jsx`
- Modify: `nextlen/src/pages/ToolsPage.jsx`

- [ ] **Step 1: Add hover state propagation**

In `ToolsPage.jsx`, add `onHover` and `onHoverEnd` props passing through to strip and canvas. When a connected card in the strip is hovered, set `highlightedTool` to its slug. On mouse leave, set back to `null`.

Add to `FlipToolCard`:
```jsx
// Add props: onMouseEnter, onMouseLeave
// On front face div, add:
onMouseEnter={() => isConnected && onMouseEnter?.(tool.slug)}
onMouseLeave={() => isConnected && onMouseLeave?.()}
```

Pass these through `ToolCatalogStrip` to `ToolsPage`:
```jsx
<ToolCatalogStrip
  tools={tools}
  onConnected={handleConnected}
  onToolHover={setHighlightedTool}
  onToolHoverEnd={() => setHighlightedTool(null)}
/>
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/tools/FlipToolCard.jsx nextlen/src/components/tools/ToolCatalogStrip.jsx nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(tools): add hover highlight — dim other connections on tool hover"
```

---

### Task 13: Visual QA and Polish

**Files:**
- Various adjustments

- [ ] **Step 1: Run the dev server and verify**

```bash
cd nextlen && npm run dev
```

Open the tools page in browser. Check:
1. Tool cards render in horizontal strip
2. Click disconnected card → flip animation shows auth form
3. Cancel flips back
4. Connected tools appear on canvas with bezier lines
5. Particles animate along paths
6. Hover on strip card highlights its connection
7. Click connected tool on canvas → popover appears
8. Dark/light theme toggle works
9. Zero-state shows onboarding hint
10. Toast appears on connect/disconnect

- [ ] **Step 2: Fix any visual issues found**

Adjust spacing, colors, animation timing as needed.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "fix(tools): visual polish for flow builder — spacing, timing, theme"
```
