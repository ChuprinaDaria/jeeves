import { useEffect, useState } from 'react';
import api from '../api/axios';
import { useTranslation } from 'react-i18next';

const IntegrationsPage = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    whatsapp_meta_enabled: false,
    meta_waba_id: '',
    meta_app_id: '',
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

      {/* WhatsApp Card */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 max-w-3xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">{t('integrations.whatsapp')}</h2>
            <p className="text-gray-600">{t('integrations.whatsappDesc')}</p>
          </div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              name="whatsapp_meta_enabled"
              checked={form.whatsapp_meta_enabled}
              onChange={onChange}
              className="h-4 w-4"
            />
            <span className="text-sm">{form.whatsapp_meta_enabled ? t('integrations.connected') : t('integrations.notConnected')}</span>
          </label>
        </div>

        <form onSubmit={onSave} className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">{t('integrations.phoneNumberId')}</label>
            <input
              name="meta_phone_number_id"
              value={form.meta_phone_number_id}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="e.g. 1234567890"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Verify Token</label>
            <input
              name="meta_verify_token"
              value={form.meta_verify_token}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="Random string for webhook verification"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t('integrations.accessToken')}</label>
            <input
              name="meta_access_token"
              value={form.meta_access_token}
              onChange={onChange}
              className="w-full border rounded-lg px-3 py-2"
              placeholder="Paste Graph API access token"
            />
          </div>
          {error && <div className="text-red-600 text-sm">{error}</div>}
          {success && <div className="text-green-600 text-sm">{success}</div>}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-primary-600 text-white disabled:opacity-50"
            >
              {saving ? t('common.loading') : t('common.save')}
            </button>
          </div>
        </form>

        <div className="mt-4 text-sm text-gray-600">
          <p>{t('integrations.whatsappNotice')}</p>
        </div>
      </div>
    </div>
  );
};

export default IntegrationsPage;

