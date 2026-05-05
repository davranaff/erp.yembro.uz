'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useCounterparties } from '@/hooks/useCounterparties';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { usePromoteToRawBatch } from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { StockMovement } from '@/types/auth';

interface Props {
  movement: StockMovement;
  onClose: () => void;
  onPromoted?: (newBatchId: string) => void;
}

function duvalShrinkPct(actual: number, base: number): number {
  if (!actual || !base || actual <= base) return 0;
  if (base >= 100) return 0;
  return (100 * (actual - base)) / (100 - base);
}

/**
 * Превратить ручной INCOMING-movement в полноценную партию сырья
 * (RawMaterialBatch). Контекст из movement показан read-only,
 * пользователь дозаполняет только feed-специфичные поля
 * (влажность / сорность / карантин).
 */
export default function PromoteToRawBatchModal({ movement, onClose, onPromoted }: Props) {
  const promote = usePromoteToRawBatch();
  const { data: parties } = useCounterparties({ kind: 'supplier' });
  const { data: noms } = useNomenclatureItems({ module_code: 'feed', is_active: 'true' });

  // Сегодня + 7 дней — типичный карантин
  const defaultQuarantine = (() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().slice(0, 10);
  })();

  const [moisture, setMoisture] = useState('');
  const [dockage, setDockage] = useState('');
  const [putToQuarantine, setPutToQuarantine] = useState(true);
  const [quarantineUntil, setQuarantineUntil] = useState(defaultQuarantine);
  const [supplier, setSupplier] = useState(movement.counterparty ?? '');
  const [storageBin, setStorageBin] = useState('');
  const [notes, setNotes] = useState('');

  const error = promote.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const nomItem = noms?.find((n) => n.id === movement.nomenclature);
  const baseMoisture = nomItem?.base_moisture_pct
    ? parseFloat(nomItem.base_moisture_pct)
    : null;

  // Live preview зачётного веса
  const preview = useMemo(() => {
    const gross = parseFloat(movement.quantity || '0');
    const m = parseFloat(moisture || '0');
    const d = parseFloat(dockage || '0');
    if (gross <= 0) return { settlement: 0, shrinkPct: 0 };

    let shrinkPct = 0;
    if (baseMoisture != null && m > 0) {
      shrinkPct = duvalShrinkPct(m, baseMoisture) + d;
    } else if (d > 0) {
      shrinkPct = d;
    }
    const settlement = shrinkPct > 0
      ? gross * (1 - shrinkPct / 100)
      : gross;
    return { settlement, shrinkPct };
  }, [movement.quantity, moisture, dockage, baseMoisture]);

  const handleSubmit = async () => {
    try {
      const result = await promote.mutateAsync({
        id: movement.id,
        body: {
          moisture_pct_actual: moisture || null,
          dockage_pct_actual: dockage || null,
          shrinkage_pct: preview.shrinkPct > 0 ? preview.shrinkPct.toFixed(3) : null,
          quarantine_until: putToQuarantine ? quarantineUntil : null,
          supplier: supplier || null,
          storage_bin: storageBin,
          notes,
        },
      });
      onPromoted?.(result.raw_batch.id);
      onClose();
    } catch { /* in state */ }
  };

  return (
    <Modal
      title={`Превратить ${movement.doc_number} в партию сырья`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={promote.isPending}
          >
            {promote.isPending ? 'Создание…' : 'Создать партию'}
          </button>
        </>
      }
    >
      <div style={{
        padding: 10, marginBottom: 14,
        background: 'var(--info-soft)',
        border: '1px solid var(--info)',
        borderRadius: 4, fontSize: 12, color: '#1E4D80',
      }}>
        Это движение станет «партией сырья» модуля «Корма» — с зачётным весом
        по Дювалю, карантином и FIFO для замеса. Существующая запись в журнале
        не дублируется, она перепривязывается к новой партии.
      </div>

      {/* Read-only context */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
        padding: 10, marginBottom: 14,
        background: 'var(--bg-soft)', borderRadius: 6, fontSize: 12,
      }}>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>SKU</div>
          <div className="mono" style={{ fontWeight: 500 }}>
            {movement.nomenclature_sku} · {movement.nomenclature_name}
          </div>
        </div>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>Склад</div>
          <div className="mono">{movement.warehouse_to_code ?? '—'}</div>
        </div>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>Брутто, кг</div>
          <div className="mono">{parseFloat(movement.quantity).toLocaleString('ru-RU')}</div>
        </div>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>Цена за ед</div>
          <div className="mono">
            {parseFloat(movement.unit_price_uzs ?? '0').toLocaleString('ru-RU')} сум
          </div>
        </div>
      </div>

      {baseMoisture != null && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="field">
            <label>
              Влажность факт., %
              <HelpHint
                text="Для расчёта зачётного веса по Дювалю."
                details={`Базисная влажность для ${nomItem?.sku}: ${baseMoisture}%. Если факт выше базы — система пересчитает зачётный вес по формуле: (100 × (факт - база)) / (100 - база).`}
              />
            </label>
            <input
              className="input mono"
              type="number" step="0.01" min="0"
              value={moisture}
              placeholder={`база: ${baseMoisture}`}
              onChange={(e) => setMoisture(e.target.value)}
            />
          </div>
          <div className="field">
            <label>
              Сорность, %
              <HelpHint
                text="Доля примесей."
                details="Прибавляется к расчёту усушки помимо влажности."
              />
            </label>
            <input
              className="input mono"
              type="number" step="0.01" min="0"
              value={dockage}
              placeholder="0"
              onChange={(e) => setDockage(e.target.value)}
            />
          </div>
        </div>
      )}

      {preview.shrinkPct > 0 && (
        <div style={{
          marginTop: 8, padding: 8, fontSize: 12,
          background: 'var(--warning-soft)', borderRadius: 4,
          color: '#6A4500',
        }}>
          Усушка: <b className="mono">{preview.shrinkPct.toFixed(2)}%</b>
          <span style={{ marginLeft: 12 }}>
            Зачётный вес: <b className="mono">{preview.settlement.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} кг</b>
          </span>
        </div>
      )}

      <div className="field" style={{ marginTop: 12 }}>
        <label>Поставщик</label>
        <select
          className="input"
          value={supplier}
          onChange={(e) => setSupplier(e.target.value)}
        >
          <option value="">— не указан —</option>
          {parties?.map((p) => (
            <option key={p.id} value={p.id}>{p.code} · {p.name}</option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 8 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={putToQuarantine}
            onChange={(e) => setPutToQuarantine(e.target.checked)}
          />
          В карантин до
        </label>
        <input
          className="input mono"
          type="date"
          value={quarantineUntil}
          onChange={(e) => setQuarantineUntil(e.target.value)}
          disabled={!putToQuarantine}
          style={{ width: 160 }}
        />
      </div>

      <div className="field" style={{ marginTop: 12 }}>
        <label>Бункер / секция</label>
        <input
          className="input"
          value={storageBin}
          onChange={(e) => setStorageBin(e.target.value)}
          placeholder="например, БК-3"
        />
      </div>

      <div className="field">
        <label>Заметка</label>
        <input
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="напр. контракт №14"
        />
      </div>

      {error && error.status === 400 && Object.entries(fieldErrors)
        .filter(([k]) => !['moisture_pct_actual', 'dockage_pct_actual', 'shrinkage_pct'].includes(k))
        .map(([k, msgs]) => (
          <div key={k} style={{
            fontSize: 12, color: 'var(--danger)', marginTop: 8,
            padding: '8px 10px', background: 'rgba(220,38,38,0.06)', borderRadius: 4,
          }}>
            <b style={{ textTransform: 'uppercase', fontSize: 10 }}>{k}: </b>
            {Array.isArray(msgs) ? msgs.join(' · ') : String(msgs)}
          </div>
        ))}
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
