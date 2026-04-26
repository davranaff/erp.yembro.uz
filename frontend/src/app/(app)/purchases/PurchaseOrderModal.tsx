'use client';

import { useEffect, useMemo, useState } from 'react';

import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import { useCounterparties } from '@/hooks/useCounterparties';
import { POPULAR_CURRENCY_CODES, useCurrenciesSorted, useRateOnDate } from '@/hooks/useCurrencyRates';
import { useModules } from '@/hooks/useModules';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { purchasesCrud } from '@/hooks/usePurchases';
import { useWarehouses } from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { PurchaseOrder } from '@/types/auth';

interface Props {
  initial?: PurchaseOrder | null;
  onClose: () => void;
}

interface ItemDraft {
  key: string;
  nomenclature: string;
  quantity: string;
  unit_price: string;
}

function makeItemDraft(overrides: Partial<ItemDraft> = {}): ItemDraft {
  return {
    key: crypto.randomUUID(),
    nomenclature: '',
    quantity: '',
    unit_price: '',
    ...overrides,
  };
}

export default function PurchaseOrderModal({ initial, onClose }: Props) {
  const isEdit = Boolean(initial);

  const create = purchasesCrud.useCreate();
  const update = purchasesCrud.useUpdate();

  const { data: modules } = useModules();
  const { data: suppliers } = useCounterparties({ kind: 'supplier' });
  const { data: warehouses } = useWarehouses();
  const { data: currencies } = useCurrenciesSorted();
  const { data: nomenclature } = useNomenclatureItems({ is_active: 'true' });

  const [moduleId, setModuleId] = useState(initial?.module ?? '');
  const [date, setDate] = useState(initial?.date ?? new Date().toISOString().slice(0, 10));
  const [supplierId, setSupplierId] = useState(initial?.counterparty ?? '');
  const [warehouseId, setWarehouseId] = useState(initial?.warehouse ?? '');
  const [currencyId, setCurrencyId] = useState(initial?.currency ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const [items, setItems] = useState<ItemDraft[]>(() => {
    if (initial?.items && initial.items.length > 0) {
      return initial.items.map((it) => ({
        key: it.id,
        nomenclature: it.nomenclature,
        quantity: it.quantity,
        unit_price: it.unit_price,
      }));
    }
    return [makeItemDraft()];
  });

  const currencyCode = useMemo(() => {
    if (!currencyId) return 'UZS';
    return currencies?.find((c) => c.id === currencyId)?.code ?? '';
  }, [currencyId, currencies]);

  const { data: rateOnDate, isLoading: rateLoading } = useRateOnDate(
    currencyCode === 'UZS' ? null : currencyCode,
    date,
  );

  const totalInDocCurrency = useMemo(() => {
    return items.reduce((sum, it) => {
      const q = parseFloat(it.quantity || '0');
      const p = parseFloat(it.unit_price || '0');
      return sum + (isNaN(q) || isNaN(p) ? 0 : q * p);
    }, 0);
  }, [items]);

  const totalInUzs = useMemo(() => {
    if (currencyCode === 'UZS' || !rateOnDate) return totalInDocCurrency;
    const r = parseFloat(rateOnDate.rate) / (rateOnDate.nominal || 1);
    return totalInDocCurrency * r;
  }, [totalInDocCurrency, currencyCode, rateOnDate]);

  useEffect(() => {
    if (!moduleId && modules && modules.length > 0 && !initial) {
      const preferred = modules.find((m) =>
        ['purchases', 'feed', 'vet', 'matochnik', 'incubation', 'feedlot'].includes(m.code),
      );
      if (preferred) setModuleId(preferred.id);
    }
  }, [modules, moduleId, initial]);

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const updateItem = (key: string, patch: Partial<ItemDraft>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  };

  const removeItem = (key: string) => {
    setItems((prev) => prev.filter((it) => it.key !== key));
  };

  const canSubmit =
    moduleId &&
    supplierId &&
    warehouseId &&
    items.length > 0 &&
    items.every((it) => it.nomenclature && it.quantity && it.unit_price) &&
    !create.isPending &&
    !update.isPending;

  const handleSubmit = async () => {
    const payload = {
      date,
      module: moduleId,
      counterparty: supplierId,
      warehouse: warehouseId,
      currency: currencyId || null,
      notes,
      items: items.map((it) => ({
        nomenclature: it.nomenclature,
        quantity: it.quantity,
        unit_price: it.unit_price,
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
      title={isEdit ? `Редактирование закупа ${initial?.doc_number ?? ''}` : 'Новая закупка'}
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
        Закуп создаётся как <b>черновик</b>. Провести (оприходовать на склад, снять
        FX-snapshot и создать проводки) можно кнопкой «Провести» в списке.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Модуль *</label>
          <select
            className="input"
            value={moduleId}
            onChange={(e) => setModuleId(e.target.value)}
            disabled={isEdit}
          >
            <option value="">—</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
          {getFieldErr('module') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('module')}</div>
          )}
        </div>

        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field">
          <label>Поставщик *</label>
          <select className="input" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">—</option>
            {suppliers?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {getFieldErr('counterparty') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('counterparty')}</div>
          )}
        </div>

        <div className="field">
          <label>Склад прихода *</label>
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
                  Нет курса на {date} и ранее. Синхронизируйте курсы ЦБ в разделе Курсы валют.
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

      <div style={{ marginTop: 18, marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <b>Позиции</b>
        <button className="btn btn-ghost btn-sm" onClick={() => setItems((p) => [...p, makeItemDraft()])}>
          <Icon name="plus" size={12} /> Добавить
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((it) => {
          const lineDoc = parseFloat(it.quantity || '0') * parseFloat(it.unit_price || '0');
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

              <div className="field">
                <label>Кол-во *</label>
                <input
                  className="input mono"
                  type="number"
                  step="0.001"
                  value={it.quantity}
                  onChange={(e) => updateItem(it.key, { quantity: e.target.value })}
                />
              </div>

              <div className="field">
                <label>Цена за ед. ({currencyCode}) *</label>
                <input
                  className="input mono"
                  type="number"
                  step="0.01"
                  value={it.unit_price}
                  onChange={(e) => updateItem(it.key, { unit_price: e.target.value })}
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
