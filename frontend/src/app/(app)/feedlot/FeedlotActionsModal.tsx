'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
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
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [day, setDay] = useState('');
  const [dead, setDead] = useState('');
  const [cause, setCause] = useState('');

  const error = apply.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const submit = async () => {
    try {
      await apply.mutateAsync({
        id: batch.id,
        body: { date, day_of_age: Number(day), dead_count: Number(dead), cause },
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Падёж · ${batch.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!date || !day || !dead || apply.isPending}
            onClick={submit}
          >
            {apply.isPending ? 'Запись…' : 'Записать'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div className="field">
          <label>День от посадки *</label>
          <input className="input mono" type="number" value={day} onChange={(e) => setDay(e.target.value)} />
        </div>
        <div className="field">
          <label>Пало голов *</label>
          <input className="input mono" type="number" value={dead} onChange={(e) => setDead(e.target.value)} />
          {fieldErrors.dead_count && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.dead_count.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Причина</label>
          <input className="input" value={cause} onChange={(e) => setCause(e.target.value)} />
        </div>
      </div>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
