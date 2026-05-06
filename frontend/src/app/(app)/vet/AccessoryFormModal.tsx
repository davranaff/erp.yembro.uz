'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useModules } from '@/hooks/useModules';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { useWarehouses } from '@/hooks/useStockMovements';
import { accessoriesCrud, useReceiveAccessory } from '@/hooks/useVet';
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
  const receive = useReceiveAccessory();
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
  const [costPrice, setCostPrice] = useState(initial?.cost_per_unit_uzs ?? '');
  // Начальный остаток (только при create) — после сохранения карточки сразу
  // дёргается /receive чтобы создать INCOMING StockMovement и оприходовать.
  // Без этого карточка создавалась с qty=0 и оператор не понимал куда пропал
  // его «закуп» (см. фидбэк).
  const [initialQty, setInitialQty] = useState('');
  const [barcode, setBarcode] = useState(initial?.barcode ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const error = isEdit ? update.error : (create.error ?? receive.error);
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
    !create.isPending && !update.isPending && !receive.isPending;

  const submit = async () => {
    if (!canSubmit) return;
    const payload = {
      module: vetModuleId,
      nomenclature: nomenclatureId,
      warehouse: warehouseId,
      sale_price_uzs: salePrice,
      cost_per_unit_uzs: costPrice || '0',
      barcode: barcode || null,
      is_active: isActive,
      notes,
    };
    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        const created = await create.mutateAsync(payload as never);
        // Если оператор задал начальный остаток — сразу оприходуем через
        // /receive чтобы появилась запись StockMovement INCOMING и баланс
        // склада обновился.
        const qty = parseFloat(initialQty);
        if (created?.id && !Number.isNaN(qty) && qty > 0) {
          await receive.mutateAsync({
            id: created.id,
            quantity: initialQty,
            unit_cost_uzs: costPrice || undefined,
            notes: 'Начальная приёмка при создании карточки',
          });
        }
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
            {(create.isPending || update.isPending || receive.isPending)
              ? 'Сохранение…'
              : (!isEdit && parseFloat(initialQty) > 0
                ? 'Создать и оприходовать'
                : 'Сохранить')}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Аксессуары — товары для перепродажи без партионного учёта.
        {isEdit
          ? ' Себестоимость и остаток правятся через «Приёмку».'
          : ' Если задать начальный остаток — он сразу оприходуется (создастся запись прихода в склад).'}
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
              {n.sku} · {n.name}
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Себестоимость, сум{isEdit ? '' : ' *'}</label>
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
            {isEdit
              ? 'Прямое изменение перезапишет текущий avg. Для корректной приёмки используйте «Принять».'
              : 'Цена за единицу при первой приёмке. После — пересчёт weighted-avg.'}
          </div>
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
      </div>

      {!isEdit && (
        <div className="field">
          <label>Начальный остаток (опц.)</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            min={0}
            value={initialQty}
            onChange={(e) => setInitialQty(e.target.value)}
            placeholder="0"
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            Сколько уже привезли при создании карточки. Если задать &gt; 0 —
            автоматически создастся приход в складе (StockMovement INCOMING)
            на склад выше, по «Себестоимости» как unit_cost.
          </div>
        </div>
      )}

      <div className="field">
        <label>Штрих-код</label>
        <input
          className="input mono"
          value={barcode}
          onChange={(e) => setBarcode(e.target.value)}
          placeholder="оставьте пустым — авто-генерация"
        />
      </div>

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
