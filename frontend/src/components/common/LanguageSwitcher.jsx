import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const languages = [
    { code: 'en', name: 'English', flag: '🇬🇧', flagUrl: 'https://flagcdn.com/24x18/gb.png' },
    { code: 'de', name: 'Deutsch', flag: '🇩🇪', flagUrl: 'https://flagcdn.com/24x18/de.png' },
    { code: 'fr', name: 'Français', flag: '🇫🇷', flagUrl: 'https://flagcdn.com/24x18/fr.png' },
    { code: 'es', name: 'Español', flag: '🇪🇸', flagUrl: 'https://flagcdn.com/24x18/es.png' },
    { code: 'it', name: 'Italiano', flag: '🇮🇹', flagUrl: 'https://flagcdn.com/24x18/it.png' },
    { code: 'nl', name: 'Nederlands', flag: '🇳🇱', flagUrl: 'https://flagcdn.com/24x18/nl.png' },
    { code: 'da', name: 'Dansk', flag: '🇩🇰', flagUrl: 'https://flagcdn.com/24x18/dk.png' },
  ];

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
      >
        <Globe size={18} />
        <span className="flex items-center gap-1 text-sm">
          <img
            src={currentLanguage.flagUrl}
            alt={currentLanguage.code.toUpperCase()}
            className="w-4 h-3 rounded-sm object-cover"
            onError={(e) => {
              // Фолбек: якщо зображення не завантажилось, просто ховаємо його
              e.target.style.display = 'none';
            }}
          />
          <span>{currentLanguage.code.toUpperCase()}</span>
        </span>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-20">
            {languages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => changeLanguage(lang.code)}
                className={`w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-3 ${
                  i18n.language === lang.code ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400' : 'text-gray-700 dark:text-gray-300'
                }`}
              >
                <span className="flex items-center gap-2">
                  <img
                    src={lang.flagUrl}
                    alt={lang.code.toUpperCase()}
                    className="w-5 h-4 rounded-sm object-cover"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                  <span className="text-sm font-medium">{lang.name}</span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default LanguageSwitcher;
