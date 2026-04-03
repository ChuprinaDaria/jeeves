import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const LangflowPage = () => {
  const { t } = useTranslation();
  const [langflowUrl, setLangflowUrl] = useState('');

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_LANGFLOW_URL || window.location.origin.replace(/:\d+$/, ':7860');
    setLangflowUrl(baseUrl);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {t('nav.langflow') || 'Langflow'}
        </h1>
        <a
          href={langflowUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-primary-600 dark:text-primary-400 hover:underline"
        >
          {t('common.openInNewTab') || 'Open in new tab'}
        </a>
      </div>
      <div className="flex-1">
        {langflowUrl && (
          <iframe
            src={langflowUrl}
            title="Langflow"
            className="w-full h-full border-0"
            allow="clipboard-read; clipboard-write"
          />
        )}
      </div>
    </div>
  );
};

export default LangflowPage;
