import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Eye, EyeOff, Loader2 } from 'lucide-react';
import { toolsAPI } from '../../api/tools';
import api from '../../api/axios';

const ConnectModal = ({ tool, onClose, onConnected }) => {
  const { t } = useTranslation();
  const [credentials, setCredentials] = useState({});
  const [showPasswords, setShowPasswords] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // QR code state
  const [qrData, setQrData] = useState(null);
  const [, setLoginId] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    // Initialize default values from auth_config fields
    const defaults = {};
    (tool.auth_config?.fields || []).forEach((field) => {
      if (field.type === 'checkbox') {
        defaults[field.name] = field.default || false;
      } else if (field.type === 'tags') {
        defaults[field.name] = field.default || [];
      } else {
        defaults[field.name] = field.default || '';
      }
    });
    setCredentials(defaults);
  }, [tool]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleChange = (name, value) => {
    setCredentials((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await toolsAPI.connect(tool.slug, credentials);
      const data = res.data;

      if (data.status === 'connected') {
        onConnected(tool.slug);
        onClose();
      } else if (data.status === 'pending' && tool.auth_type === 'qr_code') {
        // Start QR flow
        startQrFlow(data.initiate_url);
      } else if (data.auth_url) {
        // OAuth2 redirect
        window.location.href = data.auth_url;
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  const startQrFlow = async (initiateUrl) => {
    try {
      const res = await api.post(initiateUrl || '/clients/whatsapp/bridge/login/');
      if (res.data.qr) {
        setQrData(res.data.qr);
        setLoginId(res.data.login_id);
        startPolling(res.data.login_id);
      }
    } catch {
      setError('Failed to start QR login');
    }
  };

  const startPolling = (id) => {
    let retries = 0;
    const maxRetries = 48; // 48 * 2.5s = 120s timeout
    pollRef.current = setInterval(async () => {
      retries++;
      if (retries > maxRetries) {
        clearInterval(pollRef.current);
        setQrData(null);
        setError('QR code expired. Please try again.');
        return;
      }
      try {
        const res = await api.get(`/clients/whatsapp/bridge/login/status/?login_id=${id}`);
        const data = res.data;
        if (data.status === 'connected') {
          clearInterval(pollRef.current);
          onConnected(tool.slug);
          onClose();
        } else if (data.qr) {
          setQrData(data.qr);
        }
      } catch {
        // Ignore polling errors
      }
    }, 2500);
  };

  const handleNoAuthConnect = useCallback(async () => {
    setLoading(true);
    try {
      await toolsAPI.connect(tool.slug, {});
      onConnected(tool.slug);
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  }, [tool.slug, onConnected, onClose]);

  // For auth_type === 'none', connect immediately
  useEffect(() => {
    if (tool.auth_type === 'none') {
      handleNoAuthConnect();
    }
  }, [tool.auth_type, handleNoAuthConnect]);

  const fields = tool.auth_config?.fields || [];

  // QR code view
  if (qrData) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {tool.name}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
              <X size={20} />
            </button>
          </div>
          <div className="flex flex-col items-center gap-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
              {t('tools.scanQr') || 'Scan this QR code with your app'}
            </p>
            <div className="bg-white p-4 rounded-lg">
              <img
                src={`data:image/png;base64,${qrData}`}
                alt="QR Code"
                className="w-64 h-64"
              />
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t('tools.connecting')}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // auth_type === 'none' shows loading
  if (tool.auth_type === 'none') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-8">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600 mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t('tools.connect')} {tool.name}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {tool.tagline}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {fields.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {field.label || field.name}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>

              {field.type === 'password' ? (
                <div className="relative">
                  <input
                    type={showPasswords[field.name] ? 'text' : 'password'}
                    value={credentials[field.name] || ''}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    required={field.required}
                    placeholder={field.placeholder || ''}
                    className="input w-full pr-10"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowPasswords((p) => ({ ...p, [field.name]: !p[field.name] }))
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPasswords[field.name] ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              ) : field.type === 'checkbox' ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={credentials[field.name] || false}
                    onChange={(e) => handleChange(field.name, e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {field.description || ''}
                  </span>
                </label>
              ) : field.type === 'tags' ? (
                <input
                  type="text"
                  value={(credentials[field.name] || []).join(', ')}
                  onChange={(e) =>
                    handleChange(
                      field.name,
                      e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                    )
                  }
                  placeholder={field.placeholder || 'value1, value2, value3'}
                  className="input w-full"
                />
              ) : (
                <input
                  type="text"
                  value={credentials[field.name] || ''}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  required={field.required}
                  placeholder={field.placeholder || ''}
                  className="input w-full"
                />
              )}

              {field.hint && (
                <p className="text-xs text-gray-400 mt-1">{field.hint}</p>
              )}
            </div>
          ))}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary flex-1"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {t('tools.connect')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ConnectModal;
