import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, PaperPlaneRight, Sparkle, CircleNotch } from '@phosphor-icons/react';
import { mcpAPI } from '../../api/agent';

/* Tools that mean "Jeeves is editing the canvas right now" */
const CANVAS_TOOL_PREFIXES = ['canvas_', 'bridge_'];

const isCanvasTool = (name) =>
  CANVAS_TOOL_PREFIXES.some(p => (name || '').startsWith(p));

/**
 * CanvasCopilot — chat dock where Jeeves builds the canvas for you.
 *
 * Jeeves already has MCP tools (canvas_add_tool_connection,
 * bridge_start_connection, …) that edit the flow; this dock surfaces them:
 * the user asks in plain language, tool activity shows live, and the canvas
 * refreshes the moment Jeeves changes it.
 */
const CanvasCopilot = ({ open, onClose, onCanvasChanged }) => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState(null); // current tool label
  const endRef = useRef(null);
  const canvasChangedRef = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activity]);

  const send = useCallback((text) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput('');
    setBusy(true);
    canvasChangedRef.current = false;
    setMessages(prev => [...prev, { role: 'user', content: message }]);

    mcpAPI.chatSSE(
      message,
      'sandbox',
      // onToken — stream the reply
      (tok) => {
        setActivity(null);
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && last.streaming) {
            return [...prev.slice(0, -1), { ...last, content: last.content + tok }];
          }
          return [...prev, { role: 'assistant', content: tok, streaming: true }];
        });
      },
      // onDone
      () => {
        setBusy(false);
        setActivity(null);
        setMessages(prev => {
          const last = prev[prev.length - 1];
          return last?.streaming ? [...prev.slice(0, -1), { ...last, streaming: false }] : prev;
        });
        if (canvasChangedRef.current) onCanvasChanged?.();
      },
      // onError
      (err) => {
        setBusy(false);
        setActivity(null);
        setMessages(prev => [...prev, { role: 'assistant', content: t('tools.copilot.error'), error: true }]);
        console.error('Copilot error:', err);
      },
      // onStatus
      () => {},
      // onToolEvent — show activity; refresh the canvas when Jeeves edits it
      (eventType, data) => {
        const name = data?.tool_name || '';
        if (eventType === 'tool_start') {
          setActivity(isCanvasTool(name) ? t('tools.copilot.editingCanvas') : t('tools.copilot.working'));
        } else {
          setActivity(null);
          if (isCanvasTool(name)) {
            canvasChangedRef.current = true;
            onCanvasChanged?.(); // refresh immediately — node appears mid-conversation
          }
        }
      },
    );
  }, [input, busy, onCanvasChanged, t]);

  if (!open) return null;

  const suggestions = [
    t('tools.copilot.suggestion1'),
    t('tools.copilot.suggestion2'),
    t('tools.copilot.suggestion3'),
  ];

  return (
    <div className="fixed top-0 right-0 h-full w-[380px] max-w-[92vw] z-[65] flex flex-col
                    bg-paper border-l-[1.5px] border-rule shadow-ink-lg animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b-[1.5px] border-rule">
        <div className="flex items-center gap-2">
          <Sparkle size={18} weight="light" className="text-iris" />
          <div>
            <div className="text-[14px] font-semibold text-ink">{t('tools.copilot.title')}</div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-fog">
              {t('tools.copilot.subtitle')}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label={t('tools.flow.cancel')}
          className="p-1.5 rounded-sm text-slate hover:bg-mist hover:text-ink transition-colors bg-transparent"
        >
          <X size={16} weight="light" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3 pt-4">
            <p className="text-[13px] text-slate leading-relaxed">{t('tools.copilot.empty')}</p>
            <div className="flex flex-col gap-2">
              {suggestions.map((sug, i) => (
                <button
                  key={i}
                  onClick={() => send(sug)}
                  className="text-left text-[12px] text-iris px-3 py-2 rounded-lg border-[1.5px] border-iris/40
                             hover:bg-iris-soft/30 transition-colors bg-transparent"
                >
                  {sug}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap
              ${msg.role === 'user'
                ? 'bg-iris-soft/50 text-ink'
                : msg.error
                  ? 'bg-rose-soft/40 text-rose border-[1.5px] border-rose/40'
                  : 'bg-linen text-ink border-[1.5px] border-rule'}`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {activity && (
          <div className="flex items-center gap-2 text-[12px] text-iris font-mono uppercase tracking-wider">
            <CircleNotch size={14} className="animate-spin" />
            {activity}
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t-[1.5px] border-rule">
        <div className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
            placeholder={t('tools.copilot.placeholder')}
            disabled={busy}
            className="flex-1 px-3 py-2 text-[13px] rounded-lg bg-cream border-[1.5px] border-rule
                       text-ink placeholder:text-fog focus:border-iris focus:outline-none transition-colors"
          />
          <button
            onClick={() => send()}
            disabled={busy || !input.trim()}
            aria-label={t('tools.copilot.send')}
            className="p-2.5 rounded-lg bg-iris text-paper hover:opacity-90 disabled:opacity-30
                       transition-all"
          >
            {busy
              ? <CircleNotch size={16} className="animate-spin" />
              : <PaperPlaneRight size={16} weight="light" />}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CanvasCopilot;
