import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Loader2, Check, AlertCircle, Puzzle } from 'lucide-react';
import api from '../../api/axios';
import { toolsAPI } from '../../api/tools';

// Networks whose login is driven by the Puzzle extension (cookie capture)
// instead of the Telegram-style phone/code prompts.
const EXTENSION_NETWORKS = {
  instagram: 'meta-instagram',
  facebook: 'meta-facebook',
};

/**
 * Generic Matrix bridge login modal. Drives the step-based prompt flow for
 * any network exposed by /api/tools/matrix/bridges/<network>/.
 *
 * Props:
 *   network: 'whatsapp' | 'telegram' | 'instagram' | 'facebook'
 *   title:   display label (e.g. 'Instagram DM')
 *   onClose: callback
 */
const BridgeSetup = ({ network, title, onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [state, setState] = useState(null);
  const [input, setInput] = useState('');
  const [remoteHandle, setRemoteHandle] = useState('');
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  useEffect(() => {
    let mounted = true;
    api.get(`/tools/matrix/bridges/${network}/state/`)
      .then((r) => {
        if (!mounted) return;
        if (r.data?.status === 'connected') {
          setState({ step: 'connected', prompt: r.data.message });
          setRemoteHandle(r.data.remote_handle || '');
        }
      })
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; stopPolling(); };
  }, [network, stopPolling]);

  const startPolling = (loginId) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const r = await toolsAPI.bridgeLoginStatus(network, loginId);
        if (r.data?.status === 'connected') {
          stopPolling();
          setState((prev) => ({ ...(prev || {}), step: 'connected', prompt: r.data.message }));
        }
      } catch { /* ignore */ }
    }, 3000);
  };

  const startLogin = async () => {
    setError('');
    setLoading(true);
    try {
      const r = await toolsAPI.startBridgeLogin(network);
      setState(r.data);
      if (r.data?.step !== 'connected') startPolling(r.data.login_id);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to start bridge login');
    } finally {
      setLoading(false);
    }
  };

  const startExtensionLogin = async () => {
    setError('');
    const extensionId = import.meta.env.VITE_CONCIERGE_EXTENSION_ID;
    if (!extensionId) {
      setError('Concierge Puzzle extension is required. Install it from the Integrations page.');
      return;
    }
    if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      setError('Open this page in Puzzle with the Concierge extension installed.');
      return;
    }
    setLoading(true);
    setState({ step: 'extension', prompt: 'Sign in via the popup that just opened…' });
    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          extensionId,
          {
            action: 'concierge_bridge_auth',
            bridgeType: EXTENSION_NETWORKS[network],
            apiBaseUrl: import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '',
            authToken: localStorage.getItem('access_token') || '',
            clientToken: localStorage.getItem('client_token') || '',
          },
          (resp) => {
            if (chrome.runtime.lastError) {
              reject(new Error('Extension not responding. Make sure it is installed and enabled.'));
            } else if (resp?.error) {
              reject(new Error(resp.error));
            } else {
              resolve(resp);
            }
          }
        );
      });
      if (response?.status === 'connected' || response?.success) {
        setState({ step: 'connected', prompt: response.message });
        setRemoteHandle(response.remote_handle || '');
      } else {
        setError(response?.message || 'Login did not complete. Try again.');
        setState(null);
      }
    } catch (e) {
      setError(e.message);
      setState(null);
    } finally {
      setLoading(false);
    }
  };

  const submitStep = async () => {
    if (!input.trim()) return;
    setError('');
    setLoading(true);
    try {
      const r = await toolsAPI.startBridgeLogin(network, input.trim());
      setInput('');
      setState(r.data);
      if (r.data?.step === 'connected') stopPolling();
      else startPolling(r.data.login_id);
    } catch (e) {
      setError(e.response?.data?.error || 'Submit failed');
    } finally {
      setLoading(false);
    }
  };

  const isConnected = state?.step === 'connected';
  const isExtensionFlow = network in EXTENSION_NETWORKS;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30 backdrop-blur-[2px]">
      <div className="settings-drawer bg-paper border-l-[1.5px] border-rule shadow-ink-lg h-full overflow-y-auto w-[440px] max-w-[94vw]">
        <div className="flex items-center justify-between p-5 border-b-[1.5px] border-rule">
          <div>
            <h2 className="text-lg font-semibold text-ink">{title}</h2>
            <p className="text-xs text-slate mt-0.5">
              {t('integrations.bridgeViaMatrix') || 'via Matrix bridge'}
            </p>
          </div>
          <button onClick={onClose} className="text-fog hover:text-ink">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-3">
          {error && (
            <div className="flex items-start gap-2 text-sm text-rose bg-linen border-[1.5px] border-rose rounded p-2">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {loading && !state && (
            <div className="flex items-center gap-2 text-sm text-fog">
              <Loader2 size={14} className="animate-spin" />
              {t('integrations.checkingState') || 'Checking bridge state…'}
            </div>
          )}

          {isConnected && (
            <div className="bg-sage/10 border-[1.5px] border-sage rounded p-3 space-y-1">
              <div className="flex items-center gap-2 text-sage text-sm font-medium">
                <Check size={14} />
                {t('integrations.bridgeConnected') || 'Bridge connected'}
              </div>
              {remoteHandle && (
                <div className="text-xs text-slate">@{remoteHandle}</div>
              )}
            </div>
          )}

          {state?.qr && !isConnected && (
            <div className="flex flex-col items-center gap-2">
              <img
                src={`data:image/png;base64,${state.qr}`}
                alt="QR"
                className="w-48 h-48 bg-paper p-2 rounded border-[1.5px] border-rule"
              />
              <p className="text-xs text-slate text-center">
                {t('integrations.scanQrInstructions') || 'Scan QR with the app on your phone'}
              </p>
            </div>
          )}

          {!isConnected && !state && !loading && !isExtensionFlow && (
            <button
              onClick={startLogin}
              className="w-full px-3 py-2 border-[1.5px] border-iris text-iris rounded font-mono text-xs uppercase tracking-wider hover:bg-iris-soft/40"
            >
              {t('integrations.startBridgeLogin') || 'Start login'}
            </button>
          )}

          {!isConnected && isExtensionFlow && state?.step !== 'extension' && (
            <div className="space-y-2">
              <p className="text-xs text-slate">
                {t('integrations.bridgeExtensionHint')
                  || 'A new tab will open. Sign in, and the extension will sync your cookies back here.'}
              </p>
              <button
                onClick={startExtensionLogin}
                disabled={loading}
                className="w-full px-3 py-2 border-[1.5px] border-iris text-iris rounded font-mono text-xs uppercase tracking-wider hover:bg-iris-soft/40 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Puzzle size={14} />
                {t('integrations.signInViaExtension') || 'Sign in via Puzzle extension'}
              </button>
            </div>
          )}

          {state?.step === 'extension' && !isConnected && (
            <div className="flex items-center gap-2 text-sm text-fog">
              <Loader2 size={14} className="animate-spin" />
              {state.prompt || 'Waiting for the extension…'}
            </div>
          )}

          {state?.prompt && !isConnected && !state?.qr && (
            <div className="space-y-2">
              <p className="text-sm text-ink whitespace-pre-wrap">{state.prompt}</p>
              <div className="flex gap-2">
                <input
                  type={state.step === 'password' ? 'password' : 'text'}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={state.step}
                  className="flex-1 px-2 py-1.5 text-sm border-[1.5px] border-rule rounded outline-none focus:border-iris"
                />
                <button
                  onClick={submitStep}
                  disabled={loading || !input.trim()}
                  className="px-3 py-1.5 text-xs border-[1.5px] border-iris text-iris rounded disabled:opacity-50"
                >
                  {loading
                    ? <Loader2 size={12} className="animate-spin" />
                    : (t('common.submit') || 'Send')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BridgeSetup;
