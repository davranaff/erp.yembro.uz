'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import Modal from '@/components/ui/Modal';
import { ApiError, apiFetch } from '@/lib/api';
import { saleCommunicationsCrud } from '@/hooks/useSales';
import type {
  SaleCommunication,
  SaleCommunicationMethod,
  SaleCommunicationOutcome,
} from '@/types/auth';

interface OrderOption {
  id: string;
  doc_number: string;
  outstanding_uzs: string;
}

interface AddProps {
  mode: 'add';
  /** Если задан — заказ известен, скрываем picker. */
  order?: OrderOption;
  /** Если задан — режим карточки клиента: показываем picker по open_orders. */
  customerId?: string;
  customerName?: string;
  customerOpenOrders?: OrderOption[];
  onClose: () => void;
}

interface EditProps {
  mode: 'edit';
  communication: SaleCommunication;
  /** Опционально — для инвалидации debt-summary конкретного клиента. */
  customerId?: string;
  onClose: () => void;
}

type Props = AddProps | EditProps;

const METHOD_OPTIONS: { value: SaleCommunicationMethod; label: string }[] = [
  { value: 'call', label: 'Звонок' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'sms', label: 'SMS' },
  { value: 'email', label: 'Email' },
  { value: 'visit', label: 'Личная встреча' },
  { value: 'other', label: 'Другое' },
];

const OUTCOME_OPTIONS: { value: SaleCommunicationOutcome; label: string }[] = [
  { value: 'promised', label: 'Обещал оплатить' },
  { value: 'asked_defer', label: 'Попросил отсрочку' },
  { value: 'no_answer', label: 'Не ответил' },
  { value: 'wrong_number', label: 'Неверный номер' },
  { value: 'refused', label: 'Отказался' },
  { value: 'other', label: 'Другое' },
];

function fmtMoney(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function isoLocalNow(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

/**
 * Универсальная форма касания: создание (per-order или из карточки клиента
 * с picker открытых счетов) и редактирование существующей записи.
 *
 * Backend CRUD: `/api/sales/communications/{id}/` (PATCH/DELETE), `/communications/`
 * (POST). Cross-org защита и `contacted_by=request.user` форсятся в perform_create.
 */
export default function CommunicationFormModal(props: Props) {
  const qc = useQueryClient();
  const create = saleCommunicationsCrud.useCreate();
  const update = saleCommunicationsCrud.useUpdate();

  const isEdit = props.mode === 'edit';
  const initial = isEdit ? props.communication : null;

  // Резолвим customerId/customerName/order из обоих режимов
  const customerId = isEdit ? undefined : props.customerId;
  const customerName = !isEdit ? props.customerName : undefined;
  const customerOpenOrders = !isEdit ? props.customerOpenOrders ?? [] : [];
  const fixedOrder = !isEdit ? props.order : undefined;

  const [orderId, setOrderId] = useState<string>(
    isEdit ? initial!.order : (fixedOrder?.id ?? customerOpenOrders[0]?.id ?? ''),
  );
  const [contactedAt, setContactedAt] = useState<string>(() => {
    if (isEdit) {
      const d = new Date(initial!.contacted_at);
      d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
      return d.toISOString().slice(0, 16);
    }
    return isoLocalNow();
  });
  const [method, setMethod] = useState<SaleCommunicationMethod>(
    isEdit ? initial!.method : 'call',
  );
  const [outcome, setOutcome] = useState<SaleCommunicationOutcome>(
    isEdit ? initial!.outcome : 'promised',
  );
  const [customerResponse, setCustomerResponse] = useState<string>(
    isEdit ? initial!.customer_response : '',
  );
  const [internalNote, setInternalNote] = useState<string>(
    isEdit ? initial!.internal_note : '',
  );
  const [promisedDate, setPromisedDate] = useState<string>(
    isEdit ? (initial!.promised_pay_date ?? '') : '',
  );
  const [expectedDate, setExpectedDate] = useState<string>(
    isEdit ? (initial!.expected_pay_date ?? '') : '',
  );
  const [nextDate, setNextDate] = useState<string>(
    isEdit ? (initial!.next_action_date ?? '') : '',
  );

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

  const showOrderPicker = !isEdit && !fixedOrder && customerOpenOrders.length > 0;
  const showOrderMissing = !isEdit && !fixedOrder && customerOpenOrders.length === 0;

  const isValid =
    orderId &&
    contactedAt &&
    customerResponse.trim().length >= 3 &&
    !create.isPending &&
    !update.isPending;

  const submit = async () => {
    if (!isValid) return;
    const payload = {
      order: orderId,
      contacted_at: new Date(contactedAt).toISOString(),
      method,
      outcome,
      customer_response: customerResponse.trim(),
      internal_note: internalNote.trim() || '',
      promised_pay_date: promisedDate || null,
      expected_pay_date: expectedDate || null,
      next_action_date: nextDate || null,
    };
    try {
      if (isEdit) {
        await update.mutateAsync({ id: initial!.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      // Доп-инвалидация debt-summary конкретного клиента (если знаем)
      const cid = isEdit ? props.customerId : customerId;
      if (cid) {
        qc.invalidateQueries({
          queryKey: ['counterparties', 'debt-summary', cid],
        });
      }
      qc.invalidateQueries({ queryKey: ['sales', 'tasks'] });
      props.onClose();
    } catch {
      /* error visible via fieldErrors / ApiError */
    }
  };

  const title = isEdit
    ? `Редактировать касание · ${new Date(initial!.contacted_at).toLocaleDateString('ru-RU')}`
    : `Новое касание${customerName ? ` · ${customerName}` : ''}`;

  return (
    <Modal
      title={title}
      onClose={props.onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={props.onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!isValid}
            onClick={submit}
          >
            {(create.isPending || update.isPending)
              ? 'Сохранение…'
              : isEdit ? 'Сохранить' : 'Добавить'}
          </button>
        </>
      }
    >
      {showOrderMissing && (
        <div style={{
          padding: 12, marginBottom: 12, borderRadius: 6,
          background: '#fef2f2', color: 'var(--danger)', fontSize: 12,
        }}>
          У клиента нет открытых (неоплаченных) счетов — касание привязать не к чему.
          Касания фиксируются по конкретной продаже.
        </div>
      )}

      {showOrderPicker && (
        <div className="field">
          <label>По какому счёту *</label>
          <select className="input" value={orderId} onChange={(e) => setOrderId(e.target.value)}>
            <option value="">— выберите счёт —</option>
            {customerOpenOrders.map((o) => (
              <option key={o.id} value={o.id}>
                {o.doc_number} · долг {fmtMoney(o.outstanding_uzs)} сум
              </option>
            ))}
          </select>
        </div>
      )}

      {fixedOrder && !isEdit && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
          Счёт: <span className="mono">{fixedOrder.doc_number}</span> ·
          долг {fmtMoney(fixedOrder.outstanding_uzs)} сум
        </div>
      )}

      <div className="field">
        <label>Когда *</label>
        <input
          className="input"
          type="datetime-local"
          value={contactedAt}
          onChange={(e) => setContactedAt(e.target.value)}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div className="field">
          <label>Канал *</label>
          <select className="input" value={method} onChange={(e) => setMethod(e.target.value as SaleCommunicationMethod)}>
            {METHOD_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Итог *</label>
          <select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value as SaleCommunicationOutcome)}>
            {OUTCOME_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div className="field">
        <label>Что ответил клиент *</label>
        <textarea
          className="input"
          rows={3}
          value={customerResponse}
          onChange={(e) => setCustomerResponse(e.target.value)}
          placeholder="«Заплачу в пятницу» / «Просит скидку 10%» / «Жду свою з/п»…"
        />
        {getErr('customer_response') && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('customer_response')}</div>
        )}
      </div>

      <div className="field">
        <label>Внутреннее примечание</label>
        <textarea
          className="input"
          rows={2}
          value={internalNote}
          onChange={(e) => setInternalNote(e.target.value)}
          placeholder="Только для сотрудников — не уходит клиенту"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <div className="field">
          <label>Обещал клиент</label>
          <input
            className="input"
            type="date"
            value={promisedDate}
            onChange={(e) => setPromisedDate(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Жду оплату</label>
          <input
            className="input"
            type="date"
            value={expectedDate}
            onChange={(e) => setExpectedDate(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Перезвонить</label>
          <input
            className="input"
            type="date"
            value={nextDate}
            onChange={(e) => setNextDate(e.target.value)}
          />
        </div>
      </div>

      {error && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, fontSize: 12, color: 'var(--danger)', background: '#fef2f2', borderRadius: 4 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
