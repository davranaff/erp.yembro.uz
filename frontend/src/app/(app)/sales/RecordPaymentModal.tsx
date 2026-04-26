'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useRecordSalePayment } from '@/hooks/useSales';
import { ApiError } from '@/lib/api';
import type { SaleOrder } from '@/types/auth';

interface Props {
  order: SaleOrder;
  onClose: () => void;
}

function fmtUzs(v: string | number): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

/**
 * Принять оплату за проведённую продажу.
 *
 * Создаёт Payment(kind=counterparty, direction=in) с аллокацией на эту
 * SaleOrder и сразу проводит. paid_amount_uzs и payment_status обновятся.
 */
export default function RecordPaymentModal({ order, onClose }: Props) {
  const record = useRecordSalePayment();

  const remaining = useMemo(() => {
    const total = parseFloat(order.amount_uzs || '0');
    const paid = parseFloat(order.paid_amount_uzs || '0');
    return Math.max(0, total - paid);
  }, [order]);

  const [channel, setChannel] = useState<'cash' | 'transfer' | 'click' | 'other'>('cash');
  const [amount, setAmount] = useState(String(remaining));
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');

  const error = record.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const amt = parseFloat(amount || '0');
  const overPay = amt > remaining;
  const canSubmit = amt > 0 && date && !record.isPending;

  const handleSubmit = async () => {
    try {
      await record.mutateAsync({
        id: order.id,
        body: {
          channel,
          amount_uzs: amount,
          date,
          notes,
        },
      });
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
      title={`Принять оплату · ${order.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {record.isPending ? 'Проводка…' : 'Принять и провести'}
          </button>
        </>
      }
    >
      <div style={{
        padding: 10, marginBottom: 14, background: 'var(--bg-soft)',
        borderRadius: 6, fontSize: 13,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span>Клиент:</span>
          <b>{order.customer_name ?? '—'}</b>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span>Сумма продажи:</span>
          <span className="mono">{fmtUzs(order.amount_uzs)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span>Уже оплачено:</span>
          <span className="mono">{fmtUzs(order.paid_amount_uzs || '0')}</span>
        </div>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          paddingTop: 4, borderTop: '1px solid var(--border)',
          fontWeight: 600,
        }}>
          <span>Осталось:</span>
          <span className="mono" style={{ color: 'var(--brand-orange)' }}>
            {fmtUzs(remaining)}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>
            Канал *
            <HelpHint
              text="Куда поступили деньги."
              details={
                '• Наличные (касса 50.01) — клиент отдал налом.\n'
                + '• Перечисление (банк 51.01) — пришло на расчётный счёт.\n'
                + '• Click — электронный платёж Click/Payme (тоже на 51.01).\n'
                + '• Прочее — нестандартный способ, потребует явного выбора cash_subaccount.'
              }
            />
          </label>
          <select
            className="input"
            value={channel}
            onChange={(e) => setChannel(e.target.value as typeof channel)}
          >
            <option value="cash">Наличные (касса 50.01)</option>
            <option value="transfer">Перечисление (банк 51.01)</option>
            <option value="click">Click / Payme (51.01)</option>
            <option value="other">Прочее</option>
          </select>
        </div>

        <div className="field">
          <label>Дата платежа *</label>
          <input
            className="input"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>
            Сумма, UZS *
            <HelpHint
              text="Сколько клиент заплатил."
              details="По умолчанию — остаток долга. Если клиент платит часть — уменьшите; статус продажи станет «Частично оплачен». Если больше — «Переплата»."
            />
          </label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={overPay ? { borderColor: 'var(--warning)' } : undefined}
          />
          {overPay && (
            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
              Сумма больше остатка долга — продажа попадёт в «Переплата».
            </div>
          )}
          {getErr('amount_uzs') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('amount_uzs')}</div>
          )}
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметка</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={`Оплата по ${order.doc_number}`}
          />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{
          marginTop: 12, padding: 8,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 12,
        }}>
          {error.message}
        </div>
      )}

      <div style={{
        marginTop: 12, fontSize: 11, color: 'var(--fg-3)', lineHeight: 1.5,
      }}>
        При «Принять и провести» создастся платёж, сделается проводка в
        ГК (Дт касса/банк / Кт 62.01) и обновится статус оплаты продажи.
      </div>
    </Modal>
  );
}
