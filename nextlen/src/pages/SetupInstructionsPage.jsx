import { useTranslation } from 'react-i18next';
import { BookOpen } from 'lucide-react';
import PromptBook from '../components/training/PromptBook';

const SetupInstructionsPage = () => {
  const { t } = useTranslation();

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <BookOpen size={28} className="text-primary-600 dark:text-primary-400" />
          {t('nav.promptBook') || 'Prompt Book'}
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          {t('promptBook.pageSubtitle') || 'Browse and use pre-built prompts for your AI assistant'}
        </p>
      </div>

      <PromptBook showHeader={false} />
    </div>
  );
};

export default SetupInstructionsPage;
