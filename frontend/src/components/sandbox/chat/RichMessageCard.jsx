import React, { useState, useCallback } from 'react';
import { Loader2, CheckCircle2, XCircle, Wifi } from 'lucide-react';

const EXTENSION_ID = import.meta.env.VITE_CONCIERGE_EXTENSION_ID || '';
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

const BRIDGE_ICONS = {
  'meta-facebook': () => <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"/></svg>,
  'meta-instagram': () => <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor"><path d="M12 2c2.717 0 3.056.01 4.122.06 1.065.05 1.79.217 2.428.465.66.254 1.216.598 1.772 1.153.509.5.902 1.105 1.153 1.772.247.637.415 1.363.465 2.428.047 1.066.06 1.405.06 4.122 0 2.717-.01 3.056-.06 4.122-.05 1.065-.218 1.79-.465 2.428a4.883 4.883 0 01-1.153 1.772c-.5.508-1.105.902-1.772 1.153-.637.247-1.363.415-2.428.465-1.066.047-1.405.06-4.122.06-2.717 0-3.056-.01-4.122-.06-1.065-.05-1.79-.218-2.428-.465a4.89 4.89 0 01-1.772-1.153 4.904 4.904 0 01-1.153-1.772c-.248-.637-.415-1.363-.465-2.428C2.013 15.056 2 14.717 2 12c0-2.717.01-3.056.06-4.122.05-1.066.217-1.79.465-2.428a4.88 4.88 0 011.153-1.772A4.897 4.897 0 015.45 2.525c.638-.248 1.362-.415 2.428-.465C8.944 2.013 9.283 2 12 2zm0 5a5 5 0 100 10 5 5 0 000-10zm0 2a3 3 0 110 6 3 3 0 010-6zm5.25-3.5a1.25 1.25 0 100 2.5 1.25 1.25 0 000-2.5z"/></svg>,
  'linkedin': () => <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>,
};

const BRIDGE_COLORS = {
  'meta-facebook': '#1877F2',
  'meta-instagram': '#E4405F',
  'linkedin': '#0A66C2',
};

const BRIDGE_NAMES = {
  'meta-facebook': 'Facebook Messenger',
  'meta-instagram': 'Instagram DM',
  'linkedin': 'LinkedIn Messages',
};

function AuthPopupCard({ data, onComplete }) {
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const IconComp = BRIDGE_ICONS[data.bridge_type];
  const color = BRIDGE_COLORS[data.bridge_type] || '#6B7280';
  const name = BRIDGE_NAMES[data.bridge_type] || data.bridge_type;

  const handleClick = useCallback(async () => {
    setStatus('loading');
    setError('');

    if (!EXTENSION_ID) {
      setError('Extension ID not configured. Set VITE_CONCIERGE_EXTENSION_ID.');
      setStatus('error');
      return;
    }

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          EXTENSION_ID,
          {
            action: 'concierge_bridge_auth',
            bridgeType: data.bridge_type,
            apiBaseUrl: API_BASE,
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

      setStatus('success');
      if (onComplete) onComplete(data.bridge_type);
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  }, [data.bridge_type, onComplete]);

  return (
    <div className="flex items-center gap-3 p-4 rounded-xl border mt-2"
      style={{ borderColor: color + '33', background: color + '08' }}>
      <div className="p-2 rounded-lg" style={{ background: color + '15', color }}>
        {IconComp ? <IconComp /> : <Wifi size={24} />}
      </div>
      <div className="flex-1">
        <div className="font-medium text-sm">{name}</div>
        {status === 'error' && <div className="text-xs text-red-500 mt-1">{error}</div>}
        {status === 'success' && <div className="text-xs text-green-600 mt-1">Connected</div>}
      </div>
      {status === 'idle' && (
        <button onClick={handleClick}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium hover:opacity-90 transition-opacity"
          style={{ background: color }}>
          Sign in
        </button>
      )}
      {status === 'loading' && <Loader2 size={20} className="animate-spin" style={{ color }} />}
      {status === 'success' && <CheckCircle2 size={20} className="text-green-600" />}
      {status === 'error' && (
        <button onClick={handleClick}
          className="px-3 py-1.5 rounded-lg text-xs border border-red-200 text-red-600 hover:bg-red-50">
          Retry
        </button>
      )}
    </div>
  );
}

function QRCodeCard({ data }) {
  return (
    <div className="flex flex-col items-center gap-3 p-4 rounded-xl border border-gray-200 bg-white mt-2">
      <div className="text-sm font-medium">Scan QR code</div>
      {data.qr ? (
        <img src={data.qr.startsWith('data:') ? data.qr : `data:image/png;base64,${data.qr}`}
          alt="QR Code" className="w-48 h-48" />
      ) : (
        <Loader2 size={32} className="animate-spin text-gray-400" />
      )}
      <div className="text-xs text-gray-500">Waiting for scan...</div>
    </div>
  );
}

function ConnectionStatusCard({ data }) {
  const IconComp = BRIDGE_ICONS[data.bridge_type];
  const color = BRIDGE_COLORS[data.bridge_type] || '#6B7280';
  const name = BRIDGE_NAMES[data.bridge_type] || data.bridge_type;
  const isConnected = data.status === 'connected';

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-gray-200 mt-2">
      <div style={{ color }}>{IconComp ? <IconComp /> : <Wifi size={20} />}</div>
      <div className="flex-1">
        <div className="text-sm font-medium">{name}</div>
        <div className={`text-xs ${isConnected ? 'text-green-600' : 'text-gray-500'}`}>
          {data.status}{data.remote_id && ` — ${data.remote_id}`}
        </div>
      </div>
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
    </div>
  );
}

function TargetSelectorCard({ data, onSelect }) {
  const targets = data.targets || data.default_scopes || ['assistant', 'manager', 'leads'];

  return (
    <div className="flex flex-col gap-2 p-4 rounded-xl border border-gray-200 mt-2">
      <div className="text-sm font-medium">Where to connect?</div>
      <div className="flex gap-2 flex-wrap">
        {targets.map((target) => (
          <button key={target} onClick={() => onSelect?.(target)}
            className="px-3 py-1.5 rounded-lg text-sm border border-gray-200 hover:border-blue-300 hover:bg-blue-50 text-gray-700 transition-colors">
            {target.charAt(0).toUpperCase() + target.slice(1)}
          </button>
        ))}
        {targets.length > 1 && (
          <button onClick={() => onSelect?.('all')}
            className="px-3 py-1.5 rounded-lg text-sm border border-blue-300 bg-blue-50 text-blue-700 font-medium">
            All
          </button>
        )}
      </div>
    </div>
  );
}

export default function RichMessageCard({ data, onAction }) {
  if (!data || !data.type) return null;

  switch (data.type) {
    case 'auth_popup':
      return <AuthPopupCard data={data} onComplete={(bt) => onAction?.('auth_complete', bt)} />;
    case 'qr_code':
      return <QRCodeCard data={data} />;
    case 'status_card':
      return <ConnectionStatusCard data={data} />;
    case 'target_selector':
      return <TargetSelectorCard data={data} onSelect={(t) => onAction?.('target_selected', t)} />;
    case 'connection_created':
      return (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-green-200 bg-green-50 mt-2">
          <CheckCircle2 size={16} className="text-green-600" />
          <span className="text-sm text-green-700">
            Added to canvas: {data.nodes_created?.join(', ')}
          </span>
        </div>
      );
    case 'connection_removed':
      return (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-gray-200 bg-gray-50 mt-2">
          <XCircle size={16} className="text-gray-500" />
          <span className="text-sm text-gray-600">Connection removed from canvas</span>
        </div>
      );
    default:
      return null;
  }
}
