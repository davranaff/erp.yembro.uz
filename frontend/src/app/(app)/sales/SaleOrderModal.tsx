'use client';

import { useEffect, useMemo, useState } from 'react';

import BatchSelector from '@/components/BatchSelector';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import { useCounterparties } from '@/hooks/useCounterparties';
import { POPULAR_CURRENCY_CODES, useCurrenciesSorted, useRateOnDate } from '@/hooks/useCurrencyRates';
import { feedBatchesCrud } from '@/hooks/useFeed';
import { useModules } from '@/hooks/useModules';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { salesCrud } from '@/hooks/useSales';
import { useWarehouses } from '@/hooks/useStockMovements';
import { stockBatchesCrud } from '@/hooks/useVet';
import { ApiError } from '@/lib/api';
import type { SaleOrder } from '@/types/auth';

export type SaleSourceKind = 'batch' | 'vet_stock_batch' | 'feed_batch';

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
  /** Источник — один из трёх. Остальные null. */
  batch: string;
  vet_stock_batch: string;
  feed_batch: string;
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
}

function makeItemDraft(overrides: Partial<ItemDraft> = {}): ItemDraft {
  return {
    key: crypto.randomUUID(),
    nomenclature: '',
    batch: '',
    vet_stock_batch: '',
    feed_batch: '',
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
  const { data: warehouses } = useWarehouses();
  const { data: currencies } = useCurrenciesSorted();
  const { data: nomenclature } = useNomenclatureItems({ is_active: 'true' });

  // Справочники для vet/feed (ленивая загрузка по необходимости)
  const { data: vetLots } = stockBatchesCrud.useList({ status: 'available' });
  const { data: feedLots } = feedBatchesCrud.useList();

  // Состояние формы
  const [moduleId, setModuleId] = useState(initial?.module ?? '');
  const [date, setDate] = useState(initial?.date ?? new Date().toISOString().slice(0, 10));
  const [customerId, setCustomerId] = useState(initial?.customer ?? '');
  const [warehouseId, setWarehouseId] = useState(initial?.warehouse ?? preselect?.warehouseId ?? '');
  const [currencyId, setCurrencyId] = useState(initial?.currency ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const [items, setItems] = useState<ItemDraft[]>(() => {
    if (initial?.items && initial.items.length > 0) {
      return initial.items.map((it) => ({
        key: it.id,
        nomenclature: it.nomenclature,
        batch: it.batch ?? '',
        vet_stock_batch: it.vet_stock_batch ?? '',
        feed_batch: it.feed_batch ?? '',
        quantity: it.quantity,
        unit_price_uzs: it.unit_price_uzs,
      }));
    }
    // Preselect: одна строка с уже выбранной партией (если batchId задан)
    if (preselect && preselect.batchId) {
      const draft = makeItemDraft({ nomenclature: preselect.nomenclatureId ?? '' });
      if (preselect.sourceKind === 'batch') draft.batch = preselect.batchId;
      if (preselect.sourceKind === 'vet_stock_batch') draft.vet_stock_batch = preselect.batchId;
      if (preselect.sourceKind === 'feed_batch') draft.feed_batch = preselect.batchId;
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

  const selectedModuleCode = modules?.find((m) => m.id === moduleId)?.code;
  const sourceKind: SaleSourceKind = sourceKindForModule(selectedModuleCode);

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
      ...it, batch: '', vet_stock_batch: '', feed_batch: '',
    })));
  };

  const itemSourceFilled = (it: ItemDraft): boolean => {
    if (sourceKind === 'batch') return Boolean(it.batch);
    if (sourceKind === 'vet_stock_batch') return Boolean(it.vet_stock_batch);
    if (sourceKind === 'feed_batch') return Boolean(it.feed_batch);
    return false;
  };

  const itemQtyValid = (it: ItemDraft): boolean => {
    if (!it.quantity) return false;
    const q = parseFloat(it.quantity);
    if (!isFinite(q) || q <= 0) return false;
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
      items: items.map((it) => ({
        nomenclature: it.nomenclature,
        batch: it.batch || null,
        vet_stock_batch: it.vet_stock_batch || null,
        feed_batch: it.feed_batch || null,
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
          <select className="input" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            <option value="">—</option>
            {warehouses?.map((w) => (
              <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
            ))}
          </select>
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
              <div className="field" style={{ gridColumn: '1/3' }}>
                <label>Номенклатура *</label>
                <select
                  className="input"
                  value={it.nomenclature}
                  onChange={(e) => updateItem(it.key, { nomenclature: e.target.value })}
                >
                  <option value="">—</option>
                  {nomenclature?.map((n) => (
                    <option key={n.id} value={n.id}>{n.sku} · {n.name}</option>
                  ))}
                </select>
              </div>

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
                {sourceKind === 'vet_stock_batch' && (
                  <div className="field">
                    <label>Лот препарата *</label>
                    <select
                      className="input"
                      value={it.vet_stock_batch}
                      onChange={(e) => updateItem(it.key, { vet_stock_batch: e.target.value })}
                    >
                      <option value="">— выберите лот —</option>
                      {vetLots?.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.doc_number} · {v.lot_number} · {v.drug_name ?? ''} ·
                          {' '}остаток {parseFloat(v.current_quantity).toLocaleString('ru-RU')} {v.unit_code ?? ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {sourceKind === 'feed_batch' && (() => {
                  // Только одобренные партии с положительным остатком
                  const sellable = (feedLots ?? []).filter(
                    (f) => f.status === 'approved'
                      && parseFloat(f.current_quantity_kg) > 0,
                  );
                  return (
                    <div className="field">
                      <label>Партия комбикорма *</label>
                      <select
                        className="input"
                        value={it.feed_batch}
                        onChange={(e) => {
                          const fb = sellable.find((f) => f.id === e.target.value);
                          updateItem(it.key, {
                            feed_batch: e.target.value,
                            // Автозаполнение из выбранной партии
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
                            {f.doc_number} · {f.recipe_code ?? ''} ·
                            {' '}остаток {parseFloat(f.current_quantity_kg).toLocaleString('ru-RU')} кг
                            {' '}· {parseFloat(f.unit_cost_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум/кг
                          </option>
                        ))}
                      </select>
                      {sellable.length === 0 && (
                        <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
                          Нет одобренных партий комбикорма с остатком. Партии становятся
                          продаваемыми после контроля качества (статус «Одобрена»).
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>

              <div className="field">
                <label>
                  Кол-во *
                  {it.available_quantity && (
                    <span style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 6 }}>
                      доступно {parseFloat(it.available_quantity).toLocaleString('ru-RU')} {it.unit_code ?? ''}
                    </span>
                  )}
                </label>
                <input
                  className="input mono"
                  type="number"
                  step="0.001"
                  min="0"
                  max={it.available_quantity || undefined}
                  value={it.quantity}
                  onChange={(e) => updateItem(it.key, { quantity: e.target.value })}
                  style={
                    it.available_quantity
                      && parseFloat(it.quantity || '0') > parseFloat(it.available_quantity)
                      ? { borderColor: 'var(--danger)' }
                      : undefined
                  }
                />
                {it.available_quantity
                  && parseFloat(it.quantity || '0') > parseFloat(it.available_quantity)
                  && (
                    <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
                      Превышен доступный остаток партии {it.batch_doc}.
                    </div>
                  )}
              </div>

              <div className="field">
                <label>Цена за ед. ({currencyCode}) *</label>
                <input
                  className="input mono"
                  type="number"
                  step="0.01"
                  value={it.unit_price_uzs}
                  onChange={(e) => updateItem(it.key, { unit_price_uzs: e.target.value })}
                />
              </div>

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
