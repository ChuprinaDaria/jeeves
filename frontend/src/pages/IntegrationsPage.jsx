import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Browser,
  WhatsappLogo,
  TelegramLogo,
  EnvelopeSimple,
  Headset,
  PuzzlePiece,
  GoogleLogo,
  InstagramLogo,
  LinkedinLogo,
  FacebookLogo,
  CalendarBlank,
  VideoCamera,
  Phone,
  ShareNetwork,
  Code,
  DeviceMobile,
  X,
  ArrowClockwise,
  Copy,
} from '@phosphor-icons/react';

import api from '../api/axios';
import { clientAPI } from '../api/client';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatCard from '../components/ui/StatCard';

import WebWidgetSetup from '../components/integrations/WebWidgetSetup';
import EmailSetup from '../components/integrations/EmailSetup';
import TelegramSetup from '../components/integrations/TelegramSetup';
import ChromeExtensionSetup from '../components/integrations/ChromeExtensionSetup';
import HITLSetup from '../components/integrations/HITLSetup';
import WhatsAppSetup from '../components/integrations/WhatsAppSetup';
import TelegramPersonalSetup from '../components/integrations/TelegramPersonalSetup';

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

/* ─────────────── Page ─────────────── */

const IntegrationsPage = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [clientInfo, setClientInfo] = useState(null);
  const [status, setStatus] = useState({
    whatsapp: false,
    email: false,
    telegram: false,
    hitl: false,
    extension: false,
    web: true, // always "connected" for all clients
  });
  const [whatsappPhone, setWhatsappPhone] = useState('');
  const [telegramPersonalHandle, setTelegramPersonalHandle] = useState('');
  const [modal, setModal] = useState(null); // 'whatsapp' | 'email' | 'telegram' | 'hitl' | 'extension' | 'webwidget' | 'web'
  const [webQR, setWebQR] = useState(null);
  const [loadingWebQR, setLoadingWebQR] = useState(false);
  const [toast, setToast] = useState('');

  const flashToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 2200); };

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      api.get('/tools/matrix/bridges/whatsapp/state/').catch(() => ({ data: {} })),
      api.get('/clients/me/'),
      api.get('/clients/email-smtp/config/').catch(() => ({ data: {} })),
      api.get('/clients/telegram/config/').catch(() => ({ data: {} })),
      api.get('/clients/hitl/config/').catch(() => ({ data: {} })),
      api.get('/tools/matrix/bridges/telegram/state/').catch(() => ({ data: {} })),
    ])
      .then(([wa, me, email, tg, hitl, tgPersonal]) => {
        if (!mounted) return;
        setClientInfo(me.data);
        setStatus({
          whatsapp:         wa.data?.status === 'connected',
          email:            !!email.data?.email_smtp_enabled,
          telegram:         !!tg.data?.telegram_enabled,
          telegramPersonal: tgPersonal.data?.status === 'connected',
          hitl:             !!hitl.data?.hitl_enabled,
          extension:        !!me.data?.extension_enabled,
          web:              true,
        });
        setWhatsappPhone(wa.data?.remote_handle || '');
        setTelegramPersonalHandle(tgPersonal.data?.remote_handle || '');
      })
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  const reload = (keys) => {
    const tasks = [];
    if (keys.includes('whatsapp')) tasks.push(
      api.get('/tools/matrix/bridges/whatsapp/state/')
        .then((r) => {
          setStatus((s) => ({ ...s, whatsapp: r.data?.status === 'connected' }));
          setWhatsappPhone(r.data?.remote_handle || '');
        })
        .catch(() => {})
    );
    if (keys.includes('telegram-personal')) tasks.push(
      api.get('/tools/matrix/bridges/telegram/state/')
        .then((r) => {
          setStatus((s) => ({ ...s, telegramPersonal: r.data?.status === 'connected' }));
          setTelegramPersonalHandle(r.data?.remote_handle || '');
        })
        .catch(() => {})
    );
    if (keys.includes('email')) tasks.push(
      api.get('/clients/email-smtp/config/')
        .then((r) => setStatus((s) => ({ ...s, email: !!r.data?.email_smtp_enabled })))
        .catch(() => {})
    );
    if (keys.includes('telegram')) tasks.push(
      api.get('/clients/telegram/config/')
        .then((r) => setStatus((s) => ({ ...s, telegram: !!r.data?.telegram_enabled })))
        .catch(() => {})
    );
    if (keys.includes('hitl')) tasks.push(
      api.get('/clients/hitl/config/')
        .then((r) => setStatus((s) => ({ ...s, hitl: !!r.data?.hitl_enabled })))
        .catch(() => {})
    );
    return Promise.all(tasks);
  };

  /* ── Web chat QR flow ── */
  const loadOrCreateWebQR = useCallback(async () => {
    if (!clientInfo) return;
    setLoadingWebQR(true);
    try {
      const qrs = (await clientAPI.getQRCodes()).data || [];
      const tag = clientInfo?.tag || localStorage.getItem('client_tag');
      let baseUrl = window.location.origin;
      if (clientInfo?.webchat_domain) {
        const d = clientInfo.webchat_domain.trim();
        baseUrl = (d.startsWith('http://') || d.startsWith('https://')) ? d.replace(/\/$/, '') : `https://${d}`.replace(/\/$/, '');
      }
      const url = `${baseUrl}/client?tag=${tag}`;
      let qr = qrs.find((q) => q.integration_type === 'web' || q.name === 'Web Chat Integration');
      if (!qr && qrs.length < 10) {
        qr = (await clientAPI.createQRCode({
          name: 'Web Chat Integration',
          description: 'QR code for Web chat integration',
          location: url,
          integration_type: 'web',
          is_active: true,
        })).data;
      }
      if (qr?.qr_code_url_display) setWebQR({ img: qr.qr_code_url_display, url });
      else if (qr?.qr_code) setWebQR({ img: qr.qr_code, url });
      else setWebQR({ img: null, url });
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingWebQR(false);
    }
  }, [clientInfo]);

  useEffect(() => {
    if (modal === 'web' && clientInfo) loadOrCreateWebQR();
  }, [modal, clientInfo, loadOrCreateWebQR]);

  /* ── Integration catalog ── */
  const viaExt = t('integrations.viaExtension') || 'via Extension';
  const catalog = [
    {
      key: 'web',       icon: Browser,        accent: 'iris',
      name: t('integrations.webChatName')     || 'Web Chat',
      desc: t('integrations.webChatDesc')     || 'B2C client chat interface',
      state: 'connected', onClick: () => setModal('web'),
    },
    {
      key: 'webwidget', icon: Code,           accent: 'iris',
      name: t('integrations.webWidgetName')   || 'Web Widget',
      desc: t('integrations.webWidgetDesc')   || 'Embed chat on your website',
      state: clientInfo?.client_type === 'white_label' ? 'notConnected' : 'hidden',
      onClick: () => setModal('webwidget'),
    },
    {
      key: 'whatsapp',  icon: WhatsappLogo,   accent: 'sage',
      name: t('integrations.whatsappName')    || 'WhatsApp',
      desc: t('integrations.whatsappDesc2')   || 'WhatsApp Business bridge',
      state: status.whatsapp ? 'connected' : 'notConnected',
      meta: status.whatsapp && whatsappPhone ? whatsappPhone : null,
      onClick: () => setModal('whatsapp'),
    },
    {
      key: 'telegram',  icon: TelegramLogo,   accent: 'iris',
      name: t('integrations.telegramName')    || 'Telegram',
      desc: t('integrations.telegramDesc')    || 'Connect a Telegram bot',
      state: status.telegram ? 'connected' : 'notConnected',
      onClick: () => setModal('telegram'),
    },
    {
      key: 'telegram-personal', icon: TelegramLogo, accent: 'sage',
      name: t('integrations.telegramPersonalName') || 'Telegram (personal)',
      desc: t('integrations.telegramPersonalDesc') || 'Your personal account via Matrix bridge',
      state: status.telegramPersonal ? 'connected' : 'notConnected',
      meta: status.telegramPersonal && telegramPersonalHandle ? `@${telegramPersonalHandle}` : null,
      onClick: () => setModal('telegram-personal'),
    },
    {
      key: 'email',     icon: EnvelopeSimple, accent: 'rose',
      name: t('integrations.emailName')       || 'Email',
      desc: t('integrations.emailDesc')       || 'SMTP — transactional & reports',
      state: status.email ? 'connected' : 'notConnected',
      onClick: () => setModal('email'),
    },
    {
      key: 'hitl',      icon: Headset,        accent: 'amber',
      name: t('integrations.hitlName')        || 'HITL (Manager)',
      desc: t('integrations.hitlDesc')        || 'Escalate to humans via Telegram',
      state: status.hitl ? 'connected' : 'notConnected',
      onClick: () => setModal('hitl'),
    },
    {
      key: 'extension', icon: PuzzlePiece,    accent: 'iris',
      name: t('integrations.extensionName')   || 'Chrome Extension',
      desc: t('integrations.extensionDesc')   || 'Web AI agent for scraping & automation',
      state: status.extension ? 'connected' : 'notConnected',
      onClick: () => setModal('extension'),
    },
    {
      key: 'messenger', icon: FacebookLogo,   accent: 'iris',
      name: t('integrations.messengerName')   || 'Facebook Messenger',
      desc: t('integrations.messengerDesc')   || 'Bridge conversations via extension',
      state: 'notConnected', meta: viaExt,
      onClick: () => setModal('extension'),
    },
    {
      key: 'instagram', icon: InstagramLogo,  accent: 'rose',
      name: t('integrations.instagramName')   || 'Instagram DM',
      desc: t('integrations.instagramDesc')   || 'Direct messages via extension',
      state: 'notConnected', meta: viaExt,
      onClick: () => setModal('extension'),
    },
    {
      key: 'linkedin',  icon: LinkedinLogo,   accent: 'iris',
      name: t('integrations.linkedinName')    || 'LinkedIn Messages',
      desc: t('integrations.linkedinDesc')    || 'Lead-gen bridge via extension',
      state: 'notConnected', meta: viaExt,
      onClick: () => setModal('extension'),
    },
    {
      key: 'gcal',      icon: CalendarBlank,  accent: 'rose',
      name: t('integrations.gcalName')        || 'Google Calendar',
      desc: t('integrations.gcalDesc')        || 'Sync appointments & bookings',
      state: 'soon',
    },
    {
      key: 'greview',   icon: GoogleLogo,     accent: 'amber',
      name: t('integrations.greviewName')     || 'Google Reviews',
      desc: t('integrations.greviewDesc')     || 'Monitor & respond to reviews',
      state: 'soon',
    },
    {
      key: 'avatar',    icon: VideoCamera,    accent: 'iris',
      name: t('integrations.avatarName')      || 'AI Video Avatar',
      desc: t('integrations.avatarDesc')      || 'Personalised video avatar & cloning',
      state: 'soon',
    },
    {
      key: 'voice',     icon: Phone,          accent: 'sage',
      name: t('integrations.voiceName')       || 'Voice AI — Phone RAG',
      desc: t('integrations.voiceDesc')       || 'Telephony with Jeeves',
      state: 'soon',
    },
    {
      key: 'make',      icon: ShareNetwork,   accent: 'iris',
      name: t('integrations.makeName')        || 'Make.com',
      desc: t('integrations.makeDesc')        || 'No-code automation scenarios',
      state: 'soon',
    },
    {
      key: 'n8n',       icon: ShareNetwork,   accent: 'amber',
      name: 'n8n',
      desc: t('integrations.n8nDesc')         || 'Self-hosted workflow automation',
      state: 'soon',
    },
    {
      key: 'api',       icon: Code,           accent: 'iris',
      name: t('integrations.apiName')         || 'Custom API',
      desc: t('integrations.apiDesc')         || 'Direct API integration',
      state: 'soon',
    },
  ].filter((c) => c.state !== 'hidden');

  const connectedCount = Object.values(status).filter(Boolean).length;
  const available = catalog.filter((c) => c.state !== 'soon').length;
  const comingSoon = catalog.filter((c) => c.state === 'soon').length;

  const stats = [
    { accent: 'sage',  icon: WhatsappLogo,  label: t('integrations.statConnected')  || 'Connected',   value: connectedCount.toString(), delta: t('integrations.availableCount', { count: available }) || `${available} available`, trend: 'up' },
    { accent: 'iris',  icon: Browser,       label: t('integrations.statAvailable')  || 'Available',   value: available.toString(),       delta: t('integrations.readyToDeploy') || 'ready to deploy',                                 trend: 'up' },
    { accent: 'amber', icon: CalendarBlank, label: t('integrations.statComingSoon') || 'Coming Soon', value: comingSoon.toString(),      delta: t('integrations.roadmapItems')  || 'roadmap items',                                   trend: 'up' },
    { accent: 'rose',  icon: Headset,       label: t('integrations.statEscalation') || 'Escalation',  value: status.hitl ? 'ON' : 'OFF',  delta: status.hitl ? (t('integrations.hitlLive') || 'HITL live') : (t('integrations.hitlOff') || 'manager off-duty'), trend: status.hitl ? 'up' : 'down' },
  ];

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ── Header ── */}
      <div className="flex justify-between items-start mb-8 animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest">
            {t('integrations.title') || 'Integrations'}
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            {t('integrations.headerSubtitle') || 'channels · bridges · automations'}
          </div>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Catalog grid ── */}
      {loading ? (
        <Card>
          <p className="label-mono py-10 text-center">
            {t('integrations.loadingList') || 'loading integrations…'}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
          {catalog.map((item) => (
            <IntegrationCard key={item.key} t={t} {...item} />
          ))}
        </div>
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 surface px-4 py-2.5 animate-fade-up">
          <span className="font-mono text-[12px] text-ink">{toast}</span>
        </div>
      )}

      {/* ── Modals ── */}
      {modal === 'whatsapp' && (
        <WhatsAppSetup
          bridgeConfig={{ whatsapp_bridge_enabled: status.whatsapp, whatsapp_bridge_phone: whatsappPhone, whatsapp_bridge_status: status.whatsapp ? 'connected' : 'disconnected', globally_enabled: true }}
          onClose={() => { setModal(null); reload(['whatsapp']); }}
        />
      )}
      {modal === 'webwidget'  && <WebWidgetSetup      onClose={() => setModal(null)} />}
      {modal === 'email'      && <EmailSetup          onClose={() => { setModal(null); reload(['email']); }} />}
      {modal === 'telegram'   && <TelegramSetup       onClose={() => { setModal(null); reload(['telegram']); }} />}
      {modal === 'telegram-personal' && (
        <TelegramPersonalSetup
          onClose={() => { setModal(null); reload(['telegram-personal']); }}
        />
      )}
      {modal === 'extension'  && <ChromeExtensionSetup onClose={() => setModal(null)} />}
      {modal === 'hitl'       && <HITLSetup           onClose={() => { setModal(null); reload(['hitl']); }} />}

      {modal === 'web' && (
        <WebChatModal
          t={t}
          loading={loadingWebQR}
          qr={webQR}
          onRegenerate={loadOrCreateWebQR}
          onCopy={() => { if (webQR?.url) { navigator.clipboard.writeText(webQR.url); flashToast(t('integrations.linkCopied') || 'Link copied'); } }}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
};

/* ─────────────── Integration card ─────────────── */

const IntegrationCard = ({ t, icon, accent, name, desc, state, meta, onClick }) => {
  const isSoon = state === 'soon';
  const IconCmp = icon;
  return (
    <Card accent={accent} hover={!isSoon} className={isSoon ? 'opacity-75' : 'cursor-pointer'}>
      <div className="flex items-start gap-3.5 mb-4" onClick={!isSoon ? onClick : undefined}>
        <div className={`shrink-0 w-[44px] h-[44px] rounded-md border-2
                        ${ACCENT_BORDER[accent]}
                        flex items-center justify-center`}>
          <IconCmp size={22} weight="light" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-semibold text-ink leading-tight">{name}</div>
          <div className="text-[12px] text-fog mt-0.5">{desc}</div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        {state === 'connected'    && <span className="pill pill-on">{t('integrations.connected') || 'connected'}</span>}
        {state === 'notConnected' && <span className="pill pill-off">{t('integrations.notConnected') || 'not connected'}</span>}
        {state === 'soon'         && <span className="pill pill-warning">{t('integrations.comingSoon') || 'coming soon'}</span>}
        {meta && <span className="font-mono text-[11px] text-fog truncate ml-2">{meta}</span>}
      </div>

      {!isSoon && (
        <div className="mt-4 pt-4 border-t border-rule">
          <Button
            variant={state === 'connected' ? 'green' : 'violet'}
            className="w-full justify-center"
            onClick={onClick}
          >
            {state === 'connected'
              ? (t('integrations.manage')    || 'Manage')
              : (t('integrations.configure') || 'Configure')}
          </Button>
        </div>
      )}
    </Card>
  );
};

/* ─────────────── Web chat modal ─────────────── */

const WebChatModal = ({ t, loading, qr, onRegenerate, onCopy, onClose }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
      <div className="surface p-6 w-full max-w-xl animate-fade-up">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="text-[16px] font-semibold text-ink">{t('integrations.webChatName') || 'Web Chat'}</h3>
            <div className="font-mono text-[12px] text-fog mt-0.5">{t('integrations.webShareHint') || 'share link or QR with customers'}</div>
          </div>
          <button onClick={onClose} className="text-fog hover:text-ink cursor-pointer">
            <X size={20} weight="light" />
          </button>
        </div>

        <div className="p-4 bg-linen border-[1.5px] border-rule rounded-md mb-4">
          {loading ? (
            <p className="label-mono py-8 text-center">{t('integrations.generating') || 'generating…'}</p>
          ) : qr?.img ? (
            <div className="flex flex-col items-center gap-3">
              <img src={qr.img} alt={t('integrations.webChatQRAlt') || 'Web chat QR'}
                   className="w-48 h-48 object-contain border-[1.5px] border-rule rounded-sm bg-paper" />
              <p className="font-mono text-[11px] text-fog">{t('integrations.scanToOpen') || 'scan to open chat'}</p>
            </div>
          ) : (
            <p className="label-mono py-6 text-center">{t('integrations.noQR') || 'no QR yet'}</p>
          )}
        </div>

        {qr?.url && (
          <div className="mb-4">
            <div className="label-mono mb-1.5">{t('integrations.linkLabel') || 'Link'}</div>
            <div className="flex gap-2">
              <input
                readOnly
                value={qr.url}
                className="flex-1 px-3 py-2 bg-cream border-[1.5px] border-rule rounded-sm
                           font-mono text-[12px] text-ink focus:outline-none focus:border-iris"
                onClick={(e) => e.target.select()}
              />
              <Button variant="violet" icon={Copy} onClick={onCopy}>{t('integrations.copy') || 'Copy'}</Button>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2.5 pt-4 border-t border-rule">
          <Button variant="amber" onClick={onClose}>{t('common.close') || 'Close'}</Button>
          <Button variant="green" icon={ArrowClockwise} onClick={onRegenerate}>
            {t('integrations.regenerate') || 'Regenerate'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default IntegrationsPage;
