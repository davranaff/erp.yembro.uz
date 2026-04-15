export type Language = 'uz' | 'ru' | 'en';

export type TranslateParams = Record<string, string | number>;

export type TranslateFn = (key: string, params?: TranslateParams, fallback?: string) => string;
