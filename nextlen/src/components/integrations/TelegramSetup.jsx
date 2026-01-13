import { X, Copy, Loader2, Check, AlertCircle } from 'lucide-react';
import { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useTranslation } from 'react-i18next';

const TelegramSetup = ({ onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    telegram_enabled: false,
    telegram_bot_token: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const res = await api.get('/clients/telegram/config/');
      setForm(prev => ({ ...prev, ...res.data }));
      setWebhookUrl(res.data.telegram_webhook_url || '');
    } catch (error) {
      console.error('Failed to load telegram config:', error);
      setError('Failed to load Telegram configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    setError('');
    setSuccess('');
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      
      const res = await api.patch('/clients/telegram/config/', form);
      
      if (res.data.success) {
        setSuccess('Telegram configuration saved successfully');
        setWebhookUrl(res.data.telegram_webhook_url || '');
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Failed to save configuration';
      setError(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    if (webhookUrl) {
      navigator.clipboard.writeText(webhookUrl);
      setSuccess('Webhook URL copied to clipboard!');
      setTimeout(() => setSuccess(''), 2000);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-lg w-full mx-4">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={32} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-lg w-full mx-4 my-8">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {t('integrations.telegramSetup') || 'Setup Telegram Bot'}
          </h3>
          <button 
            onClick={onClose} 
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X size={24} />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg flex items-center gap-2 text-red-700 dark:text-red-300">
            <AlertCircle size={18} />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg flex items-center gap-2 text-green-700 dark:text-green-300">
            <Check size={18} />
            <span className="text-sm">{success}</span>
          </div>
        )}

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="telegram_enabled"
              name="telegram_enabled"
              checked={form.telegram_enabled}
              onChange={handleChange}
              className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
            />
            <label htmlFor="telegram_enabled" className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {t('integrations.enableTelegram') || 'Enable Telegram Bot'}
            </label>
          </div>

          {form.telegram_enabled && (
            <>
              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                <p className="text-sm text-blue-800 dark:text-blue-300 mb-2">
                  <strong>{t('integrations.telegramInstructions') || 'Instructions:'}</strong>
                </p>
                <ol className="text-xs text-blue-700 dark:text-blue-300 space-y-1 list-decimal list-inside">
                  <li>{t('integrations.telegramStep1') || 'Open Telegram and search for @BotFather'}</li>
                  <li>{t('integrations.telegramStep2') || 'Send /newbot and follow the instructions'}</li>
                  <li>{t('integrations.telegramStep3') || 'Copy the bot token and paste it below'}</li>
                </ol>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  {t('integrations.botToken') || 'Bot Token'}
                </label>
                <input
                  type="text"
                  name="telegram_bot_token"
                  value={form.telegram_bot_token}
                  onChange={handleChange}
                  placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                  className="input"
                  required
                />
              </div>

              {webhookUrl && (
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                    {t('integrations.webhookUrl') || 'Webhook URL'}
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={webhookUrl}
                      readOnly
                      className="input flex-1 bg-gray-50 dark:bg-gray-700"
                    />
                    <button onClick={handleCopy} className="btn-secondary">
                      <Copy size={18} />
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {t('integrations.webhookHint') || 'This URL is automatically set when you save the bot token'}
                  </p>
                </div>
              )}
            </>
          )}

          <div className="flex gap-3 pt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  {t('integrations.saving') || 'Saving...'}
                </>
              ) : (
                t('integrations.save') || 'Save'
              )}
            </button>
            <button
              onClick={onClose}
              disabled={saving}
              className="btn-secondary flex-1"
            >
              {t('common.cancel') || 'Cancel'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TelegramSetup;
