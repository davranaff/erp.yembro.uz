'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { feedBatchesCrud } from '@/hooks/useFeed';
import { feedConsumptionCrud, usePostFeedConsumption } from '@/hooks/useFeedlot';
import { ApiError } from '@/lib/api';
import type { FeedlotBatch } from '@/types/auth';

interface Props {
  batch: FeedlotBatch;
  onClose: () => void;
}

function fmtNum(v: string | number, digits = 0): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

/**
 * Скармливание корма партии откорма.
 *
 * При сохранении:
 *   - списывается FeedBatch.current_quantity_kg
 *   - создаётся JE Дт 20.02 / Кт 10.05 на (кг × unit_cost)
 *   - cost накапливается на batch (для расчёта unit_cost тушки в slaughter)
 *   - считается per_head_g и period_fcr (если есть взвешивания на границах)
 */
export default function FeedConsumptionModal({ batch, onClose }: Props) {
  const post = usePostFeedConsumption();
  const { data: feedBatches } = feedBatchesCrud.useList({});
  // Существующие кормления — чтобы автоставить period_from = последний to + 1
  const { data: existingConsumptions } = feedConsumptionCrud.useList({
    feedlot_batch: batch.id,
  });

  const todayDayOfAge = useMemo(() => {
    const placed = new Date(batch.placed_date);
    const today = new Date();
    const diff = Math.floor((today.getTime() - placed.getTime()) / 86400000);
    return Math.max(0, diff);
  }, [batch.placed_date]);

  const lastPeriodTo = useMemo(() => {
    if (!existingConsumptions || existingConsumptions.length === 0) return 0;
    return Math.max(...existingConsumptions.map((c) => c.period_to_day));
  }, [existingConsumptions]);

  // Только продаваемые партии корма
  const sellable = useMemo(() => {
    return (feedBatches ?? []).filter(
      (f) => f.status === 'approved' && parseFloat(f.current_quantity_kg) > 0,
    );
  }, [feedBatches]);

  const [feedBatchId, setFeedBatchId] = useState('');
  const [totalKg, setTotalKg] = useState('');
  const [fromDay, setFromDay] = useState(String(lastPeriodTo + 1));
  const [toDay, setToDay] = useState(String(todayDayOfAge));
  const [feedType, setFeedType] = useState<'start' | 'growth' | 'finish'>(
    todayDayOfAge < 14 ? 'start' : todayDayOfAge < 28 ? 'growth' : 'finish',
  );
  const [notes, setNotes] = useState('');

  const error = post.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const selectedFeedBatch = useMemo(
    () => sellable.find((f) => f.id === feedBatchId),
    [sellable, feedBatchId],
  );

  // Live preview: per_head_g, остаток после, ожидаемая стоимость
  const preview = useMemo(() => {
    const total = parseFloat(totalKg || '0');
    const heads = batch.current_heads || 0;
    const perHeadG = heads > 0 && total > 0
      ? (total * 1000) / heads
      : null;
    let unitCost = 0;
    let amount = 0;
    let remainingAfter: number | null = null;
    if (selectedFeedBatch) {
      unitCost = parseFloat(selectedFeedBatch.unit_cost_uzs);
      amount = total * unitCost;
      remainingAfter = parseFloat(selectedFeedBatch.current_quantity_kg) - total;
    }
    return { perHeadG, unitCost, amount, remainingAfter, total };
  }, [totalKg, batch.current_heads, selectedFeedBatch]);

  const overStock =
    selectedFeedBatch
    && preview.total > parseFloat(selectedFeedBatch.current_quantity_kg);

  const canSubmit =
    feedBatchId
    && totalKg
    && fromDay
    && toDay
    && parseInt(toDay, 10) >= parseInt(fromDay, 10)
    && preview.total > 0
    && !overStock
    && !post.isPending;

  const handleSubmit = async () => {
    try {
      await post.mutateAsync({
        id: batch.id,
        body: {
          feed_batch: feedBatchId,
          total_kg: totalKg,
          period_from_day: parseInt(fromDay, 10),
          period_to_day: parseInt(toDay, 10),
          feed_type: feedType,
          notes,
        },
      });
      onClose();
    } catch { /* */ }
  };

  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title={`Кормление · ${batch.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {post.isPending ? 'Списание…' : 'Списать корм'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Скармливание партии корма птице. Корм списывается со склада, создаётся
        проводка Дт 20.02 / Кт 10.05, стоимость накапливается на партии птицы.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>
            Партия корма *
            <HelpHint
              text="Какую партию готового корма скармливаем."
              details="В списке только одобренные партии (с пройденным паспортом качества) и с положительным остатком на складе."
            />
          </label>
          <select
            className="input"
            value={feedBatchId}
            onChange={(e) => setFeedBatchId(e.target.value)}
          >
            <option value="">— выберите партию —</option>
            {sellable.map((f) => (
              <option key={f.id} value={f.id}>
                {f.doc_number} · {f.recipe_code ?? ''} · остаток{' '}
                {fmtNum(f.current_quantity_kg, 0)} кг ·{' '}
                {fmtNum(f.unit_cost_uzs, 2)} сум/кг
              </option>
            ))}
          </select>
          {sellable.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
              Нет одобренных партий комбикорма. Сначала проведите замес и выпустите
              паспорт качества (раздел «Корма»).
            </div>
          )}
        </div>

        <div className="field">
          <label>
            Тип корма *
            <HelpHint
              text="Стадия откорма."
              details="• Старт (0–14 дн): высокобелковый стартовый.\n• Рост (15–28 дн): сбалансированный.\n• Финиш (29+ дн): для финального набора массы."
            />
          </label>
          <select
            className="input"
            value={feedType}
            onChange={(e) => setFeedType(e.target.value as typeof feedType)}
          >
            <option value="start">Старт (0–14 дн)</option>
            <option value="growth">Рост (15–28 дн)</option>
            <option value="finish">Финиш (29+ дн)</option>
          </select>
        </div>

        <div className="field">
          <label>
            Кол-во, кг *
            <HelpHint
              text="Сколько корма скормили за период."
              details="Можно записывать по неделям/декадам. Для расчёта периодного FCR должны быть взвешивания на день from и на день to."
            />
          </label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            min="0.001"
            value={totalKg}
            onChange={(e) => setTotalKg(e.target.value)}
            style={overStock ? { borderColor: 'var(--danger)' } : undefined}
          />
          {overStock && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              Превышен остаток в выбранной партии корма
            </div>
          )}
          {getErr('total_kg') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('total_kg')}</div>
          )}
        </div>

        <div className="field">
          <label>
            День от *
            <HelpHint
              text="Начало периода в днях откорма."
              details={`Партия посажена ${batch.placed_date}. Сегодня ≈ день ${todayDayOfAge}.`}
            />
          </label>
          <input
            className="input mono"
            type="number"
            min="0"
            value={fromDay}
            onChange={(e) => setFromDay(e.target.value)}
          />
        </div>

        <div className="field">
          <label>День по *</label>
          <input
            className="input mono"
            type="number"
            min={fromDay}
            value={toDay}
            onChange={(e) => setToDay(e.target.value)}
          />
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметка</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>

      {/* Live preview */}
      {selectedFeedBatch && totalKg && preview.total > 0 && (
        <div style={{
          marginTop: 12, padding: '8px 10px', background: 'var(--bg-soft)',
          borderRadius: 6, fontSize: 12, lineHeight: 1.6,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>На голову:</span>
            <b className="mono">
              {preview.perHeadG !== null
                ? `${preview.perHeadG.toFixed(2)} г`
                : '—'}
            </b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Стоимость:</span>
            <b className="mono">{fmtNum(preview.amount, 0)} сум</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--fg-3)' }}>
            <span>Остаток партии после:</span>
            <span className="mono">
              {preview.remainingAfter !== null
                ? `${fmtNum(preview.remainingAfter, 0)} кг`
                : '—'}
            </span>
          </div>
        </div>
      )}

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{
          marginTop: 12, padding: 8,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 12,
        }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
