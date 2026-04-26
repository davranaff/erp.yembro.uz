'use client';

import { useEffect, useRef, useState } from 'react';

export interface RowAction {
  /** Текст пункта меню. */
  label: string;
  /** Колбэк по клику. Получает `MouseEvent` чтобы можно было stopPropagation. */
  onClick: (e: React.MouseEvent) => void;
  /** Окрасить пункт как опасный (красный). */
  danger?: boolean;
  /** Отключить пункт. */
  disabled?: boolean;
  /** Иконка слева — произвольный ReactNode (Icon, эмодзи). */
  icon?: React.ReactNode;
  /** Скрыть пункт полностью. Удобно для условных actions. */
  hidden?: boolean;
}

interface Props {
  actions: RowAction[];
  /** Заголовок при наведении. */
  title?: string;
  /** Куда раскрывать меню (по умолчанию справа). */
  align?: 'right' | 'left';
}

/**
 * Кнопка-многоточие (⋯) в строке таблицы. По клику показывает выпадающее меню
 * с действиями. Закрывается по клику снаружи / Escape.
 *
 *   <RowActions
 *     actions={[
 *       { label: 'Править', onClick: () => setEditing(o) },
 *       { label: 'Сторно', danger: true, onClick: () => handleReverse(o) },
 *     ]}
 *   />
 */
export default function RowActions({ actions, title = 'Действия', align = 'right' }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const visible = actions.filter((a) => !a.hidden);
  if (visible.length === 0) return null;

  return (
    <div
      ref={ref}
      style={{ position: 'relative', display: 'inline-block' }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        title={title}
        onClick={() => setOpen((v) => !v)}
        style={{
          padding: '4px 8px',
          minWidth: 28,
          color: 'var(--fg-2)',
        }}
      >
        <svg
          viewBox="0 0 24 24"
          width={16}
          height={16}
          style={{ display: 'block' }}
          fill="currentColor"
        >
          <circle cx="5" cy="12" r="1.8" />
          <circle cx="12" cy="12" r="1.8" />
          <circle cx="19" cy="12" r="1.8" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            [align]: 0,
            zIndex: 50,
            minWidth: 180,
            background: 'var(--bg-card, #fff)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            boxShadow: '0 4px 16px rgba(0,0,0,.08)',
            padding: 4,
          }}
        >
          {visible.map((a, i) => (
            <button
              key={i}
              type="button"
              role="menuitem"
              disabled={a.disabled}
              onClick={(e) => {
                e.stopPropagation();
                if (a.disabled) return;
                setOpen(false);
                a.onClick(e);
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 10px',
                fontSize: 13,
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                borderRadius: 4,
                cursor: a.disabled ? 'not-allowed' : 'pointer',
                color: a.disabled
                  ? 'var(--fg-3)'
                  : a.danger ? 'var(--danger)' : 'var(--fg-1)',
                opacity: a.disabled ? 0.6 : 1,
              }}
              onMouseEnter={(e) => {
                if (!a.disabled) {
                  (e.currentTarget as HTMLElement).style.background = 'var(--bg-soft)';
                }
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'transparent';
              }}
            >
              {a.icon && <span style={{ display: 'inline-flex' }}>{a.icon}</span>}
              <span>{a.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
