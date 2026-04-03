import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';

const LangflowPage = () => {
  const { t } = useTranslation();
  const [langflowUrl, setLangflowUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const iframeRef = useRef(null);

  useEffect(() => {
    const apiBase = (import.meta.env.VITE_API_URL || 'https://api.nexelin.com').replace(/\/api\/?$/, '');
    const baseUrl = import.meta.env.VITE_LANGFLOW_URL || `${apiBase}/langflow/`;
    setLangflowUrl(baseUrl);
  }, []);

  const handleLoad = () => {
    setLoading(false);
    setError(false);
  };

  const handleError = () => {
    setLoading(false);
    setError(true);
  };

  const handleRetry = () => {
    setLoading(true);
    setError(false);
    if (iframeRef.current) {
      iframeRef.current.src = langflowUrl;
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {t('nav.langflow') || 'Langflow'}
        </h1>
        <div className="flex items-center gap-3">
          {error && (
            <button
              onClick={handleRetry}
              className="text-sm text-primary-600 dark:text-primary-400 hover:underline"
            >
              {t('common.retry') || 'Retry'}
            </button>
          )}
          <a
            href={langflowUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-primary-600 dark:text-primary-400 hover:underline"
          >
            {t('common.openInNewTab') || 'Open in new tab'}
          </a>
        </div>
      </div>
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-gray-900">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-3"></div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t('common.loading') || 'Loading...'}
              </p>
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-gray-900">
            <div className="text-center max-w-md">
              <p className="text-gray-700 dark:text-gray-300 mb-2">
                {t('langflow.connectionError') || "Couldn't connect to Langflow"}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                {t('langflow.connectionErrorHint') || 'Make sure the Langflow service is running'}
              </p>
              <button
                onClick={handleRetry}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm"
              >
                {t('common.retry') || 'Retry'}
              </button>
            </div>
          </div>
        )}
        {langflowUrl && (
          <iframe
            ref={iframeRef}
            src={langflowUrl}
            title="Langflow"
            className="w-full h-full border-0"
            allow="clipboard-read; clipboard-write"
            onLoad={handleLoad}
            onError={handleError}
          />
        )}
      </div>
    </div>
  );
};

export default LangflowPage;
