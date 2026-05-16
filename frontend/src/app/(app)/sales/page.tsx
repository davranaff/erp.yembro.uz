'use client';

import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import SmartSelect from '@/components/ui/SmartSelect';
import TablePagination from '@/components/ui/TablePagination';
import { useCounterparties } from '@/hooks/useCounterparties';
import { useHasLevel } from '@/hooks/usePermissions';
import { salesCrud, useConfirmSale, useReverseSale } from '@/hooks/useSales';
import type { SaleOrder, SalePaymentStatus, SaleStatus } from '@/types/auth';

import RecordPaymentModal from './RecordPaymentModal';
import RemindModal from './RemindModal';
import SaleCommunicationsModal from './SaleCommunicationsModal';
import SaleConfirmGuardModal from './SaleConfirmGuardModal';
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

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function SalesPage() {
  const router = useRouter();
  const [tab, setTab] = useState<'all' | SaleStatus>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SaleOrder | null>(null);
  const [payFor, setPayFor] = useState<SaleOrder | null>(null);
  const [commsFor, setCommsFor] = useState<SaleOrder | null>(null);
  const [remindFor, setRemindFor] = useState<SaleOrder | null>(null);
  const [confirmingFor, setConfirmingFor] = useState<SaleOrder | null>(null);

  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [customerId, setCustomerId] = useState<string>('');
  const [sortField, setSortField] = useState<'date' | 'amount_uzs' | 'doc_number'>('date');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('sales', 'rw');
  // Покупатели для селектора-фильтра. kind=buyer — те же контрагенты,
  // которых модалка продажи показывает при создании.
  const { data: customers } = useCounterparties({ kind: 'buyer' });

  const ordering = `${sortDir === 'desc' ? '-' : ''}${sortField}`;

  const filter = useMemo(() => {
    const f: Record<string, string> = {};
    if (tab !== 'all') f.status = tab;
    if (dateFrom) f.date_after = dateFrom;
    if (dateTo) f.date_before = dateTo;
    if (customerId) f.customer = customerId;
    return f;
  }, [tab, dateFrom, dateTo, customerId]);

  const { data: pageData, isLoading } = salesCrud.useListPaginated(filter, page, pageSize, ordering);
  const orders = pageData?.results ?? [];
  const { data: allOrders } = salesCrud.useList(filter);

  const confirmMutation = useConfirmSale();
  const reverseMutation = useReverseSale();

  const totals = useMemo(() => {
    const list = allOrders ?? [];
    const confirmed = list.filter((o) => o.status === 'confirmed');
    // invoiced — полный объём отгрузок (начисление), revenue — реально
    // оплаченная клиентами часть (актуальные деньги). Долг (receivable)
    // в «Выручку» не попадает, он показан отдельной карточкой.
    const invoiced = confirmed.reduce((s, o) => s + parseFloat(o.amount_uzs || '0'), 0);
    const revenue = confirmed.reduce((s, o) => s + parseFloat(o.paid_amount_uzs || '0'), 0);
    const cost = confirmed.reduce((s, o) => s + parseFloat(o.cost_uzs || '0'), 0);
    const receivable = invoiced - revenue;
    return {
      count: pageData?.count ?? list.length,
      invoiced,
      revenue,
      margin: invoiced - cost, // валовая маржа по отгрузке (accrual)
      receivable,
    };
  }, [allOrders, pageData]);

  // Confirm теперь идёт через модалку с превью кредитного гейта
  // (SaleConfirmGuardModal). window.confirm заменён на нормальный UX.
  const handleConfirm = (o: SaleOrder) => {
    setConfirmingFor(o);
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
        <KpiCard tone="green" iconName="chart" label="Выручка" sub="оплачено" value={fmtUzs(String(totals.revenue))} />
        <KpiCard tone="blue" iconName="bag" label="Отгружено" sub="начислено" value={fmtUzs(String(totals.invoiced))} />
        <KpiCard tone="blue" iconName="book" label="Маржа" sub="по отгрузке" value={fmtUzs(String(totals.margin))} />
        <KpiCard tone="red" iconName="users" label="Должны нам" sub="не оплачено" value={fmtUzs(String(totals.receivable))} />
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'all', label: 'Все' },
            { value: 'draft', label: 'Черновики' },
            { value: 'confirmed', label: 'Проведённые' },
            { value: 'cancelled', label: 'Отменённые' },
          ]}
          value={tab}
          onChange={(v) => { setTab(v as typeof tab); setPage(1); }}
        />
        <span style={{
          fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
          textTransform: 'uppercase', letterSpacing: '.04em', marginLeft: 8,
        }}>
          Период:
        </span>
        <input
          type="date"
          className="input mono"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          style={{ width: 140 }}
        />
        <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>—</span>
        <input
          type="date"
          className="input mono"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          style={{ width: 140 }}
        />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            const t = todayISO();
            setDateFrom(t);
            setDateTo(t);
            setPage(1);
          }}
          title="Только сегодня"
        >
          Сегодня
        </button>
        {(dateFrom || dateTo) && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => { setDateFrom(''); setDateTo(''); setPage(1); }}
            title="Все даты"
          >
            Сбросить
          </button>
        )}

        <span style={{
          fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
          textTransform: 'uppercase', letterSpacing: '.04em', marginLeft: 8,
        }}>
          Клиент:
        </span>
        <div style={{ minWidth: 220 }}>
          <SmartSelect
            value={customerId}
            onChange={(v) => { setCustomerId(v); setPage(1); }}
            options={(customers ?? []).map((c) => ({
              value: c.id,
              label: c.name,
              sublabel: c.code,
            }))}
            placeholder="— все клиенты —"
            searchPlaceholder="Поиск по названию или коду…"
            emptyText="Клиенты не найдены"
          />
        </div>
        {customerId && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => { setCustomerId(''); setPage(1); }}
            title="Снять фильтр по клиенту"
          >
            ✕
          </button>
        )}

        <span style={{
          fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
          textTransform: 'uppercase', letterSpacing: '.04em', marginLeft: 8,
        }}>
          Сортировка:
        </span>
        <select
          className="input"
          value={sortField}
          onChange={(e) => { setSortField(e.target.value as typeof sortField); setPage(1); }}
          style={{ width: 130, fontSize: 13, padding: '3px 8px' }}
        >
          <option value="date">Дата</option>
          <option value="amount_uzs">Сумма</option>
          <option value="doc_number">Документ</option>
        </select>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => { setSortDir((d) => d === 'desc' ? 'asc' : 'desc'); setPage(1); }}
          title={sortDir === 'desc' ? 'По убыванию — нажмите для по возрастанию' : 'По возрастанию — нажмите для по убыванию'}
          style={{ minWidth: 36, fontFamily: 'var(--font-mono)', fontSize: 14 }}
        >
          {sortDir === 'desc' ? '↓' : '↑'}
        </button>
      </div>

      <Panel flush>
        <DataTable<SaleOrder>
          isLoading={isLoading}
          rows={orders}
          rowKey={(o) => o.id}
          onRowClick={(o) => router.push(`/sales/${o.id}`)}
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
                <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                  <Badge tone={PAY_TONE[o.payment_status]}>{PAY_LABEL[o.payment_status]}</Badge>
                  {o.payment_status !== 'paid' && o.due_date && (() => {
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const due = new Date(o.due_date);
                    const days = Math.round((due.getTime() - today.getTime()) / 86400000);
                    if (days < 0) {
                      return (
                        <Badge tone="danger">
                          просрочено {Math.abs(days)} дн
                        </Badge>
                      );
                    }
                    if (days <= 3) {
                      return (
                        <Badge tone="warn">
                          {days === 0 ? 'сегодня срок' : `до срока ${days} дн`}
                        </Badge>
                      );
                    }
                    return null;
                  })()}
                </span>
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
                      label: 'Напомнить в TG…',
                      hidden: !(
                        o.status === 'confirmed' &&
                        (o.payment_status === 'unpaid' || o.payment_status === 'partial')
                      ),
                      onClick: () => setRemindFor(o),
                    },
                    {
                      label: 'Касания клиента',
                      hidden: o.status !== 'confirmed',
                      onClick: () => setCommsFor(o),
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
        {pageData && (
          <TablePagination
            page={page}
            pageSize={pageSize}
            count={pageData.count}
            hasPrev={Boolean(pageData.previous)}
            hasNext={Boolean(pageData.next)}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        )}
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
      {commsFor && (
        <SaleCommunicationsModal
          order={commsFor}
          onClose={() => setCommsFor(null)}
        />
      )}
      {remindFor && (
        <RemindModal
          order={remindFor}
          onClose={() => setRemindFor(null)}
        />
      )}
      {confirmingFor && (
        <SaleConfirmGuardModal
          order={confirmingFor}
          onClose={() => setConfirmingFor(null)}
        />
      )}
    </>
  );
}
