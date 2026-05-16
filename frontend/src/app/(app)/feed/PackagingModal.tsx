'use client';

import { useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { usePackageFeedBatch } from '@/hooks/useFeed';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { useWarehouses } from '@/hooks/useStockMovements';
import type { FeedBatch } from '@/types/auth';

interface Props {
  batch: FeedBatch;
  onClose: () => void;
}

/**
 * Расфасовать партию готового комбикорма в мешки.
 *
 * UX-контракт (минимальный): оператор вводит сколько КГ расфасовать,
 * вес мешка (по умолчанию 50), и склад, с которого списываются пустые
 * мешки и куда лягут фасованные. Кол-во мешков и нужный SKU мешка
 * вычисляются автоматически.
 */
export default function PackagingModal({ batch, onClose }: Props) {
  const { data: warehouses } = useWarehouses({ module_code: 'feed' });
  const { data: feedItems } = useNomenclatureItems({ module_code: 'feed' });
  const pkg = usePackageFeedBatch();

  const [kgToPackage, setKgToPackage] = useState('');
  const [bagWeightKg, setBagWeightKg] = useState('50');
  const [warehouseId, setWarehouseId] = useState('');

  // SKU пустых мешков (KORM-XALTA-*) — нужен бэку для списания.
  const bagSkus = useMemo(
    () => (feedItems ?? []).filter((it) => it.sku.startsWith('KORM-XALTA')),
    [feedItems],
  );

  // Авторезолв SKU по весу: 25 → KORM-XALTA-25, 50 → KORM-XALTA-50.
  // Если вес нецелый или нет SKU — бэк сам пропустит списание мешков.
  const autoBagSku = useMemo(() => {
    const w = parseFloat(bagWeightKg || '0');
    if (!isFinite(w) || w !== Math.floor(w)) return null;
    return bagSkus.find((it) => it.sku === `KORM-XALTA-${Math.floor(w)}`) ?? null;
  }, [bagWeightKg, bagSkus]);

  const remainingKg = parseFloat(batch.current_quantity_kg || '0');
  const bagWeight = parseFloat(bagWeightKg || '0');
  const kgRequested = parseFloat(kgToPackage || '0');

  // Целое число мешков = floor(kg / bagWeight). Хвост (< 1 мешка)
  // остаётся в насыпи — оператор может расфасовать остальное отдельно.
  const bagCount = useMemo(() => {
    if (!isFinite(kgRequested) || !isFinite(bagWeight) || bagWeight <= 0) return 0;
    return Math.floor(kgRequested / bagWeight);
  }, [kgRequested, bagWeight]);

  const totalKgPackaged = bagCount * bagWeight;
  const overflow = totalKgPackaged > remainingKg;

  const error = pkg.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await pkg.mutateAsync({
        id: batch.id,
        body: {
          bag_count: bagCount,
          bag_weight_kg: bagWeightKg,
          storage_warehouse: warehouseId,
          storage_bin: null,
          packaging_nomenclature: null, // авторезолв по весу на бэке
          packaging_warehouse: warehouseId, // тот же склад
          notes: '',
        },
      });
      onClose();
    } catch { /* остаётся в state */ }
  };

  const canSubmit =
    bagCount > 0
    && bagWeight > 0
    && warehouseId
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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Сколько кг расфасовать *</label>
          <input
            className="input mono"
            type="number"
            step="0.1"
            min="0"
            value={kgToPackage}
            placeholder="кг"
            onChange={(e) => setKgToPackage(e.target.value)}
            style={overflow ? { borderColor: 'var(--danger)' } : undefined}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            доступно <b className="mono">{remainingKg.toLocaleString('ru-RU')} кг</b>
          </div>
        </div>

        <div className="field">
          <label>Вес мешка, кг *</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            min="0.001"
            value={bagWeightKg}
            onChange={(e) => setBagWeightKg(e.target.value)}
          />
        </div>
      </div>

      <div className="field" style={{ marginTop: 12 }}>
        <label>Склад мешков *</label>
        <select
          className="input"
          value={warehouseId}
          onChange={(e) => setWarehouseId(e.target.value)}
        >
          <option value="">— выберите склад —</option>
          {warehouses?.filter((w) => w.module_code === 'feed').map((w) => (
            <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
          ))}
        </select>
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          Сюда лягут фасованные мешки и отсюда же спишутся пустые.
        </div>
      </div>

      {(bagCount > 0 || kgRequested > 0) && (
        <div style={{
          marginTop: 14, padding: 10, background: 'var(--bg-soft)',
          borderRadius: 6, fontSize: 12, lineHeight: 1.5,
        }}>
          <div style={{ color: 'var(--fg-2)' }}>
            Будет создано <b className="mono">{bagCount} мешков</b>
            {' '}× <b className="mono">{bagWeight.toLocaleString('ru-RU')} кг</b>
            {' = '}<b className="mono">{totalKgPackaged.toLocaleString('ru-RU')} кг</b>
          </div>
          {kgRequested > totalKgPackaged && bagWeight > 0 && (
            <div style={{ color: 'var(--fg-3)', marginTop: 4 }}>
              Хвост <b className="mono">
                {(kgRequested - totalKgPackaged).toLocaleString('ru-RU')} кг
              </b>{' '}останется в насыпи (меньше одного мешка).
            </div>
          )}
          {overflow && (
            <div style={{ color: 'var(--danger)', marginTop: 4 }}>
              Превышает остаток партии — уменьшите кол-во кг.
            </div>
          )}
          {bagWeight === 50 && !autoBagSku && bagCount > 0 && (
            <div style={{ color: 'var(--brand-orange)', marginTop: 4 }}>
              SKU пустого мешка <code>KORM-XALTA-50</code> не найден в номенклатуре —
              пустые мешки придётся списать вручную в /stock.
            </div>
          )}
        </div>
      )}

      {error && error.status === 400 && Object.entries(fieldErrors).map(([k, msgs]) => (
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
