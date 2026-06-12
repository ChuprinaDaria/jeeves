/* Dev-only preview harness: renders the Tools canvas with mock data so the
   redesign can be screenshotted without the full backend. Not shipped —
   only reachable via /preview.html in `vite dev`. */
import { useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import i18n from './i18n';
import FlowCanvas from './components/tools/FlowCanvas';
import CanvasCopilot from './components/tools/CanvasCopilot';
import { toolsAPI } from './api/tools';
import { mcpAPI } from './api/agent';

i18n.changeLanguage('uk');
try { localStorage.removeItem('flow-canvas-positions'); localStorage.removeItem('flow-canvas-viewport'); localStorage.removeItem('flow-legend-dismissed'); } catch { /* ignore */ }

const conn = (id, target, extra = {}) => ({
  id, target, status: 'connected', enabled: true, middlewares: [], ...extra,
});

const TOOL_DEFS = [
  { slug: 'rag', name: 'RAG Knowledge Search', tagline: 'semantic knowledge base', category: 'ai',
    icon: 'brain', connections: [conn(1, 'assistant'), conn(2, 'manager')] },
  { slug: 'email', name: 'Email', tagline: 'smtp / imap', category: 'communication',
    icon: 'envelope', connections: [conn(3, 'assistant')] },
  { slug: 'memory', name: 'Memory', tagline: 'persistent user memory', category: 'ai',
    icon: 'database', connections: [conn(4, 'assistant')] },
  { slug: 'xlsx', name: 'XLSX Export', tagline: 'excel reports', category: 'productivity',
    icon: 'table', connections: [conn(5, 'assistant')] },
  { slug: 'whatsapp-bridge', name: 'WhatsApp', tagline: 'matrix bridge', category: 'communication',
    icon: 'whatsapp', connections: [conn(7, 'manager')] },
  { slug: 'leads', name: 'Lead Management', tagline: 'capture & qualify', category: 'crm',
    icon: 'target', connections: [conn(8, 'leads')] },
  { slug: 'sales-intel', name: 'Sales Intelligence', tagline: 'website enrichment', category: 'analytics',
    icon: 'chart', connections: [conn(9, 'leads')] },
];

const TELEGRAM = { slug: 'telegram', name: 'Telegram Bot', tagline: 'bot api', category: 'communication',
  icon: 'telegram', connections: [conn(6, 'manager')] };

const withLegacy = (t) => ({ ...t, is_system: false, connection: t.connections[0] });

/* ── Fake live activity: rag + whatsapp pulse continuously ── */
toolsAPI.getFlowActivity = async () => ({
  data: {
    now: new Date().toISOString(),
    events: [
      { id: 1, ts: new Date().toISOString(), tool_name: 'search', status: 'ok', slug: 'rag', target: 'manager' },
      { id: 2, ts: new Date().toISOString(), tool_name: 'matrix_send_message', status: 'ok', slug: 'whatsapp-bridge', target: 'manager' },
    ],
    aggregates: [
      { slug: 'rag', target: 'manager', count: 412 },
      { slug: 'rag', target: 'assistant', count: 96 },
      { slug: 'email', target: 'assistant', count: 31 },
      { slug: 'whatsapp-bridge', target: 'manager', count: 187 },
      { slug: 'leads', target: 'leads', count: 58 },
      { slug: 'sales-intel', target: 'leads', count: 12 },
      { slug: 'memory', target: 'assistant', count: 144 },
    ],
  },
});

/* ── Fake copilot stream: Jeeves connects Telegram, node appears live ── */
mcpAPI.chatSSE = (message, channel, onToken, onDone, onError, onStatus, onToolEvent) => {
  const reply = 'Готово! Підключив Telegram Bot і направив повідомлення Консьєржу — нода вже на канвасі. Хочете, щоб ліди з Telegram теж потрапляли у воронку?';
  setTimeout(() => onToolEvent?.('tool_start', { tool_name: 'canvas_add_tool_connection' }), 400);
  setTimeout(() => {
    onToolEvent?.('tool_result', { tool_name: 'canvas_add_tool_connection' });
    window.__addTelegram?.();
  }, 1400);
  let i = 0;
  const timer = setInterval(() => {
    if (i >= reply.length) { clearInterval(timer); onDone?.(); return; }
    onToken?.(reply.slice(i, i + 4));
    i += 4;
  }, 30);
  setTimeout(() => {}, 0);
};

const noop = () => {};

const Preview = () => {
  const [tools, setTools] = useState(TOOL_DEFS.map(withLegacy));
  const [copilotOpen, setCopilotOpen] = useState(false);

  window.__setCopilot = setCopilotOpen;
  window.__addTelegram = () => setTools(prev =>
    prev.some(t => t.slug === 'telegram') ? prev : [...prev, withLegacy(TELEGRAM)]);

  const refresh = useCallback(() => {}, []);

  return (
    <div className="min-h-screen bg-cream p-8">
      <div className="max-w-[1280px] mx-auto space-y-6">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-[28px] font-bold tracking-tightest text-ink">
              Jeeves <span className="text-iris">Flow</span>
            </h1>
            <div className="font-mono text-[13px] text-fog mt-1">
              mcp · перетягніть з каталогу · киньте на канвас
            </div>
          </div>
          <div className="flex gap-5 font-mono text-[11px] uppercase tracking-wider text-fog">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-sage shadow-[0_0_4px_rgba(123,200,159,0.55)]" />
              <span className="text-sage">{tools.length}</span> підключено
            </span>
          </div>
        </div>

        <FlowCanvas
          tools={tools}
          channels={[
            { id: 'telegram', name: 'Telegram', active: true },
            { id: 'whatsapp', name: 'WhatsApp', active: true },
            { id: 'webchat', name: 'Web chat', active: true },
          ]}
          onToolClick={noop}
          highlightedTool={null}
          onToolDrop={noop}
          onDisconnect={noop}
          onConnect={noop}
          onMiddlewareRemove={noop}
          onMiddlewareAttach={noop}
          onRefresh={refresh}
          onPositionSave={noop}
        />
      </div>

      <CanvasCopilot
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        onCanvasChanged={noop}
      />
    </div>
  );
};

createRoot(document.getElementById('root')).render(<Preview />);
