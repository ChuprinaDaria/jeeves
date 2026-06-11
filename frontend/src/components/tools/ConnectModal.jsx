/* global chrome */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Eye, EyeSlash, ArrowClockwise } from '@phosphor-icons/react';
import { toolsAPI } from '../../api/tools';
import api from '../../api/axios';

const MATRIX_BRIDGES = ['telegram', 'whatsapp', 'instagram', 'facebook'];

const ConnectModal = ({ tool, onClose, onConnected }) => {
  const { t } = useTranslation();
  const [credentials, setCredentials] = useState({});
  const [bridges, setBridges] = useState([]);
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
      const res = tool.slug === 'matrix'
        ? await toolsAPI.connectWithConfig(tool.slug, credentials, { bridges })
        : await toolsAPI.connect(tool.slug, credentials);
      const data = res.data;

      if (data.status === 'connected') {
        onConnected(tool.slug);
        onClose();
      } else if (data.status === 'pending' && tool.auth_type === 'qr_code') {
        // Start QR flow
        startQrFlow(data.initiate_url);
      } else if (data.status === 'pending' && tool.auth_type === 'cookies') {
        // Cookie extraction via Chrome extension
        startCookieFlow(tool.slug);
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
      const id = res.data.login_id;
      if (!id) {
        setError('Failed to start QR login');
        return;
      }
      setLoginId(id);
      if (res.data.qr) {
        setQrData(res.data.qr);
      } else {
        // Show loading state while waiting for QR from background thread
        setQrData('loading');
      }
      startPolling(id);
    } catch {
      setError('Failed to start QR login');
    }
  };

  const startCookieFlow = async (slug) => {
    const extensionId = import.meta.env.VITE_CONCIERGE_EXTENSION_ID;
    if (!extensionId) {
      setError('Concierge extension is required. Set VITE_CONCIERGE_EXTENSION_ID.');
      return;
    }
    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          extensionId,
          {
            action: 'concierge_bridge_auth',
            bridgeType: slug,
            apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
            authToken: localStorage.getItem('access_token') || '',
          },
          (resp) => {
            if (chrome.runtime.lastError) {
              reject(new Error('Extension not found. Install the Concierge extension.'));
            } else if (resp?.error) {
              reject(new Error(resp.error));
            } else {
              resolve(resp);
            }
          }
        );
      });
      if (response.success) {
        onConnected(slug);
        onClose();
      }
    } catch (e) {
      setError(e.message);
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
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
        <div className="bg-paper border-[1.5px] border-rule rounded-xl shadow-ink-lg w-full max-w-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-ink">
              {tool.name}
            </h2>
            <button
              onClick={onClose}
              className="text-fog hover:text-ink transition-colors cursor-pointer"
            >
              <X weight="light" size={20} />
            </button>
          </div>
          <div className="flex flex-col items-center gap-4">
            {qrData === 'loading' ? (
              <>
                <p className="text-sm text-slate text-center">
                  {t('tools.waitingQr') || 'Requesting QR code...'}
                </p>
                <div className="w-64 h-64 flex items-center justify-center">
                  <ArrowClockwise weight="light" size={48} className="animate-spin text-fog" />
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-slate text-center">
                  {t('tools.scanQr') || 'Scan this QR code with your app'}
                </p>
                <div className="bg-paper p-4 rounded-lg border-[1.5px] border-rule">
                  <img
                    src={`data:image/png;base64,${qrData}`}
                    alt="QR Code"
                    className="w-64 h-64"
                  />
                </div>
              </>
            )}
            <div className="flex items-center gap-2 label-mono text-slate">
              <ArrowClockwise weight="light" size={14} className="animate-spin" />
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
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px]">
        <div className="bg-paper border-[1.5px] border-rule rounded-xl shadow-ink-lg p-8">
          <ArrowClockwise weight="light" size={32} className="animate-spin text-iris mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
      <div className="bg-paper border-[1.5px] border-rule rounded-xl shadow-ink-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b-[1.5px] border-rule">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              {t('tools.connect')} {tool.name}
            </h2>
            <p className="text-sm text-slate mt-1">
              {tool.tagline}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-fog hover:text-ink transition-colors cursor-pointer"
          >
            <X weight="light" size={20} />
          </button>
        </div>

        {tool.slug === 'matrix' && (
          <div className="px-6 pt-4 pb-2 text-xs text-slate space-y-3">
            <div className="space-y-2">
              <p className="font-medium text-ink">{t('tools.matrix.howto_title')}</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>{t('tools.matrix.step_login')}</li>
                <li>{t('tools.matrix.step_token')}</li>
                <li>
                  {t('tools.matrix.step_bridge')}
                  <ul className="list-disc list-inside ml-4 mt-1">
                    <li><code>@whatsappbot:&lt;your-domain&gt;</code> → <code>login</code> ({t('tools.matrix.bridge_whatsapp')})</li>
                    <li><code>@telegrambot:&lt;your-domain&gt;</code> → <code>login</code> ({t('tools.matrix.bridge_telegram')})</li>
                    <li><code>@metabot:&lt;your-domain&gt;</code> → <code>login instagram</code> / <code>login facebook</code> ({t('tools.matrix.bridge_meta')})</li>
                  </ul>
                </li>
              </ol>
            </div>
            <div>
              <p className="font-medium text-ink mb-1">{t('tools.matrix.bridges_label', 'Enabled bridges')}</p>
              <div className="grid grid-cols-2 gap-1">
                {MATRIX_BRIDGES.map((b) => (
                  <label key={b} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={bridges.includes(b)}
                      onChange={(e) =>
                        setBridges((prev) =>
                          e.target.checked ? [...prev, b] : prev.filter((x) => x !== b)
                        )
                      }
                      className="w-4 h-4 rounded-sm border-[1.5px] border-rule text-iris accent-iris"
                    />
                    <span className="capitalize">{b}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-linen border-[1.5px] border-rose rounded text-sm text-rose">
              {error}
            </div>
          )}

          {fields.map((field) => (
            <div key={field.name}>
              <label className="block label-mono text-slate mb-1">
                {field.label || field.name}
                {field.required && <span className="text-rose ml-1">*</span>}
              </label>

              {field.type === 'password' ? (
                <div className="relative">
                  <input
                    type={showPasswords[field.name] ? 'text' : 'password'}
                    value={credentials[field.name] || ''}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    required={field.required}
                    placeholder={field.placeholder || ''}
                    className="w-full pr-10 px-3 py-2 rounded border-[1.5px] border-rule bg-paper text-ink text-sm outline-none focus:border-iris transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowPasswords((p) => ({ ...p, [field.name]: !p[field.name] }))
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-fog hover:text-ink transition-colors cursor-pointer"
                  >
                    {showPasswords[field.name]
                      ? <EyeSlash weight="light" size={16} />
                      : <Eye weight="light" size={16} />}
                  </button>
                </div>
              ) : field.type === 'checkbox' ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={credentials[field.name] || false}
                    onChange={(e) => handleChange(field.name, e.target.checked)}
                    className="w-4 h-4 rounded-sm border-[1.5px] border-rule text-iris focus:ring-iris accent-iris"
                  />
                  <span className="text-sm text-slate">
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
                  className="w-full px-3 py-2 rounded border-[1.5px] border-rule bg-paper text-ink text-sm outline-none focus:border-iris transition-colors"
                />
              ) : (
                <input
                  type="text"
                  value={credentials[field.name] || ''}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  required={field.required}
                  placeholder={field.placeholder || ''}
                  className="w-full px-3 py-2 rounded border-[1.5px] border-rule bg-paper text-ink text-sm outline-none focus:border-iris transition-colors"
                />
              )}

              {field.hint && (
                <p className="text-xs text-fog mt-1">{field.hint}</p>
              )}
            </div>
          ))}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-pink flex-1 justify-center"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn btn-violet flex-1 justify-center disabled:opacity-50"
            >
              {loading && <ArrowClockwise weight="light" size={14} className="animate-spin" />}
              {t('tools.connect')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ConnectModal;
