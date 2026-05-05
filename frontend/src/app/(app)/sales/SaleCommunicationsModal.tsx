'use client';

import { useState } from 'react';

import DetailDrawer from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import { ApiError } from '@/lib/api';
import { saleCommunicationsCrud } from '@/hooks/useSales';
import type {
  SaleCommunication,
  SaleCommunicationMethod,
  SaleCommunicationOutcome,
  SaleOrder,
} from '@/types/auth';

interface Props {
  order: SaleOrder;
  onClose: () => void;
}

const METHOD_OPTIONS: { value: SaleCommunicationMethod; label: string }[] = [
  { value: 'call', label: 'Звонок' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'sms', label: 'SMS' },
  { value: 'email', label: 'Email' },
  { value: 'visit', label: 'Личная встреча' },
  { value: 'other', label: 'Другое' },
];

const OUTCOME_OPTIONS: { value: SaleCommunicationOutcome; label: string; tone: 'info' | 'warn' | 'danger' | 'success' | 'neutral' }[] = [
  { value: 'promised', label: 'Обещал оплатить', tone: 'success' },
  { value: 'asked_defer', label: 'Попросил отсрочку', tone: 'warn' },
  { value: 'no_answer', label: 'Не ответил', tone: 'neutral' },
  { value: 'wrong_number', label: 'Неверный номер', tone: 'danger' },
  { value: 'refused', label: 'Отказался', tone: 'danger' },
  { value: 'other', label: 'Другое', tone: 'neutral' },
];

const OUTCOME_TONE: Record<SaleCommunicationOutcome, 'info' | 'warn' | 'danger' | 'success' | 'neutral'> =
  Object.fromEntries(OUTCOME_OPTIONS.map((o) => [o.value, o.tone])) as never;

/**
 * Модалка истории касаний с клиентом по конкретной продаже.
 *
 * Слева — таймлайн (что когда сказал клиент), справа — форма «новое касание».
 * После создания запись сразу появляется в списке. Это превращает sales-карточку
 * из статичного документа в живой CRM-инструмент: «звонил вчера, обещал в пятницу
 * → пятница прошла, не позвонил → звоню снова, фиксирую отказ».
 */
export default function SaleCommunicationsModal({ order, onClose }: Props) {
  const { data: comms, isLoading } = saleCommunicationsCrud.useList({ order: order.id });
  const create = saleCommunicationsCrud.useCreate();

  const [contactedAt, setContactedAt] = useState(() => {
    // datetime-local format: YYYY-MM-DDTHH:mm
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  });
  const [method, setMethod] = useState<SaleCommunicationMethod>('call');
  const [outcome, setOutcome] = useState<SaleCommunicationOutcome>('promised');
  const [customerResponse, setCustomerResponse] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [promisedDate, setPromisedDate] = useState('');
  const [expectedDate, setExpectedDate] = useState('');
  const [nextDate, setNextDate] = useState('');

  const fieldErrors = create.error instanceof ApiError && create.error.status === 400
    ? ((create.error.data as Record<string, unknown>) ?? {})
    : {};
  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const reset = () => {
    setCustomerResponse('');
    setInternalNote('');
    setPromisedDate('');
    setExpectedDate('');
    setNextDate('');
  };

  const submit = async () => {
    if (customerResponse.trim().length < 3) return;
    try {
      await create.mutateAsync({
        order: order.id,
        contacted_at: new Date(contactedAt).toISOString(),
        method,
        outcome,
        customer_response: customerResponse.trim(),
        internal_note: internalNote.trim() || undefined,
        promised_pay_date: promisedDate || null,
        expected_pay_date: expectedDate || null,
        next_action_date: nextDate || null,
      });
      reset();
    } catch {
      /* error stays in mutation */
    }
  };

  const sortedComms = (comms ?? []).slice().sort((a, b) =>
    a.contacted_at < b.contacted_at ? 1 : -1,
  );

  const debtNum = parseFloat(order.amount_uzs) - parseFloat(order.paid_amount_uzs);
  const subtitle = (
    `${order.customer_name ?? '—'} · `
    + `Долг ${debtNum.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум`
    + (order.due_date ? ` · до ${order.due_date}` : '')
  );

  return (
    <DetailDrawer
      title={`Касания клиента · ${order.doc_number}`}
      subtitle={subtitle}
      onClose={onClose}
    >
      {/* Drawer шире модалки → 2 колонки помещаются с воздухом. */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* ── Таймлайн ─────────────────────────────────────── */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
            История ({sortedComms.length})
          </div>
          {isLoading && <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Загружаем…</div>}
          {!isLoading && sortedComms.length === 0 && (
            <div style={{
              padding: 12, fontSize: 12, color: 'var(--fg-3)',
              border: '1px dashed var(--border)', borderRadius: 6,
              textAlign: 'center',
            }}>
              Касаний ещё нет. Добавьте первое →
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 480, overflowY: 'auto' }}>
            {sortedComms.map((c) => (
              <CommunicationItem key={c.id} comm={c} />
            ))}
          </div>
        </div>

        {/* ── Новое касание ────────────────────────────────── */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
            Новое касание
          </div>

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
              placeholder="Только для сотрудников: «скандалил», «жалуется на качество»…"
            />
            <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
              Не уходит клиенту, видно только сотрудникам.
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div className="field">
              <label>Обещал клиент</label>
              <input
                className="input"
                type="date"
                value={promisedDate}
                onChange={(e) => setPromisedDate(e.target.value)}
              />
              <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
                Слова клиента
              </div>
            </div>
            <div className="field">
              <label>Жду оплату</label>
              <input
                className="input"
                type="date"
                value={expectedDate}
                onChange={(e) => setExpectedDate(e.target.value)}
              />
              <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
                Ваш прогноз — тоже триггерит напоминание
              </div>
            </div>
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

          <button
            className="btn btn-primary"
            disabled={create.isPending || customerResponse.trim().length < 3}
            onClick={submit}
            style={{ width: '100%', marginTop: 8 }}
          >
            {create.isPending ? 'Сохранение…' : 'Сохранить касание'}
          </button>

          {create.error && create.error.status !== 400 && (
            <div style={{ marginTop: 8, padding: 6, fontSize: 11, color: 'var(--danger)', background: '#fef2f2', borderRadius: 4 }}>
              {create.error.message}
            </div>
          )}
        </div>
      </div>
    </DetailDrawer>
  );
}

function CommunicationItem({ comm }: { comm: SaleCommunication }) {
  return (
    <div style={{
      padding: 8, border: '1px solid var(--border)', borderRadius: 6,
      background: 'var(--bg-card)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          {new Date(comm.contacted_at).toLocaleString('ru-RU', {
            day: '2-digit', month: '2-digit', year: '2-digit',
            hour: '2-digit', minute: '2-digit',
          })}
        </span>
        <Badge tone="info">{comm.method_display}</Badge>
        <Badge tone={OUTCOME_TONE[comm.outcome]}>{comm.outcome_display}</Badge>
      </div>

      <div style={{ fontSize: 12, color: 'var(--fg-1)', marginBottom: 4 }}>
        «{comm.customer_response}»
      </div>

      {comm.internal_note && (
        <div style={{
          fontSize: 11, color: 'var(--fg-2)', marginBottom: 6,
          padding: '4px 8px', background: 'var(--bg-soft)', borderRadius: 4,
          fontStyle: 'italic',
        }}>
          📝 {comm.internal_note}
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--fg-3)', flexWrap: 'wrap' }}>
        {comm.contacted_by_name && (
          <span>
            <Icon name="user" size={10} /> {comm.contacted_by_name}
          </span>
        )}
        {comm.promised_pay_date && (
          <span style={{ color: 'var(--brand-orange)' }}>
            ✓ обещал к {comm.promised_pay_date}
          </span>
        )}
        {comm.expected_pay_date && (
          <span style={{ color: 'var(--brand-orange)' }}>
            🎯 жду оплату к {comm.expected_pay_date}
          </span>
        )}
        {comm.next_action_date && (
          <span>↺ перезвонить {comm.next_action_date}</span>
        )}
      </div>
    </div>
  );
}
