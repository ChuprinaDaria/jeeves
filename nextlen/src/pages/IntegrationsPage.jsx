import { useEffect, useState, useCallback } from 'react';
import api from '../api/axios';
import { useTranslation } from 'react-i18next';
import { X, Loader2 } from 'lucide-react';
import { clientAPI } from '../api/client';
import WebWidgetSetup from '../components/integrations/WebWidgetSetup';
import EmailSetup from '../components/integrations/EmailSetup';
import TelegramSetup from '../components/integrations/TelegramSetup';
import ChromeExtensionSetup from '../components/integrations/ChromeExtensionSetup';
import HITLSetup from '../components/integrations/HITLSetup';
import WhatsAppSetup from '../components/integrations/WhatsAppSetup';

const IntegrationsPage = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [showWhatsAppModal, setShowWhatsAppModal] = useState(false);
  const [whatsappBridgeConfig, setWhatsappBridgeConfig] = useState({
    whatsapp_bridge_enabled: false,
    whatsapp_bridge_status: 'disconnected',
    whatsapp_bridge_phone: '',
    globally_enabled: true,
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [webQRCode, setWebQRCode] = useState(null);
  const [loadingWebQR, setLoadingWebQR] = useState(false);
  const [showWebModal, setShowWebModal] = useState(false);
  const [showWebWidgetModal, setShowWebWidgetModal] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showTelegramModal, setShowTelegramModal] = useState(false);
  const [showChromeExtensionModal, setShowChromeExtensionModal] = useState(false);
  const [showHITLModal, setShowHITLModal] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [hitlEnabled, setHitlEnabled] = useState(false);
  const [clientType, setClientType] = useState(null);
  const [clientInfo, setClientInfo] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      api.get('/clients/whatsapp/bridge/config/').catch(() => ({ data: { whatsapp_bridge_enabled: false, whatsapp_bridge_status: 'disconnected', whatsapp_bridge_phone: '', globally_enabled: true } })),
      api.get('/clients/me/'),
      api.get('/clients/email-smtp/config/').catch(() => ({ data: { email_smtp_enabled: false } })),
      api.get('/clients/telegram/config/').catch(() => ({ data: { telegram_enabled: false } })),
      api.get('/clients/hitl/config/').catch(() => ({ data: { hitl_enabled: false } }))
    ])
      .then(([whatsappRes, clientRes, emailRes, telegramRes, hitlRes]) => {
        if (!mounted) return;
        setWhatsappBridgeConfig(prev => ({ ...prev, ...whatsappRes.data }));
        setClientType(clientRes.data?.client_type || null);
        setClientInfo(clientRes.data);
        setEmailEnabled(emailRes.data?.email_smtp_enabled || false);
        setTelegramEnabled(telegramRes.data?.telegram_enabled || false);
        setHitlEnabled(hitlRes.data?.hitl_enabled || false);
      })
      .catch(() => {})
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  // Завантажити або створити QR код для Web чату
  const loadOrCreateWebQR = useCallback(async (regenerate = false) => {
    setLoadingWebQR(true);
    try {
      const existingQRCodes = await clientAPI.getQRCodes();
      const qrCodes = existingQRCodes.data || [];
      
      // Отримуємо client_tag для формування URL
      // 1) спершу з /clients/me/ (актуальний клієнт у порталі)
      // 2) якщо немає - з localStorage (старий fallback)
      const storedTag = localStorage.getItem('client_tag');
      let clientTag = clientInfo?.tag || storedTag;
      
      // Якщо tag з бекенду відрізняється від збереженого — синхронізуємо localStorage,
      // щоб уникнути ситуації, коли QR/лінк йде на "старого" клієнта (наприклад, Change Client).
      if (clientInfo?.tag && storedTag !== clientInfo.tag) {
        localStorage.setItem('client_tag', clientInfo.tag);
        clientTag = clientInfo.tag;
      }
      if (!clientTag) {
        console.error('Client tag not found (neither in localStorage nor in /clients/me/ response)');
        setLoadingWebQR(false);
        return;
      }
      
      // Формуємо URL для Web чату
      // Для white label клієнтів використовуємо webchat_domain, інакше window.location.origin
      let baseUrl = window.location.origin;
      if (clientInfo?.webchat_domain) {
        const customDomain = clientInfo.webchat_domain.trim();
        try {
          // Дозволяємо як повний URL (https://ai.bytekraft.net/...) так і просто домен (ai.bytekraft.net)
          const url = customDomain.startsWith('http://') || customDomain.startsWith('https://')
            ? new URL(customDomain)
            : new URL(`https://${customDomain}`);
          // Використовуємо тільки origin (scheme + host), ігноруємо шлях та query
          baseUrl = url.origin;
        } catch (e) {
          console.error('Invalid webchat_domain, falling back to https:// + value:', e);
          // Фолбек: прибираємо кінцевий слеш
          baseUrl = (customDomain.startsWith('http://') || customDomain.startsWith('https://'))
            ? customDomain.replace(/\/$/, '')
            : `https://${customDomain.split('/')[0]}`.replace(/\/$/, '');
        }
      }
      const webChatUrl = `${baseUrl}/client?tag=${clientTag}`;
      
      console.log('White Label Web Chat URL:', webChatUrl, 'webchat_domain:', clientInfo?.webchat_domain);
      
      // Шукаємо QR код для Web Integration (за назвою або типом інтеграції)
      let webQR = qrCodes.find(qr => 
        qr.name === 'Web Chat Integration' || qr.integration_type === 'web'
      );
      
      if (!webQR) {
        if (qrCodes.length >= 10) {
          console.warn('Maximum 10 QR codes allowed per client');
          setLoadingWebQR(false);
          return;
        }
        
        // Створюємо новий QR код для Web Integration
        const qrData = {
          name: 'Web Chat Integration',
          description: 'QR code for Web chat integration - B2C client chat',
          location: webChatUrl,
          integration_type: 'web',
          is_active: true,
        };
        
        console.log('Creating new Web QR code with data:', qrData);
        const response = await clientAPI.createQRCode(qrData);
        webQR = response.data;
        
        if (!webQR.qr_code_url_display && !webQR.qr_code) {
          setTimeout(async () => {
            try {
              const updatedQRCodes = await clientAPI.getQRCodes();
              const updatedQR = updatedQRCodes.data?.find(qr => qr.id === webQR.id);
              if (updatedQR?.qr_code_url_display) {
                setWebQRCode(updatedQR.qr_code_url_display);
              }
            } catch (err) {
              console.error('Failed to reload QR code:', err);
            }
          }, 1000);
        }
      } else {
        // Існуючий QR-код
        // Якщо це ручний регенераційний виклик або старий QR з неправильним типом інтеграції,
        // оновлюємо integration_type на 'web' і location на актуальний webChatUrl,
        // щоб примусово перегенерувати QR під веб-чат.
        // Перевіряємо чи URL правильний (може бути з custom domain для white label)
        const currentBaseUrl = clientInfo?.webchat_domain 
          ? (clientInfo.webchat_domain.startsWith('http') 
              ? clientInfo.webchat_domain.replace(/\/$/, '')
              : `https://${clientInfo.webchat_domain.replace(/\/$/, '')}`)
          : window.location.origin;
        const expectedUrlPattern = `${currentBaseUrl}/client?tag=${clientTag}`;
        
        console.log('Existing QR code found:', webQR.location, 'expected:', expectedUrlPattern);
        
        // Завжди перевіряємо, чи location відповідає очікуваному URL (з webchat_domain для white label)
        const needsFix =
          regenerate ||
          webQR.integration_type !== 'web' ||
          webQR.location !== webChatUrl; // Суворіша перевірка на точну відповідність

        if (needsFix && webQR.id) {
          const baseLocation = webChatUrl;
          const currentLocation = webQR.location || baseLocation;
          const newLocation = regenerate
            ? (currentLocation !== baseLocation ? baseLocation : `${baseLocation}?updated=${Date.now()}`)
            : baseLocation;

          console.log('Updating QR code location from', webQR.location, 'to', newLocation);
          
          await clientAPI.updateQRCode(webQR.id, {
            name: webQR.name || 'Web Chat Integration',
            description: webQR.description || 'QR code for Web chat integration - B2C client chat',
            location: newLocation,
            integration_type: 'web',
            is_active: webQR.is_active,
          });

          setTimeout(async () => {
            try {
              const updatedQRCodes = await clientAPI.getQRCodes();
              const updatedQR = updatedQRCodes.data?.find(qr => qr.id === webQR.id);
              if (updatedQR?.qr_code_url_display) {
                setWebQRCode(updatedQR.qr_code_url_display);
              } else if (updatedQR?.qr_code) {
                setWebQRCode(updatedQR.qr_code);
              }
            } catch (err) {
              console.error('Failed to reload regenerated QR code:', err);
            }
          }, 1000);
        }
      }
      
      if (webQR.qr_code_url_display) {
        setWebQRCode(webQR.qr_code_url_display);
      } else if (webQR.qr_code) {
        setWebQRCode(webQR.qr_code);
      }
    } catch (error) {
      console.error('Failed to load/create Web QR code:', error);
    } finally {
      setLoadingWebQR(false);
    }
  }, [clientInfo]);

  useEffect(() => {
    if (showWebModal && clientInfo) {
      loadOrCreateWebQR();
    }
  }, [showWebModal, clientInfo, loadOrCreateWebQR]);

  const reloadWhatsAppBridgeConfig = () => {
    api.get('/clients/whatsapp/bridge/config/')
      .then(res => setWhatsappBridgeConfig(prev => ({ ...prev, ...res.data })))
      .catch(() => {});
  };

  const extensionEnabled = clientInfo?.extension_enabled || false;
  const extensionDownloadUrl =
    import.meta.env.VITE_EXTENSION_DOWNLOAD_URL ||
    'https://app.nexelin.com/static/extensions/nexelin-chrome-extension.zip';

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-2 text-gray-900 dark:text-gray-100">{t('integrations.title')}</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">{t('integrations.subtitle')}</p>

      {/* Integration Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl">
        
        {/* Web Chat Card - Available for all clients */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Web Chat</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">B2C client chat interface</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
              {t('integrations.connected')}
            </span>
          </div>
          
          <button
            onClick={() => setShowWebModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* WhatsApp Card */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-green-600 dark:text-green-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">{t('integrations.whatsappBridge') || t('integrations.whatsapp')}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('integrations.whatsappBridgeDesc') || t('integrations.whatsappDesc')}</p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${whatsappBridgeConfig.whatsapp_bridge_status === 'connected' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}`}>
              {whatsappBridgeConfig.whatsapp_bridge_status === 'connected' ? t('integrations.connected') : t('integrations.notConnected')}
            </span>
            {whatsappBridgeConfig.whatsapp_bridge_status === 'connected' && whatsappBridgeConfig.whatsapp_bridge_phone && (
              <span className="text-xs text-gray-500 dark:text-gray-400">{whatsappBridgeConfig.whatsapp_bridge_phone}</span>
            )}
          </div>
          
          <button
            onClick={() => setShowWhatsAppModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* Web Widget - Only for white label clients */}
        {clientType === 'white_label' && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center">
                  <svg className="w-7 h-7 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Web Widget</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Embed chat on your website</p>
                </div>
              </div>
            </div>
            
            <div className="flex items-center justify-between mb-4">
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                {t('integrations.notConnected')}
              </span>
            </div>
            
            <button
              onClick={() => setShowWebWidgetModal(true)}
              className="w-full btn-primary"
            >
              {t('integrations.setup')}
            </button>
          </div>
        )}

        {/* Telegram */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.053 5.56-5.023c.242-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">{t('integrations.telegram')}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Connect to Telegram Bot</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              telegramEnabled
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}>
              {telegramEnabled ? t('integrations.connected') : t('integrations.notConnected')}
            </span>
          </div>
          
          <button
            onClick={() => setShowTelegramModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* Google Calendar (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 opacity-60 hover:opacity-70 transition-opacity">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-red-600 dark:text-red-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM9 14H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2zm-8 4H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Google Calendar</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Sync appointments & bookings</p>
              </div>
            </div>
          </div>
          
          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* Email */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Email</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Connect email via SMTP</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              emailEnabled
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}>
              {emailEnabled ? t('integrations.connected') : t('integrations.notConnected')}
            </span>
          </div>
          
          <button
            onClick={() => setShowEmailModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* Human-in-the-Loop (HITL) - Manager Escalation */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">HITL (Manager)</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Escalate to human managers via Telegram</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              hitlEnabled
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}>
              {hitlEnabled ? t('integrations.connected') : t('integrations.notConnected')}
            </span>
          </div>
          
          <button
            onClick={() => setShowHITLModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* Google Reviews (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 opacity-60 hover:opacity-70 transition-opacity">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-yellow-600 dark:text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Google Reviews</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Monitor & respond to reviews</p>
              </div>
            </div>
          </div>
          
          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* Facebook Messenger */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-[#1877F2]" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Facebook Messenger</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Bridge Facebook Messenger conversations</p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between mb-4">
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
              {t('integrations.notConnected')}
            </span>
            <span className="text-xs text-gray-400">via Chrome Extension</span>
          </div>

          <button
            onClick={() => setShowChromeExtensionModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* Instagram DM */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-pink-100 dark:bg-pink-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-[#E4405F]" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Instagram DM</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Connect Instagram Direct Messages</p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between mb-4">
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
              {t('integrations.notConnected')}
            </span>
            <span className="text-xs text-gray-400">via Chrome Extension</span>
          </div>

          <button
            onClick={() => setShowChromeExtensionModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* LinkedIn Messages */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-[#0A66C2]" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">LinkedIn Messages</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Bridge LinkedIn Messages for lead generation</p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between mb-4">
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
              {t('integrations.notConnected')}
            </span>
            <span className="text-xs text-gray-400">via Chrome Extension</span>
          </div>

          <button
            onClick={() => setShowChromeExtensionModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* Google Chrome Extension */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-sky-100 dark:bg-sky-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-sky-600 dark:text-sky-400" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 2a10 10 0 00-9.32 6.41h7.04A3.5 3.5 0 0113.5 12c0 .6-.15 1.16-.41 1.65l3.5 6.06A10 10 0 0012 2z"
                    fill="currentColor"
                    opacity="0.8"
                  />
                  <path
                    d="M4.22 8.41A10 10 0 0011 22a9.96 9.96 0 006.57-2.49l-3.5-6.06A3.5 3.5 0 017.72 8.41H4.22z"
                    fill="currentColor"
                    opacity="0.5"
                  />
                  <circle cx="12" cy="12" r="2.5" fill="white" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">
                  Google Chrome Extension
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Web AI Agent for browsing & automation. Scrape pages into Knowledge Blocks and collect contact data.
                </p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              extensionEnabled
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}>
              {extensionEnabled ? t('integrations.connected') : t('integrations.notConnected')}
            </span>
          </div>
          
          <button
            onClick={() => setShowChromeExtensionModal(true)}
            className="w-full btn-primary"
          >
            {t('integrations.configure')}
          </button>
        </div>

        {/* AI Video Avatar (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 opacity-80 hover:opacity-100 hover:border-gray-400 dark:hover:border-gray-500 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-violet-100 dark:bg-violet-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-violet-600 dark:text-violet-400" viewBox="0 0 24 24" fill="none">
                  <rect x="4" y="4" width="16" height="12" rx="2" ry="2" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M10 9l4 3-4 3V9z" fill="currentColor" />
                  <circle cx="8" cy="17.5" r="1" fill="currentColor" />
                  <circle cx="16" cy="17.5" r="1" fill="currentColor" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">
                  AI Video Avatar
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Personalized video avatar & cloning
                </p>
              </div>
            </div>
          </div>

          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* Voice AI – Phone RAG (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 opacity-80 hover:opacity-100 hover:border-gray-400 dark:hover:border-gray-500 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-emerald-600 dark:text-emerald-400" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M6.62 5.11l2.2-.73a1 1 0 011.17.45l1.2 2.07a1 1 0 01-.18 1.19l-1.01 1.01a10.05 10.05 0 005.01 5.01l1.01-1.01a1 1 0 011.19-.18l2.07 1.2a1 1 0 01.45 1.17l-.73 2.2A1.5 1.5 0 0117.5 20C10.6 20 5 14.4 5 7.5a1.5 1.5 0 011.62-1.39z"
                    fill="currentColor"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">
                  Voice AI – Phone RAG
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Connect AI voice assistant to telephony
                </p>
              </div>
            </div>
          </div>

          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* Make.com (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 opacity-80 hover:opacity-100 hover:border-gray-400 dark:hover:border-gray-500 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg flex items-center justify-center">
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-lg">M</span>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">
                  Make.com
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No‑code automation scenarios with Nexelin
                </p>
              </div>
            </div>
          </div>

          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* n8n (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 opacity-80 hover:opacity-100 hover:border-gray-400 dark:hover:border-gray-500 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-orange-100 dark:bg-orange-900/30 rounded-lg flex items-center justify-center">
                <span className="text-orange-600 dark:text-orange-400 font-semibold text-lg">n8n</span>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">
                  n8n
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Self‑hosted workflow automation with Nexelin
                </p>
              </div>
            </div>
          </div>

          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* Custom API (Coming Soon) */}
        <div className="bg-white dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 opacity-80 hover:opacity-100 hover:border-gray-400 dark:hover:border-gray-500 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-slate-100 dark:bg-slate-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-slate-600 dark:text-slate-300" viewBox="0 0 24 24" fill="none">
                  <rect x="4" y="4" width="16" height="4" rx="1" fill="currentColor" opacity="0.8" />
                  <rect x="4" y="10" width="10" height="4" rx="1" fill="currentColor" opacity="0.6" />
                  <rect x="4" y="16" width="7" height="4" rx="1" fill="currentColor" opacity="0.4" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">
                  Custom API
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Direct API integration with your stack
                </p>
              </div>
            </div>
          </div>

          <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* iOS / Android App (Highlighted Coming Soon) */}
        <div className="relative bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 rounded-2xl p-[1px] shadow-xl col-span-1 md:col-span-2 lg:col-span-3">
          <div className="bg-white dark:bg-gray-900 rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg">
                <svg className="w-9 h-9 text-white" viewBox="0 0 24 24" fill="none">
                  <rect x="6" y="2" width="7" height="20" rx="2" stroke="currentColor" strokeWidth="1.6" />
                  <rect x="13" y="4" width="5" height="16" rx="2" fill="currentColor" opacity="0.9" />
                  <circle cx="9.5" cy="18" r="0.9" fill="currentColor" />
                </svg>
              </div>
              <div>
                <div className="inline-flex items-center gap-2 mb-1">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide uppercase bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200">
                    Coming Soon
                  </span>
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide uppercase bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200">
                    Premium
                  </span>
                </div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                  iOS / Android App
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-xl">
                  Native mobile apps with full Nexelin chat, notifications and on‑device AI assistant for your team.
                </p>
              </div>
            </div>
            <div className="flex flex-col items-stretch md:items-end gap-3 w-full md:w-auto">
              <div className="flex gap-2 justify-center md:justify-end">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors"
                >
                  <span className="text-lg leading-none"></span>
                  <span className="flex flex-col items-start leading-tight">
                    <span className="text-[10px] uppercase tracking-wide opacity-70">Soon on</span>
                    <span className="text-xs">App Store</span>
                  </span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#0F9D58] text-white text-xs font-medium hover:bg-[#0c7f46] transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 512 512" fill="currentColor">
                    <path d="M325.3 234.3L104.1 18.1C97.7 11.8 89.3 8 80.3 8 63.5 8 50 21.7 50 38.3v435.3C50 490.3 63.5 504 80.3 504c9 0 17.4-3.8 23.8-10.1l221.2-216.2c6.1-6 9.5-14.3 9.5-23s-3.4-17-9.5-23z" />
                    <path d="M372.1 181.9L288 256l84.1 74.1L430 390.6c7.6 5.3 18 3.5 23.3-4.1 2.1-3 3.2-6.5 3.2-10.1V135.6c0-9.4-7.6-17-17-17-3.6 0-7.1 1.1-10.1 3.2l-57.3 60.1z" />
                  </svg>
                  <span className="flex flex-col items-start leading-tight">
                    <span className="text-[10px] uppercase tracking-wide opacity-80">Soon on</span>
                    <span className="text-xs">Google Play</span>
                  </span>
                </button>
              </div>
              <span className="text-[11px] text-gray-500 dark:text-gray-400 text-center md:text-right">
                Mobile apps are in active development. Contact us if you want early access.
              </span>
            </div>
          </div>
        </div>

      </div>

      {/* WhatsApp Bridge Setup Modal */}
      {showWhatsAppModal && (
        <WhatsAppSetup
          onClose={() => {
            setShowWhatsAppModal(false);
            reloadWhatsAppBridgeConfig();
          }}
          bridgeConfig={whatsappBridgeConfig}
        />
      )}

      {/* Web Chat Configuration Modal */}
      {showWebWidgetModal && (
        <WebWidgetSetup onClose={() => setShowWebWidgetModal(false)} />
      )}

      {showEmailModal && (
        <EmailSetup 
          onClose={() => {
            setShowEmailModal(false);
            // Перезавантажуємо статус email
            api.get('/clients/email-smtp/config/')
              .then(res => setEmailEnabled(res.data?.email_smtp_enabled || false))
              .catch(() => {});
          }} 
        />
      )}

      {showTelegramModal && (
        <TelegramSetup 
          onClose={() => {
            setShowTelegramModal(false);
            // Перезавантажуємо статус telegram
            api.get('/clients/telegram/config/')
              .then(res => setTelegramEnabled(res.data?.telegram_enabled || false))
              .catch(() => {});
          }} 
        />
      )}

      {showChromeExtensionModal && (
        <ChromeExtensionSetup 
          onClose={() => {
            setShowChromeExtensionModal(false);
          }} 
        />
      )}

      {showHITLModal && (
        <HITLSetup 
          onClose={() => {
            setShowHITLModal(false);
            // Reload HITL status
            api.get('/clients/hitl/config/')
              .then(res => setHitlEnabled(res.data?.hitl_enabled || false))
              .catch(() => {});
          }} 
        />
      )}

      {showWebModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Web Chat Configuration</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Generate QR code for B2C client chat interface</p>
              </div>
              <button
                onClick={() => setShowWebModal(false)}
                className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6">
              <div className="space-y-4">
                {/* Info Notice */}
                <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Web Chat allows your customers to chat with your AI assistant directly from a web interface. 
                    Scan the QR code or share the link to start conversations.
                  </p>
                </div>

                {/* QR Code Display */}
                <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50">
                  <h3 className="text-sm font-semibold mb-3 text-gray-900 dark:text-gray-100">QR Code for Web Chat:</h3>
                  {loadingWebQR ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 size={24} className="animate-spin text-primary-600 dark:text-primary-400" />
                      <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">Generating QR code...</span>
                    </div>
                  ) : webQRCode ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-center">
                        <img 
                          src={webQRCode} 
                          alt="Web Chat QR Code" 
                          className="max-w-full h-auto rounded border-2 border-gray-200 dark:border-gray-700"
                        />
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                        Scan this QR code or share the link to access Web Chat
                      </p>
                      {(() => {
                        // Той самий підхід, що й у loadOrCreateWebQR:
                        // спершу беремо актуальний tag з clientInfo.tag, потім fallback на localStorage
                        const storedTag = localStorage.getItem('client_tag');
                        let clientTag = clientInfo?.tag || storedTag;
                        if (clientInfo?.tag && storedTag !== clientInfo.tag) {
                          localStorage.setItem('client_tag', clientInfo.tag);
                          clientTag = clientInfo.tag;
                        }
                        // Для white label використовуємо webchat_domain
                        let baseUrl = window.location.origin;
                        if (clientInfo?.webchat_domain) {
                          const customDomain = clientInfo.webchat_domain.trim();
                          if (customDomain.startsWith('http://') || customDomain.startsWith('https://')) {
                            baseUrl = customDomain.replace(/\/$/, '');
                          } else {
                            baseUrl = `https://${customDomain}`.replace(/\/$/, '');
                          }
                        }
                        const webChatUrl = clientTag ? `${baseUrl}/client?tag=${clientTag}` : '';
                        return webChatUrl ? (
                          <div className="mt-3 p-3 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">Link:</p>
                            <input
                              type="text"
                              value={webChatUrl}
                              readOnly
                              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 font-mono text-gray-900 dark:text-gray-100"
                              onClick={(e) => e.target.select()}
                            />
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(webChatUrl);
                                setSuccess('Link copied!');
                                setTimeout(() => setSuccess(''), 2000);
                              }}
                              className="mt-2 w-full px-3 py-2 text-sm bg-primary-600 dark:bg-primary-500 text-white rounded hover:bg-primary-700 dark:hover:bg-primary-600"
                            >
                              Copy Link
                            </button>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                      QR code will be generated automatically
                    </p>
                  )}
                </div>

                {error && <div className="text-red-600 dark:text-red-400 text-sm p-3 bg-red-50 dark:bg-red-900/30 rounded-lg">{error}</div>}
                {success && <div className="text-green-600 dark:text-green-400 text-sm p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">{success}</div>}
                
                <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => setShowWebModal(false)}
                    className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    {t('common.close')}
                  </button>
                  <button
                    type="button"
                    onClick={() => loadOrCreateWebQR(true)}
                    disabled={loadingWebQR}
                    className="flex-1 px-4 py-2 rounded-lg bg-primary-600 dark:bg-primary-500 text-white hover:bg-primary-700 dark:hover:bg-primary-600 disabled:opacity-50"
                  >
                    {loadingWebQR ? t('common.loading') : 'Regenerate QR Code'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationsPage;
