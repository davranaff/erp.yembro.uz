import type { Language } from './types';

export type PluralForms = {
  one: string;
  few?: string;
  many?: string;
  other: string;
};

const buildResolver = (language: Language) => {
  try {
    return new Intl.PluralRules(
      language === 'uz' ? 'uz-UZ' : language === 'ru' ? 'ru-RU' : 'en-US',
    );
  } catch {
    return null;
  }
};

const resolverCache = new Map<Language, Intl.PluralRules | null>();

const getResolver = (language: Language): Intl.PluralRules | null => {
  if (!resolverCache.has(language)) {
    resolverCache.set(language, buildResolver(language));
  }
  return resolverCache.get(language) ?? null;
};

export function pluralize(language: Language, count: number, forms: PluralForms): string {
  const resolver = getResolver(language);
  const rule = resolver ? resolver.select(count) : count === 1 ? 'one' : 'other';
  switch (rule) {
    case 'one':
      return forms.one;
    case 'few':
      return forms.few ?? forms.other;
    case 'many':
      return forms.many ?? forms.other;
    default:
      return forms.other;
  }
}

export function formatCount(language: Language, count: number, forms: PluralForms): string {
  return `${count} ${pluralize(language, count, forms)}`;
}
