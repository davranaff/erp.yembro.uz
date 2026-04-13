import { format, isValid, parseISO } from 'date-fns';

export const toDate = (value: string | number | Date | null | undefined): Date | null => {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed = typeof value === 'string' ? parseISO(value) : new Date(value);
  return isValid(parsed) ? parsed : null;
};

export const formatDate = (
  value: string | number | Date | null | undefined,
  pattern = 'PPP',
): string => {
  const date = toDate(value);
  return date ? format(date, pattern) : '—';
};

export const toIsoString = (value: string | number | Date | null | undefined): string | null => {
  const date = toDate(value);
  return date ? date.toISOString() : null;
};
