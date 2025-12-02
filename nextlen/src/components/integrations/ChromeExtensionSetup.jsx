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

  const extensionDownloadUrl =
    import.meta.env.VITE_EXTENSION_DOWNLOAD_URL ||
    'https://app.nexelin.com/static/extensions/nexelin-chrome-extension.zip';

  useEffect(() => {
    loadClientInfo();
  }, []);

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

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-2xl w-full mx-4">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={32} />
          </div>
        </div>
      </div>
    );
  }

  const extensionEnabled = clientInfo?.extension_enabled || false;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-2xl w-full mx-4 my-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              Google Chrome Extension Setup
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Web AI Agent for browsing & automation. Scrape pages into Knowledge Blocks and collect contact data.
            </p>
          </div>
          <button 
            onClick={onClose} 
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X size={24} />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
            <div className="flex items-start gap-2">
              <AlertCircle className="text-red-600 dark:text-red-400 mt-0.5" size={18} />
              <div className="text-sm text-red-700 dark:text-red-200">{error}</div>
            </div>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700">
            <div className="flex items-start gap-2">
              <Check className="text-green-600 dark:text-green-400 mt-0.5" size={18} />
              <div className="text-sm text-green-700 dark:text-green-200">{success}</div>
            </div>
          </div>
        )}

        {!extensionEnabled ? (
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700">
              <div className="flex items-start gap-2">
                <AlertCircle className="text-yellow-600 dark:text-yellow-400 mt-0.5" size={18} />
                <div className="text-sm text-yellow-700 dark:text-yellow-200">
                  <p className="font-medium mb-1">Extension is disabled</p>
                  <p>Ask Nexelin support to enable the browser extension for your account in the admin panel.</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Client Token Section */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Client token (X-Client-Token)
              </label>
              <div className="flex items-center gap-2">
                <code className="flex-1 px-3 py-2 bg-gray-100 dark:bg-gray-900 rounded-lg text-sm font-mono text-gray-900 dark:text-gray-100 break-all">
                  {clientInfo?.tag || '—'}
                </code>
                {clientInfo?.tag && (
                  <button
                    type="button"
                    onClick={handleCopyToken}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                      copied
                        ? 'bg-green-600 dark:bg-green-500 text-white'
                        : 'bg-primary-600 dark:bg-primary-500 text-white hover:bg-primary-700 dark:hover:bg-primary-600'
                    }`}
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                    {copied ? 'Copied!' : t('common.copy') || 'Copy'}
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                Paste this token into extension settings. All requests use header <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-900 rounded">X-Client-Token</code>.
              </p>
            </div>

            {/* Download Section */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Download Extension
              </label>
              <button
                type="button"
                onClick={handleDownload}
                className="w-full px-4 py-3 rounded-lg bg-primary-600 dark:bg-primary-500 text-white hover:bg-primary-700 dark:hover:bg-primary-600 transition-colors flex items-center justify-center gap-2 font-medium"
              >
                <Download size={20} />
                Download Chrome Extension ZIP
              </button>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                Download the extension ZIP file and load it via Developer mode in Chrome.
              </p>
            </div>

            {/* Instructions Section */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Installation & Usage Instructions
              </label>
              <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700 dark:text-gray-300">
                <li>
                  <strong>Download the extension:</strong> Click the download button above to get the ZIP file.
                </li>
                <li>
                  <strong>Enable Developer mode:</strong> Open Chrome and go to <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-900 rounded">chrome://extensions/</code>, then enable "Developer mode" in the top right.
                </li>
                <li>
                  <strong>Load the extension:</strong> Click "Load unpacked" and select the extracted extension folder.
                </li>
                <li>
                  <strong>Configure the extension:</strong> Open the extension popup, paste your client token (copied above) and click "Save token".
                </li>
                <li>
                  <strong>Use the extension:</strong> Navigate to any website and use the buttons "Scrap text" or "Collect mails" in the extension popup to add content to your Knowledge Blocks.
                </li>
              </ol>
            </div>

            {/* Features Section */}
            <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700">
              <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                What the extension does:
              </h4>
              <ul className="list-disc list-inside space-y-1 text-sm text-blue-800 dark:text-blue-200">
                <li><strong>Scrap text:</strong> Extracts structured content (headings, lists, tables, quotes) from pages and saves them to Knowledge Blocks with embeddings.</li>
                <li><strong>Collect mails:</strong> Extracts emails, phone numbers, and addresses from pages and stores them for easy access.</li>
                <li>All data is organized by website domain and accessible in the "Extension data" tab.</li>
              </ul>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            {t('common.close') || 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChromeExtensionSetup;

