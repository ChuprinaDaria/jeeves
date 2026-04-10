import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from '@phosphor-icons/react';

const LANGUAGES = [
  { code: 'en', name: 'English',    flagUrl: 'https://flagcdn.com/24x18/gb.png' },
  { code: 'de', name: 'Deutsch',    flagUrl: 'https://flagcdn.com/24x18/de.png' },
  { code: 'fr', name: 'Français',   flagUrl: 'https://flagcdn.com/24x18/fr.png' },
  { code: 'es', name: 'Español',    flagUrl: 'https://flagcdn.com/24x18/es.png' },
  { code: 'it', name: 'Italiano',   flagUrl: 'https://flagcdn.com/24x18/it.png' },
  { code: 'nl', name: 'Nederlands', flagUrl: 'https://flagcdn.com/24x18/nl.png' },
  { code: 'da', name: 'Dansk',      flagUrl: 'https://flagcdn.com/24x18/dk.png' },
];

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const current = LANGUAGES.find((l) => l.code === i18n.language) || LANGUAGES[0];

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-sm text-slate
                   border-[1.5px] border-rule hover:border-iris hover:text-ink
                   transition-colors bg-paper"
      >
        <Globe size={16} weight="light" />
        <img
          src={current.flagUrl}
          alt={current.code.toUpperCase()}
          className="w-4 h-3 rounded-[2px] object-cover"
          onError={(e) => { e.target.style.display = 'none'; }}
        />
        <span className="font-mono text-[11px] tracking-wider">{current.code.toUpperCase()}</span>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 mt-2 w-48 bg-paper rounded-lg border-[1.5px] border-rule
                          shadow-ink-sm py-2 z-20">
            {LANGUAGES.map((lang) => {
              const active = i18n.language === lang.code;
              return (
                <button
                  key={lang.code}
                  onClick={() => changeLanguage(lang.code)}
                  className={`w-full text-left px-4 py-2 flex items-center gap-3 transition-colors ${
                    active ? 'bg-linen text-ink' : 'text-slate hover:bg-mist hover:text-ink'
                  }`}
                >
                  <img
                    src={lang.flagUrl}
                    alt={lang.code.toUpperCase()}
                    className="w-5 h-4 rounded-[2px] object-cover"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                  <span className="text-[13px] font-medium">{lang.name}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default LanguageSwitcher;
