'use client';

/**
 * Мини-фабрика стандартных CRUD-хуков поверх React Query.
 *
 *   const cp = makeCrud<Counterparty>({
 *     key: ['counterparties'],
 *     path: '/api/counterparties/',
 *   });
 *   cp.useList({ kind: 'supplier' });
 *   cp.useCreate();
 *   cp.useUpdate();
 *   cp.useDelete();
 *
 * Всё что нужно — определить сам тип. Дефолтный ordering можно
 * переопределить. Организационный scope прикрепляется автоматически
 * через apiFetch (X-Organization-Code).
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from '@tanstack/react-query';

import { ApiError, apiFetch, type ApiInit } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Paginated } from '@/types/auth';

export interface CrudOptions {
  /** Ключ запроса. Фильтры будут добавлены как строка querystring. */
  key: QueryKey;
  /** Путь ViewSet-а (с завершающим слешем). */
  path: string;
  /** Default ordering query. */
  ordering?: string;
  /** staleTime в мс, default 30_000. */
  staleTime?: number;
  /** skipOrg — если endpoint не требует X-Organization-Code. */
  skipOrg?: boolean;
}

export function buildQs(filter: Record<string, string | number | undefined | null>, ordering?: string) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) {
    if (v === undefined || v === null || v === '') continue;
    params.set(k, String(v));
  }
  if (ordering) params.set('ordering', ordering);
  return params.toString();
}

export function makeCrud<T extends { id: string }, CreateT = Partial<T>, UpdateT = Partial<T>>(
  opts: CrudOptions,
) {
  const { key, path, ordering, staleTime = 30_000, skipOrg } = opts;

  function useList(filter: Record<string, string | number | undefined | null> = {}) {
    const qs = buildQs(filter, ordering);
    return useQuery<T[], ApiError>({
      queryKey: [...key, qs],
      queryFn: async () => {
        const data = await apiFetch<Paginated<T> | T[]>(
          qs ? `${path}?${qs}` : path,
          skipOrg ? { skipOrg: true } : undefined,
        );
        return asList(data);
      },
      staleTime,
    });
  }

  function useCreate() {
    const qc = useQueryClient();
    return useMutation<T, ApiError, CreateT>({
      mutationFn: (body) =>
        apiFetch<T>(path, {
          method: 'POST',
          body: body as unknown as ApiInit['body'],
          ...(skipOrg ? { skipOrg: true } : {}),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: key }),
    });
  }

  function useUpdate() {
    const qc = useQueryClient();
    return useMutation<T, ApiError, { id: string; patch: UpdateT }>({
      mutationFn: ({ id, patch }) =>
        apiFetch<T>(`${path}${id}/`, {
          method: 'PATCH',
          body: patch as unknown as ApiInit['body'],
          ...(skipOrg ? { skipOrg: true } : {}),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: key }),
    });
  }

  /**
   * Удаление. Принимает либо строковый id (старый API), либо объект {id, reason}
   * (для viewset'ов с DeleteReasonMixin — reason пробрасывается в audit log).
   * Reason передаётся через query string ?reason=... чтобы работало с любым backend.
   */
  function useDelete() {
    const qc = useQueryClient();
    return useMutation<void, ApiError, string | { id: string; reason?: string }>({
      mutationFn: (input) => {
        const id = typeof input === 'string' ? input : input.id;
        const reason = typeof input === 'string' ? undefined : input.reason;
        const url = reason
          ? `${path}${id}/?reason=${encodeURIComponent(reason)}`
          : `${path}${id}/`;
        return apiFetch<void>(url, {
          method: 'DELETE',
          ...(skipOrg ? { skipOrg: true } : {}),
        });
      },
      onSuccess: () => qc.invalidateQueries({ queryKey: key }),
    });
  }

  /**
   * Возвращает _хук_, который триггерит POST на action-URL и инвалидирует список.
   * Используется так:
   *   export const useCrystallizeEggs = makeAction<Vars>((id) => `...`);
   *   // в компоненте:
   *   const m = useCrystallizeEggs();
   *   m.mutate({ id, body });
   */
  function makeAction<Vars = unknown, Result = T>(actionUrl: (id: string) => string) {
    return function useActionHook() {
      const qc = useQueryClient();
      return useMutation<Result, ApiError, { id: string; body?: Vars }>({
        mutationFn: ({ id, body }) =>
          apiFetch<Result>(actionUrl(id), {
            method: 'POST',
            body: (body ?? {}) as unknown as ApiInit['body'],
            ...(skipOrg ? { skipOrg: true } : {}),
          }),
        onSuccess: () => qc.invalidateQueries({ queryKey: key }),
      });
    };
  }

  return { useList, useCreate, useUpdate, useDelete, makeAction };
}
