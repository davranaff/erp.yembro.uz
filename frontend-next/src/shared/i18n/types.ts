export type Locale = 'ru' | 'uz' | 'en';

export type TranslateParams = Record<string, string | number>;

export type TranslateFn = (
  key: string,
  params?: TranslateParams,
  fallback?: string,
) => string;

export type Messages = Record<string, Record<string, string>>;
