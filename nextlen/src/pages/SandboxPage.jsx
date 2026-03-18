import { useTranslation } from 'react-i18next';
import { FlaskConical, ArrowRight, GraduationCap } from 'lucide-react';
import ChatWindow from '../components/sandbox/ChatWindow';
import PhotoUploadTest from '../components/sandbox/PhotoUploadTest';

const SandboxPage = () => {
  const { t } = useTranslation();

  // Функція для навігації, яка працює і в /l/:tag/ режимі і в звичайному
  const handleGoToTraining = () => {
    // Новий формат: /l/:tag/sandbox → /l/:tag/training
    const pathMatch = window.location.pathname.match(/^\/l\/([^/]+)/);
    if (pathMatch) {
      window.location.href = `/l/${pathMatch[1]}/training`;
      return;
    }
    // Старий формат: /l?tag=xxx
    const isOldClientMode = window.location.pathname === '/l' && window.location.search.includes('tag=');
    if (isOldClientMode) {
      window.dispatchEvent(new CustomEvent('nexelin:navigate', { detail: { view: 'training' } }));
    } else {
      window.location.href = '/training';
    }
  };
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('sandbox.title')}</h1>
        <p className="text-gray-600 dark:text-gray-400">{t('sandbox.subtitle')}</p>
      </div>

      {/* Info banner about new location */}
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 border border-purple-200 dark:border-purple-800 rounded-xl p-4">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
            <FlaskConical className="text-white" size={20} />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-purple-900 dark:text-purple-100 mb-1">
              {t('sandbox.newLocationTitle') || 'Sandbox is now also available in Train AI!'}
            </h3>
            <p className="text-sm text-purple-700 dark:text-purple-300 mb-3">
              {t('sandbox.newLocationDescription') || 'For your convenience, you can now test your AI assistant directly on the Train AI page, right after configuring the AI behavior prompt.'}
            </p>
            <button
              onClick={handleGoToTraining}
              className="inline-flex items-center gap-2 text-sm font-medium text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 transition-colors"
            >
              <GraduationCap size={16} />
              {t('sandbox.goToTraining') || 'Go to Train AI'}
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChatWindow />
        </div>

        <div>
          <PhotoUploadTest />
        </div>
      </div>
    </div>
  );
};

export default SandboxPage;
