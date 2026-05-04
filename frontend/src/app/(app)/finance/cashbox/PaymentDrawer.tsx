'use client';

import { useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Panel from '@/components/ui/Panel';
import { useCancelPayment, useReversePayment } from '@/hooks/usePayments';
import type { Payment, PaymentAllocation, PaymentKind, PaymentStatus } from '@/types/auth';

interface Props {
  payment: Payment;
  onClose: () => void;
}

const KIND_LABEL: Record<PaymentKind, string> = {
  counterparty: 'Контрагент',
  opex: 'Прочий расход',
  income: 'Прочий доход',
  salary: 'Зарплата',
  internal: 'Внутр. перевод',
};

const STATUS_LABEL: Record<PaymentStatus, string> = {
  draft: 'Черновик',
  confirmed: 'Подтверждён',
  posted: 'Проведён',
  cancelled: 'Отменён',
};

const STATUS_TONE: Record<PaymentStatus, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  draft: 'neutral',
  confirmed: 'info',
  posted: 'success',
  cancelled: 'danger',
};

function fmtUzs(v: string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' сум';
}

export default function PaymentDrawer({ payment, onClose }: Props) {
  const [tab, setTab] = useState<'overview' | 'allocations'>('overview');
  const reverse = useReversePayment();
  const cancel = useCancelPayment();

  const handleReverse = async () => {
    const reason = window.prompt('Причина сторнирования (необязательно):') ?? '';
    if (reason === null) return;
    try {
      await reverse.mutateAsync({ id: payment.id, body: { reason } });
      onClose();
    } catch (e) {
      alert('Не удалось сторнировать: ' + (e instanceof Error ? e.message : ''));
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Отменить этот платёж? (только для черновика/подтверждённого)')) return;
    try {
      await cancel.mutateAsync({ id: payment.id, body: { reason: '' } });
      onClose();
    } catch (e) {
      alert('Не удалось отменить: ' + (e instanceof Error ? e.message : ''));
    }
  };

  const canReverse = payment.status === 'posted';
  const canCancel = payment.status === 'draft' || payment.status === 'confirmed';

  const allocations = payment.allocations ?? [];

  return (
    <DetailDrawer
      title={'Платёж · ' + payment.doc_number}
      subtitle={
        payment.date +
        ' · ' +
        KIND_LABEL[payment.kind] +
        ' · ' +
        (payment.direction === 'in' ? 'Приход' : 'Расход')
      }
      tabs={[
        { key: 'overview', label: 'Обзор' },
        { key: 'allocations', label: 'Аллокации', count: allocations.length },
      ]}
      activeTab={tab}
      onTab={(k) => setTab(k as typeof tab)}
      onClose={onClose}
      actions={
        <>
          {canCancel && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleCancel}
              disabled={cancel.isPending}
            >
              Отменить
            </button>
          )}
          {canReverse && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleReverse}
              disabled={reverse.isPending}
              style={{ color: 'var(--danger)' }}
            >
              Сторно
            </button>
          )}
        </>
      }
    >
      {tab === 'overview' && (
        <>
          <KV
            items={[
              { k: 'Документ', v: payment.doc_number, mono: true },
              { k: 'Дата', v: payment.date, mono: true },
              {
                k: 'Статус',
                v: <Badge tone={STATUS_TONE[payment.status]}>{STATUS_LABEL[payment.status]}</Badge>,
              },
              {
                k: 'Направление',
                v: payment.direction === 'in'
                  ? <span style={{ color: 'var(--success)' }}>Приход (IN)</span>
                  : <span style={{ color: 'var(--danger)' }}>Расход (OUT)</span>,
              },
              { k: 'Тип операции', v: KIND_LABEL[payment.kind] },
              { k: 'Канал', v: payment.channel },
              { k: 'Сумма', v: fmtUzs(payment.amount_uzs), mono: true },
              {
                k: 'Касса/банк',
                v: payment.cash_subaccount_code
                  ? `${payment.cash_subaccount_code} · ${payment.cash_subaccount_name ?? ''}`
                  : '—',
                mono: true,
              },
              ...(payment.contra_subaccount_code
                ? [{
                    k: 'Контр-счёт',
                    v: `${payment.contra_subaccount_code} · ${payment.contra_subaccount_name ?? ''}`,
                    mono: true,
                  }]
                : []),
              ...(payment.expense_article_code
                ? [{
                    k: 'Статья',
                    v: `${payment.expense_article_code} · ${payment.expense_article_name ?? ''}`,
                    mono: true,
                  }]
                : []),
              ...(payment.counterparty_name
                ? [{ k: 'Контрагент', v: payment.counterparty_name }]
                : []),
              ...(payment.module_code
                ? [{ k: 'Модуль', v: payment.module_code, mono: true }]
                : []),
              ...(payment.currency_code && payment.currency_code !== 'UZS'
                ? [
                    { k: 'Валюта', v: payment.currency_code, mono: true },
                    { k: 'Сумма в валюте', v: payment.amount_foreign ?? '—', mono: true },
                    { k: 'Курс', v: payment.exchange_rate ?? '—', mono: true },
                  ]
                : []),
              ...(payment.posted_at
                ? [{ k: 'Проведён', v: new Date(payment.posted_at).toLocaleString('ru-RU') }]
                : []),
              ...(payment.notes ? [{ k: 'Примечание', v: payment.notes }] : []),
            ]}
          />

          {payment.journal_entry && (
            <Panel title="Связанная проводка">
              <div style={{ padding: 12, fontSize: 13 }}>
                <a
                  href={`/ledger?entry=${payment.journal_entry}`}
                  style={{ color: 'var(--brand-orange)' }}
                >
                  Открыть проводку →
                </a>
              </div>
            </Panel>
          )}
        </>
      )}

      {tab === 'allocations' && (
        <Panel
          title={`Разнесение на документы · ${allocations.length}`}
          flush
        >
          <DataTable<PaymentAllocation>
            rows={allocations}
            rowKey={(a) => a.id}
            emptyMessage="Платёж не разнесён ни на один документ. Это нормально для прочих расходов/доходов."
            columns={[
              { key: 'target', label: 'Документ',
                render: (a) => (
                  <span className="mono" style={{ fontSize: 12 }}>
                    {a.target_model ? `${a.target_model} · ` : ''}
                    {a.target_object_id.slice(0, 8)}…
                  </span>
                ) },
              { key: 'amount', label: 'Сумма', align: 'right', mono: true,
                render: (a) => fmtUzs(a.amount_uzs) },
              { key: 'notes', label: 'Примечание',
                cellStyle: { fontSize: 12, color: 'var(--fg-3)' },
                render: (a) => a.notes || '—' },
            ]}
          />
        </Panel>
      )}
    </DetailDrawer>
  );
}
