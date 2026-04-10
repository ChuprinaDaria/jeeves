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
import Card, { CardHeader, CardAction } from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatCard from '../components/ui/StatCard';

import WebWidgetSetup from '../components/integrations/WebWidgetSetup';
import EmailSetup from '../components/integrations/EmailSetup';
import TelegramSetup from '../components/integrations/TelegramSetup';
import ChromeExtensionSetup from '../components/integrations/ChromeExtensionSetup';
import HITLSetup from '../components/integrations/HITLSetup';
import WhatsAppSetup from '../components/integrations/WhatsAppSetup';

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
  const [modal, setModal] = useState(null); // 'whatsapp' | 'email' | 'telegram' | 'hitl' | 'extension' | 'webwidget' | 'web'
  const [webQR, setWebQR] = useState(null);
  const [loadingWebQR, setLoadingWebQR] = useState(false);
  const [toast, setToast] = useState('');

  const flashToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 2200); };

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      api.get('/clients/whatsapp/bridge/config/').catch(() => ({ data: {} })),
      api.get('/clients/me/'),
      api.get('/clients/email-smtp/config/').catch(() => ({ data: {} })),
      api.get('/clients/telegram/config/').catch(() => ({ data: {} })),
      api.get('/clients/hitl/config/').catch(() => ({ data: {} })),
    ])
      .then(([wa, me, email, tg, hitl]) => {
        if (!mounted) return;
        setClientInfo(me.data);
        setStatus({
          whatsapp:  wa.data?.whatsapp_bridge_status === 'connected',
          email:     !!email.data?.email_smtp_enabled,
          telegram:  !!tg.data?.telegram_enabled,
          hitl:      !!hitl.data?.hitl_enabled,
          extension: !!me.data?.extension_enabled,
          web:       true,
        });
        setWhatsappPhone(wa.data?.whatsapp_bridge_phone || '');
      })
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  const reload = (keys) => {
    const tasks = [];
    if (keys.includes('whatsapp')) tasks.push(
      api.get('/clients/whatsapp/bridge/config/')
        .then((r) => {
          setStatus((s) => ({ ...s, whatsapp: r.data?.whatsapp_bridge_status === 'connected' }));
          setWhatsappPhone(r.data?.whatsapp_bridge_phone || '');
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
  const catalog = [
    {
      key: 'web',       icon: Browser,        accent: 'iris',
      name: 'Web Chat', desc: 'B2C client chat interface',
      state: 'connected', onClick: () => setModal('web'),
    },
    {
      key: 'webwidget', icon: Code,           accent: 'iris',
      name: 'Web Widget', desc: 'Embed chat on your website',
      state: clientInfo?.client_type === 'white_label' ? 'notConnected' : 'hidden',
      onClick: () => setModal('webwidget'),
    },
    {
      key: 'whatsapp',  icon: WhatsappLogo,   accent: 'sage',
      name: 'WhatsApp', desc: 'WhatsApp Business bridge',
      state: status.whatsapp ? 'connected' : 'notConnected',
      meta: status.whatsapp && whatsappPhone ? whatsappPhone : null,
      onClick: () => setModal('whatsapp'),
    },
    {
      key: 'telegram',  icon: TelegramLogo,   accent: 'iris',
      name: 'Telegram', desc: 'Connect a Telegram bot',
      state: status.telegram ? 'connected' : 'notConnected',
      onClick: () => setModal('telegram'),
    },
    {
      key: 'email',     icon: EnvelopeSimple, accent: 'rose',
      name: 'Email',    desc: 'SMTP — transactional & reports',
      state: status.email ? 'connected' : 'notConnected',
      onClick: () => setModal('email'),
    },
    {
      key: 'hitl',      icon: Headset,        accent: 'amber',
      name: 'HITL (Manager)', desc: 'Escalate to humans via Telegram',
      state: status.hitl ? 'connected' : 'notConnected',
      onClick: () => setModal('hitl'),
    },
    {
      key: 'extension', icon: PuzzlePiece,    accent: 'iris',
      name: 'Chrome Extension', desc: 'Web AI agent for scraping & automation',
      state: status.extension ? 'connected' : 'notConnected',
      onClick: () => setModal('extension'),
    },
    {
      key: 'messenger', icon: FacebookLogo,   accent: 'iris',
      name: 'Facebook Messenger', desc: 'Bridge conversations via extension',
      state: 'notConnected', meta: 'via Extension',
      onClick: () => setModal('extension'),
    },
    {
      key: 'instagram', icon: InstagramLogo,  accent: 'rose',
      name: 'Instagram DM', desc: 'Direct messages via extension',
      state: 'notConnected', meta: 'via Extension',
      onClick: () => setModal('extension'),
    },
    {
      key: 'linkedin',  icon: LinkedinLogo,   accent: 'iris',
      name: 'LinkedIn Messages', desc: 'Lead-gen bridge via extension',
      state: 'notConnected', meta: 'via Extension',
      onClick: () => setModal('extension'),
    },
    {
      key: 'gcal',      icon: CalendarBlank,  accent: 'rose',
      name: 'Google Calendar', desc: 'Sync appointments & bookings',
      state: 'soon',
    },
    {
      key: 'greview',   icon: GoogleLogo,     accent: 'amber',
      name: 'Google Reviews', desc: 'Monitor & respond to reviews',
      state: 'soon',
    },
    {
      key: 'avatar',    icon: VideoCamera,    accent: 'iris',
      name: 'AI Video Avatar', desc: 'Personalised video avatar & cloning',
      state: 'soon',
    },
    {
      key: 'voice',     icon: Phone,          accent: 'sage',
      name: 'Voice AI — Phone RAG', desc: 'Telephony with Jeeves',
      state: 'soon',
    },
    {
      key: 'make',      icon: ShareNetwork,   accent: 'iris',
      name: 'Make.com', desc: 'No-code automation scenarios',
      state: 'soon',
    },
    {
      key: 'n8n',       icon: ShareNetwork,   accent: 'amber',
      name: 'n8n', desc: 'Self-hosted workflow automation',
      state: 'soon',
    },
    {
      key: 'api',       icon: Code,           accent: 'iris',
      name: 'Custom API', desc: 'Direct API integration',
      state: 'soon',
    },
  ].filter((c) => c.state !== 'hidden');

  const connectedCount = Object.values(status).filter(Boolean).length;
  const available = catalog.filter((c) => c.state !== 'soon').length;
  const comingSoon = catalog.filter((c) => c.state === 'soon').length;

  const stats = [
    { accent: 'sage',  icon: WhatsappLogo, label: 'Connected',   value: connectedCount.toString(), delta: `${available} available`, trend: 'up' },
    { accent: 'iris',  icon: Browser,      label: 'Available',   value: available.toString(),       delta: 'ready to deploy',        trend: 'up' },
    { accent: 'amber', icon: CalendarBlank,label: 'Coming Soon', value: comingSoon.toString(),      delta: 'roadmap items',          trend: 'up' },
    { accent: 'rose',  icon: Headset,      label: 'Escalation',  value: status.hitl ? 'ON' : 'OFF',  delta: status.hitl ? 'HITL live' : 'manager off-duty', trend: status.hitl ? 'up' : 'down' },
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
            channels · bridges · automations
          </div>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Catalog grid ── */}
      {loading ? (
        <Card><p className="label-mono py-10 text-center">loading integrations…</p></Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
          {catalog.map((item) => (
            <IntegrationCard key={item.key} {...item} />
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
      {modal === 'extension'  && <ChromeExtensionSetup onClose={() => setModal(null)} />}
      {modal === 'hitl'       && <HITLSetup           onClose={() => { setModal(null); reload(['hitl']); }} />}

      {modal === 'web' && (
        <WebChatModal
          loading={loadingWebQR}
          qr={webQR}
          onRegenerate={loadOrCreateWebQR}
          onCopy={() => { if (webQR?.url) { navigator.clipboard.writeText(webQR.url); flashToast('Link copied'); } }}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
};

/* ─────────────── Integration card ─────────────── */

const IntegrationCard = ({ icon, accent, name, desc, state, meta, onClick }) => {
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
        {state === 'connected' && <span className="pill pill-on">connected</span>}
        {state === 'notConnected' && <span className="pill pill-off">not connected</span>}
        {state === 'soon' && <span className="pill pill-warning">coming soon</span>}
        {meta && <span className="font-mono text-[11px] text-fog truncate ml-2">{meta}</span>}
      </div>

      {!isSoon && (
        <div className="mt-4 pt-4 border-t border-rule">
          <Button
            variant={state === 'connected' ? 'green' : 'violet'}
            className="w-full justify-center"
            onClick={onClick}
          >
            {state === 'connected' ? 'Manage' : 'Configure'}
          </Button>
        </div>
      )}
    </Card>
  );
};

/* ─────────────── Web chat modal ─────────────── */

const WebChatModal = ({ loading, qr, onRegenerate, onCopy, onClose }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
      <div className="surface p-6 w-full max-w-xl animate-fade-up">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="text-[16px] font-semibold text-ink">Web Chat</h3>
            <div className="font-mono text-[12px] text-fog mt-0.5">share link or QR with customers</div>
          </div>
          <button onClick={onClose} className="text-fog hover:text-ink cursor-pointer">
            <X size={20} weight="light" />
          </button>
        </div>

        <div className="p-4 bg-linen border-[1.5px] border-rule rounded-md mb-4">
          {loading ? (
            <p className="label-mono py-8 text-center">generating…</p>
          ) : qr?.img ? (
            <div className="flex flex-col items-center gap-3">
              <img src={qr.img} alt="Web chat QR" className="w-48 h-48 object-contain border-[1.5px] border-rule rounded-sm bg-paper" />
              <p className="font-mono text-[11px] text-fog">scan to open chat</p>
            </div>
          ) : (
            <p className="label-mono py-6 text-center">no QR yet</p>
          )}
        </div>

        {qr?.url && (
          <div className="mb-4">
            <div className="label-mono mb-1.5">Link</div>
            <div className="flex gap-2">
              <input
                readOnly
                value={qr.url}
                className="flex-1 px-3 py-2 bg-cream border-[1.5px] border-rule rounded-sm
                           font-mono text-[12px] text-ink focus:outline-none focus:border-iris"
                onClick={(e) => e.target.select()}
              />
              <Button variant="violet" icon={Copy} onClick={onCopy}>Copy</Button>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2.5 pt-4 border-t border-rule">
          <Button variant="amber" onClick={onClose}>Close</Button>
          <Button variant="green" icon={ArrowClockwise} onClick={onRegenerate}>Regenerate</Button>
        </div>
      </div>
    </div>
  );
};

export default IntegrationsPage;
