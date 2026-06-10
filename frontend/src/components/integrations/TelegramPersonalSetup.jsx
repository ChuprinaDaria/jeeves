import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Loader2, Check, AlertCircle } from 'lucide-react';
import { toolsAPI } from '../../api/tools';

/**
 * Connects a personal Telegram account to the Matrix bridge.
 * Bot connections (BotFather token) live in TelegramSetup.jsx; this one
 * drives the mautrix-telegram phone → SMS code → optional 2FA flow.
 */
const TelegramPersonalSetup = ({ onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [state, setState] = useState(null); // {step, prompt, login_id, qr?}
  const [input, setInput] = useState('');
  const [remoteHandle, setRemoteHandle] = useState('');
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  useEffect(() => {
    let mounted = true;
    toolsAPI.bridgeLoginStatus('telegram', '__init__').catch(() => null);
    // Cheaper: hit /state/ for already-connected case
    import('../../api/axios').then(({ default: api }) => {
      api.get('/tools/matrix/bridges/telegram/state/')
        .then((r) => {
          if (!mounted) return;
          if (r.data?.status === 'connected') {
            setState({ step: 'connected', prompt: r.data.message });
            setRemoteHandle(r.data.remote_handle || '');
          }
        })
        .finally(() => mounted && setLoading(false));
    });
    return () => { mounted = false; stopPolling(); };
  }, [stopPolling]);

  const startPolling = (loginId) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const r = await toolsAPI.bridgeLoginStatus('telegram', loginId);
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
      const r = await toolsAPI.startBridgeLogin('telegram');
      setState(r.data);
      if (r.data?.step !== 'connected') startPolling(r.data.login_id);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to start Telegram login');
    } finally {
      setLoading(false);
    }
  };

  const submitStep = async () => {
    if (!input.trim()) return;
    setError('');
    setLoading(true);
    try {
      const r = await toolsAPI.startBridgeLogin('telegram', input.trim());
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
      <div className="bg-paper border-[1.5px] border-rule rounded-xl shadow-ink-lg w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b-[1.5px] border-rule">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              {t('integrations.telegramPersonalName') || 'Telegram (personal)'}
            </h2>
            <p className="text-xs text-slate mt-0.5">
              {t('integrations.telegramPersonalDesc') ||
                'Connect your personal Telegram account via Matrix bridge'}
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
                {t('integrations.telegramConnected') || 'Telegram connected'}
              </div>
              {remoteHandle && (
                <div className="text-xs text-slate">@{remoteHandle}</div>
              )}
            </div>
          )}

          {!isConnected && !state && !loading && (
            <button
              onClick={startLogin}
              className="w-full px-3 py-2 border-[1.5px] border-iris text-iris rounded font-mono text-xs uppercase tracking-wider hover:bg-iris-soft/40"
            >
              {t('integrations.startTelegramLogin') || 'Start Telegram login'}
            </button>
          )}

          {state?.prompt && !isConnected && (
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

export default TelegramPersonalSetup;
