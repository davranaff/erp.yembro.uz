'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useCounterparties } from '@/hooks/useCounterparties';
import { useUnits } from '@/hooks/useNomenclature';
import { purchasesCrud } from '@/hooks/usePurchases';
import { useWarehouses } from '@/hooks/useStockMovements';
import { drugsCrud, useReceiveVetStock } from '@/hooks/useVet';

interface Props {
  onClose: () => void;
}

/**
 * POST /api/vet/stock-batches/receive/
 */
export default function ReceiveModal({ onClose }: Props) {
  const { data: drugs } = drugsCrud.useList({ is_active: 'true' });
  // Только склады модуля vet — vet-препараты лежат там
  const { data: warehouses } = useWarehouses({ module_code: 'vet' });
  const { data: suppliers } = useCounterparties({ kind: 'supplier' });
  const { data: units } = useUnits();
  const { data: purchases } = purchasesCrud.useList();
  const receive = useReceiveVetStock();

  const [drug, setDrug] = useState('');
  const [lotNumber, setLotNumber] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [supplier, setSupplier] = useState('');
  const [purchase, setPurchase] = useState('');
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().slice(0, 10));
  const [expirationDate, setExpirationDate] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('');
  const [price, setPrice] = useState('');
  const [quarantineUntil, setQuarantineUntil] = useState('');
  const [notes, setNotes] = useState('');

  const error = receive.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await receive.mutateAsync({
        drug,
        lot_number: lotNumber,
        warehouse,
        supplier,
        purchase,
        received_date: receivedDate,
        expiration_date: expirationDate,
        quantity,
        unit,
        price_per_unit_uzs: price,
        quarantine_until: quarantineUntil || undefined,
        notes,
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title="Приёмка лота препарата"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!drug || !lotNumber || !warehouse || !supplier || !purchase || !quantity || !unit || !price || !expirationDate || receive.isPending}
            onClick={handleSubmit}
          >
            {receive.isPending ? 'Приёмка…' : 'Принять'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Создаёт VetStockBatch со статусом <span className="mono">quarantine</span>.
        Выпустить из карантина — кнопкой «✓» в таблице.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Препарат *</label>
          <select className="input" value={drug} onChange={(e) => setDrug(e.target.value)}>
            <option value="">—</option>
            {drugs?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.nomenclature_sku} · {d.nomenclature_name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Lot № *</label>
          <input className="input mono" value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} placeholder="L-2603" />
          {fieldErrors.lot_number && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.lot_number.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Склад *</label>
          <select className="input" value={warehouse} onChange={(e) => setWarehouse(e.target.value)}>
            <option value="">—</option>
            {warehouses?.map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Поставщик *</label>
          <select className="input" value={supplier} onChange={(e) => setSupplier(e.target.value)}>
            <option value="">—</option>
            {suppliers?.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>
            Закуп * <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>(PurchaseOrder для compliance/audit)</span>
          </label>
          <select
            className="input"
            value={purchase}
            onChange={(e) => {
              const id = e.target.value;
              setPurchase(id);
              const po = purchases?.find((p) => p.id === id);
              if (po) {
                if (po.counterparty) setSupplier(po.counterparty);
                if (po.warehouse) setWarehouse(po.warehouse);
              }
            }}
          >
            <option value="">— выберите закуп —</option>
            {purchases?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.doc_number} · {p.date} · {p.counterparty_name ?? p.counterparty}
              </option>
            ))}
          </select>
          {purchase && (() => {
            const po = purchases?.find((p) => p.id === purchase);
            if (!po) return null;
            return (
              <div style={{
                marginTop: 6, padding: '6px 10px',
                background: 'var(--bg-soft)', borderRadius: 5,
                fontSize: 12, color: 'var(--fg-2)',
                display: 'flex', gap: 16, flexWrap: 'wrap',
              }}>
                {po.counterparty_name && <span>Поставщик: <b>{po.counterparty_name}</b></span>}
                {po.amount_uzs && (
                  <span>Сумма: <b className="mono">
                    {parseFloat(po.amount_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум
                  </b></span>
                )}
                {po.items && po.items.length > 0 && (
                  <span>Позиций: <b>{po.items.length}</b></span>
                )}
              </div>
            );
          })()}
          {fieldErrors.purchase && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {(fieldErrors.purchase as unknown as string[]).join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Дата приёмки *</label>
          <input className="input" type="date" value={receivedDate} onChange={(e) => setReceivedDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Годен до *</label>
          <input className="input" type="date" value={expirationDate} onChange={(e) => setExpirationDate(e.target.value)} />
          {fieldErrors.expiration_date && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.expiration_date.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Количество *</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Ед. *</label>
          <select className="input" value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="">—</option>
            {units?.map((u) => <option key={u.id} value={u.id}>{u.code} · {u.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Цена за ед. (UZS) *</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Карантин до (опц.)</label>
          <input
            className="input"
            type="date"
            value={quarantineUntil}
            onChange={(e) => setQuarantineUntil(e.target.value)}
          />
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
