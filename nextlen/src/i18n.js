import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import translations
import enTranslation from './locales/en/translation.json';
import deTranslation from './locales/de/translation.json';
import frTranslation from './locales/fr/translation.json';
import esTranslation from './locales/es/translation.json';
import itTranslation from './locales/it/translation.json';
import nlTranslation from './locales/nl/translation.json';
import daTranslation from './locales/da/translation.json';

const resources = {
  en: { translation: enTranslation },
  de: { translation: deTranslation },
  fr: { translation: frTranslation },
  es: { translation: esTranslation },
  it: { translation: itTranslation },
  nl: { translation: nlTranslation },
  da: { translation: daTranslation },
};

// Get saved language or use browser language
const savedLanguage = localStorage.getItem('language');
const browserLanguage = navigator.language.split('-')[0];
const defaultLanguage = savedLanguage || (resources[browserLanguage] ? browserLanguage : 'en');

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: defaultLanguage,
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
  });

// Save language when it changes
i18n.on('languageChanged', (lng) => {
  localStorage.setItem('language', lng);
});

export default i18n;
