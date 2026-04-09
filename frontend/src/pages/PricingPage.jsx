import { useTranslation } from 'react-i18next';
import PricingPlans from '../components/subscription/PricingPlans';

const PricingPage = () => {
  const { t } = useTranslation();
  
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-2 text-gray-900 dark:text-gray-100">{t('pricing.title')}</h1>
        <p className="text-gray-600 dark:text-gray-400">{t('pricing.subtitle')}</p>
      </div>

      <PricingPlans />
    </div>
  );
};

export default PricingPage;
