'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useNomenclatureItems, useUnits } from '@/hooks/useNomenclature';
import { yieldsCrud } from '@/hooks/useSlaughter';
import { ApiError } from '@/lib/api';
import type { SlaughterShift, SlaughterYield } from '@/types/auth';

interface Props {
  shift: SlaughterShift;
  yieldRow?: SlaughterYield | null;
  onClose: () => void;
}


export default function YieldModal({ shift, yieldRow, onClose }: Props) {
  const create = yieldsCrud.useCreate();
  const update = yieldsCrud.useUpdate();
  const { data: units } = useUnits();

  // Все SKU модуля slaughter (категория «Готовая продукция убоя»).
  const { data: items } = useNomenclatureItems({
    module_code: 'slaughter',
    is_active: 'true',
  });

  const kgUnit = useMemo(
    () => units?.find((u) => u.code === 'kg' || u.code === 'кг'),
    [units],
  );

  const [nomenclature, setNomenclature] = useState(yieldRow?.nomenclature ?? '');
  const [quantity, setQuantity] = useState(yieldRow?.quantity ?? '');
  const [sharePercent, setSharePercent] = useState(yieldRow?.share_percent ?? '');
  const [notes, setNotes] = useState(yieldRow?.notes ?? '');

  const isEdit = Boolean(yieldRow);
  const action = isEdit ? update : create;
  const error = action.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const liveKg = parseFloat(shift.live_weight_kg_total || '0');
  const qtyNum = parseFloat(quantity || '0');
  const previewSharePct = liveKg > 0 && qtyNum > 0
    ? (qtyNum / liveKg * 100).toFixed(2)
    : null;

  const submit = async () => {
    if (!kgUnit) {
      alert('Юнит «kg» не найден в номенклатуре');
      return;
    }
    try {
      const body = {
        shift: shift.id,
        nomenclature,
        quantity,
        unit: kgUnit.id,
        share_percent: sharePercent || null,
        notes,
      };
      if (isEdit && yieldRow) {
        await update.mutateAsync({ id: yieldRow.id, body } as never);
      } else {
        await create.mutateAsync(body as never);
      }
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={isEdit ? 'Редактировать выход' : 'Добавить выход'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!nomenclature || !quantity || action.isPending}
            onClick={submit}
          >
            {action.isPending ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Добавить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Выход продукции по SKU. <HelpHint
          text="При проведении смены себестоимость партии распределится по выходам пропорционально доле (share_percent). Если доля не указана — поровну."
        />
      </div>

      <div className="field">
        <label>Номенклатура (готовая продукция) *</label>
        <select
          className="input"
          value={nomenclature}
          onChange={(e) => setNomenclature(e.target.value)}
        >
          <option value="">—</option>
          {items?.map((it) => (
            <option key={it.id} value={it.id}>
              {it.sku} · {it.name}
            </option>
          ))}
        </select>
        {items && items.length === 0 && (
          <div style={{ fontSize: 11, color: 'var(--warning)' }}>
            Нет SKU готовой продукции убоя. Создайте через /nomenclature
            (категория с привязкой к модулю «Убойня»).
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Количество, кг *</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
          {fieldErrors.quantity && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {Array.isArray(fieldErrors.quantity)
                ? fieldErrors.quantity.join(' · ')
                : String(fieldErrors.quantity)}
            </div>
          )}
        </div>
        <div className="field">
          <label>
            Доля распределения cost, %
            <HelpHint text="Доля себестоимости (0–100). Сумма долей всех выходов даёт 100%. Если не задана — равномерно." />
          </label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            placeholder={previewSharePct ?? '—'}
            value={sharePercent}
            onChange={(e) => setSharePercent(e.target.value)}
          />
          {previewSharePct && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              ~{previewSharePct}% от живого веса
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

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
