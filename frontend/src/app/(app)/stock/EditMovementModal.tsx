'use client';

import { useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useCounterparties } from '@/hooks/useCounterparties';
import { useUpdateManualMovement } from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { StockMovement } from '@/types/auth';

interface Props {
  movement: StockMovement;
  onClose: () => void;
  onSaved?: (m: StockMovement) => void;
}

/**
 * Частичная правка manual-движения. Менять можно только метаданные
 * (дата / контрагент / партия) — суммы, склады и SKU иммутабельны
 * по архитектуре (иначе поедут остатки и ГК). Чтобы изменить сумму
 * или склад — удалите движение и создайте новое.
 */
export default function EditMovementModal({ movement, onClose, onSaved }: Props) {
  const update = useUpdateManualMovement();
  const { data: parties } = useCounterparties({ is_active: 'true' });

  // Дата приходит как ISO с таймзоной — приводим к формату input[type=datetime-local]
  const dateLocal = movement.date
    ? new Date(movement.date).toISOString().slice(0, 16)
    : '';

  const [date, setDate] = useState(dateLocal);
  const [counterparty, setCounterparty] = useState(movement.counterparty ?? '');

  const error = update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const handleSubmit = async () => {
    const patch: Record<string, string | null> = {};
    // Передаём только реально изменённые поля
    if (date !== dateLocal) {
      patch.date = date ? new Date(date).toISOString() : '';
    }
    if (counterparty !== (movement.counterparty ?? '')) {
      patch.counterparty = counterparty || null;
    }
    try {
      const updated = await update.mutateAsync({ id: movement.id, patch });
      onSaved?.(updated);
      onClose();
    } catch { /* остаётся в state */ }
  };

  return (
    <Modal
      title={`Изменить движение ${movement.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={update.isPending}
          >
            {update.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{
        padding: 10, marginBottom: 14,
        background: 'var(--warning-soft)',
        border: '1px solid var(--warning)',
        borderRadius: 4, fontSize: 12, color: '#6A4500',
      }}>
        <b>Можно править только метаданные.</b> Суммы, количество, склады и
        SKU иммутабельны — иначе поедут остатки. Чтобы их изменить,
        удалите движение и создайте новое.
      </div>

      {/* Read-only context */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
        padding: 10, marginBottom: 14,
        background: 'var(--bg-soft)', borderRadius: 6,
        fontSize: 12,
      }}>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>
            Тип
          </div>
          <div style={{ fontWeight: 500 }}>{movement.kind}</div>
        </div>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>
            Номенклатура
          </div>
          <div className="mono" style={{ fontWeight: 500 }}>
            {movement.nomenclature_sku} · {movement.nomenclature_name}
          </div>
        </div>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>
            Количество
          </div>
          <div className="mono">
            {parseFloat(movement.quantity).toLocaleString('ru-RU')}
          </div>
        </div>
        <div>
          <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>
            Сумма
          </div>
          <div className="mono">
            {parseFloat(movement.amount_uzs ?? '0').toLocaleString('ru-RU')} сум
          </div>
        </div>
        {movement.warehouse_from_code && (
          <div>
            <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>
              Со склада
            </div>
            <div className="mono">{movement.warehouse_from_code}</div>
          </div>
        )}
        {movement.warehouse_to_code && (
          <div>
            <div style={{ color: 'var(--fg-3)', fontSize: 10, textTransform: 'uppercase' }}>
              На склад
            </div>
            <div className="mono">{movement.warehouse_to_code}</div>
          </div>
        )}
      </div>

      <div className="field">
        <label>
          Дата
          <HelpHint
            text="Когда фактически произошло движение."
            details="Влияет на отображение в журнале и попадание в отчётный период. Не меняет остатков."
          />
        </label>
        <input
          className="input"
          type="datetime-local"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        {fieldErrors.date && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {Array.isArray(fieldErrors.date) ? fieldErrors.date.join(' · ') : String(fieldErrors.date)}
          </div>
        )}
      </div>

      <div className="field">
        <label>
          Контрагент
          <HelpHint
            text="Привязка к поставщику/покупателю (опц.)."
            details="Используется для фильтрации в отчётах и аналитики по контрагенту."
          />
        </label>
        <select
          className="input"
          value={counterparty}
          onChange={(e) => setCounterparty(e.target.value)}
        >
          <option value="">— не указан —</option>
          {parties?.map((p) => (
            <option key={p.id} value={p.id}>{p.code} · {p.name}</option>
          ))}
        </select>
        {fieldErrors.counterparty && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {Array.isArray(fieldErrors.counterparty)
              ? fieldErrors.counterparty.join(' · ')
              : String(fieldErrors.counterparty)}
          </div>
        )}
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
