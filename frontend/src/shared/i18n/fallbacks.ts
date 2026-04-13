import type { Language } from './types';

const STORAGE_KEY = 'frontend:language';
const FALLBACK_LANGUAGE: Language = 'ru';

const UNKNOWN_ERROR_MESSAGES: Record<Language, string> = {
  ru: 'Неизвестная ошибка',
  uz: 'Nomaʼlum xato',
  en: 'Unknown error',
};

export const getStoredLanguage = (): Language => {
  if (typeof window === 'undefined') {
    return FALLBACK_LANGUAGE;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'uz' || stored === 'ru' || stored === 'en') {
    return stored;
  }

  return FALLBACK_LANGUAGE;
};

export const getUnknownErrorLabel = (): string => UNKNOWN_ERROR_MESSAGES[getStoredLanguage()];
