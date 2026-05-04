'use client';

import Icon from './Icon';

interface Step {
  label: string;
  done?: boolean;
}

interface Props {
  icon?: string;
  title: string;
  description?: string;
  /**
   * Пошаговый чек-лист — что нужно сделать чтобы попасть в нормальное состояние.
   * Каждый шаг можно отметить как выполненный (done=true) — он зачёркнётся.
   */
  steps?: Step[];
  /** Главное действие. */
  action?: {
    label: string;
    onClick: () => void;
  };
  /** Дополнительная второстепенная ссылка. */
  hint?: React.ReactNode;
}

/**
 * Большая карточка-объяснение для пустых таблиц.
 *
 * Используется в таблицах через DataTable.emptyMessage (через ReactNode-вариант),
 * либо напрямую вместо таблицы пока данных нет.
 */
export default function EmptyState({
  icon = 'inbox',
  title,
  description,
  steps,
  action,
  hint,
}: Props) {
  return (
    <div style={{
      padding: '40px 20px',
      textAlign: 'center',
      color: 'var(--fg-2)',
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%',
        background: 'var(--bg-soft)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 14,
        color: 'var(--brand-orange)',
      }}>
        <Icon name={icon} size={28} />
      </div>

      <div style={{
        fontSize: 15, fontWeight: 600, color: 'var(--fg-1)',
        marginBottom: 6,
      }}>
        {title}
      </div>

      {description && (
        <div style={{ fontSize: 13, maxWidth: 480, margin: '0 auto 14px', lineHeight: 1.5 }}>
          {description}
        </div>
      )}

      {steps && steps.length > 0 && (
        <ol style={{
          textAlign: 'left',
          maxWidth: 420,
          margin: '0 auto 16px',
          padding: 0,
          listStyle: 'none',
          fontSize: 13,
        }}>
          {steps.map((s, i) => (
            <li key={i} style={{
              display: 'flex',
              gap: 8,
              padding: '6px 0',
              color: s.done ? 'var(--fg-3)' : 'var(--fg-2)',
              textDecoration: s.done ? 'line-through' : 'none',
            }}>
              <span style={{
                flexShrink: 0,
                width: 22, height: 22, borderRadius: '50%',
                background: s.done ? 'var(--success, #10B981)' : 'var(--bg-soft)',
                color: s.done ? '#fff' : 'var(--brand-orange)',
                border: '1px solid ' + (s.done ? 'transparent' : 'var(--border)'),
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 11,
                fontWeight: 700,
              }}>
                {s.done ? '✓' : i + 1}
              </span>
              <span>{s.label}</span>
            </li>
          ))}
        </ol>
      )}

      {action && (
        <button className="btn btn-primary btn-sm" onClick={action.onClick}>
          <Icon name="plus" size={12} /> {action.label}
        </button>
      )}

      {hint && (
        <div style={{
          marginTop: 12, fontSize: 11, color: 'var(--fg-3)',
        }}>
          {hint}
        </div>
      )}
    </div>
  );
}
