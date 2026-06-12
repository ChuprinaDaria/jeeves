import { X, Loader2, Check, AlertCircle } from 'lucide-react';
import { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useTranslation } from 'react-i18next';

const EmailSetup = ({ onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [form, setForm] = useState({
    email_smtp_enabled: false,
    email_smtp_host: '',
    email_smtp_port: 587,
    email_smtp_use_tls: true,
    email_smtp_username: '',
    email_smtp_password: '',
    email_from_address: '',
    email_from_name: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const res = await api.get('/clients/email-smtp/config/');
      // Don't overwrite password with empty string from API (security measure)
      const { email_smtp_password: _email_smtp_password, ...safeData } = res.data;
      setForm(prev => ({ 
        ...prev, 
        ...safeData,
        // Keep password empty for new entry, but show placeholder if configured
        email_smtp_password: '',
      }));
      // Track if password was already configured
      if (res.data.password_configured) {
        setForm(prev => ({ ...prev, _passwordConfigured: true }));
      }
    } catch (error) {
      console.error('Failed to load email config:', error);
      setError('Failed to load email configuration');
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
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    try {
      setTesting(true);
      setError('');
      setTestResult(null);
      
      const res = await api.patch('/clients/email-smtp/config/', {
        ...form,
        test_connection: true
      });
      
      if (res.data.test_passed) {
        setTestResult({ success: true, message: 'SMTP connection successful!' });
        setSuccess('Connection test passed');
      } else {
        setTestResult({ success: false, message: res.data.error || 'Connection test failed' });
        setError(res.data.error || 'Connection test failed');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Failed to test connection';
      setTestResult({ success: false, message: errorMsg });
      setError(errorMsg);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      
      const res = await api.patch('/clients/email-smtp/config/', form);
      
      if (res.data.success) {
        setSuccess('Email configuration saved successfully');
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

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex justify-end bg-ink/30 backdrop-blur-[2px]">
        <div className="settings-drawer bg-white dark:bg-gray-800 h-full overflow-y-auto border-l-[1.5px] border-rule shadow-ink-lg p-6 w-[560px] max-w-[94vw]">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={32} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30 backdrop-blur-[2px]">
      <div className="settings-drawer bg-white dark:bg-gray-800 h-full overflow-y-auto border-l-[1.5px] border-rule shadow-ink-lg p-6 w-[560px] max-w-[94vw]">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {t('integrations.emailSetup') || 'Setup Email SMTP'}
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

        {testResult && (
          <div className={`mb-4 p-3 border rounded-lg flex items-center gap-2 ${
            testResult.success 
              ? 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700 text-green-700 dark:text-green-300'
              : 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700 text-red-700 dark:text-red-300'
          }`}>
            {testResult.success ? <Check size={18} /> : <AlertCircle size={18} />}
            <span className="text-sm">{testResult.message}</span>
          </div>
        )}

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="email_smtp_enabled"
              name="email_smtp_enabled"
              checked={form.email_smtp_enabled}
              onChange={handleChange}
              className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
            />
            <label htmlFor="email_smtp_enabled" className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {t('integrations.enableEmail') || 'Enable Email SMTP'}
            </label>
          </div>

          {form.email_smtp_enabled && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                    {t('integrations.smtpHost') || 'SMTP Host'}
                  </label>
                  <input
                    type="text"
                    name="email_smtp_host"
                    value={form.email_smtp_host}
                    onChange={handleChange}
                    placeholder="smtp.gmail.com"
                    className="input"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                    {t('integrations.smtpPort') || 'SMTP Port'}
                  </label>
                  <input
                    type="number"
                    name="email_smtp_port"
                    value={form.email_smtp_port}
                    onChange={handleChange}
                    placeholder="587"
                    className="input"
                    required
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="email_smtp_use_tls"
                  name="email_smtp_use_tls"
                  checked={form.email_smtp_use_tls}
                  onChange={handleChange}
                  className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                />
                <label htmlFor="email_smtp_use_tls" className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('integrations.useTLS') || 'Use TLS encryption'}
                </label>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  {t('integrations.smtpUsername') || 'SMTP Username (Email)'}
                </label>
                <input
                  type="email"
                  name="email_smtp_username"
                  value={form.email_smtp_username}
                  onChange={handleChange}
                  placeholder="your-email@gmail.com"
                  className="input"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  {t('integrations.smtpPassword') || 'SMTP Password'}
                </label>
                <input
                  type="password"
                  name="email_smtp_password"
                  value={form.email_smtp_password}
                  onChange={handleChange}
                  placeholder={form._passwordConfigured ? '••••••••  (configured)' : 'Enter password'}
                  className="input"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {form._passwordConfigured 
                    ? (t('integrations.passwordConfiguredHint') || 'Password is already saved. Leave empty to keep existing, or enter new password to change.')
                    : (t('integrations.smtpPasswordHint') || 'For Gmail, use an App Password instead of your regular password')
                  }
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                    {t('integrations.fromEmail') || 'From Email Address'}
                  </label>
                  <input
                    type="email"
                    name="email_from_address"
                    value={form.email_from_address}
                    onChange={handleChange}
                    placeholder="noreply@example.com"
                    className="input"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                    {t('integrations.fromName') || 'From Name'}
                  </label>
                  <input
                    type="text"
                    name="email_from_name"
                    value={form.email_from_name}
                    onChange={handleChange}
                    placeholder="Your Company Name"
                    className="input"
                  />
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                <p className="text-sm text-blue-800 dark:text-blue-300 mb-2">
                  <strong>{t('integrations.commonProviders') || 'Common SMTP Settings:'}</strong>
                </p>
                <ul className="text-xs text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
                  <li><strong>Gmail:</strong> smtp.gmail.com, Port 587 (TLS) or 465 (SSL)</li>
                  <li><strong>Outlook:</strong> smtp-mail.outlook.com, Port 587 (TLS)</li>
                  <li><strong>Yahoo:</strong> smtp.mail.yahoo.com, Port 587 (TLS) or 465 (SSL)</li>
                  <li><strong>Custom:</strong> Check with your email provider</li>
                </ul>
              </div>
            </>
          )}

          <div className="flex gap-3 pt-4">
            {form.email_smtp_enabled && (
              <button
                onClick={handleTestConnection}
                disabled={testing || saving}
                className="btn-secondary flex-1 flex items-center justify-center gap-2"
              >
                {testing ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    {t('integrations.testing') || 'Testing...'}
                  </>
                ) : (
                  t('integrations.testConnection') || 'Test Connection'
                )}
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={saving || testing}
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
              disabled={saving || testing}
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

export default EmailSetup;

