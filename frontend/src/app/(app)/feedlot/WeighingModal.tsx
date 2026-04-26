'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useRecordWeighing, weighingsCrud } from '@/hooks/useFeedlot';
import { ApiError } from '@/lib/api';
import type { FeedlotBatch } from '@/types/auth';

interface Props {
  batch: FeedlotBatch;
  onClose: () => void;
}

function fmtNum(v: string | number, digits = 3): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

/**
 * Форма ввода контрольного взвешивания.
 *
 * Бэк автоматически:
 *   - считает gain_kg от прошлого взвешивания
 *   - переводит status PLACED→GROWING при первом замере
 *   - переводит status →READY_SLAUGHTER при достижении target_weight_kg
 */
export default function WeighingModal({ batch, onClose }: Props) {
  const record = useRecordWeighing();
  // Подтянем все взвешивания этой партии — для расчёта прироста и подсказок.
  const { data: weighings } = weighingsCrud.useList({ feedlot_batch: batch.id });

  // День возраста = (сегодня − placed_date) в днях
  const todayDayOfAge = useMemo(() => {
    const placed = new Date(batch.placed_date);
    const today = new Date();
    const diff = Math.floor((today.getTime() - placed.getTime()) / 86400000);
    return Math.max(0, diff);
  }, [batch.placed_date]);

  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [day, setDay] = useState(String(todayDayOfAge));
  const [sample, setSample] = useState('50');
  const [avg, setAvg] = useState('');
  const [notes, setNotes] = useState('');

  const error = record.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  // Прошлое взвешивание (для подсчёта прироста на превью)
  const prev = useMemo(() => {
    if (!weighings || weighings.length === 0) return null;
    return [...weighings].sort((a, b) => b.day_of_age - a.day_of_age)[0];
  }, [weighings]);

  const expectedGainKg = useMemo(() => {
    if (!prev || !avg) return null;
    const prevAvg = parseFloat(prev.avg_weight_kg);
    const cur = parseFloat(avg);
    if (Number.isNaN(prevAvg) || Number.isNaN(cur)) return null;
    return cur - prevAvg;
  }, [prev, avg]);

  const daysSincePrev = useMemo(() => {
    if (!prev) return null;
    const dn = parseInt(day || '0', 10);
    return Math.max(0, dn - prev.day_of_age);
  }, [prev, day]);

  const targetReached = (() => {
    const t = parseFloat(batch.target_weight_kg || '0');
    const a = parseFloat(avg || '0');
    return t > 0 && a >= t;
  })();

  const canSubmit = date && day && sample && avg && !record.isPending;

  const handleSubmit = async () => {
    try {
      await record.mutateAsync({
        id: batch.id,
        body: {
          date,
          day_of_age: parseInt(day, 10),
          sample_size: parseInt(sample, 10),
          avg_weight_kg: avg,
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
      title={`Взвешивание · ${batch.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {record.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Контрольное взвешивание выборки птицы. Используется для расчёта
        прироста и FCR. Бэк автоматически переведёт статус партии (PLACED→GROWING
        при первом замере, →READY_SLAUGHTER при достижении целевого веса).
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="field">
          <label>Дата *</label>
          <input
            className="input"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        <div className="field">
          <label>
            День откорма *
            <HelpHint
              text="День от посадки партии."
              details={`Партия посажена ${batch.placed_date}. Сегодня ≈ ${todayDayOfAge} день. Уникален на партию.`}
            />
          </label>
          <input
            className="input mono"
            type="number"
            min="0"
            value={day}
            onChange={(e) => setDay(e.target.value)}
          />
          {getErr('day_of_age') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('day_of_age')}</div>
          )}
        </div>

        <div className="field">
          <label>
            Размер выборки, гол *
            <HelpHint
              text="Сколько птиц взвесили."
              details="Обычно 30–100 голов из стада. Чем больше выборка — тем точнее средний вес. Норма: 50."
            />
          </label>
          <input
            className="input mono"
            type="number"
            min="1"
            value={sample}
            onChange={(e) => setSample(e.target.value)}
          />
        </div>

        <div className="field">
          <label>
            Средний вес, кг *
            <HelpHint
              text="Вес одной птицы (среднее по выборке)."
              details={
                `Целевой вес для этой партии: ${batch.target_weight_kg} кг. `
                + 'Когда avg достигнет цели — статус автоматически перейдёт в «К съёму».'
              }
            />
          </label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            min="0.001"
            value={avg}
            onChange={(e) => setAvg(e.target.value)}
            placeholder="2.500"
            style={targetReached ? { borderColor: 'var(--success)' } : undefined}
          />
          {targetReached && avg && (
            <div style={{ fontSize: 11, color: 'var(--success)', marginTop: 4 }}>
              Целевой вес достигнут — статус перейдёт в «К съёму»
            </div>
          )}
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
      {prev && expectedGainKg !== null && (
        <div style={{
          marginTop: 12, padding: '8px 10px', background: 'var(--bg-soft)',
          borderRadius: 6, fontSize: 12, lineHeight: 1.5,
        }}>
          <div>
            Прошлое взвешивание: день {prev.day_of_age} · ср. вес{' '}
            <b className="mono">{fmtNum(prev.avg_weight_kg)} кг</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
            <span>Прирост за период:</span>
            <b className="mono" style={{
              color: expectedGainKg >= 0 ? 'var(--success)' : 'var(--danger)',
            }}>
              {expectedGainKg >= 0 ? '+' : ''}{fmtNum(expectedGainKg)} кг
              {daysSincePrev && daysSincePrev > 0 && (
                <span style={{ fontSize: 10, color: 'var(--fg-3)', marginLeft: 4 }}>
                  ({Math.round((expectedGainKg * 1000) / daysSincePrev)} г/день)
                </span>
              )}
            </b>
          </div>
        </div>
      )}

      {!prev && (
        <div style={{
          marginTop: 12, padding: '8px 10px', background: 'var(--bg-soft)',
          borderRadius: 6, fontSize: 11, color: 'var(--fg-3)',
        }}>
          Это первое взвешивание для партии. Прирост рассчитается со следующего раза.
          После сохранения статус партии перейдёт в «Откорм».
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
