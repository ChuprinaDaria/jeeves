import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChatCircle,
  CheckCircle,
  ArrowBendUpRight,
  BellSimple,
  ArrowClockwise,
  TelegramLogo,
  Browser,
  EnvelopeSimple,
  DeviceMobile,
  User,
  Robot,
  Plus,
  ThumbsUp,
  ThumbsDown,
  Note,
  X,
  PaperPlaneTilt,
  Question,
} from '@phosphor-icons/react';

import { clientAPI } from '../api/client';
import { ragAPI } from '../api/agent';
import Card, { CardHeader, CardAction } from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatCard from '../components/ui/StatCard';

/* ─────────────── Helpers ─────────────── */

const channelMeta = (source) => {
  switch (source) {
    case 'telegram':   return { icon: TelegramLogo,   label: 'Telegram', accent: 'sage'  };
    case 'web':        return { icon: Browser,        label: 'Web',      accent: 'iris'  };
    case 'web_widget': return { icon: Browser,        label: 'Widget',   accent: 'iris'  };
    case 'email':      return { icon: EnvelopeSimple, label: 'Email',    accent: 'rose'  };
    case 'ios':        return { icon: DeviceMobile,   label: 'iOS',      accent: 'amber' };
    default:           return { icon: ChatCircle,     label: 'Chat',     accent: 'iris'  };
  }
};

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

/* ─────────────── Page ─────────────── */

const HistoryPage = () => {
  const { t } = useTranslation();
  const [chats, setChats] = useState([]);
  const [selectedChat, setSelectedChat] = useState(null);
  const [loading, setLoading] = useState(true);
  const [topQuestions, setTopQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);

  useEffect(() => {
    loadConversations();
    loadTopQuestions();
  }, []);

  const loadConversations = async () => {
    setLoading(true);
    try {
      const { data } = await clientAPI.getConversations();
      const list = data?.conversations || [];
      setChats(list);
      if (list.length && !selectedChat) setSelectedChat(list[0]);
    } catch (e) {
      console.error('Failed to load conversations:', e);
      setChats([]);
    } finally {
      setLoading(false);
    }
  };

  const loadTopQuestions = async () => {
    setLoadingQuestions(true);
    try {
      const { data } = await clientAPI.getTopQuestions();
      setTopQuestions(data?.top_questions || []);
    } catch {
      setTopQuestions([]);
    } finally {
      setLoadingQuestions(false);
    }
  };

  /* ── Aggregate stats for the header strip ── */
  const stats = useMemo(() => {
    const total = chats.length;
    const unread = chats.reduce((n, c) => n + (c.unread || 0), 0);
    const byChannel = chats.reduce((m, c) => {
      m[c.source || 'other'] = (m[c.source || 'other'] || 0) + 1;
      return m;
    }, {});
    const primaryChannel = Object.entries(byChannel).sort((a, b) => b[1] - a[1])[0]?.[0] || '—';
    return [
      { accent: 'rose',  icon: ChatCircle,       label: 'Conversations', value: total.toLocaleString(), delta: `${Object.keys(byChannel).length} channel(s)`, trend: 'up' },
      { accent: 'sage',  icon: CheckCircle,      label: 'Resolved',      value: (total - unread).toLocaleString(),                delta: unread ? `${unread} unread` : 'all clear', trend: unread ? 'down' : 'up' },
      { accent: 'iris',  icon: BellSimple,       label: 'Unread',        value: unread.toLocaleString(),                          delta: unread ? 'needs review' : 'inbox zero',    trend: unread ? 'down' : 'up' },
      { accent: 'amber', icon: ArrowBendUpRight, label: 'Top Channel',   value: channelMeta(primaryChannel).label,                delta: primaryChannel,                            trend: 'up' },
    ];
  }, [chats]);

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ── Header ── */}
      <div className="flex justify-between items-start mb-8 animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest">
            {t('history.title') || 'Activity'}
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            conversation log · {chats.length} total
          </div>
        </div>
        <div className="hidden md:flex gap-2.5">
          <Button variant="violet" icon={ArrowClockwise} onClick={loadConversations}>
            {t('history.refresh') || 'Refresh'}
          </Button>
        </div>
      </div>

      {/* ── Stats strip ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Chat list + detail ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-8">
        <div className="lg:col-span-1">
          <ChatListPanel
            chats={chats}
            loading={loading}
            selectedId={selectedChat?.id}
            onSelect={setSelectedChat}
          />
        </div>
        <div className="lg:col-span-2">
          {selectedChat ? (
            <ChatDetailPanel chat={selectedChat} />
          ) : (
            <Card className="h-full flex items-center justify-center py-16">
              <div className="text-center">
                <ChatCircle size={40} weight="light" className="text-fog mx-auto mb-3" />
                <p className="label-mono">{t('history.selectChat') || 'Select a conversation'}</p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ── Top Questions ── */}
      <Card>
        <CardHeader
          title={t('dashboard.topQuestions') || 'Top Questions'}
          action={<CardAction onClick={loadTopQuestions}>refresh</CardAction>}
        />
        {loadingQuestions ? (
          <p className="label-mono py-6 text-center">loading…</p>
        ) : topQuestions.filter(q => q.question).length === 0 ? (
          <p className="label-mono py-6 text-center">no questions yet</p>
        ) : (
          <div className="divide-y divide-rule">
            {topQuestions.filter(q => q.question).map((item, i) => (
              <div key={i} className="flex items-center gap-3.5 py-3">
                <div className={`w-[38px] h-[38px] rounded-md border-2 border-iris text-iris
                                flex items-center justify-center font-mono text-[13px] font-bold`}>
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] text-ink truncate">{item.question}</div>
                </div>
                <span className="pill pill-info">{item.count} asks</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

/* ─────────────── Chat list panel ─────────────── */

const ChatListPanel = ({ chats, loading, selectedId, onSelect }) => {
  const { t } = useTranslation();

  return (
    <Card className="p-0 overflow-hidden">
      <div className="px-6 pt-6 pb-4 flex items-center justify-between border-b border-rule">
        <h3 className="text-[16px] font-semibold text-ink">
          {t('history.allConversations') || 'All Conversations'}
        </h3>
        <span className="label-mono">{chats.length}</span>
      </div>

      <div className="max-h-[560px] overflow-y-auto">
        {loading ? (
          <p className="label-mono py-8 text-center">loading…</p>
        ) : chats.length === 0 ? (
          <p className="label-mono py-8 text-center">no conversations yet</p>
        ) : (
          chats.map((c) => {
            const meta = channelMeta(c.source);
            const active = selectedId === c.id;
            return (
              <button
                key={c.id}
                onClick={() => onSelect(c)}
                className={`w-full text-left px-6 py-3.5 border-b border-rule last:border-0
                            transition-colors duration-150 cursor-pointer
                            ${active ? 'bg-mist' : 'hover:bg-linen'}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`shrink-0 w-[38px] h-[38px] rounded-md border-2
                                  ${ACCENT_BORDER[meta.accent]}
                                  flex items-center justify-center`}>
                    <meta.icon size={18} weight="light" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[14px] font-medium text-ink truncate">
                        {c.customerName || 'Anonymous'}
                      </span>
                      {c.unread > 0 && (
                        <span className="pill pill-alert">{c.unread}</span>
                      )}
                    </div>
                    <div className="text-[12px] text-fog truncate mt-0.5">{c.lastMessage}</div>
                    <div className="font-mono text-[11px] text-fog mt-1">{c.timestamp}</div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </Card>
  );
};

/* ─────────────── Chat detail panel ─────────────── */

const ChatDetailPanel = ({ chat }) => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState({});
  const [rating, setRating] = useState(null);
  const [notes, setNotes] = useState('');
  const [notesOpen, setNotesOpen] = useState(false);

  useEffect(() => {
    if (!chat?.conversation_id) {
      setMessages([]);
      return;
    }
    setLoading(true);
    clientAPI.getConversationDetail(chat.conversation_id)
      .then(({ data }) => {
        setRating(data?.user_rating || null);
        setNotes(data?.notes || '');
        setMessages((data?.messages || []).map((m, i) => ({
          id: i + 1,
          text: m.text,
          sender: m.sender,
          timestamp: m.timestamp,
          photo: m.photo || null,
        })));
      })
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  }, [chat]);

  const meta = channelMeta(chat?.source);

  const handleAddToKnowledge = async () => {
    if (!messages.length) return;
    setBusy((b) => ({ ...b, kb: true }));
    try {
      const pairs = [];
      for (let i = 0; i < messages.length - 1; i++) {
        if (messages[i].sender === 'customer' && messages[i + 1].sender === 'ai') {
          pairs.push({ q: messages[i].text, a: messages[i + 1].text });
        }
      }
      if (!pairs.length) {
        alert(t('history.noQAPairs') || 'No Q&A pairs found');
        return;
      }
      for (const p of pairs) {
        try { await ragAPI.saveSandboxQA(p.q, p.a); } catch (e) { console.error(e); }
      }
      await clientAPI.syncData();
      alert(t('history.addedToKnowledge') || `${pairs.length} Q&A pairs added to knowledge base`);
    } catch (e) {
      console.error(e);
      alert(t('history.addToKnowledgeError') || 'Failed');
    } finally {
      setBusy((b) => ({ ...b, kb: false }));
    }
  };

  const handleEmail = async () => {
    if (!chat?.conversation_id) return;
    setBusy((b) => ({ ...b, email: true }));
    try {
      const { data } = await clientAPI.sendConversationEmail(chat.conversation_id);
      if (data?.email_sent) alert(t('history.emailSent') || 'Email sent');
      else if (data?.scheduled) alert(t('history.emailScheduled') || 'Email scheduled');
      else alert(data?.email_result?.message || t('history.emailNotSent') || 'Email not sent');
    } catch (e) {
      alert(e?.response?.data?.message || t('history.emailError') || 'Failed');
    } finally {
      setBusy((b) => ({ ...b, email: false }));
    }
  };

  const handleRate = async (v) => {
    if (!chat?.conversation_id) return;
    setBusy((b) => ({ ...b, rating: true }));
    try {
      await clientAPI.rateConversation(chat.conversation_id, v);
      setRating(v);
    } catch {
      alert(t('history.ratingError') || 'Failed');
    } finally {
      setBusy((b) => ({ ...b, rating: false }));
    }
  };

  const handleSaveNotes = async () => {
    if (!chat?.conversation_id) return;
    setBusy((b) => ({ ...b, notes: true }));
    try {
      await clientAPI.updateConversationNotes(chat.conversation_id, notes);
      setNotesOpen(false);
    } catch {
      alert(t('history.notesError') || 'Failed');
    } finally {
      setBusy((b) => ({ ...b, notes: false }));
    }
  };

  return (
    <Card className="p-0 overflow-hidden">
      {/* Header strip */}
      <div className="px-6 py-5 border-b border-rule flex items-start justify-between gap-4">
        <div className="flex items-center gap-3.5 min-w-0">
          <div className={`shrink-0 w-[44px] h-[44px] rounded-md border-2
                          ${ACCENT_BORDER[meta.accent]}
                          flex items-center justify-center`}>
            <meta.icon size={22} weight="light" />
          </div>
          <div className="min-w-0">
            <div className="text-[16px] font-semibold text-ink truncate">
              {chat.customerName || 'Anonymous'}
            </div>
            <div className="font-mono text-[12px] text-fog">
              {meta.label} · {t('history.lastActive') || 'last active'} {chat.timestamp}
            </div>
          </div>
        </div>
        <Button variant="violet" icon={Plus} onClick={handleAddToKnowledge}>
          {busy.kb ? (t('history.adding') || 'Adding…') : (t('history.addToKnowledge') || 'Add to Knowledge')}
        </Button>
      </div>

      {/* Action row */}
      <div className="px-6 py-3 border-b border-rule flex flex-wrap items-center gap-2.5">
        <Button variant="pink" icon={PaperPlaneTilt} onClick={handleEmail}>
          {busy.email ? '…' : (t('history.sendEmail') || 'Send Email')}
        </Button>
        <button
          onClick={() => handleRate('positive')}
          disabled={busy.rating}
          className={`btn ${rating === 'positive' ? 'btn-green' : 'btn-violet opacity-60 hover:opacity-100'}`}
        >
          <ThumbsUp size={16} weight="light" />
        </button>
        <button
          onClick={() => handleRate('negative')}
          disabled={busy.rating}
          className={`btn ${rating === 'negative' ? 'btn-pink' : 'btn-violet opacity-60 hover:opacity-100'}`}
        >
          <ThumbsDown size={16} weight="light" />
        </button>
        <Button variant="amber" icon={Note} onClick={() => setNotesOpen(true)}>
          {t('history.notes') || 'Notes'}
        </Button>
      </div>

      {/* Messages */}
      <div className="px-6 py-5 max-h-[440px] overflow-y-auto space-y-4">
        {loading ? (
          <p className="label-mono py-6 text-center">loading…</p>
        ) : messages.length === 0 ? (
          <p className="label-mono py-6 text-center">
            {t('history.noMessages') || 'No messages in this conversation'}
          </p>
        ) : (
          messages.map((m) => (
            <MessageBubble key={m.id} {...m} />
          ))
        )}
      </div>

      {/* Notes modal */}
      {notesOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
          <div className="surface p-6 w-full max-w-xl animate-fade-up">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[16px] font-semibold text-ink">
                {t('history.notes') || 'Notes'}
              </h3>
              <button onClick={() => setNotesOpen(false)} className="text-fog hover:text-ink cursor-pointer">
                <X size={20} weight="light" />
              </button>
            </div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('history.notesPlaceholder') || 'Add notes about this conversation…'}
              className="w-full h-40 p-3 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink font-sans resize-none
                         focus:outline-none focus:border-iris transition-colors"
            />
            <div className="flex justify-end gap-2.5 mt-4">
              <Button variant="amber" onClick={() => setNotesOpen(false)}>
                {t('common.cancel') || 'Cancel'}
              </Button>
              <Button variant="green" onClick={handleSaveNotes}>
                {busy.notes ? (t('common.saving') || 'Saving…') : (t('common.save') || 'Save')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};

/* ─────────────── Message bubble ─────────────── */

const MessageBubble = ({ text, sender, timestamp, photo }) => {
  const mine = sender !== 'customer';
  return (
    <div className={`flex gap-3 ${mine ? 'flex-row-reverse' : ''}`}>
      <div className={`shrink-0 w-[34px] h-[34px] rounded-md border-2
                      ${mine ? 'border-iris text-iris' : 'border-sage text-sage'}
                      flex items-center justify-center`}>
        {mine ? <Robot size={16} weight="light" /> : <User size={16} weight="light" />}
      </div>
      <div className="max-w-[78%]">
        <div className={`px-3.5 py-2.5 rounded-md border-[1.5px] border-rule
                        ${mine ? 'bg-mist' : 'bg-linen'}`}>
          <p className="text-[13px] text-ink whitespace-pre-line leading-relaxed">{text}</p>
          {photo && (
            <img src={photo} alt="attachment"
                 className="mt-2 rounded-sm border border-rule max-w-full h-auto" />
          )}
        </div>
        <div className={`font-mono text-[11px] text-fog mt-1 ${mine ? 'text-right' : ''}`}>
          {timestamp}
        </div>
      </div>
    </div>
  );
};

export default HistoryPage;
