import { enUS, ru, uz } from 'date-fns/locale';

import { getIntlLocale } from './provider';

import type { Language } from './types';
import type { Locale } from 'date-fns';

const DATE_FNS_LOCALES: Record<Language, Locale> = {
  uz,
  ru,
  en: enUS,
};

export const getDateFnsLocale = (language: Language): Locale => DATE_FNS_LOCALES[language];

export function formatLocalizedDate(
  language: Language,
  value: Date | string | number,
  options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  },
): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  try {
    return new Intl.DateTimeFormat(getIntlLocale(language), options).format(date);
  } catch {
    return date.toISOString();
  }
}

export function formatLocalizedNumber(
  language: Language,
  value: number,
  options: Intl.NumberFormatOptions = {},
): string {
  try {
    return new Intl.NumberFormat(getIntlLocale(language), options).format(value);
  } catch {
    return String(value);
  }
}
