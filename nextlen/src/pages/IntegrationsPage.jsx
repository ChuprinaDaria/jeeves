import { useEffect, useState, useCallback } from 'react';
import api from '../api/axios';
import { useTranslation } from 'react-i18next';
import { X, Loader2 } from 'lucide-react';
import { clientAPI } from '../api/client';
import WebWidgetSetup from '../components/integrations/WebWidgetSetup';
import EmailSetup from '../components/integrations/EmailSetup';
import TelegramSetup from '../components/integrations/TelegramSetup';

const IntegrationsPage = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showWhatsAppModal, setShowWhatsAppModal] = useState(false);
  const [form, setForm] = useState({
    whatsapp_meta_enabled: false,
    meta_waba_id: '',
    meta_app_id: '',
    meta_app_secret: '',
    meta_phone_number: '',
    meta_phone_number_id: '',
    meta_verify_token: '',
    meta_access_token: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [whatsappQRCode, setWhatsappQRCode] = useState(null);
  const [loadingQR, setLoadingQR] = useState(false);
  const [webQRCode, setWebQRCode] = useState(null);
  const [loadingWebQR, setLoadingWebQR] = useState(false);
  const [showWebModal, setShowWebModal] = useState(false);
  const [showWebWidgetModal, setShowWebWidgetModal] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showTelegramModal, setShowTelegramModal] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [clientType, setClientType] = useState(null);
  const [clientInfo, setClientInfo] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      api.get('/clients/whatsapp/meta/config/'),
      api.get('/clients/me/'),
      api.get('/clients/email-smtp/config/').catch(() => ({ data: { email_smtp_enabled: false } })),
      api.get('/clients/telegram/config/').catch(() => ({ data: { telegram_enabled: false } }))
    ])
      .then(([whatsappRes, clientRes, emailRes, telegramRes]) => {
        if (!mounted) return;
        setForm(prev => ({ ...prev, ...whatsappRes.data }));
        setClientType(clientRes.data?.client_type || null);
        setClientInfo(clientRes.data);
        setEmailEnabled(emailRes.data?.email_smtp_enabled || false);
        setTelegramEnabled(telegramRes.data?.telegram_enabled || false);
      })
      .catch(() => {})
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  const loadOrCreateWhatsAppQR = useCallback(async (regenerate = false) => {
    setLoadingQR(true);
    try {
      // Перевіряємо чи є вже QR коди
      const existingQRCodes = await clientAPI.getQRCodes();
      const qrCodes = existingQRCodes.data || [];
      
      // Шукаємо QR код для WhatsApp Integration
      let whatsappQR = qrCodes.find(qr => qr.name === 'WhatsApp Integration');
      
      if (!whatsappQR) {
        // Перевіряємо ліміт QR кодів
        if (qrCodes.length >= 10) {
          console.warn('Maximum 10 QR codes allowed per client');
          setLoadingQR(false);
          return;
        }
        
        // Створюємо новий QR код для WhatsApp Integration
        const qrData = {
          name: 'WhatsApp Integration',
          description: 'QR code for WhatsApp Business API integration',
          location: 'Integration',
          integration_type: 'whatsapp',
          is_active: true,
        };
        
        const response = await clientAPI.createQRCode(qrData);
        whatsappQR = response.data;
        
        // Якщо QR код ще не згенерований, чекаємо трохи і перезавантажуємо
        if (!whatsappQR.qr_code_url_display && !whatsappQR.qr_code) {
          // Чекаємо 1 секунду і перезавантажуємо список QR кодів
          setTimeout(async () => {
            try {
              const updatedQRCodes = await clientAPI.getQRCodes();
              const updatedQR = updatedQRCodes.data?.find(qr => qr.id === whatsappQR.id);
              if (updatedQR?.qr_code_url_display) {
                setWhatsappQRCode(updatedQR.qr_code_url_display);
              }
            } catch (err) {
              console.error('Failed to reload QR code:', err);
            }
          }, 1000);
        }
      } else if (regenerate && whatsappQR.id) {
        // Якщо потрібно регенерувати QR код, оновлюємо його
        // Оновлюємо location, щоб гарантувати регенерацію QR коду
        // (perform_update регенерує QR код при зміні name або location)
        // Використовуємо timestamp для гарантії зміни location
        try {
          const baseLocation = 'Integration';
          const currentLocation = whatsappQR.location || baseLocation;
          // Додаємо timestamp тільки якщо location вже містить timestamp
          // або якщо воно відрізняється від базового
          const newLocation = currentLocation.startsWith(baseLocation) 
            ? `${baseLocation} (updated ${Date.now()})`
            : baseLocation;
          
          await clientAPI.updateQRCode(whatsappQR.id, {
            name: whatsappQR.name,
            description: whatsappQR.description,
            location: newLocation,
            is_active: whatsappQR.is_active,
          });
          
          // Чекаємо трохи і перезавантажуємо оновлений QR код
          setTimeout(async () => {
            try {
              const updatedQRCodes = await clientAPI.getQRCodes();
              const updatedQR = updatedQRCodes.data?.find(qr => qr.id === whatsappQR.id);
              if (updatedQR?.qr_code_url_display) {
                setWhatsappQRCode(updatedQR.qr_code_url_display);
              } else if (updatedQR?.qr_code) {
                setWhatsappQRCode(updatedQR.qr_code);
              }
            } catch (err) {
              console.error('Failed to reload regenerated QR code:', err);
            }
          }, 1000);
        } catch (err) {
          console.error('Failed to regenerate QR code:', err);
        }
      }
      
      // Отримуємо URL зображення QR коду
      if (whatsappQR.qr_code_url_display) {
        setWhatsappQRCode(whatsappQR.qr_code_url_display);
      } else if (whatsappQR.qr_code) {
        // Якщо є qr_code поле, отримуємо URL
        setWhatsappQRCode(whatsappQR.qr_code);
      }
    } catch (error) {
      console.error('Failed to load/create WhatsApp QR code:', error);
    } finally {
      setLoadingQR(false);
    }
  }, []);

  // Завантажити або створити QR код для WhatsApp при відкритті модалки
  useEffect(() => {
    if (showWhatsAppModal && form.whatsapp_meta_enabled) {
      loadOrCreateWhatsAppQR();
    }
  }, [showWhatsAppModal, form.whatsapp_meta_enabled, loadOrCreateWhatsAppQR]);

  // Завантажити або створити QR код для Web чату
  const loadOrCreateWebQR = useCallback(async (regenerate = false) => {
    setLoadingWebQR(true);
    try {
      const existingQRCodes = await clientAPI.getQRCodes();
      const qrCodes = existingQRCodes.data || [];
      
      // Отримуємо client_tag для формування URL
      // 1) спершу з localStorage (стандартний шлях)
      // 2) якщо немає - з clientInfo.tag, який приходить з /clients/me/
      const storedTag = localStorage.getItem('client_tag');
      const clientTag = storedTag || clientInfo?.tag;
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

  const onChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(s => ({ ...s, [name]: type === 'checkbox' ? checked : value }));
  };

  const onSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await api.patch('/clients/whatsapp/meta/config/', form);
      setSuccess(t('common.success'));
      
      // Якщо інтеграція увімкнена, завантажуємо/створюємо QR код
      // Якщо QR код вже існує, регенеруємо його (щоб оновити посилання з новим номером телефону)
      if (form.whatsapp_meta_enabled) {
        await loadOrCreateWhatsAppQR(true); // true = регенерувати QR код
      }
      
      setTimeout(() => {
        // Не закриваємо модалку автоматично, щоб користувач міг побачити QR код
        setSuccess('');
      }, 1500);
    } catch (err) {
      setError(err?.response?.data?.error || 'Error');
    } finally {
      setSaving(false);
    }
  };

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
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">{t('integrations.whatsapp')}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('integrations.whatsappDesc')}</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${form.whatsapp_meta_enabled ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}`}>
              {form.whatsapp_meta_enabled ? t('integrations.connected') : t('integrations.notConnected')}
            </span>
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

        {/* Google Calendar */}
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
          
          <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
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

        {/* Google Reviews */}
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
          
          <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

        {/* Instagram */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 opacity-60 hover:opacity-70 transition-opacity">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-pink-100 dark:bg-pink-900/30 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-pink-600 dark:text-pink-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">Instagram</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Connect Instagram DMs</p>
              </div>
            </div>
          </div>
          
          <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 mb-4 inline-block">
            Coming Soon
          </span>
        </div>

      </div>

      {/* WhatsApp Configuration Modal */}
      {showWhatsAppModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{t('integrations.whatsapp')} Configuration</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('integrations.whatsappNotice')}</p>
              </div>
              <button
                onClick={() => setShowWhatsAppModal(false)}
                className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={onSave} className="p-6">
              <div className="grid grid-cols-1 gap-4">
                
                {/* Info Notice */}
                <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    WhatsApp Business API integration requires approval from Meta.
                  </p>
                </div>

                {/* QR Code Display - показуємо якщо інтеграція підключена */}
                {form.whatsapp_meta_enabled && (
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50">
                    <h3 className="text-sm font-semibold mb-3 text-gray-900 dark:text-gray-100">QR Code для підключення:</h3>
                    {loadingQR ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 size={24} className="animate-spin text-primary-600 dark:text-primary-400" />
                        <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">Генерується QR код...</span>
                      </div>
                    ) : whatsappQRCode ? (
                      <div className="space-y-3">
                        <div className="flex items-center justify-center">
                          <img 
                            src={whatsappQRCode} 
                            alt="WhatsApp QR Code" 
                            className="max-w-full h-auto rounded border-2 border-gray-200 dark:border-gray-700"
                          />
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                          Відскануйте цей QR код для підключення до WhatsApp Business API
                        </p>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                        QR код буде згенеровано після збереження налаштувань
                      </p>
                    )}
                  </div>
                )}
                
                {/* Enable/Disable Toggle */}
                <div className="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <input
                    type="checkbox"
                    name="whatsapp_meta_enabled"
                    checked={form.whatsapp_meta_enabled}
                    onChange={onChange}
                    className="h-5 w-5 text-primary-600 dark:text-primary-400"
                  />
                  <div>
                    <label className="font-medium cursor-pointer text-gray-900 dark:text-gray-100">Enable WhatsApp Integration</label>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Activate WhatsApp Business API for this client</p>
                  </div>
                </div>
                
                <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">{t('integrations.phoneNumber')}</label>
            <input
              name="meta_phone_number"
              value={form.meta_phone_number}
              onChange={onChange}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="+380671234567"
              type="tel"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('integrations.phoneNumberHint')}</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">Meta WABA ID</label>
            <input
              name="meta_waba_id"
              value={form.meta_waba_id}
              onChange={onChange}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="e.g. 1606460197401137"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Meta WhatsApp Business Account ID</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">Meta App ID</label>
            <input
              name="meta_app_id"
              value={form.meta_app_id}
              onChange={onChange}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="e.g. 1896910764591075"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Meta App ID from your Meta Business App</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">Meta App Secret</label>
            <input
              name="meta_app_secret"
              value={form.meta_app_secret || ''}
              onChange={onChange}
              type="password"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="••••••••••••••••"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Keep this secret! It's used to verify webhook requests</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">{t('integrations.phoneNumberId')}</label>
            <input
              name="meta_phone_number_id"
              value={form.meta_phone_number_id}
              onChange={onChange}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="e.g. 880980521764760"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Meta Business Phone Number ID</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">Verify Token</label>
            <input
              name="meta_verify_token"
              value={form.meta_verify_token}
              onChange={onChange}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="nexelin_wh_7f3a2c9b1e84d24f2a6c4d1e9a0b12d3"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Random string for webhook verification</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-900 dark:text-gray-100">{t('integrations.accessToken')}</label>
            <textarea
              name="meta_access_token"
              value={form.meta_access_token}
              onChange={onChange}
              rows="3"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 font-mono text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="EAAa9OvRLRZBMBPZB41vIJ6yjX2WKjITZBRWFKYAiRv732pPw..."
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Meta Graph API Access Token (long-lived)</p>
          </div>
                {error && <div className="text-red-600 dark:text-red-400 text-sm p-3 bg-red-50 dark:bg-red-900/30 rounded-lg">{error}</div>}
                {success && <div className="text-green-600 dark:text-green-400 text-sm p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">{success}</div>}
                
                <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => setShowWhatsAppModal(false)}
                    className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex-1 px-4 py-2 rounded-lg bg-primary-600 dark:bg-primary-500 text-white hover:bg-primary-700 dark:hover:bg-primary-600 disabled:opacity-50"
                  >
                    {saving ? t('common.loading') : t('common.save')}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
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
                        // спершу беремо tag з localStorage, потім з clientInfo.tag
                        const storedTag = localStorage.getItem('client_tag');
                        const clientTag = storedTag || clientInfo?.tag;
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
