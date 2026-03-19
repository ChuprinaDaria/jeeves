import { useTranslation } from 'react-i18next';

const CATEGORIES = [
  { key: 'all', labelKey: 'tools.allCategories' },
  { key: 'communication', labelKey: 'tools.categories.communication' },
  { key: 'ai', labelKey: 'tools.categories.ai' },
  { key: 'productivity', labelKey: 'tools.categories.productivity' },
  { key: 'analytics', labelKey: 'tools.categories.analytics' },
  { key: 'crm', labelKey: 'tools.categories.crm' },
  { key: 'custom', labelKey: 'tools.categories.custom' },
];

const CategoryFilter = ({ active, onChange }) => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap gap-2">
      {CATEGORIES.map(({ key, labelKey }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            active === key
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          {t(labelKey)}
        </button>
      ))}
    </div>
  );
};

export default CategoryFilter;
