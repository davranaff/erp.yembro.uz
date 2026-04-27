'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useHasLevel } from '@/hooks/usePermissions';
import { useSendDebtReminder } from '@/hooks/useTgBot';
import { salesCrud, useConfirmSale, useReverseSale } from '@/hooks/useSales';
import type { SaleOrder, SalePaymentStatus, SaleStatus } from '@/types/auth';

import RecordPaymentModal from './RecordPaymentModal';
import SaleOrderModal from './SaleOrderModal';

const STATUS_LABEL: Record<SaleStatus, string> = {
  draft: 'Черновик',
  confirmed: 'Проведён',
  cancelled: 'Отменён',
};

const STATUS_TONE: Record<SaleStatus, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  draft: 'neutral',
  confirmed: 'success',
  cancelled: 'danger',
};

const PAY_LABEL: Record<SalePaymentStatus, string> = {
  unpaid: 'Не оплачен',
  partial: 'Частично',
  paid: 'Оплачен',
  overpaid: 'Переплата',
};

const PAY_TONE: Record<SalePaymentStatus, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  unpaid: 'neutral',
  partial: 'warn',
  paid: 'success',
  overpaid: 'info',
};

function fmtUzs(v: string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

export default function SalesPage() {
  const [tab, setTab] = useState<'all' | SaleStatus>('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SaleOrder | null>(null);
  const [payFor, setPayFor] = useState<SaleOrder | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('sales', 'rw');

  const { data: orders, isLoading } = salesCrud.useList(
    tab === 'all' ? {} : { status: tab },
  );

  const confirmMutation = useConfirmSale();
  const reverseMutation = useReverseSale();
  const sendReminder = useSendDebtReminder();

  const totals = useMemo(() => {
    const list = orders ?? [];
    const confirmed = list.filter((o) => o.status === 'confirmed');
    const revenue = confirmed.reduce((s, o) => s + parseFloat(o.amount_uzs || '0'), 0);
    const cost = confirmed.reduce((s, o) => s + parseFloat(o.cost_uzs || '0'), 0);
    const receivable = confirmed.reduce(
      (s, o) => s + (parseFloat(o.amount_uzs || '0') - parseFloat(o.paid_amount_uzs || '0')),
      0,
    );
    return {
      count: list.length,
      revenue,
      margin: revenue - cost,
      receivable,
    };
  }, [orders]);

  const handleConfirm = (o: SaleOrder) => {
    if (!window.confirm('Провести продажу ' + o.doc_number + '? Списание со склада и проводки в ГК.')) return;
    confirmMutation.mutate({ id: o.id }, {
      onError: (err) => alert('Не удалось провести: ' + err.message),
    });
  };

  const handleReverse = (o: SaleOrder) => {
    const reason = window.prompt('Причина сторно (необязательно):');
    if (reason === null) return;
    reverseMutation.mutate({ id: o.id, body: { reason } }, {
      onError: (err) => alert('Не удалось сторнировать: ' + err.message),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Продажи</h1>
          <div className="sub">Отгрузки клиентам · выручка и себестоимость · оплаты</div>
        </div>
        <div className="actions">
          {canEdit && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => { setEditing(null); setModalOpen(true); }}
            >
              <Icon name="plus" size={14} /> Новая продажа
            </button>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard tone="orange" iconName="bag" label="Всего" sub="документов" value={String(totals.count)} />
        <KpiCard tone="green" iconName="chart" label="Выручка" sub="проведено" value={fmtUzs(String(totals.revenue))} />
        <KpiCard tone="blue" iconName="book" label="Маржа" sub="revenue − cost" value={fmtUzs(String(totals.margin))} />
        <KpiCard tone="red" iconName="users" label="Должны нам" sub="не оплачено" value={fmtUzs(String(totals.receivable))} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'all', label: 'Все' },
            { value: 'draft', label: 'Черновики' },
            { value: 'confirmed', label: 'Проведённые' },
            { value: 'cancelled', label: 'Отменённые' },
          ]}
          value={tab}
          onChange={(v) => setTab(v as typeof tab)}
        />
      </div>

      <Panel flush>
        <DataTable<SaleOrder>
          isLoading={isLoading}
          rows={orders}
          rowKey={(o) => o.id}
          emptyMessage="Продаж нет. Нажмите «Новая продажа» чтобы отгрузить клиенту."
          columns={[
            { key: 'doc_number', label: 'Документ', mono: true,
              render: (o) => o.doc_number || '—' },
            { key: 'date', label: 'Дата', render: (o) => o.date },
            { key: 'module', label: 'Модуль',
              render: (o) => o.module_code ?? '—' },
            { key: 'customer', label: 'Клиент',
              render: (o) => o.customer_name ?? '—' },
            { key: 'warehouse', label: 'Склад', mono: true,
              render: (o) => o.warehouse_code ?? '—' },
            {
              key: 'amount', label: 'Сумма', align: 'right', mono: true,
              render: (o) => {
                if (o.status === 'draft') {
                  const draft = o.draft_total_uzs ?? '0';
                  return (
                    <>
                      <span style={{ color: 'var(--fg-2)' }}>{fmtUzs(draft)}</span>
                      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                        предварительно
                      </div>
                    </>
                  );
                }
                return (
                  <>
                    {fmtUzs(o.amount_uzs)}
                    {o.currency_code && o.currency_code !== 'UZS' && o.amount_foreign && (
                      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                        {parseFloat(o.amount_foreign).toLocaleString('ru-RU')} {o.currency_code}
                        {o.exchange_rate && ` @ ${parseFloat(o.exchange_rate).toLocaleString('ru-RU')}`}
                      </div>
                    )}
                  </>
                );
              },
            },
            {
              key: 'margin', label: 'Маржа', align: 'right', mono: true,
              render: (o) => {
                if (o.status !== 'confirmed') return '—';
                const m = parseFloat(o.amount_uzs || '0') - parseFloat(o.cost_uzs || '0');
                return (
                  <span style={{ color: m > 0 ? 'var(--success)' : 'var(--fg-2)' }}>
                    {fmtUzs(String(m))}
                  </span>
                );
              },
            },
            {
              key: 'status', label: 'Статус',
              render: (o) => <Badge tone={STATUS_TONE[o.status]}>{STATUS_LABEL[o.status]}</Badge>,
            },
            {
              key: 'pay', label: 'Оплата',
              render: (o) => o.status === 'confirmed' ? (
                <Badge tone={PAY_TONE[o.payment_status]}>{PAY_LABEL[o.payment_status]}</Badge>
              ) : '—',
            },
            {
              key: 'actions', label: '', align: 'right', width: 60,
              render: (o) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'Править',
                      hidden: o.status !== 'draft',
                      onClick: () => { setEditing(o); setModalOpen(true); },
                    },
                    {
                      label: 'Провести',
                      hidden: o.status !== 'draft',
                      disabled: confirmMutation.isPending,
                      onClick: () => handleConfirm(o),
                    },
                    {
                      label: 'Принять оплату',
                      hidden: !(o.status === 'confirmed' && o.payment_status !== 'paid'),
                      onClick: () => setPayFor(o),
                    },
                    {
                      label: 'Напомнить в TG',
                      hidden: !(
                        o.status === 'confirmed' &&
                        (o.payment_status === 'unpaid' || o.payment_status === 'partial')
                      ),
                      disabled: sendReminder.isPending,
                      onClick: () => sendReminder.mutate(
                        { sale_order_id: o.id },
                        { onSuccess: () => alert('Напоминание отправлено в Telegram'), onError: (e) => alert('Ошибка: ' + e.message) }
                      ),
                    },
                    {
                      label: 'Сторно',
                      danger: true,
                      hidden: !(o.status === 'confirmed' && parseFloat(o.paid_amount_uzs || '0') === 0),
                      disabled: reverseMutation.isPending,
                      onClick: () => handleReverse(o),
                    },
                  ]}
                />
              ) : null,
            },
          ]}
        />
      </Panel>

      {modalOpen && (
        <SaleOrderModal
          initial={editing}
          onClose={() => { setModalOpen(false); setEditing(null); }}
        />
      )}
      {payFor && (
        <RecordPaymentModal
          order={payFor}
          onClose={() => setPayFor(null)}
        />
      )}
    </>
  );
}
