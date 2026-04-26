'use client';

import { useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { dailyEggCrud } from '@/hooks/useMatochnik';
import { ApiError } from '@/lib/api';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

/**
 * Форма ввода суточного яйцесбора.
 *
 * Unique_together=(herd, date) — если за дату уже есть запись, бекенд
 * вернёт 400. Показываем это в fieldErrors.
 */
export default function EggProductionModal({ herd, onClose }: Props) {
  const create = dailyEggCrud.useCreate();
  const { data: existing } = dailyEggCrud.useList({ herd: herd.id });

  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [collected, setCollected] = useState('');
  const [unfit, setUnfit] = useState('');
  const [notes, setNotes] = useState('');

  // Предупреждение: запись за эту дату уже существует
  const dupeWarning = useMemo(() => {
    if (!existing || !date) return null;
    return existing.find((e) => e.date === date) ?? null;
  }, [existing, date]);

  const clean = useMemo(() => {
    const c = parseFloat(collected || '0');
    const u = parseFloat(unfit || '0');
    if (Number.isNaN(c) || Number.isNaN(u)) return null;
    return Math.max(0, c - u);
  }, [collected, unfit]);

  // Яйценоскость на голову в %
  const layRate = useMemo(() => {
    if (clean === null || !herd.current_heads) return null;
    return (clean / herd.current_heads) * 100;
  }, [clean, herd.current_heads]);

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

  const collectedN = parseFloat(collected || '0');
  const unfitN = parseFloat(unfit || '0');
  const canSave =
    Boolean(date)
    && collected !== ''
    && collectedN >= 0
    && unfitN <= collectedN
    && !dupeWarning
    && !create.isPending;

  const handleSave = async () => {
    try {
      await create.mutateAsync({
        herd: herd.id,
        date,
        eggs_collected: collectedN,
        unfit_eggs: unfitN,
        notes,
      } as never);
      onClose();
    } catch {
      /* showed via error */
    }
  };

  return (
    <Modal
      title={`Яйцесбор · стадо ${herd.doc_number}`}
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
        Запись ежесуточного яйцесбора. Одна запись на стадо в сутки.
        Чистые яйца = Собрано − Брак.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          {dupeWarning && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              За {date} уже есть запись: {dupeWarning.eggs_collected} шт собрано.
              Отредактируйте её или выберите другую дату.
            </div>
          )}
        </div>

        <div className="field">
          <label>Собрано, шт *</label>
          <input
            className="input mono"
            type="number"
            min="0"
            step="1"
            value={collected}
            onChange={(e) => setCollected(e.target.value)}
            placeholder="0"
          />
          {getFieldErr('eggs_collected') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('eggs_collected')}</div>
          )}
        </div>

        <div className="field">
          <label>Брак, шт</label>
          <input
            className="input mono"
            type="number"
            min="0"
            step="1"
            value={unfit}
            onChange={(e) => setUnfit(e.target.value)}
            placeholder="0"
          />
          {unfitN > collectedN && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              Брак не может превышать собранное.
            </div>
          )}
          {getFieldErr('unfit_eggs') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('unfit_eggs')}</div>
          )}
        </div>

        <div className="field">
          <label>Заметки</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        {clean !== null && collected !== '' && (
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
              <span>Чистых (в партию):</span>
              <span className="mono" style={{ fontWeight: 600 }}>
                {clean.toLocaleString('ru-RU')} шт
              </span>
            </div>
            {layRate !== null && (
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, color: 'var(--fg-2)' }}>
                <span>Яйценоскость:</span>
                <span className="mono">
                  {layRate.toFixed(1)}% ({herd.current_heads.toLocaleString('ru-RU')} голов)
                </span>
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
