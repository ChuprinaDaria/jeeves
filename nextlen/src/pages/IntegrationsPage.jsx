import { useEffect, useState } from 'react';
import api from '../api/axios';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';

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

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.get('/clients/whatsapp/meta/config/')
      .then(res => {
        if (!mounted) return;
        setForm(prev => ({ ...prev, ...res.data }));
      })
      .catch(() => {})
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

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
      setTimeout(() => {
        setShowWhatsAppModal(false);
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
      <h1 className="text-2xl font-semibold mb-2">{t('integrations.title')}</h1>
      <p className="text-gray-600 mb-6">{t('integrations.subtitle')}</p>

      {/* Integration Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl">
        
        {/* WhatsApp Card */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-green-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg">{t('integrations.whatsapp')}</h3>
                <p className="text-sm text-gray-500">{t('integrations.whatsappDesc')}</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-between mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${form.whatsapp_meta_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
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

        {/* Placeholder for future integrations */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 opacity-50">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <svg className="w-7 h-7 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-lg">{t('integrations.telegram')}</h3>
                <p className="text-sm text-gray-500">{t('integrations.telegramDesc')}</p>
              </div>
            </div>
          </div>
          
          <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600">
            Coming Soon
          </span>
        </div>

      </div>

      {/* WhatsApp Configuration Modal */}
      {showWhatsAppModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">{t('integrations.whatsapp')} Configuration</h2>
                <p className="text-sm text-gray-500 mt-1">{t('integrations.whatsappNotice')}</p>
              </div>
              <button
                onClick={() => setShowWhatsAppModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={onSave} className="p-6">
              <div className="grid grid-cols-1 gap-4">
                
                {/* Enable/Disable Toggle */}
                <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
                  <input
                    type="checkbox"
                    name="whatsapp_meta_enabled"
                    checked={form.whatsapp_meta_enabled}
                    onChange={onChange}
                    className="h-5 w-5 text-primary-600"
                  />
                  <div>
                    <label className="font-medium cursor-pointer">Enable WhatsApp Integration</label>
                    <p className="text-sm text-gray-500">Activate WhatsApp Business API for this client</p>
                  </div>
                </div>
                
                <div>
            <label className="block text-sm font-medium mb-1">{t('integrations.phoneNumber')}</label>
            <input
              name="meta_phone_number"
              value={form.meta_phone_number}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="+380671234567"
              type="tel"
            />
            <p className="text-xs text-gray-500 mt-1">{t('integrations.phoneNumberHint')}</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Meta WABA ID</label>
            <input
              name="meta_waba_id"
              value={form.meta_waba_id}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="e.g. 1606460197401137"
            />
            <p className="text-xs text-gray-500 mt-1">Meta WhatsApp Business Account ID</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Meta App ID</label>
            <input
              name="meta_app_id"
              value={form.meta_app_id}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="e.g. 1896910764591075"
            />
            <p className="text-xs text-gray-500 mt-1">Meta App ID from your Meta Business App</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Meta App Secret</label>
            <input
              name="meta_app_secret"
              value={form.meta_app_secret || ''}
              onChange={onChange}
              type="password"
              className="w-full border rounded-lg px-3 py-2"
              placeholder="••••••••••••••••"
            />
            <p className="text-xs text-gray-500 mt-1">Keep this secret! It's used to verify webhook requests</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">{t('integrations.phoneNumberId')}</label>
            <input
              name="meta_phone_number_id"
              value={form.meta_phone_number_id}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="e.g. 880980521764760"
            />
            <p className="text-xs text-gray-500 mt-1">Meta Business Phone Number ID</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Verify Token</label>
            <input
              name="meta_verify_token"
              value={form.meta_verify_token}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="nexelin_wh_7f3a2c9b1e84d24f2a6c4d1e9a0b12d3"
            />
            <p className="text-xs text-gray-500 mt-1">Random string for webhook verification</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">{t('integrations.accessToken')}</label>
            <textarea
              name="meta_access_token"
              value={form.meta_access_token}
              onChange={onChange}
              rows="3"
              className="w-full border rounded-lg px-3 py-2 font-mono text-sm"
              placeholder="EAAa9OvRLRZBMBPZB41vIJ6yjX2WKjITZBRWFKYAiRv732pPw..."
            />
            <p className="text-xs text-gray-500 mt-1">Meta Graph API Access Token (long-lived)</p>
          </div>
                {error && <div className="text-red-600 text-sm p-3 bg-red-50 rounded-lg">{error}</div>}
                {success && <div className="text-green-600 text-sm p-3 bg-green-50 rounded-lg">{success}</div>}
                
                <div className="flex gap-3 pt-4 border-t">
                  <button
                    type="button"
                    onClick={() => setShowWhatsAppModal(false)}
                    className="flex-1 px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex-1 px-4 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
                  >
                    {saving ? t('common.loading') : t('common.save')}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationsPage;
