'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { enqueueOrSend } from '@/lib/offlineQueue';
import {
  useApplyMortality,
  useShipFeedlot,
} from '@/hooks/useFeedlot';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useWarehouses } from '@/hooks/useStockMovements';
import type { FeedlotBatch } from '@/types/auth';

interface Props {
  batch: FeedlotBatch;
  mode: 'ship' | 'mortality';
  onClose: () => void;
}

export default function FeedlotActionsModal({ batch, mode, onClose }: Props) {
  if (mode === 'ship') return <ShipModal batch={batch} onClose={onClose} />;
  return <MortalityModal batch={batch} onClose={onClose} />;
}

function ShipModal({ batch, onClose }: { batch: FeedlotBatch; onClose: () => void }) {
  const { data: slaughterLines } = useProductionBlocks({
    module_code: 'slaughter',
    kind: 'slaughter_line',
  });
  // Источник — склады откорма, приёмник — склады убойни.
  const { data: feedlotWarehouses } = useWarehouses({ module_code: 'feedlot' });
  const { data: slaughterWarehouses } = useWarehouses({ module_code: 'slaughter' });
  const ship = useShipFeedlot();

  const [slaughterLine, setSlaughterLine] = useState('');
  const [slaughterWarehouse, setSlaughterWarehouse] = useState('');
  const [sourceWarehouse, setSourceWarehouse] = useState('');
  const [qty, setQty] = useState(String(batch.current_heads));

  const error = ship.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const submit = async () => {
    try {
      await ship.mutateAsync({
        id: batch.id,
        body: {
          slaughter_line: slaughterLine,
          slaughter_warehouse: slaughterWarehouse,
          source_warehouse: sourceWarehouse,
          quantity: qty,
        },
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Отгрузка на убой · ${batch.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!slaughterLine || !slaughterWarehouse || !sourceWarehouse || ship.isPending}
            onClick={submit}
          >
            {ship.isPending ? 'Отгрузка…' : 'Отгрузить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Создаст InterModuleTransfer (AWAITING_ACCEPTANCE) и переведёт партию в статус SHIPPED.
      </div>
      <div className="field">
        <label>Линия убоя *</label>
        <select className="input" value={slaughterLine} onChange={(e) => setSlaughterLine(e.target.value)}>
          <option value="">—</option>
          {slaughterLines?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Склад убойни (приём) *</label>
        <select className="input" value={slaughterWarehouse} onChange={(e) => setSlaughterWarehouse(e.target.value)}>
          <option value="">—</option>
          {slaughterWarehouses?.map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Склад откорма (источник) *</label>
        <select className="input" value={sourceWarehouse} onChange={(e) => setSourceWarehouse(e.target.value)}>
          <option value="">—</option>
          {feedlotWarehouses?.map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Голов</label>
        <input className="input mono" type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
        {fieldErrors.quantity && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.quantity.join(' · ')}</div>}
      </div>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}

function MortalityModal({ batch, onClose }: { batch: FeedlotBatch; onClose: () => void }) {
  const apply = useApplyMortality();
  const qc = useQueryClient();

  // Авто-вычисление дня от посадки по дате — оператору не надо считать руками.
  // (placed_date в формате YYYY-MM-DD, разница в днях — простая Date-математика)
  const today = new Date().toISOString().slice(0, 10);
  const initialDay = (() => {
    if (!batch.placed_date) return '';
    const d1 = new Date(batch.placed_date + 'T00:00:00');
    const d2 = new Date(today + 'T00:00:00');
    const diff = Math.floor((d2.getTime() - d1.getTime()) / (24 * 3600 * 1000));
    return diff >= 0 ? String(diff) : '';
  })();

  const [date, setDate] = useState(today);
  const [day, setDay] = useState(initialDay);
  const [dead, setDead] = useState('');
  const [cause, setCause] = useState('');
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fieldErrors = apply.error instanceof ApiError && apply.error.status === 400
    ? ((apply.error.data as Record<string, string[]>) ?? {})
    : {};

  const inc = (delta: number) => () => {
    const cur = parseInt(dead) || 0;
    const next = Math.max(0, cur + delta);
    setDead(String(next));
  };

  const submit = async () => {
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      const result = await enqueueOrSend({
        path: `/api/feedlot/batches/${batch.id}/mortality/`,
        body: {
          date,
          day_of_age: Number(day),
          dead_count: Number(dead),
          cause: cause.trim(),
        },
      });
      // Если оффлайн — `enqueueOrSend` положил в очередь и вернул {queued: true, id}
      if (typeof result === 'object' && result !== null && 'queued' in result) {
        setInfo(
          'Нет сети. Запись сохранена локально и отправится автоматически когда сеть появится.',
        );
        // Дадим юзеру 2 сек прочитать → закрываем
        setTimeout(onClose, 2000);
      } else {
        // Онлайн → инвалидируем кэш чтобы подтянулись свежие данные
        qc.invalidateQueries({ queryKey: ['feedlot'] });
        onClose();
      }
    } catch (e) {
      const err = e as ApiError;
      // Бизнес-ошибка (400) — поля выводят свои сообщения через fieldErrors
      if (err.status !== 400) {
        setError(err.message || 'Не удалось сохранить');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={`Падёж · ${batch.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={!date || !day || !dead || busy}
            onClick={submit}
          >
            {busy ? 'Сохранение…' : 'Записать'}
          </button>
        </>
      }
    >
      <div className="mobile-form">
        <div style={{
          fontSize: 12, color: 'var(--fg-3)', marginBottom: 14,
          padding: '8px 12px', background: 'var(--bg-soft)', borderRadius: 6,
        }}>
          Партия: <strong>{batch.doc_number}</strong> · в строю{' '}
          <strong>{batch.current_heads}</strong> голов
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="field">
            <label className="label">Дата *</label>
            <input
              className="input"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="label">День от посадки *</label>
            <input
              className="input"
              type="number"
              inputMode="numeric"
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label className="label">Пало голов *</label>
          <div className="num-stepper">
            <button
              type="button"
              className="stepper-btn"
              onClick={inc(-1)}
              aria-label="Минус 1"
            >
              −
            </button>
            <input
              type="number"
              inputMode="numeric"
              value={dead}
              onChange={(e) => setDead(e.target.value.replace(/[^\d]/g, ''))}
              placeholder="0"
            />
            <button
              type="button"
              className="stepper-btn"
              onClick={inc(1)}
              aria-label="Плюс 1"
            >
              +
            </button>
          </div>
          {fieldErrors.dead_count && (
            <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 6 }}>
              {fieldErrors.dead_count.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label className="label">Причина</label>
          <input
            className="input"
            value={cause}
            onChange={(e) => setCause(e.target.value)}
            placeholder="например: ослабление, травма"
          />
        </div>

        {info && (
          <div style={{
            padding: 10, marginTop: 10, fontSize: 13,
            background: 'color-mix(in srgb, var(--brand-orange) 15%, transparent)',
            color: 'var(--fg-1)', borderRadius: 6,
          }}>
            ⚡ {info}
          </div>
        )}
        {error && (
          <div style={{
            padding: 10, marginTop: 10, fontSize: 13,
            color: 'var(--danger)',
          }}>
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}
