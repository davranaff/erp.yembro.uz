'use client';

import type { CSSProperties, ReactNode } from 'react';

/**
 * Описание колонки DataTable.
 *
 * @template T — тип строки.
 */
export interface DataTableColumn<T> {
  /** Уникальный ключ колонки (для React key). */
  key: string;
  /** Заголовок (header). Пустая строка — не рисует текст, но колонка остаётся. */
  label?: ReactNode;
  /**
   * Как отрендерить ячейку строки. Если не задан — попытка взять row[key] как
   * строку. Рекомендуется всегда задавать явно для типобезопасности.
   */
  render?: (row: T, rowIndex: number) => ReactNode;
  /** Выравнивание текста. По умолчанию 'left'. */
  align?: 'left' | 'right' | 'center';
  /** Моноширинный шрифт (tabular-nums). */
  mono?: boolean;
  /** Фиксированная ширина ячейки (например "120px" или "10%"). */
  width?: string | number;
  /** Маленький серый размер шрифта (для дат/вспомогательных значений). */
  muted?: boolean;
  /** Inline-стиль для ячейки (<td>) — применяется после базовых. */
  cellStyle?: CSSProperties;
  /** Inline-стиль для заголовка (<th>). */
  headerStyle?: CSSProperties;
  /**
   * className для <td>. Удобно когда нужна чужая стилизация
   * (.num / .mono из globals).
   */
  cellClassName?: string;
  /** className для <th>. */
  headerClassName?: string;
}

export interface DataTableProps<T> {
  /** Описание колонок. */
  columns: DataTableColumn<T>[];
  /** Данные. */
  rows: T[] | null | undefined;
  /** Как получить стабильный ключ строки. */
  rowKey: (row: T, index: number) => string;
  /** Клик по строке (добавляет cursor:pointer). */
  onRowClick?: (row: T) => void;
  /** Кастомные стили/класс для строки (подсветка, highlight активного). */
  rowProps?: (row: T, index: number) => {
    style?: CSSProperties;
    className?: string;
    active?: boolean;
  };
  /** Таблица в loading-состоянии. */
  isLoading?: boolean;
  /** Текст при loading. По умолчанию «Загрузка…». */
  loadingText?: string;
  /** Текст при пустом списке. По умолчанию «Нет записей». */
  emptyMessage?: ReactNode;
  /**
   * Ошибка запроса. Если задана — вместо таблицы показывается сообщение.
   * Принимается любой объект с .message или просто строка.
   */
  error?: { message?: string } | string | null;
  /** Дополнительные строки после <tbody> (для «Итого» и т.п.). */
  footer?: ReactNode;
  /** Inline-стиль контейнера. */
  style?: CSSProperties;
}

/**
 * Универсальная таблица, покрывающая 80%+ сценариев.
 *
 * Использует глобальный CSS-класс `.tbl` (см. `globals.css`). Берёт на себя:
 *   - states: loading / empty / error;
 *   - hover-cursor при onRowClick;
 *   - aria-sort при align='right' (mono tabular-nums уже в .tbl CSS).
 *
 * Для нестандартных таблиц (groupby, collapse, footer-итоги) используйте
 * props `footer` или `rowProps`. Совсем экзотические кейсы (flatMap
 * разворачивания групп) — оставляйте на <table className="tbl">.
 */
export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  rowProps,
  isLoading = false,
  loadingText = 'Загрузка…',
  emptyMessage = 'Нет записей',
  error = null,
  footer,
  style,
}: DataTableProps<T>) {
  const errorMessage = typeof error === 'string' ? error : error?.message;

  if (errorMessage) {
    return (
      <div style={{ padding: 24, color: 'var(--danger)', fontSize: 13, ...(style ?? {}) }}>
        Ошибка: {errorMessage}
      </div>
    );
  }

  if (isLoading && (!rows || rows.length === 0)) {
    return (
      <div style={{ padding: 24, color: 'var(--fg-3)', fontSize: 13, ...(style ?? {}) }}>
        {loadingText}
      </div>
    );
  }

  const list = rows ?? [];
  if (list.length === 0 && !footer) {
    return (
      <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center', fontSize: 13, ...(style ?? {}) }}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <table className="tbl" style={style}>
      <thead>
        <tr>
          {columns.map((c) => {
            const style: CSSProperties = { ...c.headerStyle };
            if (c.align === 'right') style.textAlign = 'right';
            if (c.align === 'center') style.textAlign = 'center';
            if (c.width != null) style.width = c.width;
            return (
              <th
                key={c.key}
                className={[
                  c.align === 'right' ? 'num' : '',
                  c.headerClassName ?? '',
                ].filter(Boolean).join(' ') || undefined}
                style={style}
              >
                {c.label ?? ''}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {list.map((row, i) => {
          const extra = rowProps?.(row, i);
          const clickable = Boolean(onRowClick);
          return (
            <tr
              key={rowKey(row, i)}
              className={[
                extra?.className ?? '',
                extra?.active ? 'active' : '',
                clickable ? 'clickable' : '',
              ].filter(Boolean).join(' ') || undefined}
              style={{
                cursor: clickable ? 'pointer' : undefined,
                ...(extra?.style ?? {}),
              }}
              onClick={clickable ? () => onRowClick!(row) : undefined}
            >
              {columns.map((c) => {
                const style: CSSProperties = { ...c.cellStyle };
                if (c.align === 'right') style.textAlign = 'right';
                if (c.align === 'center') style.textAlign = 'center';
                if (c.muted) {
                  style.fontSize = 11;
                  style.color = 'var(--fg-3)';
                }
                const classes = [
                  c.align === 'right' ? 'num' : '',
                  c.mono ? 'mono' : '',
                  c.cellClassName ?? '',
                ].filter(Boolean).join(' ') || undefined;
                const value = c.render
                  ? c.render(row, i)
                  : (row as unknown as Record<string, ReactNode>)[c.key];
                return (
                  <td key={c.key} className={classes} style={style}>
                    {value as ReactNode}
                  </td>
                );
              })}
            </tr>
          );
        })}
        {footer}
      </tbody>
    </table>
  );
}
