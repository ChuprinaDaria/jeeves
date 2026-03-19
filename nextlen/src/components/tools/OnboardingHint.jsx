import { ArrowDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const OnboardingHint = () => {
  const { t } = useTranslation();

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-start pt-8 pointer-events-none z-10">
      <div className="flex flex-col items-center gap-2">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
          {t('tools.flow.onboarding')}
        </p>
        <ArrowDown
          className="w-6 h-6 text-primary-400 dark:text-primary-500"
          style={{ animation: 'flow-pulse-arrow 2s ease-in-out infinite' }}
        />
      </div>
    </div>
  );
};

export default OnboardingHint;
