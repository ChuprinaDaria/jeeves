import { X, Copy, Check, Code, Monitor } from 'lucide-react';
import { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useTranslation } from 'react-i18next';

const WebWidgetSetup = ({ onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [widgetEnabled, setWidgetEnabled] = useState(false);
  const [widgetData, setWidgetData] = useState(null);
  const [copied, setCopied] = useState({});
  const [activeTab, setActiveTab] = useState('widget'); // 'widget' or 'iframe'

  useEffect(() => {
    loadWidgetConfig();
  }, []);

  const loadWidgetConfig = async () => {
    try {
      setLoading(true);
      const res = await api.get('/clients/web-widget/config/');
      setWidgetEnabled(res.data.widget_enabled || false);
      setWidgetData(res.data);
    } catch (error) {
      console.error('Failed to load widget config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    try {
      setSaving(true);
      const res = await api.patch('/clients/web-widget/config/', {
        widget_enabled: !widgetEnabled
      });
      setWidgetEnabled(res.data.widget_enabled);
      setWidgetData(res.data);
    } catch (error) {
      console.error('Failed to update widget config:', error);
      alert('Failed to update widget configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(prev => ({ ...prev, [key]: true }));
    setTimeout(() => {
      setCopied(prev => ({ ...prev, [key]: false }));
    }, 2000);
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto p-2 sm:p-4 safe-top safe-bottom">
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 sm:p-6 max-w-4xl w-full max-h-[calc(100vh-env(safe-area-inset-top)-env(safe-area-inset-bottom)-1rem)] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            {t('integrations.setupWebWidget') || 'Web Widget Setup'}
          </h3>
          <button 
            onClick={onClose} 
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X size={24} />
          </button>
        </div>

        <div className="space-y-6">
          {/* Enable/Disable Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div>
              <h4 className="font-medium text-gray-900 dark:text-gray-100">
                {t('integrations.enableWidget') || 'Enable Web Widget'}
              </h4>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                {t('integrations.widgetDescription') || 'Enable web widget for embedding on your website'}
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={widgetEnabled}
                onChange={handleToggle}
                disabled={saving}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {widgetEnabled && widgetData && (
            <>
              {/* Tabs */}
              <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => setActiveTab('widget')}
                  className={`px-4 py-2 font-medium text-sm ${
                    activeTab === 'widget'
                      ? 'text-blue-600 border-b-2 border-blue-600 dark:text-blue-400'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                >
                  <Code size={16} className="inline mr-2" />
                  Widget Code
                </button>
                <button
                  onClick={() => setActiveTab('iframe')}
                  className={`px-4 py-2 font-medium text-sm ${
                    activeTab === 'iframe'
                      ? 'text-blue-600 border-b-2 border-blue-600 dark:text-blue-400'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                >
                  <Monitor size={16} className="inline mr-2" />
                  Iframe Code
                </button>
              </div>

              {/* Widget Code Tab */}
              {activeTab === 'widget' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                      {t('integrations.widgetCode') || 'Widget Code'}
                    </label>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {t('integrations.widgetInstructions') || 'Copy and paste this code before the closing </body> tag on your website'}
                    </p>
                    <div className="relative">
                      <textarea
                        readOnly
                        value={widgetData.widget_code_html || ''}
                        className="w-full p-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg font-mono text-sm"
                        rows={6}
                      />
                      <button
                        onClick={() => handleCopy(widgetData.widget_code_html, 'widget')}
                        className="absolute top-3 right-3 p-2 bg-white dark:bg-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-500"
                      >
                        {copied.widget ? (
                          <Check size={18} className="text-green-600" />
                        ) : (
                          <Copy size={18} className="text-gray-600 dark:text-gray-300" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                      {t('integrations.widgetUrl') || 'Widget URL'}
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        readOnly
                        value={widgetData.widget_url || ''}
                        className="flex-1 p-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
                      />
                      <button
                        onClick={() => handleCopy(widgetData.widget_url, 'widgetUrl')}
                        className="px-4 py-2 bg-gray-100 dark:bg-gray-600 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-500"
                      >
                        {copied.widgetUrl ? (
                          <Check size={18} className="text-green-600" />
                        ) : (
                          <Copy size={18} className="text-gray-600 dark:text-gray-300" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Iframe Code Tab */}
              {activeTab === 'iframe' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                      {t('integrations.iframeCode') || 'Iframe Code'}
                    </label>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {t('integrations.iframeInstructions') || 'Copy and paste this code where you want to embed the chat'}
                    </p>
                    <div className="relative">
                      <textarea
                        readOnly
                        value={widgetData.iframe_code_html || ''}
                        className="w-full p-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg font-mono text-sm"
                        rows={6}
                      />
                      <button
                        onClick={() => handleCopy(widgetData.iframe_code_html, 'iframe')}
                        className="absolute top-3 right-3 p-2 bg-white dark:bg-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-500"
                      >
                        {copied.iframe ? (
                          <Check size={18} className="text-green-600" />
                        ) : (
                          <Copy size={18} className="text-gray-600 dark:text-gray-300" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                      {t('integrations.iframeUrl') || 'Iframe URL'}
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        readOnly
                        value={widgetData.iframe_url || ''}
                        className="flex-1 p-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
                      />
                      <button
                        onClick={() => handleCopy(widgetData.iframe_url, 'iframeUrl')}
                        className="px-4 py-2 bg-gray-100 dark:bg-gray-600 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-500"
                      >
                        {copied.iframeUrl ? (
                          <Check size={18} className="text-green-600" />
                        ) : (
                          <Copy size={18} className="text-gray-600 dark:text-gray-300" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {!widgetEnabled && (
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                {t('integrations.widgetDisabled') || 'Enable the widget to see the integration code'}
              </p>
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button onClick={onClose} className="btn-primary flex-1">
              {t('common.close') || 'Close'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WebWidgetSetup;

