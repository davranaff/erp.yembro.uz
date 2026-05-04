'use client';

import { useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { mirageCrud } from '@/hooks/useIncubation';
import { useUser } from '@/hooks/useUser';
import { ApiError } from '@/lib/api';
import type { IncubationRun, MirageInspection } from '@/types/auth';

interface Props {
  run: IncubationRun;
  initial?: MirageInspection | null;
  onClose: () => void;
}

/**
 * Овоскопирование — проверка яиц на просвет на 7-й, 14-й и 18-й день.
 *
 * Бизнес-логика:
 *   inspected_count — сколько проверили (≤ eggs_loaded)
 *   fertile_count   — оплодотворённые (живой эмбрион)
 *   discarded_count — на выбраковку (мёртвые/неоплоды и т.п.)
 *   infertile = inspected − fertile  (неоплоды, считается на бэке)
 */
export default function MirageModal({ run, initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = mirageCrud.useCreate();
  const update = mirageCrud.useUpdate();
  const { data: user } = useUser();

  const [inspectionDate, setInspectionDate] = useState(
    initial?.inspection_date ?? new Date().toISOString().slice(0, 10),
  );
  const [day, setDay] = useState(String(initial?.day_of_incubation ?? Math.max(1, run.current_day ?? 7)));
  const [inspected, setInspected] = useState(String(initial?.inspected_count ?? run.eggs_loaded));
  const [fertile, setFertile] = useState(String(initial?.fertile_count ?? ''));
  const [discarded, setDiscarded] = useState(String(initial?.discarded_count ?? 0));
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const totals = useMemo(() => {
    const i = parseInt(inspected || '0', 10);
    const f = parseInt(fertile || '0', 10);
    const d = parseInt(discarded || '0', 10);
    const infertile = Math.max(0, i - f - d);
    const fertilePct = i > 0 ? (f / i) * 100 : 0;
    const infertilePct = i > 0 ? (infertile / i) * 100 : 0;
    const sumInvalid = (f + d) > i;
    const overLoaded = i > run.eggs_loaded;
    return { i, f, d, infertile, fertilePct, infertilePct, sumInvalid, overLoaded };
  }, [inspected, fertile, discarded, run.eggs_loaded]);

  const canSubmit =
    inspectionDate && day && inspected && fertile !== '' &&
    !totals.sumInvalid && !totals.overLoaded &&
    Boolean(initial?.inspector || user?.id) &&
    !create.isPending && !update.isPending;

  const handleSave = async () => {
    const payload = {
      run: run.id,
      inspection_date: inspectionDate,
      day_of_incubation: Number(day),
      inspected_count: Number(inspected),
      fertile_count: Number(fertile),
      discarded_count: Number(discarded || 0),
      inspector: initial?.inspector ?? user?.id,
      notes,
    } as unknown as MirageInspection;

    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
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
      title={isEdit ? `Овоскопия · ${initial?.inspection_date}` : 'Новая овоскопия'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSave}
          >
            {(create.isPending || update.isPending) ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Партия <b className="mono">{run.doc_number}</b> · загружено {run.eggs_loaded.toLocaleString('ru-RU')} яиц
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата осмотра *</label>
          <input
            className="input"
            type="date"
            value={inspectionDate}
            onChange={(e) => setInspectionDate(e.target.value)}
          />
          {getErr('inspection_date') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('inspection_date')}</div>
          )}
        </div>

        <div className="field">
          <label>День инкубации *</label>
          <input
            className="input mono"
            type="number"
            min="1"
            max={run.days_total}
            value={day}
            onChange={(e) => setDay(e.target.value)}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            типично 7 / 14 / 18
          </div>
        </div>

        <div className="field">
          <label>Осмотрено яиц *</label>
          <input
            className="input mono"
            type="number"
            min="1"
            value={inspected}
            onChange={(e) => setInspected(e.target.value)}
          />
          {totals.overLoaded && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              Больше чем загружено ({run.eggs_loaded.toLocaleString('ru-RU')})
            </div>
          )}
        </div>

        <div className="field">
          <label>Оплодотворённых *</label>
          <input
            className="input mono"
            type="number"
            min="0"
            value={fertile}
            onChange={(e) => setFertile(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Брак (отбраковка)</label>
          <input
            className="input mono"
            type="number"
            min="0"
            value={discarded}
            onChange={(e) => setDiscarded(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Заметка</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      {/* Превью расчётов */}
      <div style={{ marginTop: 14, padding: 10, background: 'var(--bg-soft)', borderRadius: 8, fontSize: 13 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Неоплодов (расчёт):</span>
          <span className="mono">
            {totals.infertile.toLocaleString('ru-RU')} ({totals.infertilePct.toFixed(1)}%)
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, color: 'var(--fg-2)' }}>
          <span>Оплодотворённость:</span>
          <span className="mono">{totals.fertilePct.toFixed(1)}%</span>
        </div>
        {totals.sumInvalid && (
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>
            Сумма оплодотворённых + бракованных не может превышать осмотренных.
          </div>
        )}
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
