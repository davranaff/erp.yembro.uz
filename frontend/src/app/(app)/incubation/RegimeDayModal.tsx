'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { regimeDaysCrud } from '@/hooks/useIncubation';
import { ApiError } from '@/lib/api';
import type { IncubationRegimeDay, IncubationRun } from '@/types/auth';

interface Props {
  run: IncubationRun;
  initial?: IncubationRegimeDay | null;
  onClose: () => void;
}

/**
 * Замер режима за конкретный день инкубации.
 *
 * temperature_c / humidity_percent / egg_turns_per_day — целевые показатели
 * (норма для дня цикла).
 * actual_* — фактические замеры технолога. Если отличаются от целевых — UI
 * подсветит дельту красным.
 */
export default function RegimeDayModal({ run, initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = regimeDaysCrud.useCreate();
  const update = regimeDaysCrud.useUpdate();

  const [day, setDay] = useState(String(initial?.day ?? Math.max(1, run.current_day ?? 1)));
  const [temperatureC, setTemperatureC] = useState(initial?.temperature_c ?? '37.80');
  const [humidityPct, setHumidityPct] = useState(initial?.humidity_percent ?? '55.00');
  const [turnsPerDay, setTurnsPerDay] = useState(String(initial?.egg_turns_per_day ?? 12));
  const [actualTemp, setActualTemp] = useState(initial?.actual_temperature_c ?? '');
  const [actualHum, setActualHum] = useState(initial?.actual_humidity_percent ?? '');
  const [observedAt, setObservedAt] = useState(
    initial?.observed_at?.slice(0, 16) ?? new Date().toISOString().slice(0, 16),
  );
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const tempDelta = actualTemp && temperatureC
    ? parseFloat(actualTemp) - parseFloat(temperatureC) : null;
  const humDelta = actualHum && humidityPct
    ? parseFloat(actualHum) - parseFloat(humidityPct) : null;
  const tempWarn = tempDelta !== null && Math.abs(tempDelta) > 1.0;
  const humWarn = humDelta !== null && Math.abs(humDelta) > 5.0;

  const handleSave = async () => {
    const payload = {
      run: run.id,
      day: Number(day),
      temperature_c: temperatureC,
      humidity_percent: humidityPct,
      egg_turns_per_day: Number(turnsPerDay),
      actual_temperature_c: actualTemp || null,
      actual_humidity_percent: actualHum || null,
      observed_at: observedAt ? new Date(observedAt).toISOString() : null,
      notes,
    } as unknown as IncubationRegimeDay;

    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch { /* поднимется в state */ }
  };

  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title={isEdit ? `Замер режима · день ${initial?.day}` : 'Новый замер режима'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={create.isPending || update.isPending || !day || !temperatureC || !humidityPct}
            onClick={handleSave}
          >
            {(create.isPending || update.isPending) ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Партия <b className="mono">{run.doc_number}</b> · день инкубации (1..{run.days_total})
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>День *</label>
          <input
            className="input mono"
            type="number"
            min="1"
            max={run.days_total}
            value={day}
            onChange={(e) => setDay(e.target.value)}
            disabled={isEdit}
          />
          {getErr('day') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('day')}</div>}
        </div>

        <div className="field">
          <label>Время замера</label>
          <input
            className="input"
            type="datetime-local"
            value={observedAt}
            onChange={(e) => setObservedAt(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Целевая T °C *</label>
          <input
            className="input mono"
            type="number"
            step="0.1"
            value={temperatureC}
            onChange={(e) => setTemperatureC(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Целевая H % *</label>
          <input
            className="input mono"
            type="number"
            step="0.1"
            value={humidityPct}
            onChange={(e) => setHumidityPct(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Фактическая T °C</label>
          <input
            className="input mono"
            type="number"
            step="0.1"
            value={actualTemp}
            onChange={(e) => setActualTemp(e.target.value)}
            placeholder="—"
          />
          {tempDelta !== null && (
            <div style={{
              fontSize: 11,
              color: tempWarn ? 'var(--danger)' : 'var(--fg-3)',
              marginTop: 4,
            }}>
              Δ {tempDelta > 0 ? '+' : ''}{tempDelta.toFixed(2)} °C
              {tempWarn && ' · отклонение!'}
            </div>
          )}
        </div>

        <div className="field">
          <label>Фактическая H %</label>
          <input
            className="input mono"
            type="number"
            step="0.1"
            value={actualHum}
            onChange={(e) => setActualHum(e.target.value)}
            placeholder="—"
          />
          {humDelta !== null && (
            <div style={{
              fontSize: 11,
              color: humWarn ? 'var(--danger)' : 'var(--fg-3)',
              marginTop: 4,
            }}>
              Δ {humDelta > 0 ? '+' : ''}{humDelta.toFixed(2)} %
              {humWarn && ' · отклонение!'}
            </div>
          )}
        </div>

        <div className="field">
          <label>Поворотов/сутки</label>
          <input
            className="input mono"
            type="number"
            min="0"
            value={turnsPerDay}
            onChange={(e) => setTurnsPerDay(e.target.value)}
          />
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметка</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
