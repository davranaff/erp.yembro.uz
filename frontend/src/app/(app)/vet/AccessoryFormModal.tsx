'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useModules } from '@/hooks/useModules';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import {
  useWarehouseBalance,
  useWarehouses,
} from '@/hooks/useStockMovements';
import { accessoriesCrud } from '@/hooks/useVet';
import type { VetAccessory } from '@/types/auth';

interface Props {
  initial?: VetAccessory | null;
  onClose: () => void;
}

/**
 * Форма карточки аксессуара (create / edit).
 *
 * При create задаём nomenclature/warehouse/sale_price + опц. barcode.
 * `current_quantity` и `cost_per_unit_uzs` правятся ТОЛЬКО через
 * приёмку (receive endpoint) — в форме они read-only при edit.
 */
export default function AccessoryFormModal({ initial, onClose }: Props) {
  const create = accessoriesCrud.useCreate();
  const update = accessoriesCrud.useUpdate();
  const { data: modules } = useModules();
  // По умолчанию — только vet-номенклатура (категория «Ветпрепараты»
  // и любые другие категории, привязанные к модулю vet). Раньше показывали
  // все SKU, и оператор случайно привязывал аксессуар к корму/яйцам — каша.
  // Если нужного SKU нет в списке — переключатель «Все категории» показывает
  // полный набор (escape hatch для редких кейсов вне vet).
  const [showAllCategories, setShowAllCategories] = useState(false);
  const { data: nomenclature } = useNomenclatureItems(
    showAllCategories
      ? { is_active: 'true' }
      : { is_active: 'true', module_code: 'vet' },
  );
  const vetModuleId = modules?.find((m) => m.code === 'vet')?.id ?? '';
  const { data: warehouses } = useWarehouses({
    module_code: 'vet', is_active: 'true',
  });

  const isEdit = !!initial;

  const [nomenclatureId, setNomenclatureId] = useState(initial?.nomenclature ?? '');
  const [warehouseId, setWarehouseId] = useState(initial?.warehouse ?? '');
  const [salePrice, setSalePrice] = useState(initial?.sale_price_uzs ?? '');
  // Себестоимость в edit показываем read-only (правится через /stock приход).
  // В create форме поля нет — backend подставит из последнего INCOMING.
  const [costPrice, setCostPrice] = useState(initial?.cost_per_unit_uzs ?? '');
  // Barcode на create скрыт — авто-генерируется на бэкенде. На edit
  // тоже не редактируется через эту форму (если нужно — отдельный flow).
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [notes, setNotes] = useState(initial?.notes ?? '');

  // Проверка: на выбранном складе есть приход по этому SKU? Без stock'а нельзя
  // создать карточку — заставляем сначала оприходовать через /stock + приход
  // или через PurchaseOrder.confirm. Это держит «склад → vet» инвариант
  // (склад — единственный источник истины по физическому остатку).
  const { data: warehouseBalance } = useWarehouseBalance(
    !isEdit && warehouseId ? warehouseId : null,
  );
  const stockOnHand = !isEdit && warehouseId && nomenclatureId
    ? (warehouseBalance?.rows ?? []).find((r) => r.nomenclature_id === nomenclatureId)
    : null;
  const stockQty = stockOnHand ? parseFloat(stockOnHand.balance_qty) : 0;
  const hasStock = stockQty > 0;

  const error = isEdit ? update.error : create.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};
  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const canSubmit =
    nomenclatureId &&
    warehouseId &&
    salePrice &&
    parseFloat(salePrice) > 0 &&
    (isEdit || hasStock) &&
    !create.isPending && !update.isPending;

  const submit = async () => {
    if (!canSubmit) return;
    const payload: Record<string, unknown> = {
      module: vetModuleId,
      nomenclature: nomenclatureId,
      warehouse: warehouseId,
      sale_price_uzs: salePrice,
      is_active: isActive,
      notes,
    };
    // Себестоимость и barcode НЕ отправляем при create — backend
    // подтянет cost из последнего INCOMING на складе и сгенерит barcode.
    // При edit можно править cost (если оператор вручную поправил avg).
    if (isEdit) {
      payload.cost_per_unit_uzs = costPrice || '0';
    }
    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload as never);
      }
      onClose();
    } catch {
      /* fielderrors */
    }
  };

  return (
    <Modal
      title={isEdit ? `Редактировать · ${initial?.nomenclature_name ?? ''}` : 'Новый аксессуар'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={submit}
          >
            {(create.isPending || update.isPending) ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Аксессуары — товары для перепродажи. <b>Склад — единственный
        источник истины:</b> чтобы создать карточку, на выбранном складе
        уже должен быть приход по этому SKU (через <code>/stock → +приход</code>
        или закуп). При продаже остаток списывается со склада.
      </div>

      <div className="field">
        <label>
          Номенклатура *{' '}
          <span style={{ fontWeight: 400, color: 'var(--fg-3)', fontSize: 11 }}>
            ({showAllCategories ? 'все категории' : 'только vet'})
          </span>
        </label>
        <select
          className="input"
          value={nomenclatureId}
          onChange={(e) => setNomenclatureId(e.target.value)}
          disabled={isEdit}
        >
          <option value="">— выбрать —</option>
          {nomenclature?.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
              {n.category_name ? ` · ${n.category_name}` : ''}
            </option>
          ))}
        </select>
        {getErr('nomenclature') && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('nomenclature')}</div>
        )}
        {!isEdit && (
          <label style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: 11, color: 'var(--fg-3)', marginTop: 6,
          }}>
            <input
              type="checkbox"
              checked={showAllCategories}
              onChange={(e) => {
                setShowAllCategories(e.target.checked);
                setNomenclatureId('');
              }}
            />
            Показать SKU из других модулей (если нужного нет в vet)
          </label>
        )}
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          Не нашли нужный товар? Создайте позицию в{' '}
          <a href="/nomenclature?module_code=vet" target="_blank" rel="noreferrer" style={{ color: 'var(--brand-orange)' }}>
            /nomenclature
          </a>{' '}
          в категории, привязанной к модулю vet.
        </div>
      </div>

      <div className="field">
        <label>Склад *</label>
        <select
          className="input"
          value={warehouseId}
          onChange={(e) => setWarehouseId(e.target.value)}
        >
          <option value="">— склад вет-аптеки —</option>
          {warehouses?.map((w) => (
            <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
          ))}
        </select>
        {!warehouses?.length && (
          <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
            В модуле vet нет активных складов. Создайте в разделе «Склады».
          </div>
        )}
      </div>

      <div className="field">
        <label>Цена продажи, сум *</label>
        <input
          className="input mono"
          type="number"
          step="0.01"
          min={0}
          value={salePrice}
          onChange={(e) => setSalePrice(e.target.value)}
        />
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          Меняется без переоценки склада.
        </div>
      </div>

      {isEdit && (
        <div className="field">
          <label>Себестоимость, сум</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            min={0}
            value={costPrice}
            onChange={(e) => setCostPrice(e.target.value)}
            placeholder="0.00"
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            Текущий avg-cost (берётся из последнего прихода). Прямое
            изменение перезапишет — обычно не требуется.
          </div>
        </div>
      )}

      {!isEdit && warehouseId && nomenclatureId && (
        <div style={{
          padding: 10, marginTop: 4, marginBottom: 8,
          borderRadius: 6, fontSize: 12,
          background: hasStock ? 'var(--bg-soft)' : '#fef2f2',
          border: `1px solid ${hasStock ? 'var(--border)' : 'var(--danger)'}`,
        }}>
          {hasStock ? (
            <span>
              ✅ <b>На складе:</b>{' '}
              <span className="mono">
                {stockQty.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
                {stockOnHand?.unit ? ` ${stockOnHand.unit}` : ''}
              </span>
              <span style={{ color: 'var(--fg-3)', marginLeft: 6 }}>
                — карточку создавать можно
              </span>
            </span>
          ) : (
            <span>
              ⛔ <b>На складе ноль</b> по этому SKU. Сначала оприходуйте
              товар через <code>/stock</code> → <b>+ Приход</b> (или
              закупом через <code>/purchases</code>), потом возвращайтесь
              сюда создавать карточку.
            </span>
          )}
        </div>
      )}

      {/* Штрих-код скрыт — авто-генерируется на бэкенде в формате
          VET-A-{SKU}-{rand4}. Если нужно ввести вручную — отдельный flow. */}

      <div className="field">
        <label>Заметки</label>
        <input
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {isEdit && (
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Активен (доступен для продажи)
        </label>
      )}

      {isEdit && initial && (
        <div style={{
          marginTop: 12, padding: 8, background: 'var(--bg-soft)',
          fontSize: 11, color: 'var(--fg-3)', borderRadius: 4,
        }}>
          Текущий остаток: <b>{initial.current_quantity} {initial.unit_code ?? ''}</b>
          {initial.cost_per_unit_uzs != null && (
            <> · Себестоимость: <b>{initial.cost_per_unit_uzs} сум</b></>
          )}
        </div>
      )}

      {error && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, fontSize: 12, color: 'var(--danger)', background: '#fef2f2', borderRadius: 4 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
