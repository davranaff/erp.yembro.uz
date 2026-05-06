'use client';

import { useEffect, useMemo, useState } from 'react';

import { useQueryClient } from '@tanstack/react-query';
import Modal from '@/components/ui/Modal';
import { useSubaccounts } from '@/hooks/useAccounts';
import { ApiError } from '@/lib/api';
import { useAllocatePayment, usePostPayment, paymentsCrud } from '@/hooks/usePayments';
import type { PurchaseOrder } from '@/types/auth';

interface Props {
  order: PurchaseOrder;
  onClose: () => void;
}

function fmtUzs(v: string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

export default function PayPurchaseModal({ order, onClose }: Props) {
  const { data: subaccounts } = useSubaccounts();
  const qc = useQueryClient();

  const create = paymentsCrud.useCreate();
  const post = usePostPayment();
  const allocate = useAllocatePayment();

  const remaining = parseFloat(order.amount_uzs || '0') - parseFloat(order.paid_amount_uzs || '0');

  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState(remaining > 0 ? String(remaining) : '');
  const [channel, setChannel] = useState<'cash' | 'transfer' | 'click' | 'other'>('cash');
  const [cashSubId, setCashSubId] = useState('');
  const [notes, setNotes] = useState('');

  // Кассы для выбора: только 50.NN/51.NN, и сужаем по модулю закупа
  // (vet-закуп → не показываем feed-кассу, чтобы платёж не попал в чужой
  // котёл). Кассы без модуля («общие» 50.01/51.01) показываем всегда.
  const filteredSubs = useMemo(() => {
    if (!subaccounts) return [];
    return subaccounts
      .filter((s) => s.code.startsWith('50.') || s.code.startsWith('51.'))
      .filter((s) => !order.module || !s.module || s.module === order.module);
  }, [subaccounts, order.module]);

  // Авто-выбор: при смене канала/субсчета подхватываем первую подходящую
  // кассу (приоритет — модульная, общая 50.01/51.01 как fallback).
  useEffect(() => {
    if (!filteredSubs.length) return;
    const wantPrefix = channel === 'cash' ? '50.' : '51.';
    const candidates = filteredSubs.filter((s) => s.code.startsWith(wantPrefix));
    if (!candidates.length) return;
    // Если уже выбрана подходящая по prefix — не трогаем
    if (cashSubId && candidates.some((s) => s.id === cashSubId)) return;
    // Приоритет: модульная > общая
    const moduleMatch = candidates.find((s) => s.module === order.module);
    setCashSubId((moduleMatch ?? candidates[0]).id);
  }, [channel, filteredSubs, order.module, cashSubId]);

  const isPending = create.isPending || post.isPending || allocate.isPending;

  const error = create.error ?? post.error ?? allocate.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};
  const getErr = (k: string) => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const canSubmit =
    Boolean(amount) &&
    parseFloat(amount) > 0 &&
    Boolean(cashSubId) &&
    !isPending;

  const handleSubmit = async () => {
    try {
      // 1. Создать платёж типа counterparty (OUT). Module берём с закупа —
      // backend (PaymentViewSet) скоупит платежи по модулям, на которые у
      // юзера rw. Без module=null head'ы получали 403.
      const payment = await create.mutateAsync({
        date,
        module: order.module,
        direction: 'out',
        channel,
        kind: 'counterparty',
        counterparty: order.counterparty,
        amount_uzs: amount,
        cash_subaccount: cashSubId,
        notes: notes || `Оплата закупа ${order.doc_number}`,
      });

      // 2. Аллоцировать на закуп
      await allocate.mutateAsync({
        id: payment.id,
        body: {
          target_content_type: order.content_type_id,
          target_object_id: order.id,
          amount_uzs: amount,
        },
      });

      // 3. Провести платёж
      await post.mutateAsync({ id: payment.id });

      // Инвалидируем закупы — payment_status и paid_amount_uzs обновятся сразу
      await qc.invalidateQueries({ queryKey: ['purchases', 'orders'] });

      onClose();
    } catch {
      /* ошибки отображаются из mutation-ов */
    }
  };

  return (
    <Modal
      title={`Оплата закупа · ${order.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {isPending ? 'Проводим…' : 'Оплатить и провести'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 16 }}>
        Создаёт платёж типа <b>Оплата поставщику</b>, привязывает к закупу и проводит.
        Статус закупа изменится автоматически.
      </div>

      {/* Сводка по закупу */}
      <div style={{
        background: 'var(--bg-soft)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '10px 14px',
        marginBottom: 16,
        fontSize: 13,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '6px 16px',
      }}>
        <div style={{ color: 'var(--fg-3)' }}>Поставщик</div>
        <div style={{ fontWeight: 500 }}>{order.counterparty_name ?? '—'}</div>
        <div style={{ color: 'var(--fg-3)' }}>Сумма закупа</div>
        <div className="mono">{fmtUzs(order.amount_uzs)}</div>
        <div style={{ color: 'var(--fg-3)' }}>Уже оплачено</div>
        <div className="mono" style={{ color: 'var(--success)' }}>
          {fmtUzs(order.paid_amount_uzs)}
        </div>
        <div style={{ color: 'var(--fg-3)' }}>Остаток к оплате</div>
        <div className="mono" style={{ fontWeight: 700, color: remaining > 0 ? 'var(--danger)' : 'var(--success)' }}>
          {fmtUzs(String(remaining))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата оплаты *</label>
          <input
            className="input"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Сумма, UZS *</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
          />
          {getErr('amount_uzs') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('amount_uzs')}</div>
          )}
        </div>

        <div className="field">
          <label>Канал оплаты *</label>
          <select
            className="input"
            value={channel}
            onChange={(e) => setChannel(e.target.value as typeof channel)}
          >
            <option value="cash">Наличные (касса 50.01)</option>
            <option value="transfer">Перечисление (банк 51.01)</option>
            <option value="click">Click (банк 51.01)</option>
            <option value="other">Прочее</option>
          </select>
        </div>

        <div className="field">
          <label>Счёт (касса/банк) *</label>
          <select
            className="input"
            value={cashSubId}
            onChange={(e) => setCashSubId(e.target.value)}
          >
            <option value="">— выберите —</option>
            {filteredSubs.map((s) => (
              <option key={s.id} value={s.id}>{s.code} · {s.name}</option>
            ))}
          </select>
          {!filteredSubs.length && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              Нет доступных касс/счетов в этом модуле — попросите админа создать.
            </div>
          )}
          {getErr('cash_subaccount') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('cash_subaccount')}</div>
          )}
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Примечание</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={`Оплата закупа ${order.doc_number}`}
          />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{
          marginTop: 10, padding: 8,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 12,
        }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
