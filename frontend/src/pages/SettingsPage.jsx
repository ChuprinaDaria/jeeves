import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Upload,
  X,
  Image as ImageIcon,
  ChatText,
  EnvelopeSimple,
  Bell,
  Translate,
  FloppyDisk,
  PaperPlaneTilt,
  Plus,
  Trash,
  User,
  PlugsConnected,
} from '@phosphor-icons/react';

import { useAuth } from '../context/AuthContext';
import { clientAPI } from '../api/client';
import api from '../api/axios';

import Card, { CardHeader, CardAction } from '../components/ui/Card';
import Button from '../components/ui/Button';
import ChannelsTab from '../components/settings/ChannelsTab';

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

const LANGS = [
  { value: 'en', label: 'English'    },
  { value: 'de', label: 'Deutsch'    },
  { value: 'fr', label: 'Français'   },
  { value: 'es', label: 'Español'    },
  { value: 'it', label: 'Italiano'   },
  { value: 'nl', label: 'Nederlands' },
  { value: 'da', label: 'Dansk'      },
  { value: 'uk', label: 'Українська' },
];

/* ─────────────── Page ─────────────── */

const SettingsPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState('profile');
  const [logoUrl, setLogoUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState({ type: null, text: '' });

  const [greetingMessage, setGreetingMessage] = useState('');
  const [notificationLanguage, setNotificationLanguage] = useState('en');

  const [reportEnabled, setReportEnabled] = useState(false);
  const [reportRecipients, setReportRecipients] = useState([]);
  const [reportEmail, setReportEmail] = useState('');
  const [reportSaving, setReportSaving] = useState(false);
  const [reportSending, setReportSending] = useState(false);

  const flash = (type, text) => {
    setStatus({ type, text });
    setTimeout(() => setStatus({ type: null, text: '' }), 3500);
  };

  /* ── Load ── */
  useEffect(() => {
    if (authLoading || !isAuthenticated) return;
    loadClient();
    loadReportSettings();
  }, [authLoading, isAuthenticated]);

  const loadClient = async () => {
    try {
      const { data } = await clientAPI.getMe();
      const raw = data?.logo_url || data?.logo;
      if (raw) {
        const base = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        setLogoUrl(raw.startsWith('/') ? `${base}${raw}` : raw);
      }
    } catch (e) {
      console.error('Failed to load client:', e);
    }
  };

  const loadReportSettings = async () => {
    try {
      const { data } = await api.get('/clients/email-smtp/config/');
      setReportEnabled(!!data?.email_report_enabled);
      setReportRecipients(Array.isArray(data?.email_report_recipients) ? data.email_report_recipients : []);
      setNotificationLanguage(data?.notification_language || 'en');
      setGreetingMessage(data?.greeting_message || '');
    } catch (e) {
      console.error('Failed to load report settings:', e);
    }
  };

  /* ── Logo ── */
  const handleLogoSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      flash('error', t('settings.logoInvalidType') || 'File must be an image');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      flash('error', t('settings.logoTooLarge') || 'File must be under 5 MB');
      return;
    }
    setUploading(true);
    try {
      const { data } = await clientAPI.uploadLogo(file);
      const raw = data?.logo_url;
      if (raw) {
        const base = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        setLogoUrl(raw.startsWith('/') ? `${base}${raw}` : raw);
      }
      flash('success', t('settings.logoUploaded') || 'Logo uploaded');
    } catch {
      flash('error', t('settings.logoUploadError') || 'Failed to upload logo');
    } finally {
      setUploading(false);
    }
  };

  const handleLogoDelete = async () => {
    if (!confirm(t('settings.deleteLogoConfirm') || 'Delete logo?')) return;
    setUploading(true);
    try {
      await clientAPI.deleteLogo();
      setLogoUrl(null);
      flash('success', t('settings.logoDeleted') || 'Logo deleted');
    } catch {
      flash('error', t('settings.logoDeleteError') || 'Failed to delete logo');
    } finally {
      setUploading(false);
    }
  };

  /* ── Greeting + settings save ── */
  const saveGeneralSettings = async () => {
    setReportSaving(true);
    try {
      await api.patch('/clients/email-smtp/config/', {
        email_report_enabled: reportEnabled,
        email_report_recipients: reportRecipients,
        notification_language: notificationLanguage,
        greeting_message: greetingMessage,
      });
      flash('success', t('settings.settingsSaved') || 'Settings saved');
    } catch {
      flash('error', t('settings.settingsSaveError') || 'Failed to save settings');
    } finally {
      setReportSaving(false);
    }
  };

  /* ── Report recipients ── */
  const addRecipient = () => {
    const email = reportEmail.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      flash('error', t('settings.reportInvalidEmail') || 'Invalid email');
      return;
    }
    if (reportRecipients.some((r) => r.toLowerCase() === email.toLowerCase())) {
      setReportEmail('');
      return;
    }
    if (reportRecipients.length >= 5) {
      flash('error', t('settings.reportMaxRecipients') || 'Max 5 recipients');
      return;
    }
    setReportRecipients((prev) => [...prev, email]);
    setReportEmail('');
  };

  const removeRecipient = (email) => {
    setReportRecipients((prev) => prev.filter((r) => r !== email));
  };

  const sendDailyReportNow = async () => {
    setReportSending(true);
    try {
      const { data } = await api.post('/clients/reports/daily-digest/send/', {});
      if (data?.success) flash('success', t('settings.reportScheduled') || 'Report scheduled');
      else flash('error', data?.error || t('common.error') || 'Failed');
    } catch {
      flash('error', t('settings.reportSendError') || 'Failed to send report');
    } finally {
      setReportSending(false);
    }
  };

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-full py-20">
        <p className="label-mono">{t('common.loading') || 'loading…'}</p>
      </div>
    );
  }

  const tabs = [
    { key: 'profile',  label: t('settings.tabProfile')  || 'Profile',  icon: User },
    { key: 'channels', label: t('settings.tabChannels') || 'Channels', icon: PlugsConnected },
  ];

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ── Header ── */}
      <div className="flex justify-between items-start mb-8 animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest">
            {t('settings.title') || 'Settings'}
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            {t('settings.headerSubtitle') || 'workspace · reports · channels'}
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex flex-wrap gap-2.5 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-sm border-[1.5px]
                        font-sans text-[13px] font-medium cursor-pointer transition-colors
                        ${activeTab === tab.key
                          ? 'border-iris text-ink bg-mist'
                          : 'border-rule text-slate hover:border-iris hover:text-ink'}`}
          >
            <tab.icon size={16} weight="light" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Status toast ── */}
      {status.type && (
        <div className={`mb-5 border-[1.5px] rounded-sm px-4 py-2.5 font-mono text-[12px] animate-fade-up
                        ${status.type === 'success' ? 'border-sage text-sage bg-sage-soft/30'
                                                    : 'border-rose text-rose bg-rose-soft/30'}`}>
          {status.text}
        </div>
      )}

      {/* ── Channels tab ── */}
      {activeTab === 'channels' && (
        <Card>
          <CardHeader title={t('settings.channelControl') || 'Channel Control'} />
          <ChannelsTab />
        </Card>
      )}

      {/* ── Profile tab ── */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Logo */}
          <Card accent="iris" className="lg:col-span-1">
            <CardHeader title={t('settings.workspaceLogo') || 'Workspace Logo'} />
            <div className="flex flex-col items-center gap-4 py-2">
              <div className={`w-28 h-28 rounded-md border-2 ${ACCENT_BORDER.iris}
                              flex items-center justify-center overflow-hidden bg-cream`}>
                {logoUrl ? (
                  <img src={logoUrl} alt={t('settings.workspaceLogo') || 'Workspace logo'} className="w-full h-full object-contain p-2" />
                ) : (
                  <ImageIcon size={36} weight="light" />
                )}
              </div>
              <p className="font-mono text-[11px] text-fog text-center">
                {t('settings.logoHint') || 'PNG / SVG · ≤ 5 MB · used in QR, chat header, reports'}
              </p>
              <div className="flex gap-2.5 w-full">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleLogoSelect}
                  className="hidden"
                  id="logo-input"
                  disabled={uploading}
                />
                <label htmlFor="logo-input" className="flex-1">
                  <Button variant="violet" icon={Upload} className="w-full justify-center">
                    {uploading
                      ? (t('settings.uploading') || 'Uploading…')
                      : logoUrl
                        ? (t('settings.replace') || 'Replace')
                        : (t('settings.upload')  || 'Upload')}
                  </Button>
                </label>
                {logoUrl && !uploading && (
                  <Button variant="pink" icon={X} onClick={handleLogoDelete}>
                    {t('settings.remove') || 'Remove'}
                  </Button>
                )}
              </div>
            </div>
          </Card>

          {/* Greeting */}
          <Card accent="sage" className="lg:col-span-2">
            <CardHeader
              title={t('settings.greetingTitle') || 'Greeting Message'}
              action={<span className="label-mono">{greetingMessage.length}/500</span>}
            />
            <p className="text-[12px] text-fog mb-3">
              {t('settings.greetingHint') || 'Shown to customers when they first open a chat. Keep it warm and short.'}
            </p>
            <textarea
              value={greetingMessage}
              onChange={(e) => setGreetingMessage(e.target.value)}
              placeholder={t('settings.greetingPlaceholder') || 'Hello! How can I help you today?'}
              maxLength={500}
              className="w-full h-32 p-3 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink resize-y focus:outline-none focus:border-sage transition-colors"
            />
            <div className="flex justify-end mt-4">
              <Button variant="green" icon={FloppyDisk} onClick={saveGeneralSettings}>
                {reportSaving ? (t('common.saving') || 'Saving…') : (t('common.save') || 'Save')}
              </Button>
            </div>
          </Card>

          {/* Notification language */}
          <Card accent="amber" className="lg:col-span-1">
            <CardHeader title={t('settings.notificationLanguageLabel') || 'Notification Language'} />
            <p className="text-[12px] text-fog mb-3 leading-relaxed">
              {t('settings.notificationLanguageDescription') || "Reports, manager alerts and email notifications. Customer replies still use each visitor's language."}
            </p>
            <div className="relative">
              <Translate size={16} weight="light" className="absolute left-3 top-1/2 -translate-y-1/2 text-amber pointer-events-none" />
              <select
                value={notificationLanguage}
                onChange={(e) => setNotificationLanguage(e.target.value)}
                className="w-full pl-9 pr-3 py-2.5 bg-cream border-[1.5px] border-rule rounded-sm
                           font-sans text-[13px] text-ink cursor-pointer
                           focus:outline-none focus:border-amber transition-colors appearance-none"
              >
                {LANGS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end mt-4">
              <Button variant="green" icon={FloppyDisk} onClick={saveGeneralSettings}>
                Save
              </Button>
            </div>
          </Card>

          {/* Daily reports */}
          <Card accent="rose" className="lg:col-span-2">
            <CardHeader
              title={t('settings.reportSettingsTitle') || 'Daily Reports'}
              action={
                <CardAction onClick={sendDailyReportNow}>
                  {reportSending
                    ? (t('settings.sendingShort') || 'sending…')
                    : (t('settings.sendNowShort') || 'send now')}
                </CardAction>
              }
            />

            <label className="flex items-center gap-3 mb-4 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={reportEnabled}
                onChange={(e) => setReportEnabled(e.target.checked)}
                className="w-4 h-4 accent-rose cursor-pointer"
              />
              <Bell size={16} weight="light" className="text-rose" />
              <span className="text-[13px] font-medium text-ink">
                {t('settings.reportEnabledLabel') || 'Enable daily digest email'}
              </span>
            </label>

            <div className="mb-4">
              <div className="label-mono mb-1.5">
                {t('settings.reportRecipientsLabel') || 'Recipients (up to 5)'}
              </div>
              <div className="flex gap-2">
                <input
                  type="email"
                  value={reportEmail}
                  onChange={(e) => setReportEmail(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRecipient(); } }}
                  placeholder={t('settings.reportEmailPlaceholder') || 'team@company.com'}
                  className="flex-1 px-3 py-2 bg-cream border-[1.5px] border-rule rounded-sm
                             font-mono text-[12px] text-ink focus:outline-none focus:border-rose transition-colors"
                />
                <Button variant="violet" icon={Plus} onClick={addRecipient}>
                  {t('settings.reportAdd') || 'Add'}
                </Button>
              </div>
            </div>

            {reportRecipients.length > 0 ? (
              <div className="divide-y divide-rule border-[1.5px] border-rule rounded-sm">
                {reportRecipients.map((email) => (
                  <div key={email} className="flex items-center justify-between gap-3 px-3 py-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <EnvelopeSimple size={14} weight="light" className="text-fog shrink-0" />
                      <span className="font-mono text-[12px] text-ink truncate">{email}</span>
                    </div>
                    <button
                      onClick={() => removeRecipient(email)}
                      className="text-fog hover:text-rose transition-colors cursor-pointer p-1"
                      aria-label={t('settings.reportRemove') || 'Remove recipient'}
                    >
                      <Trash size={14} weight="light" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="label-mono text-center py-4">
                {t('settings.reportNoRecipients') || 'no recipients yet'}
              </p>
            )}

            <div className="flex justify-end gap-2.5 mt-4 pt-4 border-t border-rule">
              <Button variant="pink" icon={PaperPlaneTilt} onClick={sendDailyReportNow}>
                {reportSending
                  ? (t('settings.reportSending') || 'Sending…')
                  : (t('settings.reportSendNow') || 'Send Now')}
              </Button>
              <Button variant="green" icon={FloppyDisk} onClick={saveGeneralSettings}>
                {reportSaving
                  ? (t('common.saving') || 'Saving…')
                  : (t('common.save')   || 'Save')}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
