import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
import { toolsAPI } from '../../api/tools';
import api from '../../api/axios';
import ToolStatusBadge from './ToolStatusBadge';
import ToolIcon from './ToolIcon';

const CAT_COLORS = {
  communication: { stripe: 'border-l-green-500',   iconBg: 'bg-green-500/10',   iconText: 'text-green-500' },
  ai:            { stripe: 'border-l-primary-500',  iconBg: 'bg-primary-500/10',  iconText: 'text-primary-500' },
  productivity:  { stripe: 'border-l-orange-500',   iconBg: 'bg-orange-500/10',   iconText: 'text-orange-500' },
  analytics:     { stripe: 'border-l-blue-500',     iconBg: 'bg-blue-500/10',     iconText: 'text-blue-500' },
  crm:           { stripe: 'border-l-pink-500',     iconBg: 'bg-pink-500/10',     iconText: 'text-pink-500' },
  custom:        { stripe: 'border-l-gray-500',     iconBg: 'bg-gray-500/10',     iconText: 'text-gray-500' },
};

const resolveTagline = (tool, lang) => {
  if (tool.tagline_i18n && tool.tagline_i18n[lang]) return tool.tagline_i18n[lang];
  return tool.tagline;
};

const FlipToolCard = ({ tool, onConnected, onMouseEnter, onMouseLeave }) => {
  const { t, i18n } = useTranslation();
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [credentials, setCredentials] = useState({});
  const [showPasswords, setShowPasswords] = useState({});
  const [qrData, setQrData] = useState(null);
  const pollRef = useRef(null);
  const backRef = useRef(null);
  const [backHeight, setBackHeight] = useState(0);

  // Measure back side height when flipped
  const measureBack = useCallback(() => {
    if (backRef.current) {
      setBackHeight(backRef.current.scrollHeight);
    }
  }, []);

  useEffect(() => {
    if (flipped) {
      // Small delay to allow DOM to render
      const raf = requestAnimationFrame(measureBack);
      return () => cancelAnimationFrame(raf);
    }
  }, [flipped, qrData, error, measureBack]);

  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
  const cat = CAT_COLORS[tool.category] || CAT_COLORS.custom;
  const fields = tool.auth_config?.fields || [];

  // Initialize credentials with defaults
  useEffect(() => {
    const defaults = {};
    fields.forEach((f) => {
      if (f.type === 'checkbox') defaults[f.name] = f.default || false;
      else if (f.type === 'tags') defaults[f.name] = f.default || [];
      else defaults[f.name] = f.default || '';
    });
    setCredentials(defaults);
  }, [tool.slug]);

  // Cleanup polling
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const isSkill = tool._group === 'skills';

  // Track if we're reconnecting (already has credentials on server)
  const hasExistingConnection = tool.connection?.status === 'connected' ||
    tool.connection?.status === 'disconnected' || tool.connection?.status === 'expired';

  const handleClick = () => {
    if (isConnected) return; // Connected cards handled by popover
    if (isSkill) return;    // Skills are drag-only — drop onto edges
    if (tool.auth_type === 'none') {
      handleNoAuth();
    } else if (hasExistingConnection && tool.connection?.status !== 'connected') {
      // Has credentials already — reconnect without re-entering
      handleReconnect();
    } else {
      setFlipped(true);
    }
  };

  const handleReconnect = async () => {
    setLoading(true);
    try {
      // Re-enable existing connection
      await toolsAPI.updateFlowConnection(tool.connection.id, { enabled: true });
      onConnected(tool.slug);
    } catch {
      // Fallback to flip form if re-enable fails
      setFlipped(true);
    } finally {
      setLoading(false);
    }
  };

  const handleNoAuth = async () => {
    setLoading(true);
    try {
      await toolsAPI.connect(tool.slug, {});
      onConnected(tool.slug);
    } catch (err) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await toolsAPI.connect(tool.slug, credentials, { timeout: 10000 });
      if (res.data.status === 'connected') {
        setFlipped(false);
        onConnected(tool.slug);
      } else if (res.data.status === 'pending' && tool.auth_type === 'qr_code') {
        startQrFlow(res.data.initiate_url);
      } else if (res.data.auth_url) {
        window.location.href = res.data.auth_url;
      }
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        setError('Connection timed out. Please try again.');
      } else {
        setError(err.response?.data?.error || 'Connection failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const startQrFlow = async (initiateUrl) => {
    try {
      const url = initiateUrl || tool.auth_config?.initiate_url || '/clients/whatsapp/bridge/login/';
      const res = await api.post(url);
      if (res.data.qr) {
        setQrData(res.data.qr);
        startPolling(res.data.login_id);
      }
    } catch {
      setError('Failed to start QR login');
    }
  };

  const startPolling = (id) => {
    let retries = 0;
    const statusUrl = tool.auth_config?.status_url || '/clients/whatsapp/bridge/login/status/';
    pollRef.current = setInterval(async () => {
      retries++;
      if (retries > 48) {
        clearInterval(pollRef.current);
        setQrData(null);
        setError(t('tools.flow.qrExpired'));
        return;
      }
      try {
        const res = await api.get(`${statusUrl}?login_id=${id}`);
        if (res.data.status === 'connected') {
          clearInterval(pollRef.current);
          setFlipped(false);
          onConnected(tool.slug);
        } else if (res.data.qr) {
          setQrData(res.data.qr);
        }
      } catch { /* ignore polling errors */ }
    }, 2500);
  };

  const handleCancel = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setFlipped(false);
    setError('');
    setQrData(null);
  };

  const handleChange = (name, value) => {
    setCredentials(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="perspective-1000 w-[160px] shrink-0">
      <div
        className={`relative w-full ${flipped ? 'rotate-y-180' : ''}`}
        style={{
          transformStyle: 'preserve-3d',
          transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1), min-height 0.3s ease',
          minHeight: flipped && backHeight > 0 ? `${backHeight}px` : undefined,
          transformOrigin: 'center center',
        }}
      >
        {/* FRONT — relative to give parent natural height */}
        <div
          className={`backface-hidden relative rounded-xl border p-3 cursor-pointer transition-all
            ${isConnected
              ? `border-l-4 ${cat.stripe} border-gray-200 dark:border-gray-700 opacity-100`
              : 'border-dashed border-gray-300 dark:border-gray-600 opacity-60 hover:opacity-80'
            }
            bg-white dark:bg-gray-800`}
          draggable={true}
          onDragStart={(e) => {
            e.dataTransfer.setData('tool-slug', tool.slug);
            const group = tool._group || 'tools';
            e.dataTransfer.setData('tool-group', group);
            if (group === 'skills') {
              e.dataTransfer.setData('is-skill', '1');
            }
            e.dataTransfer.effectAllowed = 'copy';
          }}
          onClick={handleClick}
          onMouseEnter={() => isConnected && onMouseEnter?.(tool.slug)}
          onMouseLeave={() => isConnected && onMouseLeave?.()}
          title={isConnected ? t('tools.connected') : resolveTagline(tool, i18n.language) + ' — ' + t('tools.flow.clickToConnect')}
        >
          {loading && tool.auth_type === 'none' && (
            <div className="absolute inset-0 bg-white/80 dark:bg-gray-800/80 rounded-xl flex items-center justify-center z-10">
              <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
            </div>
          )}
          <div className="flex items-center gap-2 mb-1.5">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${cat.iconBg} ${cat.iconText}`}>
              <ToolIcon name={tool.icon} className="w-4 h-4" />
            </div>
            <div className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate leading-tight" title={tool.name}>
              {tool.name}
            </div>
          </div>
          <div className="text-[10px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-snug mb-1">
            {resolveTagline(tool, i18n.language)}
          </div>
          <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
        </div>

        {/* BACK — absolute, full size */}
        <div
          ref={backRef}
          className="backface-hidden rotate-y-180 absolute top-0 left-0 w-full rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 overflow-y-auto shadow-lg"
          style={{ transformStyle: 'preserve-3d', minHeight: '100%' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-900 dark:text-gray-100 truncate">{tool.name}</span>
            <button onClick={handleCancel} aria-label={t('common.close')} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-1.5 -m-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              <X size={14} />
            </button>
          </div>

          {error && (
            <div className="flex items-start gap-1 text-[11px] text-red-600 dark:text-red-400 mb-2 leading-snug bg-red-50 dark:bg-red-900/20 rounded p-1.5" role="alert">
              <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {qrData ? (
            <div className="flex flex-col items-center gap-1">
              <div className="bg-white p-1 rounded">
                <img src={`data:image/png;base64,${qrData}`} alt="QR" className="w-24 h-24" />
              </div>
              <div className="flex items-center gap-1 text-[10px] text-gray-500">
                <Loader2 className="w-3 h-3 animate-spin" />
                {t('tools.connecting')}
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-1.5">
              {fields.map(field => (
                <div key={field.name}>
                  {field.type === 'password' ? (
                    <div className="relative">
                      <input
                        type={showPasswords[field.name] ? 'text' : 'password'}
                        value={credentials[field.name] || ''}
                        onChange={(e) => handleChange(field.name, e.target.value)}
                        required={field.required}
                        placeholder={field.label || field.name}
                        aria-label={field.label || field.name}
                        className="w-full px-2 py-1.5 pr-7 text-[11px] border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 outline-none focus:ring-1 focus:ring-primary-500"
                      />
                      <button type="button"
                        onClick={() => setShowPasswords(p => ({ ...p, [field.name]: !p[field.name] }))}
                        aria-label={showPasswords[field.name] ? t('tools.flow.hidePassword') || 'Hide password' : t('tools.flow.showPassword') || 'Show password'}
                        className="absolute right-1 top-1/2 -translate-y-1/2 text-gray-400 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
                      >
                        {showPasswords[field.name] ? <EyeOff size={12} /> : <Eye size={12} />}
                      </button>
                    </div>
                  ) : field.type === 'checkbox' ? (
                    <label className="flex items-center gap-1.5 text-[11px] text-gray-600 dark:text-gray-400 cursor-pointer">
                      <input type="checkbox" checked={credentials[field.name] || false}
                        onChange={(e) => handleChange(field.name, e.target.checked)}
                        className="w-3.5 h-3.5 rounded border-gray-300 text-primary-600"
                      />
                      {field.label || field.name}
                    </label>
                  ) : (
                    <input
                      type="text"
                      value={credentials[field.name] || ''}
                      onChange={(e) => handleChange(field.name, e.target.value)}
                      required={field.required}
                      placeholder={field.label || field.name}
                      aria-label={field.label || field.name}
                      className="w-full px-2 py-1.5 text-[11px] border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  )}
                </div>
              ))}
              <button type="submit" disabled={loading}
                className="w-full py-1.5 text-[11px] font-medium rounded bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-1"
              >
                {loading && <Loader2 className="w-3 h-3 animate-spin" />}
                {tool.auth_type === 'qr_code' ? t('tools.flow.startQr') : t('tools.connect')}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default FlipToolCard;
