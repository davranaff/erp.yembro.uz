import { z } from 'zod';

import type { TranslateFn, TranslateParams } from '@/shared/i18n';

type ValidationOptions = {
  t?: TranslateFn;
};

const interpolate = (template: string, params?: TranslateParams): string => {
  if (!params) {
    return template;
  }

  return Object.entries(params).reduce((result, [key, value]) => {
    return result.replaceAll(`{${key}}`, String(value));
  }, template);
};

const translateValidation = (
  key: string,
  fallback: string,
  options?: ValidationOptions,
  params?: TranslateParams,
): string => {
  if (options?.t) {
    return options.t(`validation.${key}`, params, fallback);
  }

  return interpolate(fallback, params);
};

const normalizeLabel = (label?: string): string | null => {
  if (typeof label !== 'string') {
    return null;
  }

  const trimmed = label.trim();
  return trimmed.length > 0 ? trimmed : null;
};

const resolveLabel = (label: string | undefined, fallbackLabel: string): string =>
  normalizeLabel(label) ?? fallbackLabel;

const resolveDefaultTextLabel = (options?: ValidationOptions): string =>
  translateValidation('defaultValueLabel', 'Value', options);

const resolveDefaultDateLabel = (options?: ValidationOptions): string =>
  translateValidation('defaultDateLabel', 'Date', options);

export const requiredText = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, resolveDefaultTextLabel(options));

  return z
    .string({
      required_error: translateValidation('required', '"{label}" is required.', options, {
        label: resolvedLabel,
      }),
    })
    .trim()
    .min(
      1,
      translateValidation('nonEmpty', '"{label}" cannot be empty.', options, {
        label: resolvedLabel,
      }),
    );
};

export const optionalText = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, resolveDefaultTextLabel(options));

  return z
    .string({
      invalid_type_error: translateValidation('textType', '"{label}" must be text.', options, {
        label: resolvedLabel,
      }),
    })
    .trim()
    .optional()
    .or(z.literal(''));
};

export const requiredNumber = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, resolveDefaultTextLabel(options));

  return z.number({
    required_error: translateValidation('required', '"{label}" is required.', options, {
      label: resolvedLabel,
    }),
  });
};

export const positiveNumber = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, resolveDefaultTextLabel(options));

  return z
    .number({
      required_error: translateValidation('required', '"{label}" is required.', options, {
        label: resolvedLabel,
      }),
      invalid_type_error: translateValidation(
        'numberType',
        '"{label}" must be a number.',
        options,
        { label: resolvedLabel },
      ),
    })
    .positive(
      translateValidation('positive', '"{label}" must be greater than 0.', options, {
        label: resolvedLabel,
      }),
    );
};

export const requiredEmail = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, 'Email');

  return requiredText(resolvedLabel, options).email(
    translateValidation('validEmail', 'Enter a valid {label}.', options, { label: resolvedLabel }),
  );
};

export const optionalEmail = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, 'Email');

  return z
    .string()
    .trim()
    .toLowerCase()
    .email(
      translateValidation('validEmail', 'Enter a valid {label}.', options, {
        label: resolvedLabel,
      }),
    )
    .optional()
    .or(z.literal(''));
};

export const dateString = (label?: string, options?: ValidationOptions) => {
  const resolvedLabel = resolveLabel(label, resolveDefaultDateLabel(options));

  return z
    .string({
      required_error: translateValidation('required', '"{label}" is required.', options, {
        label: resolvedLabel,
      }),
    })
    .trim()
    .regex(
      /^\d{4}-\d{2}-\d{2}$/,
      translateValidation('dateFormat', '"{label}" must be in YYYY-MM-DD format.', options, {
        label: resolvedLabel,
      }),
    );
};
