import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Flask,
  GraduationCap,
  ArrowRight,
  X,
  Lightning,
  CheckCircle,
  ChatCircleDots,
  Eye,
} from '@phosphor-icons/react';

import ChatWindow from '../components/sandbox/ChatWindow';
import PhotoUploadTest from '../components/sandbox/PhotoUploadTest';
import { useAuth } from '../context/AuthContext';

import Card, { CardHeader } from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatCard from '../components/ui/StatCard';

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

const SandboxPage = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const knowledgeSplitEnabled = user?.feature_flags?.mcp_knowledge_split;

  const [bannerDismissed, setBannerDismissed] = useState(
    () => localStorage.getItem('sandbox-banner-dismissed') === 'true'
  );

  const dismissBanner = () => {
    setBannerDismissed(true);
    localStorage.setItem('sandbox-banner-dismissed', 'true');
  };

  const goToTraining = () => {
    const pathMatch = window.location.pathname.match(/^\/l\/([^/]+)/);
    if (pathMatch) {
      window.location.href = `/l/${pathMatch[1]}/training`;
      return;
    }
    const isOld = window.location.pathname === '/l' && window.location.search.includes('tag=');
    if (isOld) {
      window.dispatchEvent(new CustomEvent('concierge:navigate', { detail: { view: 'training' } }));
    } else {
      window.location.href = '/training';
    }
  };

  /* Assistant mode — full-height immersive */
  if (knowledgeSplitEnabled) {
    return (
      <div className="max-w-[1200px] mx-auto flex flex-col h-[calc(100vh-140px)] min-h-[540px]">
        <div className="flex justify-between items-start mb-6 animate-fade-up">
          <div>
            <h1 className="text-[28px] font-bold tracking-tightest">
              {t('sandbox.assistantTitle') || 'Nexy Assistant'}
            </h1>
            <div className="font-mono text-[13px] text-fog mt-1">
              live AI assistant · MCP enabled
            </div>
          </div>
        </div>
        <Card className="flex-1 min-h-0 p-0 overflow-hidden">
          <ChatWindow fullHeight />
        </Card>
      </div>
    );
  }

  const stats = [
    { accent: 'iris',  icon: Flask,          label: 'Mode',       value: 'Sandbox',  delta: 'test only',        trend: 'up' },
    { accent: 'sage',  icon: CheckCircle,    label: 'Persona',    value: 'Jeevs',    delta: 'synced',           trend: 'up' },
    { accent: 'amber', icon: Lightning,      label: 'Latency',    value: '< 2s',     delta: 'avg response',     trend: 'up' },
    { accent: 'rose',  icon: ChatCircleDots, label: 'Privacy',    value: 'Private',  delta: 'not logged to KB', trend: 'up' },
  ];

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ── Header ── */}
      <div className="flex justify-between items-start mb-8 animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest">
            {t('sandbox.title') || 'Sandbox'}
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            rehearsal room · chat with Jeevs before going live
          </div>
        </div>
        <div className="hidden md:flex gap-2.5">
          <Button variant="violet" icon={GraduationCap} onClick={goToTraining}>
            Open Jeevs
          </Button>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Info banner ── */}
      {!bannerDismissed && (
        <Card accent="iris" className="mb-5 relative">
          <button
            onClick={dismissBanner}
            className="absolute top-4 right-4 text-fog hover:text-ink cursor-pointer"
            aria-label="Dismiss"
          >
            <X size={18} weight="light" />
          </button>
          <div className="flex items-start gap-4 pr-8">
            <div className={`shrink-0 w-[44px] h-[44px] rounded-md border-2 ${ACCENT_BORDER.iris}
                            flex items-center justify-center`}>
              <Flask size={22} weight="light" />
            </div>
            <div className="flex-1">
              <div className="text-[15px] font-semibold text-ink mb-1">
                {t('sandbox.newLocationTitle') || 'Sandbox is also available inside Jeevs'}
              </div>
              <p className="text-[13px] text-slate leading-relaxed mb-3">
                {t('sandbox.newLocationDescription') ||
                  'For convenience, you can now rehearse right from the Jeevs training room, directly under the system prompt editor.'}
              </p>
              <button
                onClick={goToTraining}
                className="inline-flex items-center gap-1.5 font-mono text-[12px] text-iris
                           border-[1.5px] border-iris-soft rounded-sm px-2.5 py-1
                           hover:border-iris transition-colors cursor-pointer"
              >
                <GraduationCap size={14} weight="light" />
                {t('sandbox.goToTraining') || 'Go to Jeevs'}
                <ArrowRight size={14} weight="light" />
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* ── Main sandbox grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-8">
        <div className="lg:col-span-2">
          <Card className="p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-rule flex items-center justify-between">
              <h3 className="text-[16px] font-semibold text-ink">Chat Rehearsal</h3>
              <span className="label-mono">sandbox</span>
            </div>
            <div className="min-h-[560px]">
              <ChatWindow />
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card accent="rose">
            <CardHeader title="Photo Test" />
            <PhotoUploadTest />
          </Card>

          <Card accent="amber">
            <CardHeader title="What to Try" />
            <ul className="space-y-3 text-[13px] text-slate leading-relaxed">
              <li className="flex gap-2.5">
                <Eye size={16} weight="light" className="text-amber shrink-0 mt-0.5" />
                Ask the most common customer question.
              </li>
              <li className="flex gap-2.5">
                <Eye size={16} weight="light" className="text-amber shrink-0 mt-0.5" />
                Try an edge case — broken English, typos, multiple questions.
              </li>
              <li className="flex gap-2.5">
                <Eye size={16} weight="light" className="text-amber shrink-0 mt-0.5" />
                Push Jeevs off-topic and check how gracefully he declines.
              </li>
              <li className="flex gap-2.5">
                <Eye size={16} weight="light" className="text-amber shrink-0 mt-0.5" />
                Request escalation — confirm HITL handoff fires.
              </li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default SandboxPage;
