'use client';

import { useMemo, useState } from 'react';

import AmountInput from '@/components/ui/AmountInput';
import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useCounterparties } from '@/hooks/useCounterparties';
import { rawBatchesCrud } from '@/hooks/useFeed';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import {
  useStockMovements,
  useWarehouseBalance,
  useWarehouses,
} from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { NomenclatureItem, RawMaterialBatch, StockMovement } from '@/types/auth';

/**
 * Префилл из других мест (например, переключение из «Новое движение» в /stock).
 * Все поля опциональны.
 */
export interface RawBatchPrefill {
  nomenclature?: string;
  warehouse?: string;
  supplier?: string;
  quantity?: string;       // приходит как «количество» из stock-формы — кладём в gross_weight_kg
  price_per_unit?: string;
}

interface Props {
  initial?: RawMaterialBatch | null;
  prefill?: RawBatchPrefill;
  onClose: () => void;
  /**
   * Юзер кликнул в секции «Из существующего движения /stock» — родитель
   * закрывает эту модалку и открывает PromoteToRawBatchModal с выбранным
   * movement (там уже правильный flow для конвертации).
   */
  onPickStockMovement?: (movement: StockMovement) => void;
}

function fmtMoney(v: number): string {
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' сум';
}

export default function RawBatchModal({ initial, prefill, onClose, onPickStockMovement }: Props) {
  const isEdit = Boolean(initial);
  const create = rawBatchesCrud.useCreate();
  const update = rawBatchesCrud.useUpdate();

  // Подсказка: есть ли в /stock ручные INCOMING-приходы для feed-сырья,
  // которые ещё не превращены в партию. Показываем только при создании
  // (не при редактировании / не при prefill из /stock).
  const showPicker = !isEdit && !prefill && Boolean(onPickStockMovement);
  const { data: stockMovements } = useStockMovements(
    showPicker ? { kind: 'incoming', module_code: 'feed' } : {},
  );
  const eligibleMovements = useMemo(() => {
    if (!showPicker || !stockMovements) return [];
    return stockMovements.filter((m) =>
      m.is_manual
      && (m.nomenclature_sku?.startsWith('KORM-') ?? false)
      && !m.nomenclature_sku?.startsWith('KORM-XALTA')
    );
  }, [showPicker, stockMovements]);
  const [pickerOpen, setPickerOpen] = useState(false);

  // Сырьё корма — только из nomenclature модуля feed
  const { data: noms } = useNomenclatureItems({ module_code: 'feed', is_active: 'true' });
  const { data: warehouses } = useWarehouses({ module_code: 'feed' });
  const { data: suppliers } = useCounterparties({ kind: 'supplier' });
  const { data: bins } = useProductionBlocks({
    module_code: 'feed', kind: 'storage_bin', is_active: 'true',
  });

  const [nomenclatureId, setNomenclatureId] = useState(
    initial?.nomenclature ?? prefill?.nomenclature ?? '',
  );
  const [supplierId, setSupplierId] = useState(
    initial?.supplier ?? prefill?.supplier ?? '',
  );
  const [warehouseId, setWarehouseId] = useState(
    initial?.warehouse ?? prefill?.warehouse ?? '',
  );
  const [storageBin, setStorageBin] = useState(initial?.storage_bin ?? '');
  const [receivedDate, setReceivedDate] = useState(
    initial?.received_date ?? new Date().toISOString().slice(0, 10),
  );
  const [pricePerUnit, setPricePerUnit] = useState(
    initial?.price_per_unit_uzs ?? prefill?.price_per_unit ?? '',
  );
  const [notes, setNotes] = useState(initial?.notes ?? '');

  // Простой учёт без расчёта усушки: оператор вводит итоговое количество
  // как уже договорились с поставщиком. Backend хранит это в `quantity`
  // (legacy-режим). Если позже понадобится Дюваль / профили усушки — можно
  // вернуть отдельной формой.
  const [quantity, setQuantity] = useState(
    initial?.quantity ?? prefill?.quantity ?? '',
  );

  // Карантин
  const [putToQuarantine, setPutToQuarantine] = useState(true);
  const [quarantineUntil, setQuarantineUntil] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().slice(0, 10);
  });

  const selectedNom = useMemo<NomenclatureItem | undefined>(
    () => noms?.find((n) => n.id === nomenclatureId),
    [noms, nomenclatureId],
  );

  // ── Live preview: qty × price ────────────────────────────────────────
  const totalUzs = useMemo(() => {
    const q = parseFloat(quantity || '0');
    const p = parseFloat(pricePerUnit || '0');
    if (!Number.isFinite(q) || !Number.isFinite(p)) return 0;
    return q * p;
  }, [quantity, pricePerUnit]);

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  // Warehouse-first guard: на складе должен быть приход >= партии (qty).
  // Без backing inventory партия становится «фантомной» (StockMovement
  // не создаётся при create на бэкенде с этого момента).
  const { data: warehouseBalance } = useWarehouseBalance(
    !isEdit && warehouseId ? warehouseId : null,
  );
  const stockRow = !isEdit && warehouseId && nomenclatureId
    ? (warehouseBalance?.rows ?? []).find((r) => r.nomenclature_id === nomenclatureId)
    : null;
  const stockQty = stockRow ? parseFloat(stockRow.balance_qty) : 0;
  const requestedQty = parseFloat(quantity || '0');
  const stockOk = isEdit || (stockQty > 0 && stockQty >= requestedQty);

  const canSubmit =
    nomenclatureId &&
    warehouseId &&
    receivedDate &&
    pricePerUnit &&
    quantity &&
    stockOk &&
    !create.isPending &&
    !update.isPending;

  const handleSave = async () => {
    if (!selectedNom) return;
    const payload = {
      nomenclature: nomenclatureId,
      supplier: supplierId || null,
      warehouse: warehouseId,
      storage_bin: storageBin,
      received_date: receivedDate,
      unit: selectedNom.unit,
      price_per_unit_uzs: pricePerUnit,
      notes,
      status: putToQuarantine ? 'quarantine' as const : 'available' as const,
      quarantine_until: putToQuarantine ? quarantineUntil : null,
      quantity,
    };

    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch { /* */ }
  };

  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title={isEdit ? `Партия сырья · ${initial?.doc_number}` : 'Новая партия сырья'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={handleSave}>
            {(create.isPending || update.isPending) ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Приёмка сырья на склад модуля «Корма».
      </div>

      {/* Импорт из существующего INCOMING-движения /stock — чтобы не вводить
          номенклатуру/склад/цену вручную если они уже есть в журнале. */}
      {showPicker && eligibleMovements.length > 0 && (
        <div style={{
          padding: 10, marginBottom: 12,
          background: 'var(--info-soft)',
          border: '1px solid var(--info)',
          borderRadius: 6, fontSize: 12, color: '#1E4D80',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div>
              <b>В /stock есть {eligibleMovements.length} прихода без партии</b>
              <div style={{ fontSize: 11, marginTop: 2, opacity: 0.85 }}>
                Можно загрузить данные оттуда (SKU, склад, поставщик, кол-во, цена)
                и дозаполнить только влажность/сорность.
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setPickerOpen((v) => !v)}
            >
              {pickerOpen ? 'Свернуть' : 'Выбрать →'}
            </button>
          </div>
          {pickerOpen && (
            <div style={{
              marginTop: 10, maxHeight: 220, overflowY: 'auto',
              border: '1px solid var(--border)', borderRadius: 4,
              background: 'var(--bg-card, #fff)',
            }}>
              {eligibleMovements.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  style={{
                    display: 'flex', width: '100%', gap: 10,
                    padding: '8px 10px', alignItems: 'center',
                    background: 'transparent', border: 'none',
                    borderBottom: '1px solid var(--border)',
                    textAlign: 'left', cursor: 'pointer',
                    color: 'var(--fg-1)', fontSize: 12,
                  }}
                  onClick={() => onPickStockMovement?.(m)}
                >
                  <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', minWidth: 110 }}>
                    {m.doc_number}
                  </span>
                  <span style={{ minWidth: 90, color: 'var(--fg-3)', fontSize: 11 }}>
                    {new Date(m.date).toLocaleDateString('ru')}
                  </span>
                  <span style={{ fontWeight: 500, flex: 1, minWidth: 0 }}>
                    {m.nomenclature_name}
                  </span>
                  <span className="mono" style={{ fontWeight: 600 }}>
                    {parseFloat(m.quantity).toLocaleString('ru-RU')} кг
                  </span>
                  <span className="mono" style={{ color: 'var(--fg-3)', minWidth: 90, textAlign: 'right' }}>
                    {parseFloat(m.unit_price_uzs ?? '0').toLocaleString('ru-RU')} сум/кг
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Номенклатура (сырьё) *</label>
          <select
            className="input"
            value={nomenclatureId}
            onChange={(e) => setNomenclatureId(e.target.value)}
            disabled={isEdit}
          >
            <option value="">—</option>
            {noms?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name}
                {n.base_moisture_pct ? ` (базис. вл. ${n.base_moisture_pct}%)` : ''}
              </option>
            ))}
          </select>
          {getErr('nomenclature') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('nomenclature')}</div>
          )}
        </div>

        <div className="field">
          <label>Дата приёмки *</label>
          <input
            className="input"
            type="date"
            value={receivedDate}
            onChange={(e) => setReceivedDate(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Цена за 1 кг (UZS) *</label>
          <AmountInput
            className="input mono"
            value={pricePerUnit}
            onChange={setPricePerUnit}
            placeholder="3 200"
          />
        </div>

        <div className="field">
          <label>Поставщик</label>
          <select
            className="input"
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
          >
            <option value="">—</option>
            {suppliers?.map((s) => (
              <option key={s.id} value={s.id}>{s.code} · {s.name}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>
            Склад *
            <HelpHint
              text="Склад модуля «Корма»."
              details="Партия — это lot-метаданные поверх остатка склада. На складе сначала должен быть приход (через /stock + Приход или закуп)."
            />
          </label>
          <select
            className="input"
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
          >
            <option value="">—</option>
            {warehouses?.filter((w) => w.module_code === 'feed').map((w) => (
              <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
            ))}
          </select>
        </div>

        {!isEdit && warehouseId && nomenclatureId && (
          <div style={{
            gridColumn: '1/3',
            padding: 10, fontSize: 12, borderRadius: 6,
            background: stockOk ? 'var(--bg-soft)' : '#fef2f2',
            border: `1px solid ${stockOk ? 'var(--border)' : 'var(--danger)'}`,
          }}>
            {stockOk && stockQty > 0 ? (
              <span>
                ✅ <b>На складе:</b>{' '}
                <span className="mono">
                  {stockQty.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}
                  {stockRow?.unit ? ` ${stockRow.unit}` : ''}
                </span>
                {requestedQty > 0 && (
                  <span style={{ color: 'var(--fg-3)', marginLeft: 8 }}>
                    — нужно для партии {requestedQty.toLocaleString('ru-RU')}
                    {stockQty < requestedQty ? ' (не хватает!)' : ' ✓'}
                  </span>
                )}
              </span>
            ) : stockQty > 0 && stockQty < requestedQty ? (
              <span>
                ⛔ <b>На складе только {stockQty}</b>, а партия запрашивает{' '}
                {requestedQty}. Сначала довезите остаток через{' '}
                <code>/stock → +Приход</code>.
              </span>
            ) : (
              <span>
                ⛔ <b>На складе ноль</b> по этому SKU. Сначала оприходуйте
                товар через <code>/stock → +Приход</code> (создаст автозакуп
                в /purchases) или через <code>/purchases</code>, потом
                возвращайтесь сюда. Если приход уже есть — используйте
                «Превратить в партию» прямо в /stock.
              </span>
            )}
          </div>
        )}

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>
            Бункер / секция
            <HelpHint
              text="Где физически хранится партия на складе."
              details={
                'Бункер — это конкретная ёмкость (силос, бункер, секция) на складе сырья. '
                + 'Выбираем из блоков типа «Бункер хранения» (создаются в /blocks). '
                + 'Используется для печати акта и логистики.'
              }
            />
          </label>
          <select
            className="input"
            value={storageBin}
            onChange={(e) => setStorageBin(e.target.value)}
          >
            <option value="">— не выбран —</option>
            {bins?.map((b) => (
              <option key={b.id} value={b.code}>
                {b.code} · {b.name}
              </option>
            ))}
          </select>
          {bins && bins.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
              Нет блоков-бункеров. Создайте в{' '}
              <a href="/blocks" target="_blank" rel="noreferrer"
                 style={{ color: 'var(--brand-orange)', textDecoration: 'underline' }}>
                /blocks
              </a>
              {' '}— тип «Бункер хранения», модуль «feed».
            </div>
          )}
        </div>
      </div>

      {/* ── Количество ─────────────────────────────────────────────── */}
      <div className="field" style={{ marginTop: 10 }}>
        <label>
          Количество, кг *
          <HelpHint
            text="Сколько кг сырья оприходуется на склад."
            details={
              'Учётное количество как уже договорились с поставщиком. '
              + 'Если позже понадобится расчёт по влажности (формула Дюваля) '
              + 'или периодическое списание усушки — это другие сценарии и '
              + 'делаются отдельно.'
            }
          />
        </label>
        <input
          className="input mono"
          type="number"
          step="0.001"
          min="0"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="10000.000"
        />
      </div>

      {/* Live preview: qty × price */}
      <div style={{
        marginTop: 8, padding: '8px 10px', background: 'var(--bg-soft)',
        borderRadius: 6, fontSize: 12,
        display: 'flex', justifyContent: 'flex-end', gap: 16, flexWrap: 'wrap',
      }}>
        <span style={{ color: 'var(--fg-2)' }}>
          К оплате: <b className="mono">{fmtMoney(totalUzs)}</b>
        </span>
      </div>

      {/* Карантин и заметки в одной строке */}
      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, alignItems: 'end' }}>
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 4 }}>
            <input
              type="checkbox"
              checked={putToQuarantine}
              onChange={(e) => setPutToQuarantine(e.target.checked)}
            />
            <span>Положить в карантин до анализа</span>
            <HelpHint
              text="Пауза до результата лаборатории."
              details={
                'Партия в карантине не может использоваться в замесе. '
                + 'Снять карантин или отклонить можно через кнопку в drawer\'е партии.'
              }
            />
          </label>
          {putToQuarantine && (
            <input
              className="input"
              type="date"
              value={quarantineUntil}
              onChange={(e) => setQuarantineUntil(e.target.value)}
            />
          )}
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Заметки</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="напр. контракт №14"
          />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
