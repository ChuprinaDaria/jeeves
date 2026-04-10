import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  BellSimple,
  PaperPlaneTilt,
  Sparkle,
  User,
  BookmarkSimple,
  Image as ImageIcon,
  X,
  Lightning,
  CalendarBlank,
  Question,
  Translate,
  WarningCircle,
  Check,
  ArrowsClockwise,
} from '@phosphor-icons/react';

import { ragAPI } from '../api/agent';

/* ─────────────── Constants ─────────────── */

const STORAGE_KEY = 'jeevs-chat-session';
const MAX_CONTEXT = 30;

const QUICK_PROMPTS = [
  { icon: Question,      accent: 'iris',  title: 'Most asked',       prompt: "What's the most common question you get from customers?" },
  { icon: CalendarBlank, accent: 'sage',  title: 'Opening hours',    prompt: 'When are we open? Include weekends and holidays.' },
  { icon: Lightning,     accent: 'amber', title: 'Edge case',        prompt: "I don't speak your language. Can you help me in broken English?" },
  { icon: Translate,     accent: 'rose',  title: 'Escalate',         prompt: 'I need to speak with a human manager right now.' },
];

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

/* ─────────────── Helpers ─────────────── */

const formatTime = (d) => {
  try {
    return new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
};

const loadSession = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const saveSession = (messages) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-200)));
  } catch {
    /* quota — ignore */
  }
};

/* ─────────────── Page ─────────────── */

const SandboxPage = () => {
  const [messages, setMessages] = useState(() => loadSession());
  const [input, setInput] = useState('');
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [sending, setSending] = useState(false);
  const [savingId, setSavingId] = useState(null);
  const [savedIds, setSavedIds] = useState(new Set());
  const [error, setError] = useState('');

  const scrollRef = useRef(null);
  const textareaRef = useRef(null);
  const fileRef = useRef(null);

  /* ── Side-effects ── */

  useEffect(() => { saveSession(messages); }, [messages]);

  useEffect(() => {
    // autoscroll on new content
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  useEffect(() => {
    // focus input on mount
    textareaRef.current?.focus();
  }, []);

  const autosize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  }, []);

  useEffect(() => { autosize(); }, [input, autosize]);

  /* ── Image handling ── */

  const handleImage = (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Only image files are allowed');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Image must be under 5 MB');
      return;
    }
    setError('');
    setImage(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const clearImage = () => {
    setImage(null);
    setImagePreview(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  /* ── Send ── */

  const send = async (textOverride) => {
    const text = (textOverride ?? input).trim();
    if ((!text && !image) || sending) return;

    setError('');
    const userMsg = {
      id: Date.now(),
      text: text || '(image)',
      sender: 'user',
      timestamp: new Date().toISOString(),
      image: imagePreview || null,
    };

    const next = [...messages, userMsg];
    setMessages(next);
    setInput('');
    const sentImage = image;
    clearImage();
    setSending(true);

    try {
      const context = next.slice(-MAX_CONTEXT).map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));
      const { data } = await ragAPI.chat(text, sentImage, context);
      const answer = data?.response || data?.answer || data?.text || "I'm not sure how to respond to that.";

      setMessages((prev) => [...prev, {
        id: Date.now() + 1,
        text: answer,
        sender: 'ai',
        timestamp: new Date().toISOString(),
      }]);
    } catch (e) {
      console.error(e);
      setError(e?.response?.data?.error || 'Jeeves stumbled — please try again.');
      setMessages((prev) => [...prev, {
        id: Date.now() + 1,
        text: '⚠ Could not reach the model. Check your connection and try again.',
        sender: 'ai',
        timestamp: new Date().toISOString(),
        error: true,
      }]);
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  /* ── Session actions ── */

  const resetSession = () => {
    if (messages.length && !confirm('Start a fresh conversation? Current session will be cleared.')) return;
    setMessages([]);
    setSavedIds(new Set());
    setError('');
    textareaRef.current?.focus();
  };

  const saveQA = async (aiMsg) => {
    const idx = messages.findIndex((m) => m.id === aiMsg.id);
    const userMsg = idx > 0 ? messages[idx - 1] : null;
    if (!userMsg || userMsg.sender !== 'user') {
      setError('Could not locate the question for this answer');
      return;
    }
    setSavingId(aiMsg.id);
    try {
      await ragAPI.saveSandboxQA(userMsg.text, aiMsg.text);
      setSavedIds((s) => new Set([...s, aiMsg.id]));
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to save Q&A');
    } finally {
      setSavingId(null);
    }
  };

  const empty = messages.length === 0;

  return (
    <div className="max-w-[1080px] mx-auto flex flex-col h-[calc(100vh-104px)] min-h-[620px]">
      {/* ─────────── Header ─────────── */}
      <header className="flex items-start justify-between mb-5 animate-fade-up">
        <div className="flex items-center gap-4">
          {/* Breathing avatar */}
          <div className="relative">
            <div className="w-14 h-14 rounded-xl border-2 border-iris text-iris
                            flex items-center justify-center bg-paper animate-breathe">
              <BellSimple size={26} weight="light" />
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full
                             border-2 border-paper bg-sage" />
          </div>

          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-[28px] font-bold tracking-tightest leading-none">Jeeves</h1>
              <span className="pill pill-info">beta</span>
            </div>
            <div className="font-mono text-[12px] text-fog mt-1.5 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-sage" />
              {sending ? (
                <span className="shimmer-text">thinking…</span>
              ) : (
                <>online · rehearsal channel · {messages.length} msgs</>
              )}
            </div>
          </div>
        </div>

        <div className="hidden md:flex gap-2.5">
          <button
            onClick={resetSession}
            disabled={!messages.length}
            className="btn btn-amber disabled:opacity-40 disabled:cursor-not-allowed"
            title="Reset conversation (new session)"
          >
            <ArrowsClockwise size={16} weight="light" />
            Reset
          </button>
        </div>
      </header>

      {/* ─────────── Chat area ─────────── */}
      <div className="relative flex-1 min-h-0 surface p-0 overflow-hidden flex flex-col">
        {/* Dot-grid watermark */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.35] dot-grid" />

        {/* Scrollable messages */}
        <div
          ref={scrollRef}
          className="relative flex-1 min-h-0 overflow-y-auto px-5 md:px-8 py-6 space-y-5"
        >
          {empty ? (
            <EmptyState onPrompt={(p) => send(p)} />
          ) : (
            messages.map((m, i) => (
              <MessageRow
                key={m.id}
                msg={m}
                idx={i}
                onSaveQA={saveQA}
                saving={savingId === m.id}
                saved={savedIds.has(m.id)}
              />
            ))
          )}

          {sending && <TypingBubble />}
        </div>

        {/* Inline error */}
        {error && (
          <div className="relative px-5 md:px-8 py-2 border-t border-rule bg-rose-soft/30
                          flex items-center gap-2 animate-fade-up">
            <WarningCircle size={14} weight="light" className="text-rose shrink-0" />
            <span className="font-mono text-[11px] text-rose flex-1">{error}</span>
            <button onClick={() => setError('')} className="text-rose hover:text-ink cursor-pointer">
              <X size={14} weight="light" />
            </button>
          </div>
        )}

        {/* ─────────── Composer ─────────── */}
        <div className="relative border-t border-rule bg-paper px-4 md:px-6 py-4">
          {imagePreview && (
            <div className="mb-3 inline-flex items-center gap-2 p-1.5 pr-3
                            border-[1.5px] border-iris-soft rounded-sm bg-linen animate-fade-up">
              <img src={imagePreview} alt="attachment"
                   className="w-10 h-10 rounded-sm object-cover border border-rule" />
              <span className="font-mono text-[11px] text-slate">{image?.name}</span>
              <button
                onClick={clearImage}
                className="text-fog hover:text-rose cursor-pointer"
                aria-label="Remove image"
              >
                <X size={14} weight="light" />
              </button>
            </div>
          )}

          <div className="flex items-end gap-2.5">
            {/* Image button */}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={sending}
              className="shrink-0 w-[42px] h-[42px] rounded-sm border-[1.5px] border-rule
                         text-fog hover:border-iris hover:text-iris
                         transition-colors cursor-pointer flex items-center justify-center
                         disabled:opacity-40 disabled:cursor-not-allowed"
              title="Attach image"
              aria-label="Attach image"
            >
              <ImageIcon size={18} weight="light" />
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => { handleImage(e.target.files?.[0]); e.target.value = ''; }}
            />

            {/* Textarea */}
            <div className="flex-1 min-w-0">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                placeholder="Ask Jeeves anything…  ( Enter to send · Shift+Enter for newline )"
                className="w-full resize-none px-4 py-2.5 bg-cream border-[1.5px] border-rule
                           rounded-sm text-[14px] text-ink font-sans leading-relaxed
                           focus:outline-none focus:border-iris transition-colors
                           placeholder:text-fog placeholder:font-mono placeholder:text-[12px]"
                disabled={sending}
              />
            </div>

            {/* Send */}
            <button
              onClick={() => send()}
              disabled={sending || (!input.trim() && !image)}
              className="shrink-0 btn btn-violet h-[42px] px-4
                         disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Send message"
            >
              <PaperPlaneTilt size={16} weight="light" />
              <span className="hidden md:inline">Send</span>
            </button>
          </div>

          {/* Footer hints */}
          <div className="mt-2.5 flex items-center justify-between">
            <span className="font-mono text-[10px] text-fog tracking-wider uppercase">
              enter to send · shift+enter newline · session saved locally
            </span>
            <span className="font-mono text-[10px] text-fog">{input.length}/2000</span>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ─────────────── Empty state ─────────────── */

const EmptyState = ({ onPrompt }) => {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center pt-6 pb-10">
      <div className="w-16 h-16 rounded-xl border-2 border-iris text-iris
                      flex items-center justify-center bg-paper animate-breathe mb-5">
        <Sparkle size={28} weight="light" />
      </div>

      <h2 className="text-[24px] font-bold text-ink tracking-tightest mb-1.5">
        Good to see you.
      </h2>
      <p className="text-[14px] text-slate max-w-md leading-relaxed mb-8">
        I'm Jeeves — your rehearsal-room concierge. Ask me anything you'd ask a customer-facing
        assistant. Use the quick-starts below or type your own.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
        {QUICK_PROMPTS.map((q, i) => (
          <button
            key={q.title}
            onClick={() => onPrompt(q.prompt)}
            className={`group text-left surface p-4 cursor-pointer hover:shadow-ink
                        transition-all duration-200 hover:-translate-y-[2px]
                        animate-quick-rise`}
            style={{ animationDelay: `${i * 80 + 120}ms` }}
          >
            <div className="flex items-start gap-3">
              <div className={`shrink-0 w-[38px] h-[38px] rounded-md border-2
                              ${ACCENT_BORDER[q.accent]}
                              flex items-center justify-center
                              transition-transform duration-200 group-hover:scale-105`}>
                <q.icon size={18} weight="light" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="label-mono mb-0.5">{q.title}</div>
                <div className="text-[13px] text-ink leading-snug">{q.prompt}</div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

/* ─────────────── Message row ─────────────── */

const MessageRow = ({ msg, idx, onSaveQA, saving, saved }) => {
  const mine = msg.sender === 'user';

  return (
    <div
      className={`flex gap-3 animate-bubble ${mine ? 'flex-row-reverse' : ''}`}
      style={{ animationDelay: `${Math.min(idx, 4) * 40}ms` }}
    >
      {/* Avatar */}
      <div className={`shrink-0 w-[38px] h-[38px] rounded-md border-2
                      ${mine ? 'border-sage text-sage' : 'border-iris text-iris'}
                      flex items-center justify-center bg-paper`}>
        {mine ? <User size={18} weight="light" /> : <BellSimple size={18} weight="light" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[78%] min-w-0 ${mine ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`px-4 py-2.5 rounded-md border-[1.5px]
                         ${mine ? 'bg-mist border-iris-soft' : 'bg-linen border-rule'}
                         ${msg.error ? 'border-rose bg-rose-soft/20' : ''}`}>
          {msg.image && (
            <img
              src={msg.image}
              alt="attachment"
              className="mb-2 rounded-sm border border-rule max-w-full max-h-72 object-contain"
            />
          )}
          {mine ? (
            <p className="text-[14px] text-ink whitespace-pre-wrap leading-relaxed">{msg.text}</p>
          ) : (
            <div className="prose prose-sm max-w-none text-[14px] text-ink leading-relaxed
                            prose-p:my-1.5 prose-headings:text-ink prose-headings:mt-3
                            prose-strong:text-ink prose-code:text-ink prose-code:bg-mist
                            prose-code:px-1 prose-code:py-0.5 prose-code:rounded-sm
                            prose-code:before:content-none prose-code:after:content-none
                            prose-a:text-iris prose-a:no-underline hover:prose-a:underline
                            prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Meta row */}
        <div className={`mt-1 flex items-center gap-2 font-mono text-[10px] text-fog ${mine ? 'flex-row-reverse' : ''}`}>
          <span>{formatTime(msg.timestamp)}</span>
          {!mine && !msg.error && (
            <>
              <span>·</span>
              <button
                onClick={() => onSaveQA(msg)}
                disabled={saving || saved}
                className={`inline-flex items-center gap-1 cursor-pointer transition-colors
                           ${saved ? 'text-sage' : 'hover:text-iris'}`}
                title={saved ? 'Saved to knowledge base' : 'Save Q&A to knowledge base'}
              >
                {saved ? <Check size={12} weight="bold" /> : <BookmarkSimple size={12} weight="light" />}
                {saving ? 'saving…' : saved ? 'saved to KB' : 'save Q&A'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

/* ─────────────── Typing bubble ─────────────── */

const TypingBubble = () => (
  <div className="flex gap-3 animate-bubble">
    <div className="shrink-0 w-[38px] h-[38px] rounded-md border-2 border-iris text-iris
                    flex items-center justify-center bg-paper">
      <BellSimple size={18} weight="light" />
    </div>
    <div className="px-4 py-3 rounded-md border-[1.5px] border-rule bg-linen
                    flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full bg-iris typing-dot" style={{ animationDelay: '0ms'   }} />
      <span className="w-1.5 h-1.5 rounded-full bg-iris typing-dot" style={{ animationDelay: '200ms' }} />
      <span className="w-1.5 h-1.5 rounded-full bg-iris typing-dot" style={{ animationDelay: '400ms' }} />
    </div>
  </div>
);

export default SandboxPage;
