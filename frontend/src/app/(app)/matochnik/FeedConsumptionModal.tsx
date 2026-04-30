'use client';

import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import Modal from '@/components/ui/Modal';
import { feedBatchesCrud } from '@/hooks/useFeed';
import { ApiError } from '@/lib/api';
import { enqueueOrSend } from '@/lib/offlineQueue';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

/**
 * Форма записи суточного расхода корма стадом.
 * При сохранении бэкенд автоматически:
 *   - уменьшит current_quantity_kg у FeedBatch,
 *   - создаст проводку Дт 20.01 / Кт 10.05,
 *   - если есть ACTIVE egg-партия — создаст BatchCostEntry(FEED).
 */
export default function FeedConsumptionModal({ herd, onClose }: Props) {
  const qc = useQueryClient();

  const { data: allFeedBatches } = feedBatchesCrud.useList();
  // Для списания берём только те, у которых есть остаток.
  const feedBatches = useMemo(() => {
    if (!allFeedBatches) return [];
    return allFeedBatches.filter((b) => parseFloat(b.current_quantity_kg) > 0);
  }, [allFeedBatches]);

  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [feedBatch, setFeedBatch] = useState('');
  const [quantityKg, setQuantityKg] = useState('');
  const [perHeadG, setPerHeadG] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const selected = feedBatches.find((b) => b.id === feedBatch);
  const remaining = selected ? parseFloat(selected.current_quantity_kg) : null;
  // unit_cost_uzs может прийти null/undefined для юзеров без feed/ledger-доступа
  // (FinancialFieldsMixin nullify-ит). Тогда блок «Стоимость» просто не рисуем.
  const unitCost = selected && selected.unit_cost_uzs
    ? parseFloat(selected.unit_cost_uzs)
    : null;
  const totalCost = quantityKg && unitCost && !Number.isNaN(unitCost)
    ? parseFloat(quantityKg) * unitCost
    : null;

  const fieldErrors = error && error.status === 400
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
    && Boolean(quantityKg)
    && parseFloat(quantityKg) > 0
    && !busy;

  const handleSave = async () => {
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      const result = await enqueueOrSend({
        path: '/api/matochnik/feed-consumption/',
        body: {
          herd: herd.id,
          date,
          feed_batch: feedBatch || null,
          quantity_kg: quantityKg,
          per_head_g: perHeadG || null,
          notes,
        },
      });
      if (typeof result === 'object' && result !== null && 'queued' in result) {
        setInfo('Нет сети. Запись сохранена локально и отправится автоматически когда сеть появится.');
        setTimeout(onClose, 2000);
      } else {
        qc.invalidateQueries({ queryKey: ['matochnik'] });
        qc.invalidateQueries({ queryKey: ['feed'] });
        onClose();
      }
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={`Расход корма · стадо ${herd.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSave} onClick={handleSave}>
            {busy ? 'Сохранение…' : 'Сохранить и провести'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        При сохранении: уменьшится остаток партии корма, будет создана проводка
        <span className="mono"> Дт 20.01 / Кт 10.05</span>, стоимость начислится
        на последнюю активную партию яиц стада.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field">
          <label>Количество, кг *</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={quantityKg}
            onChange={(e) => setQuantityKg(e.target.value)}
            placeholder="0.000"
          />
          {getFieldErr('quantity_kg') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('quantity_kg')}</div>
          )}
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Партия корма (опционально)</label>
          <select className="input" value={feedBatch} onChange={(e) => setFeedBatch(e.target.value)}>
            <option value="">— без партии (без проводки) —</option>
            {feedBatches.map((b) => {
              const remainingKg = parseFloat(b.current_quantity_kg).toLocaleString('ru-RU');
              const priceLabel = b.unit_cost_uzs
                ? ` · ${parseFloat(b.unit_cost_uzs).toLocaleString('ru-RU')} сум/кг`
                : '';
              return (
                <option key={b.id} value={b.id}>
                  {b.doc_number} · {b.recipe_code ?? '—'} · остаток {remainingKg} кг{priceLabel}
                </option>
              );
            })}
          </select>
          {selected && remaining !== null && quantityKg && parseFloat(quantityKg) > remaining && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              Превышен остаток партии ({remaining.toLocaleString('ru-RU')} кг).
            </div>
          )}
        </div>

        <div className="field">
          <label>Норма на голову, г</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={perHeadG}
            onChange={(e) => setPerHeadG(e.target.value)}
            placeholder="опционально"
          />
        </div>

        <div className="field">
          <label>Заметки</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        {totalCost !== null && (
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
              <span>Стоимость:</span>
              <span className="mono" style={{ fontWeight: 600 }}>
                {totalCost.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--fg-3)' }}>
              <span>Проводка:</span>
              <span className="mono">Дт 20.01 / Кт 10.05</span>
            </div>
          </div>
        )}
      </div>

      {info && (
        <div style={{
          marginTop: 10, padding: 10, fontSize: 13,
          background: 'color-mix(in srgb, var(--brand-orange) 15%, transparent)',
          color: 'var(--fg-1)', borderRadius: 6,
        }}>
          ⚡ {info}
        </div>
      )}
      {error && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
