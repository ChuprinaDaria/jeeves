import { ArrowDown } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';

const OnboardingHint = () => {
  const { t } = useTranslation();

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-start pt-8 pointer-events-none z-10">
      <div className="flex flex-col items-center gap-2">
        <p className="font-mono text-[11px] uppercase tracking-wider text-fog">
          {t('tools.flow.dragToConnect', t('tools.flow.onboarding'))}
        </p>
        <ArrowDown
          weight="light"
          size={22}
          className="text-iris"
          style={{ animation: 'flow-pulse-arrow 2s ease-in-out infinite' }}
        />
      </div>
    </div>
  );
};

export default OnboardingHint;
