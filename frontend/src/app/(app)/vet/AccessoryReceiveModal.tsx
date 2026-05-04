'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useReceiveAccessory } from '@/hooks/useVet';
import type { VetAccessory } from '@/types/auth';

interface Props {
  accessory: VetAccessory;
  onClose: () => void;
}

/**
 * Модалка приёмки аксессуара.
 *
 * Если задать `unit_cost_uzs` — backend пересчитает weighted-avg себестоимости.
 * Если оставить пустым — просто +qty без переоценки (довоз по той же цене).
 */
export default function AccessoryReceiveModal({ accessory, onClose }: Props) {
  const receive = useReceiveAccessory();
  const [quantity, setQuantity] = useState('');
  const [unitCost, setUnitCost] = useState('');
  const [notes, setNotes] = useState('');

  const error = receive.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};
  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const submit = async () => {
    if (!quantity || parseFloat(quantity) <= 0) return;
    try {
      await receive.mutateAsync({
        id: accessory.id,
        quantity,
        unit_cost_uzs: unitCost.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch {
      /* */
    }
  };

  // Прогноз нового avg-cost
  const oldQty = parseFloat(accessory.current_quantity);
  const oldCost = parseFloat(accessory.cost_per_unit_uzs ?? '0');
  const addQty = parseFloat(quantity || '0');
  const newCostInput = parseFloat(unitCost || '0');
  let predictedAvg: number | null = null;
  if (addQty > 0 && unitCost.trim()) {
    if (oldQty <= 0) predictedAvg = newCostInput;
    else predictedAvg = (oldQty * oldCost + addQty * newCostInput) / (oldQty + addQty);
  }

  return (
    <Modal
      title={`Приёмка · ${accessory.nomenclature_name ?? accessory.nomenclature_sku}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!quantity || parseFloat(quantity) <= 0 || receive.isPending}
            onClick={submit}
          >
            {receive.isPending ? 'Принимаем…' : 'Принять'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Текущий остаток:{' '}
        <b className="mono">{accessory.current_quantity} {accessory.unit_code ?? ''}</b>
        {accessory.cost_per_unit_uzs != null && (
          <> · Текущая себестоимость:{' '}
            <b className="mono">{parseFloat(accessory.cost_per_unit_uzs).toLocaleString('ru-RU')} сум</b>
          </>
        )}
      </div>

      <div className="field">
        <label>Количество к приёмке *</label>
        <input
          className="input mono"
          type="number"
          step="0.001"
          min={0}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
        {getErr('quantity') && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('quantity')}</div>
        )}
      </div>

      <div className="field">
        <label>Себестоимость новой партии (опц.)</label>
        <input
          className="input mono"
          type="number"
          step="0.01"
          min={0}
          value={unitCost}
          onChange={(e) => setUnitCost(e.target.value)}
          placeholder="оставьте пустым — без переоценки"
        />
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          Если задано — пересчёт weighted-avg по формуле{' '}
          <code>(старый_qty × старый_cost + новый_qty × новая_цена) / итог_qty</code>
        </div>
        {getErr('unit_cost_uzs') && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('unit_cost_uzs')}</div>
        )}
      </div>

      {predictedAvg != null && (
        <div style={{
          padding: 10, marginBottom: 12, borderRadius: 6,
          background: 'var(--bg-soft)', border: '1px solid var(--border)',
          fontSize: 12,
        }}>
          После приёмки:<br />
          • Остаток: <b className="mono">{(oldQty + addQty).toLocaleString('ru-RU')} {accessory.unit_code ?? ''}</b><br />
          • Avg-себестоимость: <b className="mono">{predictedAvg.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} сум</b>
        </div>
      )}

      <div className="field">
        <label>Комментарий</label>
        <input
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="довоз из китая · накладная № …"
        />
      </div>

      {error && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, fontSize: 12, color: 'var(--danger)', background: '#fef2f2', borderRadius: 4 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
