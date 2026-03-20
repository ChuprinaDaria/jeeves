import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Moon, Sun } from 'lucide-react';
import LanguageSwitcher from '../common/LanguageSwitcher';
import { useTheme } from '../../context/ThemeContext';
import { clientAPI } from '../../api/client';
import { updateBrandingFromClient } from '../../utils/helpers';

const Header = () => {
  const { t } = useTranslation();
  const { darkMode, toggleDarkMode } = useTheme();
  const [clientName, setClientName] = useState('');
  const [clientDescription, setClientDescription] = useState('');

  useEffect(() => {
    const loadClientInfo = async () => {
      try {
        const response = await clientAPI.getMe();
        const data = response.data || {};

        // Ім'я клієнта / організації – завжди показуємо саме його
        const name =
          data.company_name ||
          data.user ||
          t('dashboard.welcomeBack');

        // Для white label можемо показувати description як підзаголовок,
        // для інших клієнтів – стандартний текст "керуйте асистентом"
        const isWhiteLabel = data.client_type === 'white_label';
        const description = isWhiteLabel
          ? (data.description || t('dashboard.manageAssistant'))
          : t('dashboard.manageAssistant');

        setClientName(name);
        setClientDescription(description);

        // Оновлюємо заголовок вкладки та favicon під КЛІЄНТА (для всіх типів)
        updateBrandingFromClient(data, { context: 'portal' });
      } catch {
        // Фолбек, якщо бекенд недоступний
        setClientName(t('dashboard.welcomeBack'));
        setClientDescription(t('dashboard.manageAssistant'));
      }
    };

    loadClientInfo();
  }, [t]);

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xl font-semibold text-gray-800 dark:text-gray-100">
            {clientName || t('dashboard.welcomeBack')}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {clientDescription || t('dashboard.manageAssistant')}
          </p>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={toggleDarkMode}
            className="flex items-center gap-2 px-3 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title={darkMode ? 'Light Mode' : 'Dark Mode'}
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
};

export default Header;


