'use client';

import { useEffect, useMemo, useState } from 'react';

import BatchSelector from '@/components/BatchSelector';
import AmountInput from '@/components/ui/AmountInput';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Seg from '@/components/ui/Seg';
import { useCounterparties } from '@/hooks/useCounterparties';
import { POPULAR_CURRENCY_CODES, useCurrenciesSorted, useRateOnDate } from '@/hooks/useCurrencyRates';
import { feedBagLotsCrud, feedBatchesCrud, rawBatchesCrud } from '@/hooks/useFeed';
import { useModules } from '@/hooks/useModules';
import { salesCrud } from '@/hooks/useSales';
import { useWarehouses } from '@/hooks/useStockMovements';
import { accessoriesCrud, stockBatchesCrud } from '@/hooks/useVet';
import { ApiError } from '@/lib/api';
import type { SaleOrder } from '@/types/auth';

export type SaleSourceKind =
  | 'batch'
  | 'vet_stock_batch'
  | 'vet_accessory'
  | 'feed_batch'
  | 'feed_bag_lot'
  | 'raw_batch';

/**
 * Preselect из drawer любой партии: "открыть модалку продаж с уже выбранным
 * батчем данного типа".
 */
export interface SalePreselect {
  moduleCode: string;
  sourceKind: SaleSourceKind;
  batchId: string;
  /** Можно также сразу указать номенклатуру (чтобы пользователь не искал повторно). */
  nomenclatureId?: string;
  /** И склад-источник (если известен). */
  warehouseId?: string;
}

interface Props {
  initial?: SaleOrder | null;
  preselect?: SalePreselect | null;
  onClose: () => void;
}

interface ItemDraft {
  key: string;
  nomenclature: string;
  /** Источник — один из пяти. Остальные null. */
  batch: string;
  vet_stock_batch: string;
  vet_accessory: string;
  feed_batch: string;
  feed_bag_lot: string;
  raw_batch: string;
  /**
   * Per-item kind override. Используется в vet-модуле (препарат vs аксессуар)
   * и в feed (насыпь vs мешки).
   */
  kindOverride?: SaleSourceKind;
  quantity: string;
  unit_price_uzs: string;
  /**
   * Кэшированный доступный остаток выбранной партии (для подсказки и max).
   * Заполняется когда пользователь выбирает Batch в селекторе.
   */
  available_quantity?: string;
  /** Документ-номер партии для UI-сообщения об ошибке. */
  batch_doc?: string;
  /** Единица измерения для подсказки. */
  unit_code?: string;
  /**
   * UI-only: при продаже FeedBagLot юзер может вводить цену «за мешок»
   * (default) или «за кг» — для convenience. На бэк всегда уходит цена
   * за единицу учёта (мешок), kg-версия конвертируется через bag_weight_kg.
   */
  price_unit?: 'bag' | 'kg';
  /**
   * UI-only: режим ввода количества для FeedBagLot. 'bag' — пишем мешки
   * (default), 'kg' — пишем кг, система округляет до целого числа мешков
   * (1 мешок = bag_weight_kg). На бэк всегда уходит quantity в мешках.
   */
  quantity_unit?: 'bag' | 'kg';
  /**
   * UI-only буфер для kg-режима: то, что пользователь физически набрал
   * в инпуте. quantity (мешки) пересчитывается через round(kg / bagKg),
   * но если показывать в инпуте `bags * bagKg`, при наборе 99 (≈2 мешка)
   * значение прыгает обратно в 100 — кажется, что не печатается.
   */
  quantity_kg_input?: string;
}

function makeItemDraft(overrides: Partial<ItemDraft> = {}): ItemDraft {
  return {
    key: crypto.randomUUID(),
    nomenclature: '',
    batch: '',
    vet_stock_batch: '',
    vet_accessory: '',
    feed_batch: '',
    feed_bag_lot: '',
    raw_batch: '',
    quantity: '',
    unit_price_uzs: '',
    ...overrides,
  };
}

/** Модуль → тип партии, который из него продаём. */
function sourceKindForModule(code: string | undefined): SaleSourceKind {
  if (code === 'vet') return 'vet_stock_batch';
  if (code === 'feed') return 'feed_batch';
  return 'batch';
}

export default function SaleOrderModal({ initial, preselect, onClose }: Props) {
  const isEdit = Boolean(initial);

  const create = salesCrud.useCreate();
  const update = salesCrud.useUpdate();

  const { data: modules } = useModules();

  // Пользователь может снять блокировку модуля при preselect (например чтобы
  // перенести продажу в другой модуль перед сохранением).
  const [moduleLocked, setModuleLocked] = useState(Boolean(preselect?.moduleCode));
  const { data: customers } = useCounterparties({ kind: 'buyer' });
  const { data: currencies } = useCurrenciesSorted();

  // Справочники для vet/feed (ленивая загрузка по необходимости)
  const { data: vetLots } = stockBatchesCrud.useList({ status: 'available' });
  const { data: vetAccessories } = accessoriesCrud.useList({ is_active: 'true' });
  const { data: feedLots } = feedBatchesCrud.useList();
  const { data: feedBagLots } = feedBagLotsCrud.useList({ status: 'active' });
  const { data: rawBatches } = rawBatchesCrud.useList({ status: 'available' });

  // Состояние формы
  const [moduleId, setModuleId] = useState(initial?.module ?? '');

  // Код модуля используется для резолва типа партии (sourceKindForModule)
  // и для фильтрации списка складов отгрузки — оператор не должен видеть
  // склады других модулей (раньше в дропдауне был весь зоопарк, путало).
  const selectedModuleCode = modules?.find((m) => m.id === moduleId)?.code;
  const { data: warehouses } = useWarehouses(
    selectedModuleCode ? { module_code: selectedModuleCode } : {},
  );
  const [date, setDate] = useState(initial?.date ?? new Date().toISOString().slice(0, 10));
  const [customerId, setCustomerId] = useState(initial?.customer ?? '');
  const [warehouseId, setWarehouseId] = useState(initial?.warehouse ?? preselect?.warehouseId ?? '');
  const [currencyId, setCurrencyId] = useState(initial?.currency ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [dueDate, setDueDate] = useState(initial?.due_date ?? '');

  const [items, setItems] = useState<ItemDraft[]>(() => {
    if (initial?.items && initial.items.length > 0) {
      return initial.items.map((it): ItemDraft => {
        const vetAcc = (it as { vet_accessory?: string | null }).vet_accessory ?? '';
        const bagLot = (it as { feed_bag_lot?: string | null }).feed_bag_lot ?? '';
        const rawBatch = (it as { raw_batch?: string | null }).raw_batch ?? '';
        let kindOverride: SaleSourceKind | undefined;
        if (vetAcc) kindOverride = 'vet_accessory';
        else if (bagLot) kindOverride = 'feed_bag_lot';
        else if (rawBatch) kindOverride = 'raw_batch';
        return {
          key: it.id,
          nomenclature: it.nomenclature,
          batch: it.batch ?? '',
          vet_stock_batch: it.vet_stock_batch ?? '',
          vet_accessory: vetAcc,
          feed_batch: it.feed_batch ?? '',
          feed_bag_lot: bagLot,
          raw_batch: rawBatch,
          kindOverride,
          quantity: it.quantity,
          unit_price_uzs: it.unit_price_uzs,
        };
      });
    }
    // Preselect: одна строка с уже выбранной партией (если batchId задан)
    if (preselect && preselect.batchId) {
      const draft = makeItemDraft({ nomenclature: preselect.nomenclatureId ?? '' });
      if (preselect.sourceKind === 'batch') draft.batch = preselect.batchId;
      if (preselect.sourceKind === 'vet_stock_batch') draft.vet_stock_batch = preselect.batchId;
      if (preselect.sourceKind === 'vet_accessory') {
        draft.vet_accessory = preselect.batchId;
        draft.kindOverride = 'vet_accessory';
      }
      if (preselect.sourceKind === 'feed_batch') draft.feed_batch = preselect.batchId;
      if (preselect.sourceKind === 'feed_bag_lot') {
        draft.feed_bag_lot = preselect.batchId;
        draft.kindOverride = 'feed_bag_lot';
      }
      if (preselect.sourceKind === 'raw_batch') {
        draft.raw_batch = preselect.batchId;
        draft.kindOverride = 'raw_batch';
      }
      return [draft];
    }
    return [makeItemDraft()];
  });

  // Preselect: если передан moduleCode — выставим moduleId когда модули загрузятся
  useEffect(() => {
    if (preselect?.moduleCode && modules && !moduleId) {
      const m = modules.find((x) => x.code === preselect.moduleCode);
      if (m) setModuleId(m.id);
    }
  }, [preselect, modules, moduleId]);

  // Авто-выбор склада: если для выбранного модуля ровно один склад — берём
  // его молча. Если текущий warehouseId не входит в отфильтрованный список
  // (например после смены модуля) — сбрасываем, иначе уйдёт несовместимая
  // пара модуль/склад → бек 400.
  useEffect(() => {
    if (!warehouses) return;
    if (warehouseId && !warehouses.some((w) => w.id === warehouseId)) {
      setWarehouseId(warehouses.length === 1 ? warehouses[0].id : '');
      return;
    }
    if (!warehouseId && warehouses.length === 1) {
      setWarehouseId(warehouses[0].id);
    }
  }, [warehouses, warehouseId]);

  const moduleSourceKind: SaleSourceKind = sourceKindForModule(selectedModuleCode);
  // Per-item kind: для vet оператор может переключиться на vet_accessory.
  const itemSourceKind = (it: ItemDraft): SaleSourceKind =>
    it.kindOverride ?? moduleSourceKind;
  // Глобальный sourceKind для подсказки в шапке (не per-item)
  const sourceKind = moduleSourceKind;

  // Код выбранной валюты
  const currencyCode = useMemo(() => {
    if (!currencyId) return 'UZS';
    return currencies?.find((c) => c.id === currencyId)?.code ?? '';
  }, [currencyId, currencies]);

  // Живой курс на выбранную дату
  const { data: rateOnDate, isLoading: rateLoading } = useRateOnDate(
    currencyCode === 'UZS' ? null : currencyCode,
    date,
  );

  const totalInDocCurrency = useMemo(() => {
    return items.reduce((sum, it) => {
      const q = parseFloat(it.quantity || '0');
      const p = parseFloat(it.unit_price_uzs || '0');
      return sum + (isNaN(q) || isNaN(p) ? 0 : q * p);
    }, 0);
  }, [items]);

  const totalInUzs = useMemo(() => {
    if (currencyCode === 'UZS' || !rateOnDate) return totalInDocCurrency;
    const r = parseFloat(rateOnDate.rate) / (rateOnDate.nominal || 1);
    return totalInDocCurrency * r;
  }, [totalInDocCurrency, currencyCode, rateOnDate]);

  // Авто-модуль при первом открытии (если не preselect и не edit)
  useEffect(() => {
    if (!moduleId && modules && modules.length > 0 && !initial && !preselect) {
      const preferred = modules.find((m) =>
        ['slaughter', 'feedlot', 'vet', 'feed', 'matochnik', 'incubation'].includes(m.code),
      );
      if (preferred) setModuleId(preferred.id);
    }
  }, [modules, moduleId, initial, preselect]);

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const updateItem = (key: string, patch: Partial<ItemDraft>) => {
    setItems((prev) => prev.map((it) => it.key === key ? { ...it, ...patch } : it));
  };

  const removeItem = (key: string) => {
    setItems((prev) => prev.filter((it) => it.key !== key));
  };

  // Смена модуля — сбрасываем источники у всех item, чтобы не отправить несовместимую пару
  const handleModuleChange = (newId: string) => {
    setModuleId(newId);
    setItems((prev) => prev.map((it) => ({
      ...it, batch: '', vet_stock_batch: '', vet_accessory: '',
      feed_batch: '', feed_bag_lot: '', raw_batch: '',
      kindOverride: undefined,
    })));
  };

  const itemSourceFilled = (it: ItemDraft): boolean => {
    const k = itemSourceKind(it);
    if (k === 'batch') return Boolean(it.batch);
    if (k === 'vet_stock_batch') return Boolean(it.vet_stock_batch);
    if (k === 'vet_accessory') return Boolean(it.vet_accessory);
    if (k === 'feed_batch') return Boolean(it.feed_batch);
    if (k === 'feed_bag_lot') return Boolean(it.feed_bag_lot);
    if (k === 'raw_batch') return Boolean(it.raw_batch);
    return false;
  };

  const itemQtyValid = (it: ItemDraft): boolean => {
    if (!it.quantity) return false;
    const q = parseFloat(it.quantity);
    if (!isFinite(q) || q <= 0) return false;
    // feed_bag_lot — целое число мешков (бэк отбрасывает .5)
    if (itemSourceKind(it) === 'feed_bag_lot' && !Number.isInteger(q)) return false;
    if (it.available_quantity) {
      const av = parseFloat(it.available_quantity);
      if (q > av) return false;
    }
    return true;
  };

  const canSubmit =
    moduleId &&
    customerId &&
    warehouseId &&
    items.length > 0 &&
    items.every((it) => it.nomenclature && itemSourceFilled(it) && itemQtyValid(it) && it.unit_price_uzs) &&
    !create.isPending &&
    !update.isPending;

  const handleSubmit = async () => {
    const payload = {
      date,
      module: moduleId,
      customer: customerId,
      warehouse: warehouseId,
      currency: currencyId || null,
      notes,
      due_date: dueDate || null,
      items: items.map((it) => ({
        nomenclature: it.nomenclature,
        batch: it.batch || null,
        vet_stock_batch: it.vet_stock_batch || null,
        vet_accessory: it.vet_accessory || null,
        feed_batch: it.feed_batch || null,
        feed_bag_lot: it.feed_bag_lot || null,
        raw_batch: it.raw_batch || null,
        quantity: it.quantity,
        unit_price_uzs: it.unit_price_uzs,
      })),
    };

    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch {
      /* ошибка остаётся в state mutation-а */
    }
  };

  const getFieldErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title={isEdit ? `Редактирование продажи ${initial?.doc_number ?? ''}` : 'Новая продажа'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {create.isPending || update.isPending ? 'Сохранение…' : 'Сохранить черновик'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Продажа создаётся как <b>черновик</b>. Провести (списать со склада и создать проводки)
        можно кнопкой «Провести» в списке.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>Источник (модуль) *</span>
            {moduleLocked && (
              <>
                <span style={{ fontSize: 10, color: 'var(--brand-orange)' }}>
                  открыто из модуля
                </span>
                <button
                  type="button"
                  onClick={() => setModuleLocked(false)}
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-3)',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  изменить
                </button>
              </>
            )}
          </label>
          <select
            className="input"
            value={moduleId}
            onChange={(e) => handleModuleChange(e.target.value)}
            disabled={isEdit || moduleLocked}
            title={moduleLocked ? 'Модуль-источник зафиксирован — вы открыли продажу из страницы модуля. Нажмите «изменить» чтобы сменить.' : undefined}
          >
            <option value="">—</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
          {getFieldErr('module') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('module')}</div>}
        </div>

        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field">
          <label>Клиент *</label>
          <select className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">—</option>
            {customers?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {getFieldErr('customer') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('customer')}</div>}
        </div>

        <div className="field">
          <label>Склад отгрузки *</label>
          <select
            className="input"
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
            disabled={!moduleId}
          >
            <option value="">
              {moduleId ? '—' : 'Сначала выберите модуль'}
            </option>
            {warehouses?.map((w) => (
              <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
            ))}
          </select>
          {moduleId && warehouses && warehouses.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
              У модуля «{selectedModuleCode}» нет складов. Создайте в /stock.
            </div>
          )}
        </div>

        <div className="field">
          <label>Валюта</label>
          <select className="input" value={currencyId} onChange={(e) => setCurrencyId(e.target.value)}>
            <option value="">UZS (сум)</option>
            <optgroup label="Популярные">
              {currencies?.filter((c) => c.code !== 'UZS' && POPULAR_CURRENCY_CODES.includes(c.code)).map((c) => (
                <option key={c.id} value={c.id}>{c.code} · {c.name_ru}</option>
              ))}
            </optgroup>
            <optgroup label="Все валюты">
              {currencies?.filter((c) => c.code !== 'UZS' && !POPULAR_CURRENCY_CODES.includes(c.code)).map((c) => (
                <option key={c.id} value={c.id}>{c.code} · {c.name_ru}</option>
              ))}
            </optgroup>
          </select>
          {currencyCode !== 'UZS' && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
              {rateLoading && 'Загружаем курс…'}
              {!rateLoading && rateOnDate && (
                <>
                  Курс на {rateOnDate.date}:{' '}
                  <span className="mono" style={{ color: 'var(--brand-orange)' }}>
                    {parseFloat(rateOnDate.rate).toLocaleString('ru-RU')} сум / {currencyCode}
                  </span>
                  {' '}· зафиксируется при проведении
                </>
              )}
              {!rateLoading && !rateOnDate && (
                <span style={{ color: 'var(--danger)' }}>
                  Нет курса на {date} и ранее. Синхронизируйте курсы ЦБ в Настройках.
                </span>
              )}
            </div>
          )}
        </div>

        <div className="field">
          <label>Срок оплаты (для напоминаний)</label>
          <input
            className="input"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            TG-бот будет напоминать клиенту за 3 дня, в день срока и при просрочке.
          </div>
        </div>

        <div className="field">
          <label>Заметки</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-3)' }}>
        Тип партии: <b className="mono">{sourceKind}</b>{' '}
        {sourceKind === 'batch' && '(обычная партия slaughter/feedlot/matochnik/incubation)'}
        {sourceKind === 'vet_stock_batch' && '(лот вет-препарата)'}
        {sourceKind === 'feed_batch' && '(партия комбикорма)'}
      </div>

      {/* ─── Items ──────────────────────────────────────────────────── */}
      <div style={{ marginTop: 18, marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <b>Позиции</b>
        <button className="btn btn-ghost btn-sm" onClick={() => setItems((p) => [...p, makeItemDraft()])}>
          <Icon name="plus" size={12} /> Добавить
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((it) => {
          const lineDoc = parseFloat(it.quantity || '0') * parseFloat(it.unit_price_uzs || '0');
          return (
            <div
              key={it.key}
              style={{
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 10,
                background: 'var(--bg-card)',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 8,
              }}
            >
              <div style={{ gridColumn: '1/3' }}>
                {sourceKind === 'batch' && (
                  <BatchSelector
                    label="Партия *"
                    value={it.batch}
                    onChange={(id, batch) => {
                      const avail = batch?.available_quantity
                        ?? batch?.current_quantity
                        ?? '';
                      updateItem(it.key, {
                        batch: id,
                        // автоставим nomenclature из партии (партия всегда привязана к номенклатуре)
                        nomenclature: batch?.nomenclature ?? it.nomenclature,
                        // если кол-во ещё не задано — поставим максимум доступного
                        quantity: it.quantity || avail,
                        available_quantity: avail,
                        batch_doc: batch?.doc_number,
                        unit_code: batch?.unit_code ?? '',
                      });
                    }}
                    filter={
                      moduleId
                        ? { state: 'active', current_module: moduleId }
                        : { state: 'active' }
                    }
                  />
                )}
                {moduleSourceKind === 'vet_stock_batch' && (
                  <>
                    <div className="field">
                      <label>Тип товара</label>
                      <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
                        <label style={{ display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="radio"
                            name={`kind-${it.key}`}
                            checked={itemSourceKind(it) === 'vet_stock_batch'}
                            onChange={() => updateItem(it.key, {
                              kindOverride: 'vet_stock_batch',
                              vet_accessory: '',
                            })}
                          />
                          Препарат (лот)
                        </label>
                        <label style={{ display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="radio"
                            name={`kind-${it.key}`}
                            checked={itemSourceKind(it) === 'vet_accessory'}
                            onChange={() => updateItem(it.key, {
                              kindOverride: 'vet_accessory',
                              vet_stock_batch: '',
                            })}
                          />
                          Аксессуар
                        </label>
                      </div>
                    </div>

                    {itemSourceKind(it) === 'vet_stock_batch' && (
                      <div className="field">
                        <label>Лот препарата *</label>
                        <select
                          className="input"
                          value={it.vet_stock_batch}
                          onChange={(e) => {
                            const lot = (vetLots ?? []).find((v) => v.id === e.target.value);
                            updateItem(it.key, {
                              vet_stock_batch: e.target.value,
                              nomenclature: lot?.nomenclature ?? '',
                              quantity: it.quantity || lot?.current_quantity || '',
                              available_quantity: lot?.current_quantity,
                              batch_doc: lot?.doc_number,
                              unit_code: lot?.unit_code ?? '',
                              // Авто-подстановка цены за единицу из price_per_unit_uzs лота —
                              // если оператор уже задал цену вручную, не перезатираем.
                              unit_price_uzs: it.unit_price_uzs || lot?.price_per_unit_uzs || '',
                            });
                          }}
                        >
                          <option value="">— выберите лот —</option>
                          {vetLots?.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.doc_number} · {v.lot_number} · {v.drug_name ?? ''} ·
                              {' '}остаток {parseFloat(v.current_quantity).toLocaleString('ru-RU')} {v.unit_code ?? ''}
                            </option>
                          ))}
                        </select>
                        {it.vet_stock_batch && !it.nomenclature && (
                          <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                            У препарата не привязана номенклатура — продажа не пройдёт. Откройте /vet → препарат и привяжите номенклатуру.
                          </div>
                        )}
                      </div>
                    )}

                    {itemSourceKind(it) === 'vet_accessory' && (() => {
                      const sellable = (vetAccessories ?? []).filter(
                        (a) => parseFloat(a.current_quantity) > 0,
                      );
                      return (
                        <div className="field">
                          <label>Аксессуар *</label>
                          <select
                            className="input"
                            value={it.vet_accessory}
                            onChange={(e) => {
                              const acc = sellable.find((a) => a.id === e.target.value);
                              updateItem(it.key, {
                                vet_accessory: e.target.value,
                                nomenclature: acc?.nomenclature ?? '',
                                quantity: it.quantity || '1',
                                available_quantity: acc?.current_quantity,
                                batch_doc: acc?.nomenclature_sku ?? undefined,
                                unit_code: acc?.unit_code ?? undefined,
                                unit_price_uzs: it.unit_price_uzs || acc?.sale_price_uzs || '',
                              });
                            }}
                          >
                            <option value="">— выберите аксессуар —</option>
                            {sellable.map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.nomenclature_name} ·
                                {' '}остаток {parseFloat(a.current_quantity).toLocaleString('ru-RU')} {a.unit_code ?? ''}
                                {' '}· {parseFloat(a.sale_price_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум/шт
                              </option>
                            ))}
                          </select>
                          {sellable.length === 0 && (
                            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
                              Нет аксессуаров с положительным остатком — добавьте через
                              {' '}/vet → «Аксессуары» → «Приёмка».
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </>
                )}
                {moduleSourceKind === 'feed_batch' && (
                  <>
                    <div className="field">
                      <label>Тип отгрузки</label>
                      <div style={{ display: 'flex', gap: 12, fontSize: 12, flexWrap: 'wrap' }}>
                        <label style={{ display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="radio"
                            name={`feedkind-${it.key}`}
                            checked={itemSourceKind(it) === 'feed_batch'}
                            onChange={() => updateItem(it.key, {
                              kindOverride: undefined,
                              feed_bag_lot: '', raw_batch: '',
                              nomenclature: '', quantity: '', available_quantity: undefined,
                              unit_code: '', batch_doc: undefined,
                            })}
                          />
                          Готовый корм (насыпью, кг)
                        </label>
                        <label style={{ display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="radio"
                            name={`feedkind-${it.key}`}
                            checked={itemSourceKind(it) === 'feed_bag_lot'}
                            onChange={() => updateItem(it.key, {
                              kindOverride: 'feed_bag_lot',
                              feed_batch: '', raw_batch: '',
                              nomenclature: '', quantity: '', available_quantity: undefined,
                              unit_code: '', batch_doc: undefined,
                            })}
                          />
                          Готовый корм (мешки, шт)
                        </label>
                        <label style={{ display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="radio"
                            name={`feedkind-${it.key}`}
                            checked={itemSourceKind(it) === 'raw_batch'}
                            onChange={() => updateItem(it.key, {
                              kindOverride: 'raw_batch',
                              feed_batch: '', feed_bag_lot: '',
                              nomenclature: '', quantity: '', available_quantity: undefined,
                              unit_code: '', batch_doc: undefined,
                            })}
                          />
                          Сырьё (кг)
                        </label>
                      </div>
                    </div>

                    {itemSourceKind(it) === 'feed_batch' && (() => {
                      // Только одобренные партии с положительным остатком
                      const sellable = (feedLots ?? []).filter(
                        (f) => f.status === 'approved'
                          && parseFloat(f.current_quantity_kg) > 0,
                      );
                      return (
                        <div className="field">
                          <label>Партия комбикорма (насыпь) *</label>
                          <select
                            className="input"
                            value={it.feed_batch}
                            onChange={(e) => {
                              const fb = sellable.find((f) => f.id === e.target.value);
                              updateItem(it.key, {
                                feed_batch: e.target.value,
                                nomenclature: fb?.nomenclature ?? '',
                                quantity: it.quantity || fb?.current_quantity_kg || '',
                                available_quantity: fb?.current_quantity_kg,
                                batch_doc: fb?.doc_number,
                                unit_code: 'кг',
                              });
                            }}
                          >
                            <option value="">— выберите партию —</option>
                            {sellable.map((f) => (
                              <option key={f.id} value={f.id}>
                                {f.doc_number} · {f.recipe_code ?? ''}
                                {f.nomenclature_name ? ` · ${f.nomenclature_name}` : ''} ·
                                {' '}остаток {parseFloat(f.current_quantity_kg).toLocaleString('ru-RU')} кг
                                {' '}· {parseFloat(f.unit_cost_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум/кг
                              </option>
                            ))}
                          </select>
                          {it.feed_batch && !it.nomenclature && (
                            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                              В справочнике номенклатуры нет позиции с SKU = коду рецептуры.
                              Создайте её в /nomenclature (модуль «Корма», SKU = код рецепта).
                            </div>
                          )}
                          {sellable.length === 0 && (
                            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
                              Нет одобренных партий насыпью. Партии становятся
                              продаваемыми после контроля качества (статус «Одобрена»).
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {itemSourceKind(it) === 'feed_bag_lot' && (() => {
                      const sellable = (feedBagLots ?? []).filter(
                        (b) => b.status === 'active' && b.bags_remaining > 0,
                      );
                      return (
                        <div className="field">
                          <label>Партия мешков *</label>
                          <select
                            className="input"
                            value={it.feed_bag_lot}
                            onChange={(e) => {
                              const bl = sellable.find((b) => b.id === e.target.value);
                              updateItem(it.key, {
                                feed_bag_lot: e.target.value,
                                nomenclature: bl?.nomenclature ?? '',
                                // qty в штуках мешков
                                quantity: it.quantity || (bl ? String(bl.bags_remaining) : ''),
                                available_quantity: bl ? String(bl.bags_remaining) : undefined,
                                batch_doc: bl?.doc_number,
                                unit_code: 'мешок',
                                // Дефолтная цена = себест × 1 (наценку оператор поставит сам);
                                // оставляем пусто чтобы оператор явно ввёл sale-цену.
                              });
                            }}
                          >
                            <option value="">— выберите партию —</option>
                            {sellable.map((b) => (
                              <option key={b.id} value={b.id}>
                                {b.doc_number} · {b.recipe_code ?? ''}
                                {b.nomenclature_name ? ` · ${b.nomenclature_name}` : ''} ·
                                {' '}остаток {b.bags_remaining} шт ×{' '}
                                {parseFloat(b.bag_weight_kg).toLocaleString('ru-RU')} кг
                                {' '}· {parseFloat(b.unit_cost_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум/мешок
                              </option>
                            ))}
                          </select>
                          {it.feed_bag_lot && !it.nomenclature && (
                            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                              В справочнике номенклатуры нет позиции с SKU = коду рецептуры —
                              продажа партии мешков невозможна без неё.
                            </div>
                          )}
                          {sellable.length === 0 && (
                            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
                              Нет активных партий мешков. Расфасуйте готовый
                              корм в /feed → таб «Готовые партии» → «Расфасовать в мешки».
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {itemSourceKind(it) === 'raw_batch' && (() => {
                      const sellable = (rawBatches ?? []).filter(
                        (r) => r.status === 'available'
                          && parseFloat(r.current_quantity) > 0,
                      );
                      return (
                        <div className="field">
                          <label>Партия сырья *</label>
                          <select
                            className="input"
                            value={it.raw_batch}
                            onChange={(e) => {
                              const rb = sellable.find((r) => r.id === e.target.value);
                              updateItem(it.key, {
                                raw_batch: e.target.value,
                                nomenclature: rb?.nomenclature ?? '',
                                quantity: it.quantity || rb?.current_quantity || '',
                                available_quantity: rb?.current_quantity,
                                batch_doc: rb?.doc_number,
                                unit_code: rb?.unit_code ?? 'кг',
                                // Дефолтная цена = закупочная (при необходимости
                                // оператор поднимет с наценкой).
                                unit_price_uzs: it.unit_price_uzs || rb?.price_per_unit_uzs || '',
                              });
                            }}
                          >
                            <option value="">— выберите партию сырья —</option>
                            {sellable.map((r) => (
                              <option key={r.id} value={r.id}>
                                {r.nomenclature_name ?? r.nomenclature_sku ?? '—'} ·
                                {' '}остаток {parseFloat(r.current_quantity).toLocaleString('ru-RU')} {r.unit_code ?? 'кг'}
                                {' '}· {parseFloat(r.price_per_unit_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум/{r.unit_code ?? 'кг'}
                                {' '}· {r.doc_number}
                              </option>
                            ))}
                          </select>
                          {it.raw_batch && !it.nomenclature && (
                            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                              У партии сырья не определена номенклатурная позиция —
                              продажа невозможна.
                            </div>
                          )}
                          {sellable.length === 0 && (
                            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
                              Нет доступных партий сырья (статус «В наличии»). Приходи́те
                              сырьё в /feed → «+ Партия сырья».
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </>
                )}
              </div>

              {(() => {
                // Для feed_bag_lot показываем кг-эквивалент: партия физически
                // продаётся в мешках (целое число), но фермер думает в кг.
                const isBag = itemSourceKind(it) === 'feed_bag_lot';
                const bagLot = isBag
                  ? (feedBagLots ?? []).find((b) => b.id === it.feed_bag_lot)
                  : undefined;
                const bagKg = bagLot ? parseFloat(bagLot.bag_weight_kg) : 0;
                const qtyNum = parseFloat(it.quantity || '0');
                const qtyKg = isBag && bagKg > 0 ? qtyNum * bagKg : 0;
                const availNum = it.available_quantity
                  ? parseFloat(it.available_quantity)
                  : 0;
                const availKg = isBag && bagKg > 0 ? availNum * bagKg : 0;
                const qtyUnit = (it.quantity_unit ?? 'bag') as 'bag' | 'kg';
                const priceUnit = (it.price_unit ?? 'bag') as 'bag' | 'kg';
                // В kg-режиме показываем то, что юзер реально набрал
                // (quantity_kg_input), а не bags × bagKg — иначе при наборе
                // «99» значение прыгает обратно в 100 (1 мешок ≈ 50 кг).
                const displayedQty = isBag && qtyUnit === 'kg' && bagKg > 0
                  ? (it.quantity_kg_input ?? (qtyKg > 0 ? String(qtyKg) : ''))
                  : it.quantity;
                return (
                  <>
                    <div className="field">
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span>Кол-во *</span>
                        {isBag && bagKg > 0 && (
                          <Seg
                            options={[{ value: 'bag', label: 'шт' }, { value: 'kg', label: 'кг' }]}
                            value={qtyUnit}
                            onChange={(v) => {
                              const next = v as 'bag' | 'kg';
                              const patch: Partial<ItemDraft> = { quantity_unit: next };
                              // При переключении на kg заполняем буфер из текущих мешков,
                              // чтобы юзер сразу видел эквивалент в кг.
                              if (next === 'kg' && qtyKg > 0) {
                                patch.quantity_kg_input = String(qtyKg);
                              }
                              updateItem(it.key, patch);
                            }}
                          />
                        )}
                        {it.available_quantity && (
                          <span style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 400 }}>
                            доступно {availNum.toLocaleString('ru-RU')} {it.unit_code ?? ''}
                            {isBag && availKg > 0 && (
                              <> = {availKg.toLocaleString('ru-RU')} кг</>
                            )}
                          </span>
                        )}
                      </label>
                      <input
                        className="input mono"
                        type="number"
                        step={isBag && qtyUnit === 'kg' ? '0.1' : (isBag ? '1' : '0.001')}
                        min="0"
                        value={displayedQty}
                        placeholder={isBag && qtyUnit === 'kg' ? 'кг' : (isBag ? 'мешков' : '')}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (!isBag || qtyUnit === 'bag' || bagKg <= 0) {
                            updateItem(it.key, { quantity: val });
                            return;
                          }
                          // KG-режим: сохраняем сырой ввод в буфер, чтобы юзер мог
                          // свободно набирать; в quantity (мешки) кладём округлённое
                          // значение для бэка.
                          const kg = parseFloat(val || '0');
                          if (val === '' || kg <= 0) {
                            updateItem(it.key, { quantity: '', quantity_kg_input: val });
                            return;
                          }
                          const bags = Math.round(kg / bagKg);
                          updateItem(it.key, {
                            quantity: String(bags),
                            quantity_kg_input: val,
                          });
                        }}
                        style={
                          it.available_quantity
                            && qtyNum > availNum
                            ? { borderColor: 'var(--danger)' }
                            : undefined
                        }
                      />
                      {isBag && qtyNum > 0 && bagKg > 0 && (
                        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                          {qtyNum.toLocaleString('ru-RU')} мешок × {bagKg.toLocaleString('ru-RU')} кг ={' '}
                          <b>{qtyKg.toLocaleString('ru-RU')} кг</b>
                        </div>
                      )}
                      {it.available_quantity
                        && qtyNum > availNum
                        && (
                          <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                            Превышен доступный остаток партии {it.batch_doc}.
                          </div>
                        )}
                    </div>

                    <div className="field">
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span>Цена * ({currencyCode})</span>
                        {isBag && bagKg > 0 && (
                          <Seg
                            options={[
                              { value: 'bag', label: 'за мешок' },
                              { value: 'kg', label: 'за кг' },
                            ]}
                            value={priceUnit}
                            onChange={(v) => updateItem(it.key, { price_unit: v as 'bag' | 'kg' })}
                          />
                        )}
                      </label>
                      {(() => {
                        // Храним unit_price_uzs всегда как цену «за мешок» —
                        // это то что нужно бэку (SaleItem.unit_price × quantity_шт).
                        // Если юзер ввёл «за кг» — конвертим: bag_price = kg × bagKg.
                        const stored = parseFloat(it.unit_price_uzs || '0');
                        const displayed = !isBag || bagKg <= 0 || priceUnit === 'bag'
                          ? it.unit_price_uzs
                          : (stored > 0 ? String(stored / bagKg) : '');
                        return (
                          <AmountInput
                            className="input mono"
                            value={displayed || ''}
                            placeholder={isBag && priceUnit === 'kg' ? 'UZS за кг' : 'UZS за мешок'}
                            onChange={(val) => {
                              if (!isBag || bagKg <= 0 || priceUnit === 'bag') {
                                updateItem(it.key, { unit_price_uzs: val });
                                return;
                              }
                              const kg = parseFloat(val || '0');
                              const bagPrice = kg > 0 ? (kg * bagKg).toString() : val;
                              updateItem(it.key, { unit_price_uzs: bagPrice });
                            }}
                          />
                        );
                      })()}
                      {isBag && bagKg > 0 && parseFloat(it.unit_price_uzs || '0') > 0 && (
                        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                          ≈ {(parseFloat(it.unit_price_uzs) / bagKg).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} {currencyCode}/кг
                          {' · '}{parseFloat(it.unit_price_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} {currencyCode}/мешок
                        </div>
                      )}
                    </div>
                  </>
                );
              })()}

              <div style={{ gridColumn: '1/3', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: 'var(--fg-2)' }}>
                <span>
                  Итого по строке:{' '}
                  <span className="mono">
                    {lineDoc.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} {currencyCode}
                  </span>
                </span>
                {items.length > 1 && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => removeItem(it.key)}
                    style={{ color: 'var(--danger)' }}
                  >
                    <Icon name="close" size={12} /> Удалить
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Итого */}
      <div style={{ marginTop: 14, padding: 10, background: 'var(--bg-soft)', borderRadius: 8, fontSize: 13 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Итого в валюте документа:</span>
          <span className="mono">
            {totalInDocCurrency.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} {currencyCode}
          </span>
        </div>
        {currencyCode !== 'UZS' && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, color: 'var(--fg-2)' }}>
            <span>В сомах (по текущему курсу):</span>
            <span className="mono">
              {rateOnDate
                ? totalInUzs.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум'
                : '—'}
            </span>
          </div>
        )}
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
