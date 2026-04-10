import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChatCircle,
  CheckCircle,
  UserFocus,
  ArrowBendUpRight,
  FilePlus,
  Export,
  Plus,
  TelegramLogo,
  WhatsappLogo,
  Browser,
  EnvelopeSimple,
  DeviceMobile,
  MagnifyingGlass,
  FileText,
  Headset,
  Translate,
} from '@phosphor-icons/react';

import { useAuth } from '../context/AuthContext';
import { clientAPI } from '../api/client';

import StatCard from '../components/ui/StatCard';
import Card, { CardHeader, CardAction } from '../components/ui/Card';
import Button from '../components/ui/Button';

/* ─────────────── Helpers ─────────────── */

const DEFAULT_STATS = [
  { accent: 'rose',  icon: ChatCircle,       label: 'Conversations',   value: '1,284', delta: '+12% this week', trend: 'up' },
  { accent: 'sage',  icon: CheckCircle,      label: 'Resolution Rate', value: '94.2%', delta: '+2.1%',          trend: 'up' },
  { accent: 'iris',  icon: UserFocus,        label: 'Active Leads',    value: '47',    delta: '+8 new',         trend: 'up' },
  { accent: 'amber', icon: ArrowBendUpRight, label: 'Escalations',     value: '23',    delta: '−5% fewer',      trend: 'down' },
];

const DEFAULT_CHANNELS = [
  { icon: TelegramLogo,    accent: 'sage',  name: 'Telegram Bot', desc: '@concierge_demo_bot',    status: 'connected' },
  { icon: WhatsappLogo,    accent: 'sage',  name: 'WhatsApp',     desc: '+49 xxx xxx xx',          status: 'connected' },
  { icon: Browser,         accent: 'iris',  name: 'Web Widget',   desc: 'widget.example.com',      status: 'connected' },
  { icon: EnvelopeSimple,  accent: 'rose',  name: 'Email',        desc: 'ai@client-domain.com',    status: 'connected' },
  { icon: DeviceMobile,    accent: 'amber', name: 'iOS App',      desc: 'Jeeves Chat',              status: 'draft' },
];

const DEFAULT_AGENTS = [
  { icon: MagnifyingGlass, accent: 'iris',  name: 'SearchAgent',      type: 'RAG · vector search', calls: '2.4k calls' },
  { icon: FileText,        accent: 'sage',  name: 'DocumentAgent',    type: 'PDF · parsing',       calls: '891 calls' },
  { icon: Headset,         accent: 'rose',  name: 'EscalationAgent',  type: 'HITL · manager',      calls: '156 calls' },
  { icon: Translate,       accent: 'amber', name: 'TranslationAgent', type: 'multilingual · auto', calls: '1.1k calls' },
];

const DEFAULT_CONVERSATIONS = [
  { user: 'Maria K.',   channel: 'tg',  icon: TelegramLogo, preview: 'Can I book a consultation for Friday?', status: 'active',    time: '2 min' },
  { user: 'Hans M.',    channel: 'web', icon: Browser,      preview: 'What are your office hours?',            status: 'active',    time: '8 min' },
  { user: 'Sophie L.',  channel: 'ios', icon: DeviceMobile, preview: 'I need to speak with a manager',         status: 'escalated', time: '14 min' },
  { user: 'Oleksiy P.', channel: 'tg',  icon: TelegramLogo, preview: 'Thank you for the info!',                status: 'closed',    time: '1 hr' },
];

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

/* ─────────────── Greeting ─────────────── */

const greeting = () => {
  const hour = new Date().getHours();
  if (hour < 5)  return 'Good night';
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
};

const formatDelta = (num, suffix = '%') => {
  if (num == null) return null;
  const sign = num >= 0 ? '+' : '−';
  return `${sign}${Math.abs(num)}${suffix}`;
};

/* ─────────────── Page ─────────────── */

const DashboardPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading, user } = useAuth();

  const [stats, setStats] = useState(DEFAULT_STATS);
  const [syncedLabel, setSyncedLabel] = useState('just now');

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;

    let cancelled = false;
    (async () => {
      try {
        const { data } = await clientAPI.getStats();
        if (cancelled || !data) return;

        setStats([
          {
            accent: 'rose',
            icon: ChatCircle,
            label: t('dashboard.totalChats') || 'Conversations',
            value: (data.total_chats ?? 0).toLocaleString(),
            delta: formatDelta(data.chats_change),
            trend: (data.chats_change ?? 0) >= 0 ? 'up' : 'down',
          },
          {
            accent: 'sage',
            icon: CheckCircle,
            label: t('dashboard.resolutionRate') || 'Resolution Rate',
            value: `${data.conversion_rate ?? 0}%`,
            delta: formatDelta(data.conversion_change),
            trend: (data.conversion_change ?? 0) >= 0 ? 'up' : 'down',
          },
          {
            accent: 'iris',
            icon: UserFocus,
            label: t('dashboard.activeUsers') || 'Active Leads',
            value: (data.active_users ?? 0).toLocaleString(),
            delta: formatDelta(data.users_change),
            trend: (data.users_change ?? 0) >= 0 ? 'up' : 'down',
          },
          {
            accent: 'amber',
            icon: ArrowBendUpRight,
            label: t('dashboard.messages') || 'Messages',
            value: (data.total_messages ?? 0).toLocaleString(),
            delta: formatDelta(data.messages_change),
            trend: (data.messages_change ?? 0) >= 0 ? 'up' : 'down',
          },
        ]);
        setSyncedLabel('just now');
      } catch {
        // keep defaults — demo mode
      }
    })();
    return () => { cancelled = true; };
  }, [authLoading, isAuthenticated, t]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-full py-20">
        <p className="label-mono">{t('common.loading') || 'Loading…'}</p>
      </div>
    );
  }

  const userFirstName =
    (user?.first_name && user.first_name.trim()) ||
    (user?.username && user.username.split(/[@._\s]/)[0]) ||
    '';

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ── Greeting header ── */}
      <div className="flex justify-between items-start mb-8 animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest">
            {greeting()}
            {userFirstName ? `, ${userFirstName}` : ''}
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            jeeves v2.1 · synced {syncedLabel}
          </div>
        </div>
        <div className="hidden md:flex gap-2.5">
          <Button variant="violet" icon={FilePlus}>Add Document</Button>
          <Button variant="pink"   icon={Export}>Export</Button>
          <Button variant="green"  icon={Plus}>New Lead</Button>
        </div>
      </div>

      {/* ── Stats grid ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      {/* ── Channels + Agents ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-8">
        <Card>
          <CardHeader
            title={t('dashboard.channels') || 'Channels'}
            action={<CardAction>manage</CardAction>}
          />
          <div className="divide-y divide-rule">
            {DEFAULT_CHANNELS.map((ch) => (
              <div key={ch.name} className="flex items-center gap-3.5 py-3">
                <div className={`w-[38px] h-[38px] rounded-md border-2 ${ACCENT_BORDER[ch.accent]}
                                flex items-center justify-center`}>
                  <ch.icon size={20} weight="light" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-ink truncate">{ch.name}</div>
                  <div className="text-[12px] text-fog truncate">{ch.desc}</div>
                </div>
                <span className={`pill ${ch.status === 'connected' ? 'pill-on' : 'pill-off'}`}>
                  {ch.status}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title={t('dashboard.microAgents') || 'Micro-Agents'}
            action={<CardAction>configure</CardAction>}
          />
          <div className="divide-y divide-rule">
            {DEFAULT_AGENTS.map((a) => (
              <div key={a.name} className="flex items-center gap-3.5 py-3">
                <div className={`w-[38px] h-[38px] rounded-md border-2 ${ACCENT_BORDER[a.accent]}
                                flex items-center justify-center`}>
                  <a.icon size={20} weight="light" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-ink truncate">{a.name}</div>
                  <div className="font-mono text-[11px] text-fog truncate">{a.type}</div>
                </div>
                <div className="font-mono text-[12px] text-slate">{a.calls}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ── Recent Conversations ── */}
      <Card>
        <CardHeader
          title={t('dashboard.recentConversations') || 'Recent Conversations'}
          action={<CardAction>view all</CardAction>}
        />
        <div className="overflow-x-auto -mx-2">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {['User', 'Channel', 'Last Message', 'Status', 'Time'].map((h) => (
                  <th key={h}
                      className="label-mono text-left px-3 pb-3 pt-2 border-b-[1.5px] border-rule">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DEFAULT_CONVERSATIONS.map((c, i) => (
                <tr key={i} className="border-b border-rule last:border-0">
                  <td className="px-3 py-3 text-[13px] font-medium text-ink">{c.user}</td>
                  <td className="px-3 py-3">
                    <span className={`inline-flex items-center gap-1.5 font-mono text-[12px] px-2 py-0.5 rounded-sm border ${
                      c.channel === 'tg'  ? 'border-sage text-sage' :
                      c.channel === 'web' ? 'border-iris text-iris' :
                                            'border-amber text-amber'
                    }`}>
                      <c.icon size={14} weight="light" />
                      {c.channel === 'tg' ? 'Telegram' : c.channel === 'web' ? 'Web' : 'iOS'}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-[12px] text-fog">{c.preview}</td>
                  <td className="px-3 py-3">
                    <span className={`pill ${
                      c.status === 'active'    ? 'pill-on'    :
                      c.status === 'escalated' ? 'pill-alert' :
                                                 'pill-off'
                    }`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="px-3 py-3 font-mono text-[12px] text-fog">{c.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default DashboardPage;
