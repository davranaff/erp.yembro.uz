import type { Paginated } from '@/types/auth';

/**
 * DRF-эндпоинты иногда возвращают {results: [...]}, а иногда — массив.
 * Этот хелпер приводит ответ к массиву.
 */
export function asList<T>(payload: Paginated<T> | T[]): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === 'object' && 'results' in payload) {
    return payload.results;
  }
  return [];
}
