/**
 * Frontend-side helpers для field-level RBAC.
 *
 * Backend (`apps.common.serializers.FinancialFieldsMixin`) скрывает
 * финансовые поля от пользователей без доступа к модулю `ledger` и
 * добавляет в response флаг `_finances_visible: boolean`.
 *
 * На фронте мы либо просто рендерим скрытые поля как «—»
 * (через `fmtNum(null) → '—'`), либо для лучшего UX **скрываем колонки
 * целиком** через этот хелпер.
 */

interface MaybeFinancesVisible {
  _finances_visible?: boolean;
}

/**
 * Извлекает флаг `_finances_visible` из ответа API. Принимает либо
 * один объект, либо массив (берёт первый элемент). Default — true
 * (если флага нет — показываем как раньше, обратная совместимость).
 */
export function getFinancesVisible<T extends MaybeFinancesVisible>(
  data: T | T[] | null | undefined,
): boolean {
  if (!data) return true;
  if (Array.isArray(data)) {
    if (data.length === 0) return true;
    return data[0]._finances_visible !== false;
  }
  return data._finances_visible !== false;
}
