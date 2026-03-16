import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { Upload, X, Loader2 } from 'lucide-react';
import { clientAPI } from '../api/client';
import api from '../api/axios';

const SettingsPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [logo, setLogo] = useState(null);
  const [logoUrl, setLogoUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [reportEnabled, setReportEnabled] = useState(false);
  const [reportRecipients, setReportRecipients] = useState([]);
  const [reportEmail, setReportEmail] = useState('');
  const [reportSaving, setReportSaving] = useState(false);
  const [reportSending, setReportSending] = useState(false);
  const [reportMessage, setReportMessage] = useState('');
  const [notificationLanguage, setNotificationLanguage] = useState('en');
  const [greetingMessage, setGreetingMessage] = useState('');

  // Notification language options
  const notificationLanguageOptions = [
    { value: 'en', label: 'English', flag: '🇬🇧' },
    { value: 'de', label: 'Deutsch', flag: '🇩🇪' },
    { value: 'fr', label: 'Français', flag: '🇫🇷' },
    { value: 'es', label: 'Español', flag: '🇪🇸' },
    { value: 'it', label: 'Italiano', flag: '🇮🇹' },
    { value: 'nl', label: 'Nederlands', flag: '🇳🇱' },
    { value: 'da', label: 'Dansk', flag: '🇩🇰' },
    { value: 'uk', label: 'Українська', flag: '🇺🇦' },
  ];

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!isAuthenticated) {
      return;
    }

    const timer = setTimeout(() => {
      if (!dataLoaded) {
        loadClientLogo();
        loadReportSettings();
        setDataLoaded(true);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [authLoading, isAuthenticated, dataLoaded]);

  const loadClientLogo = async () => {
    try {
      const response = await clientAPI.getMe();
      const logoUrlFromAPI = response.data?.logo_url || response.data?.logo;
      if (logoUrlFromAPI) {
        if (logoUrlFromAPI.startsWith('/')) {
          const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          setLogoUrl(`${baseURL}${logoUrlFromAPI}`);
        } else {
          setLogoUrl(logoUrlFromAPI);
        }
      }
    } catch (err) {
      console.error('Failed to load client logo:', err);
    }
  };

  const loadReportSettings = async () => {
    try {
      const res = await api.get('/clients/email-smtp/config/');
      setReportEnabled(!!res.data?.email_report_enabled);
      const recipients = res.data?.email_report_recipients;
      setReportRecipients(Array.isArray(recipients) ? recipients : []);
      setNotificationLanguage(res.data?.notification_language || 'en');
      setGreetingMessage(res.data?.greeting_message || '');
    } catch (err) {
      // Silent: report settings are optional
      console.error('Failed to load report settings:', err);
    }
  };

  const handleLogoSelect = async (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        setError(t('settings.logoInvalidType') || 'File must be an image');
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        setError(t('settings.logoTooLarge') || 'File size must be less than 5MB');
        return;
      }

      setError(null);
      setLogo(file);

      const reader = new FileReader();
      reader.onloadend = () => {
        setLogoUrl(reader.result);
      };
      reader.readAsDataURL(file);

      // Автоматично завантажуємо фото одразу без додаткової кнопки
      await handleLogoUpload(file);
    }
  };

  const handleLogoUpload = async (fileToUpload = null) => {
    const file = fileToUpload || logo;
    if (!file) return;

    setUploading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await clientAPI.uploadLogo(file);
      const uploadedLogoUrl = response.data?.logo_url;
      
      if (uploadedLogoUrl) {
        if (uploadedLogoUrl.startsWith('/')) {
          const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          setLogoUrl(`${baseURL}${uploadedLogoUrl}`);
        } else {
          setLogoUrl(uploadedLogoUrl);
        }
      }
      
      setSuccess(true);
      setLogo(null);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to upload logo:', err);
      setError(t('settings.logoUploadError') || 'Failed to upload logo');
      // Якщо помилка, залишаємо файл для повторної спроби
      if (!fileToUpload) {
        setLogo(file);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleLogoDelete = async () => {
    if (!confirm(t('settings.deleteLogoConfirm') || 'Are you sure you want to delete the logo?')) {
      return;
    }

    setUploading(true);
    setError(null);

    try {
      await clientAPI.deleteLogo();
      setLogoUrl(null);
      setLogo(null);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to delete logo:', err);
      setError(t('settings.logoDeleteError') || 'Failed to delete logo');
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = () => {
    setLogo(null);
    setError(null);
    loadClientLogo();
  };

  const isValidEmail = (value) => {
    const v = (value || '').trim();
    if (!v) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  };

  const addReportRecipient = () => {
    setReportMessage('');
    const email = reportEmail.trim();

    if (!isValidEmail(email)) {
      setReportMessage(t('settings.reportInvalidEmail') || 'Invalid email address');
      return;
    }

    const exists = reportRecipients.some((r) => String(r).toLowerCase() === email.toLowerCase());
    if (exists) {
      setReportEmail('');
      return;
    }

    if (reportRecipients.length >= 5) {
      setReportMessage(t('settings.reportMaxRecipients') || 'You can add up to 5 recipients');
      return;
    }

    setReportRecipients((prev) => [...prev, email]);
    setReportEmail('');
  };

  const removeReportRecipient = (email) => {
    setReportRecipients((prev) => prev.filter((r) => r !== email));
  };

  const saveReportSettings = async () => {
    try {
      setReportSaving(true);
      setReportMessage('');

      await api.patch('/clients/email-smtp/config/', {
        email_report_enabled: reportEnabled,
        email_report_recipients: reportRecipients,
        notification_language: notificationLanguage,
        greeting_message: greetingMessage,
      });

      setReportMessage(t('settings.reportSaved') || t('common.success') || 'Saved');
    } catch (err) {
      console.error('Failed to save report settings:', err);
      setReportMessage(t('settings.reportSaveError') || t('common.error') || 'Error');
    } finally {
      setReportSaving(false);
    }
  };

  const sendDailyReportNow = async () => {
    try {
      setReportSending(true);
      setReportMessage('');
      const res = await api.post('/clients/reports/daily-digest/send/', {});
      if (res.data?.success) {
        setReportMessage(t('settings.reportScheduled') || 'Daily report scheduled');
      } else {
        setReportMessage(res.data?.error || t('common.error') || 'Error');
      }
    } catch (err) {
      console.error('Failed to send daily report:', err);
      setReportMessage(t('settings.reportSendError') || t('common.error') || 'Error');
    } finally {
      setReportSending(false);
    }
  };

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 dark:text-primary-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">{t('common.loading') || 'Loading...'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('settings.title') || 'Settings'}</h1>
        <p className="text-gray-600 dark:text-gray-400">{t('settings.subtitle') || 'Manage your account settings'}</p>
      </div>

      {/* Logo Upload Section */}
      <div className="max-w-2xl">
        <div className="card">
          <div className="mb-6">
            <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100">{t('settings.uploadLogo') || 'Upload Logo'}</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              {t('settings.logoDescription') || 'Upload your company logo. It will be used in QR code generation.'}
            </p>
          </div>

        <div className="space-y-4">
          {/* Current Logo Preview */}
          {logoUrl && (
            <div className="relative inline-block">
              <img
                src={logoUrl}
                alt="Company Logo"
                className="max-w-xs max-h-32 object-contain border border-gray-200 dark:border-gray-700 rounded-lg p-2 bg-white dark:bg-gray-700"
              />
              {logo && (
                <button
                  onClick={handleCancel}
                  className="absolute -top-2 -right-2 bg-red-500 dark:bg-red-600 text-white rounded-full p-1 hover:bg-red-600 dark:hover:bg-red-700 transition"
                  title={t('common.cancel') || 'Cancel'}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          )}

          {/* Error/Success Messages */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded text-red-700 dark:text-red-400 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="p-3 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded text-green-700 dark:text-green-400 text-sm">
              {t('settings.logoUploadSuccess') || 'Logo uploaded successfully! QR codes will be regenerated with the new logo.'}
            </div>
          )}

          {/* Upload Controls */}
          <div className="flex items-center gap-3">
            <input
              type="file"
              accept="image/*"
              onChange={handleLogoSelect}
              className="hidden"
              id="logo-input"
              disabled={uploading}
            />
            <label
              htmlFor="logo-input"
              className={`btn-secondary flex items-center gap-2 cursor-pointer ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {uploading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  {t('settings.uploading') || 'Uploading...'}
                </>
              ) : (
                <>
                  <Upload size={16} />
                  {logoUrl ? t('settings.changeLogo') : t('settings.selectLogo')}
                </>
              )}
            </label>

            {logoUrl && !uploading && (
              <button
                onClick={handleLogoDelete}
                disabled={uploading}
                className="btn-danger flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <X size={16} />
                {t('settings.deleteLogo') || 'Delete Logo'}
              </button>
            )}
          </div>

          {/* Info about QR codes */}
          {logoUrl && (
            <div className="text-xs text-gray-500 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded p-2">
              {t('settings.logoQRInfo') || 'Your logo will be used in all QR code generations. Existing QR codes will be regenerated automatically.'}
            </div>
          )}
        </div>
        </div>
      </div>

      {/* Greeting Message Section */}
      <div className="max-w-2xl">
        <div className="card">
          <div className="mb-6">
            <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100">
              {t('settings.greetingTitle') || 'Greeting Message'}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              {t('settings.greetingDescription') || 'This message is shown to customers when they first open the chat or contact you via Telegram/WhatsApp. It will be displayed exactly as written.'}
            </p>
          </div>
          <div className="space-y-4">
            <textarea
              value={greetingMessage}
              onChange={(e) => setGreetingMessage(e.target.value)}
              placeholder={t('settings.greetingPlaceholder') || 'Hello! How can I help you today?'}
              className="input w-full h-24 resize-y"
              maxLength={500}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {greetingMessage.length}/500
              </span>
              <button
                onClick={saveReportSettings}
                disabled={reportSaving}
                className="btn-primary flex items-center justify-center gap-2"
              >
                {reportSaving ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    {t('common.loading') || 'Saving...'}
                  </>
                ) : (
                  t('common.save') || 'Save'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Report Settings Section */}
      <div className="max-w-2xl">
        <div className="card">
          <div className="mb-6">
            <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100">
              {t('settings.reportSettingsTitle') || 'Report settings'}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              {t('settings.reportSettingsSubtitle') || 'Configure recipients and send the daily report manually.'}
            </p>
          </div>

          <div className="space-y-4">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={reportEnabled}
                onChange={(e) => setReportEnabled(e.target.checked)}
                className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
              />
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {t('settings.reportEnabledLabel') || 'Enable daily reports'}
              </span>
            </label>

            {/* Notification Language Selector */}
            <div>
              <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                {t('settings.notificationLanguageLabel') || 'Notification Language'}
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                {t('settings.notificationLanguageDescription') || 'Language for daily reports, email notifications, and manager messages. Customer chat responses use the customer\'s language.'}
              </p>
              <select
                value={notificationLanguage}
                onChange={(e) => setNotificationLanguage(e.target.value)}
                className="input w-full max-w-xs"
              >
                {notificationLanguageOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.flag} {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                {t('settings.reportRecipientsLabel') || 'Recipients (up to 5 emails)'}
              </label>
              <div className="flex gap-3">
                <input
                  type="email"
                  value={reportEmail}
                  onChange={(e) => setReportEmail(e.target.value)}
                  placeholder={t('settings.reportEmailPlaceholder') || 'email@example.com'}
                  className="input flex-1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addReportRecipient();
                    }
                  }}
                />
                <button onClick={addReportRecipient} className="btn-secondary">
                  {t('settings.reportAdd') || t('common.create') || 'Add'}
                </button>
              </div>
            </div>

            {reportRecipients?.length ? (
              <div className="space-y-2">
                {reportRecipients.map((email) => (
                  <div
                    key={email}
                    className="flex items-center justify-between gap-3 bg-gray-50 dark:bg-gray-800/40 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2"
                  >
                    <div className="text-sm font-mono text-gray-900 dark:text-gray-100">{email}</div>
                    <button
                      onClick={() => removeReportRecipient(email)}
                      className="btn-danger"
                    >
                      {t('settings.reportRemove') || t('common.delete') || 'Remove'}
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {t('settings.reportNoRecipients') || 'No recipients added yet.'}
              </div>
            )}

            {reportMessage && (
              <div className="p-3 bg-gray-50 dark:bg-gray-800/40 border border-gray-200 dark:border-gray-700 rounded text-gray-800 dark:text-gray-200 text-sm">
                {reportMessage}
              </div>
            )}

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                onClick={saveReportSettings}
                disabled={reportSaving}
                className="btn-primary flex items-center justify-center gap-2"
              >
                {reportSaving ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    {t('settings.reportSaving') || t('common.loading') || 'Saving...'}
                  </>
                ) : (
                  t('settings.reportSave') || t('common.save') || 'Save'
                )}
              </button>

              <button
                onClick={sendDailyReportNow}
                disabled={reportSending}
                className="btn-secondary flex items-center justify-center gap-2"
              >
                {reportSending ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    {t('settings.reportSending') || t('common.loading') || 'Sending...'}
                  </>
                ) : (
                  t('settings.reportSendNow') || 'Send daily report now'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;

