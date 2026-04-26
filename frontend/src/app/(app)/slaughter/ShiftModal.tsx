'use client';

import { useEffect, useMemo, useState } from 'react';

import BatchSelector from '@/components/BatchSelector';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { feedlotCrud } from '@/hooks/useFeedlot';
import { useModules } from '@/hooks/useModules';
import { usePeople } from '@/hooks/usePeople';
import { shiftsCrud } from '@/hooks/useSlaughter';
import type { Batch } from '@/types/auth';

interface Props {
  onClose: () => void;
}

/** POST /api/slaughter/shifts/ */
export default function ShiftModal({ onClose }: Props) {
  const create = shiftsCrud.useCreate();
  const { data: modules } = useModules();
  const { data: lines } = useProductionBlocks({
    module_code: 'slaughter', kind: 'slaughter_line',
  });
  const { data: people } = usePeople({ is_active: 'true' });

  const slaughterModuleId = modules?.find((m) => m.code === 'slaughter')?.id ?? '';

  const today = new Date();
  const [docNumber, setDocNumber] = useState('');
  const [lineBlock, setLineBlock] = useState('');
  const [sourceBatch, setSourceBatch] = useState('');
  const [pickedBatch, setPickedBatch] = useState<Batch | null>(null);
  const [shiftDate, setShiftDate] = useState(today.toISOString().slice(0, 10));
  const [startTime, setStartTime] = useState(
    new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 16),
  );
  // touched-флаги — пользователь редактировал поле вручную → не перезаписываем автозаполнением
  const [headsTouched, setHeadsTouched] = useState(false);
  const [weightTouched, setWeightTouched] = useState(false);
  const [liveHeads, setLiveHeads] = useState('');
  const [liveWeight, setLiveWeight] = useState('');
  const [foreman, setForeman] = useState('');
  const [notes, setNotes] = useState('');

  // Подтянуть FeedlotBatch для текущей партии — для среднего веса
  const { data: feedlotBatches } = feedlotCrud.useList(
    sourceBatch ? { batch: sourceBatch } : {},
  );
  const fbatch = useMemo(
    () => feedlotBatches?.find((fb) => fb.batch === sourceBatch) ?? null,
    [feedlotBatches, sourceBatch],
  );
  const avgWeightKg = fbatch?.current_avg_weight_kg
    ? parseFloat(fbatch.current_avg_weight_kg)
    : null;

  // Авто-заполнение при выборе партии
  useEffect(() => {
    if (!pickedBatch) return;
    const heads = parseFloat(pickedBatch.current_quantity || '0');
    if (!headsTouched && heads > 0) {
      setLiveHeads(String(Math.round(heads)));
    }
    if (!weightTouched && heads > 0 && avgWeightKg && avgWeightKg > 0) {
      setLiveWeight((heads * avgWeightKg).toFixed(3));
    }
  }, [pickedBatch, avgWeightKg, headsTouched, weightTouched]);

  const error = create.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    if (!slaughterModuleId) { alert('Модуль slaughter не найден'); return; }
    try {
      await create.mutateAsync({
        doc_number: docNumber,
        module: slaughterModuleId,
        line_block: lineBlock,
        source_batch: sourceBatch,
        shift_date: shiftDate,
        start_time: new Date(startTime).toISOString(),
        live_heads_received: Number(liveHeads),
        live_weight_kg_total: liveWeight,
        foreman,
        notes,
      } as never);
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title="Новая смена убоя"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!docNumber || !lineBlock || !sourceBatch || !liveHeads || !liveWeight || !foreman || create.isPending}
            onClick={handleSubmit}
          >
            {create.isPending ? 'Создание…' : 'Создать смену'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Создаёт смену в статусе ACTIVE. Партия должна быть уже принята в модуль убоя
        (через приёмку транзфера из откорма). Голов и живой вес автозаполняются
        из партии — можно скорректировать вручную.
      </div>
      <BatchSelector
        label="Партия источник *"
        value={sourceBatch}
        onChange={(id, batch) => {
          setSourceBatch(id);
          setPickedBatch(batch);
          // При смене партии разрешить новое автозаполнение
          setHeadsTouched(false);
          setWeightTouched(false);
        }}
        filter={{
          state: 'active',
          ...(slaughterModuleId ? { current_module: slaughterModuleId } : {}),
        }}
      />
      {fieldErrors.source_batch && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.source_batch.join(' · ')}</div>}

      {pickedBatch && (
        <div
          style={{
            marginTop: 8, marginBottom: 8, padding: 8,
            background: 'var(--bg-soft)', borderRadius: 6,
            border: '1px solid var(--border)',
            fontSize: 12, color: 'var(--fg-2)',
            display: 'flex', gap: 16, flexWrap: 'wrap',
          }}
        >
          <span>
            <span style={{ color: 'var(--fg-3)' }}>В партии: </span>
            <strong className="mono">
              {parseFloat(pickedBatch.current_quantity).toLocaleString('ru-RU')} {pickedBatch.unit_code ?? 'шт'}
            </strong>
          </span>
          {avgWeightKg !== null ? (
            <span>
              <span style={{ color: 'var(--fg-3)' }}>Ср. вес из последнего взвешивания: </span>
              <strong className="mono">{avgWeightKg.toFixed(3)} кг</strong>
            </span>
          ) : (
            <span style={{ color: 'var(--warning)' }}>
              Взвешиваний в откорме не было — введите живой вес вручную
            </span>
          )}
          <span>
            <span style={{ color: 'var(--fg-3)' }}>Накопленная себестоимость: </span>
            <strong className="mono">
              {parseFloat(pickedBatch.accumulated_cost_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум
            </strong>
          </span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Документ *</label>
          <input
            className="input mono"
            value={docNumber}
            onChange={(e) => setDocNumber(e.target.value)}
            placeholder="УБ-2026-001"
          />
          {fieldErrors.doc_number && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.doc_number.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Линия *</label>
          <select className="input" value={lineBlock} onChange={(e) => setLineBlock(e.target.value)}>
            <option value="">—</option>
            {lines?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Дата смены *</label>
          <input className="input" type="date" value={shiftDate} onChange={(e) => setShiftDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Начало *</label>
          <input
            className="input"
            type="datetime-local"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
          />
        </div>
        <div className="field">
          <label>
            Голов принято *
            {pickedBatch && !headsTouched && (
              <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--brand-orange)' }}>
                ← из партии
              </span>
            )}
          </label>
          <input
            className="input mono"
            type="number"
            value={liveHeads}
            onChange={(e) => { setLiveHeads(e.target.value); setHeadsTouched(true); }}
          />
        </div>
        <div className="field">
          <label>
            Живой вес, кг *
            {pickedBatch && !weightTouched && avgWeightKg !== null && (
              <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--brand-orange)' }}>
                ← {parseFloat(liveHeads || '0').toLocaleString('ru-RU')} × {avgWeightKg.toFixed(3)} кг
              </span>
            )}
          </label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={liveWeight}
            onChange={(e) => { setLiveWeight(e.target.value); setWeightTouched(true); }}
          />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Бригадир *</label>
          <select className="input" value={foreman} onChange={(e) => setForeman(e.target.value)}>
            <option value="">—</option>
            {people?.map((p) => (
              <option key={p.user} value={p.user}>{p.user_full_name} · {p.position_title || p.user_email}</option>
            ))}
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметка</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
