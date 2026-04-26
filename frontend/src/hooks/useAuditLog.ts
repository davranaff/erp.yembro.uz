'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { AuditLogEntry, Paginated } from '@/types/auth';

export interface AuditFilter {
  action?: string;
  /** Multi-select: CSV-список action codes — backend ?action__in=create,delete. */
  actions?: string[];
  module?: string;
  actor?: string;
  entity_content_type?: number;
  entity_object_id?: string;
  date_after?: string;
  date_before?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

function buildQs(filter: AuditFilter): URLSearchParams {
  const params = new URLSearchParams();
  // Если задан список actions[] — отправляем как __in (приоритет над action).
  if (filter.actions && filter.actions.length > 0) {
    params.set('action__in', filter.actions.join(','));
  } else if (filter.action) {
    params.set('action', filter.action);
  }
  if (filter.module) params.set('module', filter.module);
  if (filter.actor) params.set('actor', filter.actor);
  if (filter.entity_content_type != null) {
    params.set('entity_content_type', String(filter.entity_content_type));
  }
  if (filter.entity_object_id) params.set('entity_object_id', filter.entity_object_id);
  if (filter.date_after) params.set('date_after', filter.date_after);
  if (filter.date_before) params.set('date_before', filter.date_before);
  if (filter.search) params.set('search', filter.search);
  if (filter.page) params.set('page', String(filter.page));
  if (filter.page_size) params.set('page_size', String(filter.page_size));
  params.set('ordering', '-occurred_at');
  return params;
}

// ─── Stats ────────────────────────────────────────────────────────────────

export interface AuditStats {
  total: number;
  unique_actors: number;
  by_action: Record<string, number>;
  by_module: { code: string; count: number }[];
  top_actors: {
    user_id: string;
    email: string;
    full_name: string;
    count: number;
  }[];
  daily: { date: string; count: number }[];
  period: { from: string; to: string };
}

/**
 * Агрегированная сводка с теми же фильтрами что у /audit/. Используется
 * для KPI-карточек, топ-юзеров и sparkline. Один запрос вместо клиентской
 * агрегации текущей страницы.
 */
export function useAuditStats(filter: AuditFilter, opts: { enabled?: boolean } = {}) {
  const qs = buildQs(filter).toString();
  return useQuery<AuditStats, ApiError>({
    queryKey: ['audit-stats', qs],
    queryFn: () => apiFetch<AuditStats>(`/api/audit/stats/?${qs}`),
    staleTime: 30_000,
    enabled: opts.enabled ?? true,
  });
}

// ─── User activity ────────────────────────────────────────────────────────

export interface AuditUserActivity {
  user: { id: string; email: string; full_name: string };
  total: number;
  first_event: string | null;
  last_event: string | null;
  by_action: Record<string, number>;
  by_module: { code: string; count: number }[];
  by_entity: { entity_type: string; count: number }[];
  logins: number;
  unique_ips: { ip: string; count: number }[];
  daily: { date: string; count: number }[];
  recent: AuditLogEntry[];
}

/**
 * Профиль активности конкретного пользователя за период (фильтры
 * date_after / date_before — те же что у списка). null userId → query
 * не выполняется (для использования с условным открытием drawer'а).
 */
export function useAuditUserActivity(
  userId: string | null,
  filter: Omit<AuditFilter, 'actor' | 'actions' | 'action'>,
) {
  const qs = buildQs(filter).toString();
  return useQuery<AuditUserActivity, ApiError>({
    queryKey: ['audit-user-activity', userId, qs],
    queryFn: () =>
      apiFetch<AuditUserActivity>(
        `/api/audit/users/${userId}/activity/?${qs}`,
      ),
    enabled: !!userId,
    staleTime: 30_000,
  });
}

/**
 * Список записей аудита (плоский, для текущей страницы пагинации).
 *
 * Бэкенд возвращает `Paginated<AuditLogEntry>`. На фронте мы пока работаем
 * с одной страницей за раз — кнопки prev/next в UI странички.
 */
export function useAuditLog(filter: AuditFilter) {
  const qs = buildQs(filter).toString();

  return useQuery<Paginated<AuditLogEntry>, ApiError>({
    queryKey: ['audit', qs],
    queryFn: () =>
      apiFetch<Paginated<AuditLogEntry> | AuditLogEntry[]>(`/api/audit/?${qs}`).then(
        (data) => {
          // Если бэкенд по какой-то причине вернул массив (старый клиент),
          // нормализуем к Paginated-shape.
          if (Array.isArray(data)) {
            return {
              count: data.length,
              next: null,
              previous: null,
              results: data,
            };
          }
          return data;
        },
      ),
    staleTime: 15_000,
  });
}

/**
 * Возвращает плоский список (без пагинации) — удобно для KPI-расчётов
 * или для drill-down с указанием entity_object_id где результатов мало.
 *
 * Использует `page_size=1000` чтобы избежать лишних запросов.
 */
export function useAuditLogList(filter: AuditFilter) {
  const qs = buildQs({ ...filter, page_size: 1000 }).toString();
  return useQuery<AuditLogEntry[], ApiError>({
    queryKey: ['audit-list', qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<AuditLogEntry> | AuditLogEntry[]>(
        `/api/audit/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 15_000,
  });
}
