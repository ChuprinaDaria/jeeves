import { X, Loader2, Check, AlertCircle, RefreshCw, Smartphone, Wifi, WifiOff } from 'lucide-react';
import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../../api/axios';
import { useTranslation } from 'react-i18next';

const WhatsAppSetup = ({ onClose, bridgeConfig }) => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(bridgeConfig?.whatsapp_bridge_status || 'disconnected');
  const [phone, setPhone] = useState(bridgeConfig?.whatsapp_bridge_phone || '');
  const [qrData, setQrData] = useState(null);
  const [loginId, setLoginId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const pollRef = useRef(null);

  const globallyEnabled = bridgeConfig?.globally_enabled !== false;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const startLogin = async () => {
    setLoading(true);
    setError('');
    setQrData(null);
    try {
      const res = await api.post('/tools/matrix/bridges/whatsapp/login/start/');
      const data = res.data;
      if (data.step === 'connected') {
        setStatus('connected');
        setPhone(data.prompt || '');
        setSuccess(t('integrations.whatsappConnected') || 'Connected');
      } else if (data.qr) {
        setQrData(data.qr);
        setLoginId(data.login_id);
        startPolling(data.login_id);
      } else {
        setError(data.error || data.prompt || 'Bridge did not return a QR code');
      }
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.detail || 'Failed to start login';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const startPolling = (id) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/tools/matrix/bridges/whatsapp/login/status/?login_id=${encodeURIComponent(id)}`);
        const data = res.data;
        if (data.status === 'connected') {
          stopPolling();
          setStatus('connected');
          setQrData(null);
          setLoginId(null);
          setSuccess(t('integrations.whatsappConnected') || 'Connected');
          setTimeout(() => setSuccess(''), 3000);
        } else if (data.status === 'expired') {
          stopPolling();
          setQrData(null);
          setLoginId(null);
          setError(t('integrations.qrExpired') || 'QR expired');
        }
      } catch {
        // ignore polling errors
      }
    }, 2500);
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    setError('');
    try {
      await api.post('/clients/whatsapp/bridge/logout/');
      setStatus('disconnected');
      setPhone('');
      setQrData(null);
      setLoginId(null);
      stopPolling();
      setSuccess(t('integrations.whatsappDisconnected'));
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to disconnect';
      setError(msg);
    } finally {
      setDisconnecting(false);
    }
  };

  const handleRetry = () => {
    setError('');
    startLogin();
  };

  if (!globallyEnabled) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-lg w-full mx-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              {t('integrations.whatsappBridge') || 'WhatsApp'}
            </h3>
            <button onClick={onClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300">
              <X size={24} />
            </button>
          </div>
          <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-yellow-700 dark:text-yellow-300">
              <AlertCircle size={18} />
              <span className="text-sm">{t('integrations.whatsappDisabledByAdmin') || 'WhatsApp integration is disabled by administrator'}</span>
            </div>
          </div>
          <div className="flex gap-3 pt-4">
            <button onClick={onClose} className="btn-secondary flex-1">
              {t('common.close') || 'Close'}
            </button>
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
            {t('integrations.whatsappBridge') || 'WhatsApp'}
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
            <span className="text-sm flex-1">{error}</span>
            <button
              onClick={handleRetry}
              className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200"
              title="Retry"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg flex items-center gap-2 text-green-700 dark:text-green-300">
            <Check size={18} />
            <span className="text-sm">{success}</span>
          </div>
        )}

        <div className="space-y-4">
          {/* Status indicator */}
          <div className="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            {status === 'connected' ? (
              <Wifi className="text-green-500" size={20} />
            ) : (
              <WifiOff className="text-gray-400 dark:text-gray-500" size={20} />
            )}
            <div className="flex-1">
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {status === 'connected'
                  ? (t('integrations.whatsappConnected') || 'WhatsApp Connected')
                  : (t('integrations.whatsappDisconnected') || 'WhatsApp Disconnected')}
              </p>
              {status === 'connected' && phone && (
                <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1.5 mt-0.5">
                  <Smartphone size={14} />
                  {phone}
                </p>
              )}
            </div>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
              status === 'connected'
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}>
              {status === 'connected'
                ? (t('integrations.connected') || 'Connected')
                : (t('integrations.notConnected') || 'Not connected')}
            </span>
          </div>

          {/* Connected state: show disconnect */}
          {status === 'connected' && (
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
            >
              {disconnecting ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <WifiOff size={18} />
              )}
              {t('integrations.disconnectWhatsApp') || 'Disconnect WhatsApp'}
            </button>
          )}

          {/* Disconnected state: show connect or QR */}
          {status !== 'connected' && !qrData && (
            <>
              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  {t('integrations.scanInstructions') || 'Open WhatsApp on your phone \u2192 Settings \u2192 Linked Devices \u2192 Link a Device \u2192 Scan this QR code'}
                </p>
              </div>

              <button
                onClick={startLogin}
                disabled={loading}
                className="w-full btn-primary flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    {t('integrations.connecting') || 'Connecting...'}
                  </>
                ) : (
                  <>
                    <Wifi size={18} />
                    {t('integrations.connectWhatsApp') || 'Connect WhatsApp'}
                  </>
                )}
              </button>
            </>
          )}

          {/* QR Code display */}
          {qrData && (
            <div className="space-y-4">
              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  {t('integrations.scanInstructions') || 'Open WhatsApp on your phone \u2192 Settings \u2192 Linked Devices \u2192 Link a Device \u2192 Scan this QR code'}
                </p>
              </div>

              <div className="flex flex-col items-center p-6 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
                <img
                  src={`data:image/png;base64,${qrData}`}
                  alt="WhatsApp QR Code"
                  className="w-64 h-64 rounded"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-3">
                  {t('integrations.scanQR') || 'Scan QR Code'}
                </p>
                <div className="flex items-center gap-2 mt-2 text-xs text-gray-400 dark:text-gray-500">
                  <Loader2 className="animate-spin" size={12} />
                  {t('integrations.connecting') || 'Connecting...'}
                </div>
              </div>

              <button
                onClick={handleRetry}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <RefreshCw size={16} />
                {t('integrations.qrExpired') || 'QR code expired. Click to refresh.'}
              </button>
            </div>
          )}

          {/* Close button */}
          <div className="flex gap-3 pt-4">
            <button
              onClick={onClose}
              className="btn-secondary flex-1"
            >
              {t('common.close') || 'Close'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhatsAppSetup;
