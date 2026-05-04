'use client';

import { useMemo, useState } from 'react';

import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import { useBatches, type BatchesFilter } from '@/hooks/useBatches';
import type { Batch } from '@/types/auth';

interface Props {
  /** Текущее значение (UUID партии). */
  value: string;
  /** Колбэк выбора. */
  onChange: (id: string, batch: Batch) => void;
  /** Подпись поля */
  label?: string;
  /** Дополнительные фильтры (state=active, current_module=…). */
  filter?: BatchesFilter;
  /** Заглушка-плейсхолдер если ничего не выбрано. */
  placeholder?: string;
  disabled?: boolean;
}

/**
 * Универсальный селектор партии (Batch).
 *
 *   <BatchSelector
 *     value={batchId}
 *     onChange={(id) => setBatchId(id)}
 *     filter={{ state: 'active', current_module: matochnikModuleId }}
 *   />
 */
export default function BatchSelector({
  value,
  onChange,
  label = 'Партия',
  filter,
  placeholder = '— выберите партию —',
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const { data, isLoading } = useBatches({ ...filter, search: search || undefined });

  const selectedLabel = useMemo(() => {
    if (!value) return null;
    const found = data?.find((b) => b.id === value);
    if (found) return `${found.doc_number} · ${found.nomenclature_sku ?? '—'} (${found.current_quantity})`;
    return `Batch · ${value.slice(0, 8)}…`;
  }, [value, data]);

  return (
    <>
      <div className="field">
        {label && <label>{label}</label>}
        <button
          type="button"
          className="input"
          onClick={() => !disabled && setOpen(true)}
          disabled={disabled}
          style={{
            textAlign: 'left',
            cursor: disabled ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          <span style={{ color: value ? 'var(--fg-1)' : 'var(--fg-3)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedLabel ?? placeholder}
          </span>
          <Icon name="chevron-down" size={12} style={{ color: 'var(--fg-3)' }} />
        </button>
      </div>

      {open && (
        <Modal
          title="Выбор партии"
          onClose={() => setOpen(false)}
          footer={
            value ? (
              <button
                className="btn btn-ghost"
                onClick={() => {
                  // очистка
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  onChange('', null as any);
                  setOpen(false);
                }}
                style={{ color: 'var(--danger)' }}
              >
                Очистить
              </button>
            ) : null
          }
        >
          <input
            className="input"
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по номеру, SKU, названию…"
            style={{ marginBottom: 12 }}
          />
          {isLoading ? (
            <div style={{ padding: 12, color: 'var(--fg-3)' }}>Загрузка…</div>
          ) : !data || data.length === 0 ? (
            <div style={{ padding: 12, color: 'var(--fg-3)', textAlign: 'center' }}>
              Партий нет.
            </div>
          ) : (
            <div style={{ maxHeight: 380, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {data.slice(0, 50).map((b) => {
                const isSel = b.id === value;
                const cur = parseFloat(b.current_quantity || '0');
                const reserved = parseFloat(b.reserved_quantity ?? '0');
                const available = b.available_quantity != null
                  ? parseFloat(b.available_quantity)
                  : cur;
                const isDepleted = available <= 0;
                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => {
                      onChange(b.id, b);
                      setOpen(false);
                    }}
                    disabled={isDepleted}
                    style={{
                      display: 'flex',
                      gap: 10,
                      alignItems: 'center',
                      padding: 10,
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      background: isSel ? 'var(--bg-soft)' : 'var(--bg-card)',
                      textAlign: 'left',
                      cursor: isDepleted ? 'not-allowed' : 'pointer',
                      opacity: isDepleted ? 0.5 : 1,
                      borderLeft: isSel ? '3px solid var(--brand-orange)' : '1px solid var(--border)',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                        <span className="badge id">{b.doc_number}</span>
                        <span style={{ fontSize: 11, color: 'var(--fg-3)' }} className="mono">
                          {b.state}
                        </span>
                        {isDepleted && (
                          <span style={{ fontSize: 10, color: 'var(--danger)', fontWeight: 600 }}>
                            нет доступного остатка
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                        {b.nomenclature_sku ? `${b.nomenclature_sku} · ` : ''}
                        {b.nomenclature_name ?? '—'}
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
                        <span style={{ color: isDepleted ? 'var(--danger)' : 'var(--fg-2)', fontWeight: 600 }}>
                          Доступно: {available.toLocaleString('ru-RU')} {b.unit_code ?? ''}
                        </span>
                        {reserved > 0 && (
                          <span style={{ marginLeft: 6 }}>
                            (остаток {cur.toLocaleString('ru-RU')}, резерв {reserved.toLocaleString('ru-RU')})
                          </span>
                        )}
                        {b.current_module_code && ` · ${b.current_module_code}`}
                        {b.current_block_code && ` · ${b.current_block_code}`}
                      </div>
                    </div>
                    {isSel && <Icon name="check" size={14} style={{ color: 'var(--brand-orange)' }} />}
                  </button>
                );
              })}
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
