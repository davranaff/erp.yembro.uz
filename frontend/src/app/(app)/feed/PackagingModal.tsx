'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { usePackageFeedBatch } from '@/hooks/useFeed';
import { useWarehouses } from '@/hooks/useStockMovements';
import type { FeedBatch } from '@/types/auth';

interface Props {
  batch: FeedBatch;
  onClose: () => void;
}

/**
 * Расфасовать партию готового комбикорма в мешки.
 * Декрементит batch.current_quantity_kg на bag_count × bag_weight_kg,
 * создаёт FeedBagLot со штучным учётом на отдельном складе мешков.
 */
export default function PackagingModal({ batch, onClose }: Props) {
  const { data: warehouses } = useWarehouses({ module_code: 'feed' });
  const { data: bins } = useProductionBlocks({ module_code: 'feed', kind: 'storage_bin' });
  const pkg = usePackageFeedBatch();

  const [bagCount, setBagCount] = useState('');
  const [bagWeightKg, setBagWeightKg] = useState('50');
  // По умолчанию НЕ тот же склад что у замеса — чтобы фасовка лежала отдельно.
  // Оператор пусть выберет явно.
  const [storageWarehouse, setStorageWarehouse] = useState('');
  const [storageBin, setStorageBin] = useState('');
  const [notes, setNotes] = useState('');

  const error = pkg.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const remainingKg = parseFloat(batch.current_quantity_kg || '0');
  const totalKgConsumed = useMemo(() => {
    const c = parseInt(bagCount || '0', 10);
    const w = parseFloat(bagWeightKg || '0');
    if (!isFinite(c) || !isFinite(w)) return 0;
    return c * w;
  }, [bagCount, bagWeightKg]);
  const overflow = totalKgConsumed > remainingKg;

  const handleSubmit = async () => {
    try {
      await pkg.mutateAsync({
        id: batch.id,
        body: {
          bag_count: parseInt(bagCount, 10),
          bag_weight_kg: bagWeightKg,
          storage_warehouse: storageWarehouse,
          storage_bin: storageBin || null,
          notes,
        },
      });
      onClose();
    } catch { /* остаётся в state */ }
  };

  const canSubmit =
    bagCount && parseInt(bagCount, 10) > 0
    && bagWeightKg && parseFloat(bagWeightKg) > 0
    && storageWarehouse
    && !overflow
    && !pkg.isPending;

  return (
    <Modal
      title={`Расфасовать ${batch.doc_number} в мешки`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {pkg.isPending ? 'Фасовка…' : 'Расфасовать'}
          </button>
        </>
      }
    >
      <div style={{
        padding: 10, background: 'var(--bg-soft)', borderRadius: 6,
        fontSize: 12, lineHeight: 1.5, marginBottom: 14,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          Что произойдёт при фасовке:
        </div>
        <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--fg-2)' }}>
          <li>Из партии замеса <b>{batch.doc_number}</b> спишется
            {' '}{totalKgConsumed.toLocaleString('ru-RU')} кг</li>
          <li>Создастся партия мешков (учёт в штуках)</li>
          <li>Себестоимость одного мешка = себест/кг × вес мешка</li>
          <li>Можно вызвать несколько раз — например частями</li>
        </ul>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>
            Кол-во мешков *
            <HelpHint
              text="Сколько мешков расфасовали."
              details="Должно быть целое > 0. Можно расфасовать только часть партии — остаток останется в насыпи и может быть продан крупным оптом."
            />
          </label>
          <input
            className="input mono"
            type="number"
            step="1"
            min="1"
            value={bagCount}
            onChange={(e) => setBagCount(e.target.value)}
          />
          {fieldErrors.bag_count && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {Array.isArray(fieldErrors.bag_count)
                ? fieldErrors.bag_count.join(' · ')
                : String(fieldErrors.bag_count)}
            </div>
          )}
        </div>
        <div className="field">
          <label>
            Вес мешка, кг *
            <HelpHint
              text="Стандартная фасовка."
              details="Обычно 50 кг (полипропиленовые мешки). Если по факту вес плавает — указывайте средний; для строгого учёта по фактическому весу нужна отдельная операция взвешивания."
            />
          </label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            min="0.001"
            value={bagWeightKg}
            onChange={(e) => setBagWeightKg(e.target.value)}
          />
          {fieldErrors.bag_weight_kg && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {Array.isArray(fieldErrors.bag_weight_kg)
                ? fieldErrors.bag_weight_kg.join(' · ')
                : String(fieldErrors.bag_weight_kg)}
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: overflow ? 'var(--danger)' : 'var(--fg-3)' }}>
        Будет списано: <b className="mono">{totalKgConsumed.toLocaleString('ru-RU')} кг</b>
        {' '}/ доступно <b className="mono">{remainingKg.toLocaleString('ru-RU')} кг</b>
        {overflow && ' · превышает остаток партии'}
      </div>

      <div className="field" style={{ marginTop: 12 }}>
        <label>
          Склад мешков *
          <HelpHint
            text="Куда складываем расфасованные мешки."
            details="Желательно отдельный склад от бункера замеса — чтобы при инвентаризации можно было отдельно пересчитать мешки физически."
          />
        </label>
        <select
          className="input"
          value={storageWarehouse}
          onChange={(e) => setStorageWarehouse(e.target.value)}
        >
          <option value="">—</option>
          {warehouses?.filter((w) => w.module_code === 'feed').map((w) => (
            <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
          ))}
        </select>
        {fieldErrors.storage_warehouse && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {Array.isArray(fieldErrors.storage_warehouse)
              ? fieldErrors.storage_warehouse.join(' · ')
              : String(fieldErrors.storage_warehouse)}
          </div>
        )}
      </div>

      <div className="field">
        <label>
          Бункер / зона хранения
          <HelpHint
            text="Опциональный блок внутри склада."
            details="Если на складе есть зонирование (паллеты A, B, C — или конкретный бункер) — выберите. Можно оставить пустым."
          />
        </label>
        <select
          className="input"
          value={storageBin}
          onChange={(e) => setStorageBin(e.target.value)}
        >
          <option value="">— не указывать —</option>
          {bins?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
        </select>
      </div>

      <div className="field">
        <label>Заметка</label>
        <input
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="например, смена утренняя, оператор Иванов"
        />
      </div>

      {error && error.status === 400 && Object.entries(fieldErrors)
        .filter(([k]) => !['bag_count', 'bag_weight_kg', 'storage_warehouse'].includes(k))
        .map(([k, msgs]) => (
          <div key={k} style={{
            fontSize: 12, color: 'var(--danger)', marginTop: 8,
            padding: '8px 10px', background: 'rgba(220,38,38,0.06)', borderRadius: 4,
          }}>
            <b style={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: 0.4 }}>{k}: </b>
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
