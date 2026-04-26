'use client';

import { useEffect, useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { useCounterparties } from '@/hooks/useCounterparties';
import { useModules } from '@/hooks/useModules';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import {
  useCreateManualMovement,
  useWarehouses,
  type ManualMovementPayload,
} from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { StockMovement, StockMovementKind } from '@/types/auth';

const KIND_OPTIONS: { value: StockMovementKind; label: string; help: string }[] = [
  { value: 'incoming',  label: 'Приход',       help: 'Поступление на склад без закупа (инвентарная корректировка).' },
  { value: 'outgoing',  label: 'Расход',       help: 'Снятие со склада без продажи.' },
  { value: 'transfer',  label: 'Перемещение',  help: 'Со склада на склад внутри организации.' },
  { value: 'write_off', label: 'Списание',     help: 'Списание с указанием причины (брак, порча).' },
];

interface Props {
  onClose: () => void;
  onSaved?: (m: StockMovement) => void;
}

export default function StockMovementModal({ onClose, onSaved }: Props) {
  const create = useCreateManualMovement();
  const saving = create.isPending;
  const error = create.error;

  const [kind, setKind] = useState<StockMovementKind>('incoming');
  const [moduleId, setModuleId] = useState('');
  const [nomenclatureId, setNomenclatureId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unitPrice, setUnitPrice] = useState('');
  const [whFrom, setWhFrom] = useState('');
  const [whTo, setWhTo] = useState('');
  const [counterparty, setCounterparty] = useState('');

  const { data: modules } = useModules();
  const moduleCode = useMemo(
    () => modules?.find((m) => m.id === moduleId)?.code,
    [modules, moduleId],
  );
  const { data: warehouses } = useWarehouses();
  const { data: items } = useNomenclatureItems({
    module_code: moduleCode,
    is_active: 'true',
  });
  const { data: parties } = useCounterparties({ is_active: 'true' });

  // Сбрасываем поля, несовместимые с выбранным типом
  useEffect(() => {
    if (kind === 'incoming') {
      setWhFrom('');
    } else if (kind === 'outgoing' || kind === 'write_off') {
      setWhTo('');
    }
  }, [kind]);

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[] | string>) ?? {})
      : {};

  const totalUzs = useMemo(() => {
    const q = parseFloat(quantity || '0');
    const p = parseFloat(unitPrice || '0');
    if (Number.isNaN(q) || Number.isNaN(p)) return 0;
    return q * p;
  }, [quantity, unitPrice]);

  const needFrom = kind === 'outgoing' || kind === 'transfer' || kind === 'write_off';
  const needTo = kind === 'incoming' || kind === 'transfer';

  const canSave =
    !saving &&
    !!moduleId &&
    !!nomenclatureId &&
    !!quantity &&
    !!unitPrice &&
    parseFloat(quantity) > 0 &&
    (!needFrom || !!whFrom) &&
    (!needTo || !!whTo);

  const handleSave = async () => {
    const payload: ManualMovementPayload = {
      module: moduleId,
      kind,
      nomenclature: nomenclatureId,
      quantity,
      unit_price_uzs: unitPrice,
      warehouse_from: needFrom ? whFrom : null,
      warehouse_to: needTo ? whTo : null,
      counterparty: counterparty || null,
    };
    try {
      const res = await create.mutateAsync(payload);
      onSaved?.(res);
      onClose();
    } catch {
      /* errors surfaced inline */
    }
  };

  const renderError = (key: string) => {
    const e = fieldErrors[key];
    if (!e) return null;
    const txt = Array.isArray(e) ? e.join(' · ') : e;
    return (
      <div style={{ fontSize: 11, color: 'var(--danger)' }}>{txt}</div>
    );
  };

  return (
    <Modal
      title="Новое движение по складу"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary" disabled={!canSave} onClick={handleSave}>
            {saving ? 'Сохранение…' : 'Создать'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field" style={{ gridColumn: '1 / -1' }}>
          <label>Тип движения *</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {KIND_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={kind === opt.value ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
                onClick={() => setKind(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            {KIND_OPTIONS.find((o) => o.value === kind)?.help}
          </div>
        </div>

        <div className="field">
          <label>Модуль *</label>
          <select
            className="input"
            value={moduleId}
            onChange={(e) => {
              setModuleId(e.target.value);
              setNomenclatureId('');
            }}
          >
            <option value="">— выберите —</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          {renderError('module')}
        </div>

        <div className="field">
          <label>Номенклатура *</label>
          <select
            className="input"
            value={nomenclatureId}
            onChange={(e) => setNomenclatureId(e.target.value)}
            disabled={!moduleId}
          >
            <option value="">{moduleId ? '— выберите —' : 'выберите модуль'}</option>
            {items?.map((i) => (
              <option key={i.id} value={i.id}>
                {i.sku} · {i.name}
              </option>
            ))}
          </select>
          {renderError('nomenclature')}
        </div>

        <div className="field">
          <label>Количество *</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            min="0"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0.000"
          />
          {renderError('quantity')}
        </div>

        <div className="field">
          <label>Цена за ед., UZS *</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            min="0"
            value={unitPrice}
            onChange={(e) => setUnitPrice(e.target.value)}
            placeholder="0.00"
          />
          {renderError('unit_price_uzs')}
        </div>

        {needFrom && (
          <div className="field">
            <label>Со склада *</label>
            <select
              className="input"
              value={whFrom}
              onChange={(e) => setWhFrom(e.target.value)}
            >
              <option value="">— выберите —</option>
              {warehouses?.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} · {w.name}
                </option>
              ))}
            </select>
            {renderError('warehouse_from')}
          </div>
        )}

        {needTo && (
          <div className="field">
            <label>На склад *</label>
            <select
              className="input"
              value={whTo}
              onChange={(e) => setWhTo(e.target.value)}
            >
              <option value="">— выберите —</option>
              {warehouses?.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} · {w.name}
                </option>
              ))}
            </select>
            {renderError('warehouse_to')}
          </div>
        )}

        <div className="field" style={{ gridColumn: '1 / -1' }}>
          <label>Контрагент (опционально)</label>
          <select
            className="input"
            value={counterparty}
            onChange={(e) => setCounterparty(e.target.value)}
          >
            <option value="">— не указан —</option>
            {parties?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.name}
              </option>
            ))}
          </select>
        </div>

        <div
          className="field"
          style={{
            gridColumn: '1 / -1',
            background: 'var(--bg-soft)',
            padding: 10,
            borderRadius: 6,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>Сумма движения</span>
          <span className="mono" style={{ fontSize: 16, fontWeight: 600 }}>
            {totalUzs.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} UZS
          </span>
        </div>
      </div>

      {fieldErrors.__all__ && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          {Array.isArray(fieldErrors.__all__) ? fieldErrors.__all__.join(' · ') : fieldErrors.__all__}
        </div>
      )}
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
