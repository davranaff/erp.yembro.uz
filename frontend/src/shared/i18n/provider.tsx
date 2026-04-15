import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { messages } from './messages';

import type { Language, TranslateFn, TranslateParams } from './types';

const STORAGE_KEY = 'frontend:language';
const FALLBACK_LANGUAGE: Language = 'ru';

const LOCALES: Record<Language, string> = {
  uz: 'uz-UZ',
  ru: 'ru-RU',
  en: 'en-US',
};

type I18nContextValue = {
  language: Language;
  locale: string;
  setLanguage: (language: Language) => void;
  t: TranslateFn;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function resolveMessage(language: Language, key: string): string | undefined {
  const segments = key.split('.');
  let current: unknown = messages[language];

  for (const segment of segments) {
    if (typeof current !== 'object' || current === null || !(segment in current)) {
      return undefined;
    }

    current = (current as Record<string, unknown>)[segment];
  }

  return typeof current === 'string' ? current : undefined;
}

function interpolate(template: string, params?: TranslateParams): string {
  if (!params) {
    return template;
  }

  return Object.entries(params).reduce((result, [key, value]) => {
    return result.replaceAll(`{${key}}`, String(value));
  }, template);
}

function loadLanguage(): Language {
  if (typeof window === 'undefined') {
    return FALLBACK_LANGUAGE;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'uz' || stored === 'ru' || stored === 'en') {
    return stored;
  }

  return FALLBACK_LANGUAGE;
}

export function getIntlLocale(language: Language): string {
  return LOCALES[language];
}

export function I18nProvider({ children }: PropsWithChildren) {
  const [language, setLanguage] = useState<Language>(() => loadLanguage());

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, language);
    }

    if (typeof document !== 'undefined') {
      document.documentElement.lang = language;
    }
  }, [language]);

  const t = useCallback<TranslateFn>(
    (key, params, fallback) => {
      const template =
        resolveMessage(language, key) ?? resolveMessage(FALLBACK_LANGUAGE, key) ?? fallback;

      if (!template) {
        return key;
      }

      return interpolate(template, params);
    },
    [language],
  );

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      locale: getIntlLocale(language),
      setLanguage,
      t,
    }),
    [language, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);

  if (!context) {
    throw new Error('useI18n must be used inside I18nProvider');
  }

  return context;
}
