'use client';

import { useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { herdMortalityCrud } from '@/hooks/useMatochnik';
import { ApiError } from '@/lib/api';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

const CAUSE_OPTIONS = [
  '',
  'естественная убыль',
  'заболевание',
  'травма',
  'жара',
  'холод',
  'каннибализм',
  'транспортировка',
  'прочее',
];

/**
 * Форма записи суточного падежа.
 *
 * При save post_save сигнал (apps/matochnik/signals.py) автоматически
 * уменьшит current_heads стада. При опустении до 0 — status=DEPOPULATED.
 *
 * Unique_together=(herd, date) — повторная запись за дату вернёт 400.
 * Для слияния (merge) нужно использовать кнопку «Снятие» с mark_as_mortality.
 */
export default function MortalityModal({ herd, onClose }: Props) {
  const create = herdMortalityCrud.useCreate();
  const { data: existing } = herdMortalityCrud.useList({ herd: herd.id });

  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [deadCount, setDeadCount] = useState('');
  const [cause, setCause] = useState('');
  const [notes, setNotes] = useState('');

  const dupe = useMemo(() => {
    if (!existing || !date) return null;
    return existing.find((e) => e.date === date) ?? null;
  }, [existing, date]);

  const n = parseFloat(deadCount || '0');

  const error = create.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const getFieldErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const canSave =
    Boolean(date)
    && deadCount !== ''
    && n > 0
    && n <= herd.current_heads
    && !dupe
    && !create.isPending;

  const handleSave = async () => {
    try {
      await create.mutateAsync({
        herd: herd.id,
        date,
        dead_count: n,
        cause,
        notes,
      } as never);
      onClose();
    } catch {
      /* */
    }
  };

  const afterHeads = Math.max(0, herd.current_heads - n);

  return (
    <Modal
      title={`Падёж · стадо ${herd.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSave} onClick={handleSave}>
            {create.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Запись падежа автоматически <b>уменьшит текущее поголовье</b> стада.
        Если стадо опустеет, статус перейдёт в «Снято».
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          {dupe && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              За {date} уже есть запись: {dupe.dead_count} голов. Используйте кнопку «Снятие» для дополнения.
            </div>
          )}
        </div>

        <div className="field">
          <label>Погибло, гол *</label>
          <input
            className="input mono"
            type="number"
            min="1"
            step="1"
            value={deadCount}
            onChange={(e) => setDeadCount(e.target.value)}
            placeholder="0"
          />
          {n > herd.current_heads && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              Больше чем текущее поголовье ({herd.current_heads.toLocaleString('ru-RU')}).
            </div>
          )}
          {getFieldErr('dead_count') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('dead_count')}</div>
          )}
        </div>

        <div className="field">
          <label>Причина</label>
          <select className="input" value={cause} onChange={(e) => setCause(e.target.value)}>
            {CAUSE_OPTIONS.map((c) => (
              <option key={c} value={c}>{c || '—'}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Заметки</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        {n > 0 && n <= herd.current_heads && (
          <div
            style={{
              gridColumn: '1 / 3',
              padding: 10,
              background: 'var(--bg-soft)',
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Поголовье после:</span>
              <span className="mono" style={{ fontWeight: 600, color: afterHeads === 0 ? 'var(--danger)' : undefined }}>
                {herd.current_heads.toLocaleString('ru-RU')} → {afterHeads.toLocaleString('ru-RU')}
              </span>
            </div>
            {afterHeads === 0 && (
              <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                Стадо опустеет и перейдёт в статус «Снято».
              </div>
            )}
          </div>
        )}
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
