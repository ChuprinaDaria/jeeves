/* global chrome */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Eye, EyeSlash, ArrowClockwise, Warning } from '@phosphor-icons/react';
import { toolsAPI } from '../../api/tools';
import api from '../../api/axios';
import ToolStatusBadge from './ToolStatusBadge';
import ToolIcon from './ToolIcon';

// Semantic accent mapping per category — only 4 accents allowed
const CAT_ACCENT = {
  communication: 'sage',
  ai:            'iris',
  productivity:  'amber',
  analytics:     'iris',
  crm:           'rose',
  custom:        'iris',
};

const ACCENT_CLASSES = {
  iris:  { stripe: 'border-l-iris',  iconBg: 'bg-iris/10',  iconText: 'text-iris'  },
  sage:  { stripe: 'border-l-sage',  iconBg: 'bg-sage/10',  iconText: 'text-sage'  },
  rose:  { stripe: 'border-l-rose',  iconBg: 'bg-rose/10',  iconText: 'text-rose'  },
  amber: { stripe: 'border-l-amber', iconBg: 'bg-amber/10', iconText: 'text-amber' },
};

const resolveTagline = (tool, lang) => {
  if (tool.tagline_i18n && tool.tagline_i18n[lang]) return tool.tagline_i18n[lang];
  return tool.tagline;
};

const MATRIX_BRIDGES = ['telegram', 'whatsapp', 'instagram', 'facebook'];

const MatrixBridgesPanel = ({ bridges, setBridges, t }) => {
  const [activeBridge, setActiveBridge] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [loginState, setLoginState] = useState(null); // {login_id, qr, prompt, step}
  const [input, setInput] = useState('');
  const pollRef = useRef(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const startBridge = async (network) => {
    setError('');
    setActiveBridge(network);
    setLoading(true);
    setLoginState(null);
    setInput('');
    try {
      const res = await toolsAPI.startBridgeLogin(network);
      setLoginState(res.data);
      if (res.data.step !== 'connected') startPolling(network, res.data.login_id);
      else stopPolling();
    } catch (e) {
      setError(e.response?.data?.error || 'Bridge login failed');
    } finally {
      setLoading(false);
    }
  };

  const startPolling = (network, loginId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await toolsAPI.bridgeLoginStatus(network, loginId);
        if (s.data.status === 'connected') {
          setLoginState(prev => ({ ...(prev || {}), step: 'connected', prompt: s.data.message }));
          stopPolling();
          if (!bridges.includes(network)) setBridges([...bridges, network]);
        }
      } catch { /* ignore */ }
    }, 3000);
  };

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const submitStep = async () => {
    if (!input.trim() || !activeBridge) return;
    setLoading(true);
    setError('');
    try {
      const res = await toolsAPI.startBridgeLogin(activeBridge, input.trim());
      setInput('');
      setLoginState(res.data);
      if (res.data.step === 'connected') {
        stopPolling();
        if (!bridges.includes(activeBridge)) setBridges([...bridges, activeBridge]);
      } else {
        startPolling(activeBridge, res.data.login_id);
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Submit failed');
    } finally {
      setLoading(false);
    }
  };

  const isConnected = loginState?.step === 'connected';

  return (
    <div className="pt-1">
      <div className="text-[10px] font-medium text-slate mb-1">
        {t('tools.matrix.bridges_label')}
      </div>
      <div className="grid grid-cols-2 gap-0.5">
        {MATRIX_BRIDGES.map((b) => (
          <label key={b} className="flex items-center gap-1 text-[10px] text-slate cursor-pointer">
            <input
              type="checkbox"
              checked={bridges.includes(b)}
              onChange={(e) => {
                if (e.target.checked) startBridge(b);
                else setBridges(bridges.filter((x) => x !== b));
              }}
              className="w-3 h-3 rounded-sm border-[1.5px] border-rule accent-iris"
            />
            <span className="capitalize">{b}</span>
          </label>
        ))}
      </div>

      {activeBridge && (
        <div className="mt-2 p-2 border-[1.5px] border-rule rounded-sm bg-mist/40 space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-semibold capitalize text-ink">{activeBridge} login</div>
            <button
              type="button"
              onClick={() => { stopPolling(); setActiveBridge(null); setLoginState(null); }}
              className="text-[10px] text-fog hover:text-ink"
            >×</button>
          </div>

          {error && (
            <div className="text-[10px] text-rose">{error}</div>
          )}

          {loading && !loginState && (
            <div className="flex items-center gap-1 text-[10px] text-fog">
              <ArrowClockwise weight="light" size={12} className="animate-spin" />
              Talking to bridge…
            </div>
          )}

          {loginState?.qr && !isConnected && (
            <div className="flex flex-col items-center gap-1">
              <img src={`data:image/png;base64,${loginState.qr}`} alt="QR" className="w-32 h-32 bg-paper p-1 rounded-sm" />
              <div className="text-[10px] text-slate text-center">Scan with phone's WhatsApp → Linked devices</div>
            </div>
          )}

          {loginState?.prompt && !loginState?.qr && !isConnected && (
            <div className="space-y-1">
              <div className="text-[10px] text-slate whitespace-pre-wrap">{loginState.prompt}</div>
              <div className="flex gap-1">
                <input
                  type={loginState.step === 'password' ? 'password' : 'text'}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={loginState.step}
                  className="flex-1 px-1.5 py-1 text-[10px] border-[1.5px] border-rule rounded-sm bg-paper outline-none focus:border-iris"
                />
                <button
                  type="button"
                  onClick={submitStep}
                  disabled={loading || !input.trim()}
                  className="px-2 py-1 text-[10px] border-[1.5px] border-iris text-iris rounded-sm disabled:opacity-50"
                >Send</button>
              </div>
            </div>
          )}

          {isConnected && (
            <div className="text-[10px] text-sage">
              ✓ {loginState.prompt || 'Connected'}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const FlipToolCard = ({ tool, onConnected, onMouseEnter, onMouseLeave }) => {
  const { t, i18n } = useTranslation();
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [credentials, setCredentials] = useState({});
  const [bridges, setBridges] = useState([]);
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
  const accentKey = CAT_ACCENT[tool.category] || 'iris';
  const cat = ACCENT_CLASSES[accentKey];
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
    if (tool.is_system) return; // System tools: always connected, no action needed
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
      const res = tool.slug === 'matrix'
        ? await toolsAPI.connectWithConfig(tool.slug, credentials, { bridges })
        : await toolsAPI.connect(tool.slug, credentials, { timeout: 10000 });
      if (res.data.status === 'connected') {
        setFlipped(false);
        onConnected(tool.slug);
      } else if (res.data.status === 'pending' && tool.auth_type === 'qr_code') {
        startQrFlow(res.data.initiate_url);
      } else if (res.data.status === 'pending' && tool.auth_type === 'cookies') {
        startCookieFlow(tool.slug);
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

  const startCookieFlow = async (slug) => {
    const extensionId = import.meta.env.VITE_CONCIERGE_EXTENSION_ID;
    if (!extensionId) {
      setError('Concierge Chrome extension is required for this integration.');
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
              reject(new Error('Extension not found. Install the Concierge Chrome extension.'));
            } else if (resp?.error) {
              reject(new Error(resp.error));
            } else {
              resolve(resp);
            }
          }
        );
      });
      if (response.success) {
        setFlipped(false);
        onConnected(slug);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  const startQrFlow = async (initiateUrl) => {
    try {
      const raw = initiateUrl || tool.auth_config?.initiate_url || 'clients/whatsapp/bridge/login/';
      // Strip leading slash so axios appends to baseURL instead of ignoring it
      const url = raw.startsWith('/') ? raw.slice(1) : raw;
      // Switch to QR view immediately (empty string = show loader)
      setQrData('');
      const res = await api.post(url);
      if (res.data.qr) {
        setQrData(res.data.qr);
      }
      // Always start polling — QR may arrive later from background thread
      if (res.data.login_id) {
        startPolling(res.data.login_id);
      }
    } catch {
      setError('Failed to start QR login');
    }
  };

  const startPolling = (id) => {
    let retries = 0;
    const rawStatus = tool.auth_config?.status_url || 'clients/whatsapp/bridge/login/status/';
    const statusUrl = rawStatus.startsWith('/') ? rawStatus.slice(1) : rawStatus;
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
          className={`backface-hidden relative rounded-lg p-3 cursor-pointer transition-all bg-paper border-[1.5px]
            ${isConnected
              ? `border-l-4 ${cat.stripe} border-rule opacity-100`
              : 'border-dashed border-rule opacity-60 hover:opacity-90'
            }`}
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
            <div className="absolute inset-0 bg-paper/80 rounded-lg flex items-center justify-center z-10">
              <ArrowClockwise weight="light" size={20} className="animate-spin text-iris" />
            </div>
          )}
          <div className="flex items-center gap-2 mb-1.5">
            <div className={`w-7 h-7 rounded-sm flex items-center justify-center shrink-0 ${cat.iconBg} ${cat.iconText}`}>
              <ToolIcon name={tool.icon} className="w-4 h-4" />
            </div>
            <div className="text-xs font-medium text-ink truncate leading-tight" title={tool.name}>
              {tool.name}
            </div>
          </div>
          <div className="text-[10px] text-slate line-clamp-2 leading-snug mb-1">
            {resolveTagline(tool, i18n.language)}
          </div>
          <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
        </div>

        {/* BACK — absolute, full size */}
        <div
          ref={backRef}
          className="backface-hidden rotate-y-180 absolute top-0 left-0 w-full rounded-lg border-[1.5px] border-rule bg-paper p-3 overflow-y-auto shadow-ink"
          style={{ transformStyle: 'preserve-3d', minHeight: '100%' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-ink truncate">{tool.name}</span>
            <button
              onClick={handleCancel}
              aria-label={t('common.close')}
              className="text-fog hover:text-ink p-1.5 -m-1 rounded-sm hover:bg-mist transition-colors cursor-pointer"
            >
              <X weight="light" size={14} />
            </button>
          </div>

          {error && (
            <div
              className="flex items-start gap-1 text-[11px] text-rose mb-2 leading-snug bg-linen border-[1.5px] border-rose rounded-sm p-1.5"
              role="alert"
            >
              <Warning weight="light" size={12} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {qrData !== null ? (
            <div className="flex flex-col items-center gap-1">
              {qrData ? (
                <div className="bg-paper p-1 rounded-sm border-[1.5px] border-rule">
                  <img src={`data:image/png;base64,${qrData}`} alt="QR" className="w-24 h-24" />
                </div>
              ) : (
                <div className="w-24 h-24 flex items-center justify-center">
                  <ArrowClockwise weight="light" size={24} className="animate-spin text-iris" />
                </div>
              )}
              <div className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-fog">
                <ArrowClockwise weight="light" size={12} className="animate-spin" />
                {qrData ? t('tools.connecting') : t('tools.flow.startQr')}
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
                        className="w-full px-2 py-1.5 pr-7 text-[11px] border-[1.5px] border-rule rounded-sm bg-paper text-ink outline-none focus:border-iris transition-colors"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPasswords(p => ({ ...p, [field.name]: !p[field.name] }))}
                        aria-label={showPasswords[field.name] ? t('tools.flow.hidePassword') || 'Hide password' : t('tools.flow.showPassword') || 'Show password'}
                        className="absolute right-1 top-1/2 -translate-y-1/2 text-fog p-1 rounded-sm hover:bg-mist transition-colors cursor-pointer"
                      >
                        {showPasswords[field.name]
                          ? <EyeSlash weight="light" size={12} />
                          : <Eye weight="light" size={12} />}
                      </button>
                    </div>
                  ) : field.type === 'checkbox' ? (
                    <label className="flex items-center gap-1.5 text-[11px] text-slate cursor-pointer">
                      <input
                        type="checkbox"
                        checked={credentials[field.name] || false}
                        onChange={(e) => handleChange(field.name, e.target.checked)}
                        className="w-3.5 h-3.5 rounded-sm border-[1.5px] border-rule accent-iris"
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
                      className="w-full px-2 py-1.5 text-[11px] border-[1.5px] border-rule rounded-sm bg-paper text-ink outline-none focus:border-iris transition-colors"
                    />
                  )}
                </div>
              ))}
              {tool.slug === 'matrix' && (
                <MatrixBridgesPanel
                  bridges={bridges}
                  setBridges={setBridges}
                  t={t}
                />
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-1.5 font-mono text-[11px] uppercase tracking-wider rounded-sm border-[1.5px] border-iris text-iris hover:bg-iris-soft/40 disabled:opacity-50 flex items-center justify-center gap-1 transition-all cursor-pointer"
              >
                {loading && <ArrowClockwise weight="light" size={12} className="animate-spin" />}
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
