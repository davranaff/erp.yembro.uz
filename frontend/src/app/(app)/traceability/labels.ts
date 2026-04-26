/**
 * Локализованные ярлыки для перечислений, используемых на странице
 * трассировки. Backend кое-где отдаёт человекочитаемые `..._label`
 * (например `BatchCostBreakdownItem.category_label`), но не везде —
 * в журнале затрат `BatchCostEntry` приходит только raw `category`.
 *
 * Это единая точка перевода — если появится i18n-библиотека, эти карты
 * легко вынести в JSON-словарь.
 */

import type { BatchCostCategory, BatchState } from '@/types/auth';

export const BATCH_COST_CATEGORY_LABEL: Record<BatchCostCategory, string> = {
  egg_inherited: 'Себест. яйца',
  feed: 'Корм',
  vet: 'Ветпрепараты',
  labor: 'Зарплата',
  utilities: 'Коммуналка',
  depreciation: 'Амортизация',
  transfer_in: 'Передача',
  other: 'Прочее',
};

export const BATCH_COST_CATEGORY_TONE: Record<BatchCostCategory, string> = {
  egg_inherited: 'var(--kpi-orange, #E8751A)',
  feed: 'var(--kpi-green, #10B981)',
  vet: 'var(--kpi-red, #EF4444)',
  labor: 'var(--kpi-blue, #3B82F6)',
  utilities: 'var(--fg-3)',
  depreciation: 'var(--fg-3)',
  transfer_in: 'var(--brand-orange)',
  other: 'var(--fg-3)',
};

export const BATCH_STATE_LABEL: Record<BatchState | string, string> = {
  active: 'Активна',
  in_transit: 'В пути',
  completed: 'Завершена',
  rejected: 'Отклонена',
  review: 'На проверке',
};

export const BATCH_STATE_TONE: Record<
  BatchState | string,
  'success' | 'warn' | 'danger' | 'neutral' | 'info'
> = {
  active: 'success',
  in_transit: 'info',
  completed: 'neutral',
  rejected: 'danger',
  review: 'warn',
};

/**
 * Перевод кода модуля в человеческое название. Покрывает все сидовые
 * модули; если придёт неизвестный код — возвращаем сам код.
 */
export const MODULE_LABEL: Record<string, string> = {
  core: 'Ядро',
  matochnik: 'Маточник',
  incubation: 'Инкубация',
  feedlot: 'Откорм',
  slaughter: 'Убойня',
  feed: 'Корма',
  vet: 'Вет. аптека',
  stock: 'Склад',
  ledger: 'Проводки',
  reports: 'Отчёты',
  purchases: 'Закупки',
  sales: 'Продажи',
  admin: 'Администрирование',
};

export function moduleLabel(code: string | null | undefined): string {
  if (!code) return '—';
  return MODULE_LABEL[code] ?? code;
}
