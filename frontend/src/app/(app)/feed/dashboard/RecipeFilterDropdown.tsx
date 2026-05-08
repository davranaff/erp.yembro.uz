'use client';

/**
 * Multi-select dropdown для фильтрации рецептур в матрице feed/dashboard.
 *
 * Trigger: компактная кнопка «Все (N)» / «N выбрано».
 * Popover: чекбоксы + быстрый поиск + кнопки «Все» / «Сбросить».
 *
 * Закрытие: клик вне / Esc. Кнопка-trigger держит ref для anchor-измерений
 * (popover абсолютный, под trigger'ом).
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import Icon from '@/components/ui/Icon';

interface VersionLite {
  id: string;
  recipe_code: string;
  recipe_name: string;
  version: number;
}

interface Props {
  versions: VersionLite[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  onClear: () => void;
  onSelectAll: () => void;
}

export default function RecipeFilterDropdown({
  versions, selectedIds, onToggle, onClear, onSelectAll,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  // Click-outside + Esc.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return versions;
    return versions.filter((v) => (
      v.recipe_code.toLowerCase().includes(q)
      || v.recipe_name.toLowerCase().includes(q)
    ));
  }, [versions, query]);

  const triggerLabel = selectedIds.size === 0
    ? `Все (${versions.length})`
    : `${selectedIds.size} выбрано`;

  return (
    <div ref={wrapperRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => setOpen((v) => !v)}
        style={{
          fontSize: 12, padding: '4px 10px',
          display: 'inline-flex', alignItems: 'center', gap: 6,
          minWidth: 140, justifyContent: 'space-between',
        }}
      >
        <span>{triggerLabel}</span>
        <Icon name={open ? 'chevron-down' : 'chevron-right'} size={12} />
      </button>

      {open && (
        <div
          role="dialog"
          style={{
            position: 'absolute', top: 'calc(100% + 4px)', left: 0,
            minWidth: 280, maxWidth: 'min(360px, 90vw)',
            background: 'var(--bg-raised)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            boxShadow: 'var(--shadow-modal, 0 8px 32px rgba(0,0,0,0.12))',
            zIndex: 100,
            display: 'flex', flexDirection: 'column',
            maxHeight: 'min(420px, 70vh)',
          }}
        >
          <div style={{
            padding: 8, borderBottom: '1px solid var(--border)',
            display: 'flex', gap: 6, alignItems: 'center',
          }}>
            <input
              type="text"
              autoFocus
              className="input"
              placeholder="Поиск по коду / названию…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ flex: 1, fontSize: 12, height: 28 }}
            />
          </div>

          <div style={{
            display: 'flex', gap: 4, padding: 6,
            borderBottom: '1px solid var(--border)',
          }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onSelectAll}
              style={{ fontSize: 11, padding: '4px 10px' }}
            >
              Выбрать все
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onClear}
              style={{ fontSize: 11, padding: '4px 10px' }}
            >
              Сбросить
            </button>
          </div>

          <div style={{ overflowY: 'auto', flex: 1, padding: 4 }}>
            {filtered.length === 0 && (
              <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 12 }}>
                Ничего не найдено
              </div>
            )}
            {filtered.map((v) => {
              const checked = selectedIds.has(v.id);
              return (
                <label
                  key={v.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 10px', cursor: 'pointer',
                    fontSize: 13,
                    background: checked ? 'rgba(232,117,26,0.06)' : 'transparent',
                    borderRadius: 4,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggle(v.id)}
                  />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span className="mono" style={{ fontWeight: 600 }}>
                      {v.recipe_code}
                    </span>
                    <span style={{ color: 'var(--fg-3)', marginLeft: 6, fontSize: 11 }}>
                      v{v.version}
                    </span>
                    <div style={{
                      fontSize: 11, color: 'var(--fg-3)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {v.recipe_name}
                    </div>
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
