import { getLocales } from 'expo-localization';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './en.json';
import fr from './fr.json';
import { normalizeLanguage } from '@/utils/language';

const deviceLanguage = normalizeLanguage(getLocales()[0]?.languageCode);

void i18n.use(initReactI18next).init({
  compatibilityJSON: 'v4',
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
  lng: deviceLanguage,
  resources: {
    en: { translation: en },
    fr: { translation: fr },
  },
});

export { i18n };
