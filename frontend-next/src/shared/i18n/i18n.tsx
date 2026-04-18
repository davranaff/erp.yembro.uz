import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { LOCALES, messages } from './messages';
import type { Locale, TranslateFn, TranslateParams } from './types';

const STORAGE_KEY = 'frontend-next:locale';

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: TranslateFn;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function loadInitialLocale(): Locale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && (LOCALES as readonly string[]).includes(raw)) {
      return raw as Locale;
    }
  } catch {
    // ignore
  }
  return 'ru';
}

function interpolate(template: string, params: TranslateParams | undefined): string {
  if (!params) return template;
  return Object.entries(params).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => loadInitialLocale());

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      // ignore
    }
  }, [locale]);

  const t: TranslateFn = useCallback(
    (key, params, fallback) => {
      const entry = messages[key];
      const raw = entry?.[locale] ?? entry?.ru ?? fallback ?? key;
      return interpolate(raw, params);
    },
    [locale],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale: setLocaleState, t }),
    [locale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n must be used inside <I18nProvider>');
  }
  return ctx;
}
