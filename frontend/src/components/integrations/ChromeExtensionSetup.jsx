import { X, Copy, Loader2, Check, AlertCircle, Download } from 'lucide-react';
import { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useTranslation } from 'react-i18next';

const ChromeExtensionSetup = ({ onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [clientInfo, setClientInfo] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [copied, setCopied] = useState(false);
  const [visible, setVisible] = useState(false);

  const extensionDownloadUrl =
    import.meta.env.VITE_EXTENSION_DOWNLOAD_URL ||
    '/static/extensions/concierge-chrome-extension.zip';

  useEffect(() => {
    loadClientInfo();
    // Trigger slide-in after mount
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const handleClose = () => {
    setVisible(false);
    setTimeout(onClose, 300);
  };

  const loadClientInfo = async () => {
    try {
      setLoading(true);
      const res = await api.get('/clients/me/');
      setClientInfo(res.data);
    } catch (error) {
      console.error('Failed to load client info:', error);
      setError('Failed to load client information');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyToken = () => {
    if (clientInfo?.tag) {
      navigator.clipboard.writeText(clientInfo.tag);
      setCopied(true);
      setSuccess('Client token copied to clipboard!');
      setTimeout(() => {
        setCopied(false);
        setSuccess('');
      }, 2000);
    }
  };

  const handleDownload = () => {
    window.open(extensionDownloadUrl, '_blank', 'noopener,noreferrer');
  };

  const extensionEnabled = clientInfo?.extension_enabled || false;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black transition-opacity duration-300 ${
          visible ? 'opacity-40' : 'opacity-0'
        }`}
        onClick={handleClose}
      />

      {/* Sidebar */}
      <div
        className={`relative w-full max-w-md h-full bg-white dark:bg-gray-800 shadow-2xl
          transform transition-transform duration-300 ease-out
          ${visible ? 'translate-x-0' : 'translate-x-full'}
          flex flex-col`}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Chrome Extension
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Web AI Agent for browsing, scraping &amp; social bridge auth
            </p>
          </div>
          <button
            onClick={handleClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-primary-500" size={28} />
            </div>
          ) : (
            <>
              {error && (
                <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="text-red-600 dark:text-red-400 mt-0.5 shrink-0" size={16} />
                    <div className="text-sm text-red-700 dark:text-red-200">{error}</div>
                  </div>
                </div>
              )}

              {success && (
                <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700">
                  <div className="flex items-start gap-2">
                    <Check className="text-green-600 dark:text-green-400 mt-0.5 shrink-0" size={16} />
                    <div className="text-sm text-green-700 dark:text-green-200">{success}</div>
                  </div>
                </div>
              )}

              {!extensionEnabled ? (
                <div className="p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="text-yellow-600 dark:text-yellow-400 mt-0.5 shrink-0" size={16} />
                    <div className="text-sm text-yellow-700 dark:text-yellow-200">
                      <p className="font-medium mb-1">Extension is disabled</p>
                      <p>Ask Concierge support to enable it for your account.</p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Download */}
                  <div>
                    <button
                      type="button"
                      onClick={handleDownload}
                      className="w-full px-4 py-3 rounded-xl bg-primary-600 dark:bg-primary-500 text-white
                        hover:bg-primary-700 dark:hover:bg-primary-600 transition-colors
                        flex items-center justify-center gap-2 font-medium shadow-sm"
                    >
                      <Download size={18} />
                      Download Extension
                    </button>
                  </div>

                  {/* Client Token */}
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                      Client Token
                    </label>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-mono text-gray-900 dark:text-gray-100 break-all border border-gray-200 dark:border-gray-700">
                        {clientInfo?.tag || '—'}
                      </code>
                      {clientInfo?.tag && (
                        <button
                          type="button"
                          onClick={handleCopyToken}
                          className={`p-2 rounded-lg transition-colors shrink-0 ${
                            copied
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                          }`}
                        >
                          {copied ? <Check size={16} /> : <Copy size={16} />}
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-1.5">
                      Paste into extension settings
                    </p>
                  </div>

                  {/* Setup steps */}
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                      Setup
                    </label>
                    <div className="space-y-3">
                      {[
                        { n: '1', text: 'Download the ZIP above and unzip it' },
                        { n: '2', text: <>Go to <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs">chrome://extensions/</code> → enable <strong>Developer mode</strong></> },
                        { n: '3', text: 'Click "Load unpacked" → select the extension folder' },
                        { n: '4', text: 'Open the extension popup → paste your Client Token → Save' },
                      ].map((step) => (
                        <div key={step.n} className="flex items-start gap-3">
                          <span className="shrink-0 w-6 h-6 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 flex items-center justify-center text-xs font-bold">
                            {step.n}
                          </span>
                          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{step.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Capabilities */}
                  <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700">
                    <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                      Capabilities
                    </h4>
                    <div className="space-y-2">
                      {[
                        { label: 'Scrap text', desc: 'Extract content from pages → Knowledge Blocks' },
                        { label: 'Collect contacts', desc: 'Emails, phones, addresses from any page' },
                        { label: 'Social bridges', desc: 'Auth for Facebook, Instagram, LinkedIn bridges' },
                      ].map((cap) => (
                        <div key={cap.label} className="flex items-start gap-2">
                          <div className="w-1.5 h-1.5 rounded-full bg-primary-500 mt-1.5 shrink-0" />
                          <p className="text-sm text-gray-700 dark:text-gray-300">
                            <strong>{cap.label}:</strong> {cap.desc}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 p-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={handleClose}
            className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600
              text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700
              transition-colors text-sm font-medium"
          >
            {t('common.close') || 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChromeExtensionSetup;
