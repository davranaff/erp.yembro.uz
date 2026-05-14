'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import {
  useCounterpartyFullSummary,
  useInviteToTg,
} from '@/hooks/useCounterparties';
import { useDeleteCommunicationWithDebtRefresh } from '@/hooks/useSales';
import type { SaleCommunication } from '@/types/auth';

import CommunicationFormModal from '../../sales/CommunicationFormModal';
import NotifyDebtModal from './NotifyDebtModal';

type TabKey = 'info' | 'docs' | 'payments';

const PAY_LABEL: Record<string, string> = {
  unpaid: 'Не оплачен',
  partial: 'Частично',
  paid: 'Оплачен',
  overpaid: 'Переплата',
};

const PAY_TONE: Record<string, 'neutral' | 'success' | 'warn' | 'info'> = {
  unpaid: 'neutral',
  partial: 'warn',
  paid: 'success',
  overpaid: 'info',
};

const ORDER_KIND_LABEL: Record<string, string> = {
  sale: 'Продажа',
  purchase: 'Закуп',
};

const ORDER_STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  confirmed: 'Проведён',
  cancelled: 'Отменён',
};

const PAYMENT_KIND_LABEL: Record<string, string> = {
  counterparty: 'Контрагенту',
  opex: 'Прочий расход',
  income: 'Прочий доход',
  salary: 'Зарплата',
  internal: 'Внутр. перевод',
  opening_balance_prepayment: 'Старт. предоплата',
};

function fmt(uzs: string | number | null | undefined): string {
  if (uzs == null || uzs === '') return '—';
  const n = typeof uzs === 'number' ? uzs : parseFloat(uzs);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

export default function CounterpartyDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  const { data, isLoading, error } = useCounterpartyFullSummary(id);
  const [tab, setTab] = useState<TabKey>('info');
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<SaleCommunication | null>(null);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const deleteComm = useDeleteCommunicationWithDebtRefresh();
  const inviteTg = useInviteToTg();

  if (isLoading) return <div className="page-hdr"><div><h1>Загружаем…</h1></div></div>;
  if (error) return (
    <div style={{ padding: 16, margin: 16, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6 }}>
      Не удалось загрузить: {error.message}
    </div>
  );
  if (!data) return null;

  const cp = data.counterparty;
  const aging = data.aging;
  const credit = data.credit;
  const isBuyer = cp.kind === 'buyer';
  const debt = parseFloat(credit.current_debt_uzs || '0');

  return (
    <>
      <div className="page-hdr">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => router.push('/counterparties')}>
              <Icon name="chevron-left" size={12} /> К списку
            </button>
          </div>
          <h1>
            {cp.name}{' '}
            <span className="mono" style={{ fontSize: 16, color: 'var(--fg-3)' }}>· {cp.code}</span>
          </h1>
          <div className="sub" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Badge tone={isBuyer ? 'info' : 'neutral'}>
              {cp.kind === 'buyer' ? 'Покупатель' : cp.kind === 'supplier' ? 'Поставщик' : 'Прочее'}
            </Badge>
            {!cp.is_active && <Badge tone="danger">Заблокирован</Badge>}
            {cp.inn && <span className="mono">ИНН {cp.inn}</span>}
            {cp.phone && <span>· {cp.phone}</span>}
          </div>
        </div>
        <div className="actions" style={{ display: 'flex', gap: 6 }}>
          {isBuyer && debt > 0 && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setNotifyOpen(true)}
              title="Отправить SMS/Telegram-напоминание о долге"
            >
              <Icon name="download" size={12} /> Уведомить о долге
            </button>
          )}
          {cp.phone && (
            <button
              className="btn btn-secondary btn-sm"
              disabled={inviteTg.isPending}
              onClick={async () => {
                const res = await inviteTg.mutateAsync(id!);
                alert(
                  (res.ok ? '✓ ' : '✗ ') + res.detail
                  + (res.ok
                    ? '\n\nКогда контрагент откроет ссылку и нажмёт Старт, '
                      + 'дальнейшие уведомления будут уходить в Telegram.'
                    : ''),
                );
              }}
              title="Послать SMS с ссылкой на Telegram-бот (узб. латиница)"
            >
              <Icon name="users" size={12} /> Пригласить в TG
            </button>
          )}
        </div>
      </div>

      {/* Один большой блок: Долг */}
      <div style={{
        marginTop: 4,
        padding: '20px 24px',
        borderRadius: 8,
        background: debt > 0
          ? 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
          : debt < 0
            ? 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)'
            : 'linear-gradient(135deg, #e5e7eb 0%, #d1d5db 100%)',
        border: '1px solid',
        borderColor: debt > 0 ? '#f59e0b' : debt < 0 ? '#10b981' : '#9ca3af',
      }}>
        <div style={{ fontSize: 12, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          {isBuyer
            ? (debt > 0 ? 'Клиент должен нам' : debt < 0 ? 'Мы должны клиенту (предоплата)' : 'Расчётов нет')
            : (debt > 0 ? 'Мы должны поставщику' : debt < 0 ? 'Поставщик должен нам (предоплата)' : 'Расчётов нет')}
        </div>
        <div style={{
          fontSize: 36, fontWeight: 700, fontFamily: 'var(--mono, monospace)',
          color: debt > 0 ? '#92400e' : debt < 0 ? '#065f46' : '#374151',
          marginTop: 4,
        }}>
          {fmt(Math.abs(debt))} <span style={{ fontSize: 18, fontWeight: 500 }}>сум</span>
        </div>
        {aging && aging.has_overdue && (
          <div style={{ fontSize: 13, color: '#dc2626', marginTop: 8, fontWeight: 500 }}>
            ⚠ Просрочка: {aging.oldest_overdue_days} дн · {aging.orders_count} счетов
          </div>
        )}
      </div>

      {!credit.ok && isBuyer && (
        <div style={{
          marginTop: 12, padding: 10, borderRadius: 6,
          background: '#fef2f2', border: '1px solid var(--danger)',
          fontSize: 12, color: 'var(--danger)',
        }}>
          ⚠ Новые продажи блокируются: {credit.reasons.join('; ')}
        </div>
      )}

      <div style={{ marginTop: 14, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'info', label: 'Инфо' },
            { value: 'docs', label: `Документы (${data.all_orders_count})` },
            { value: 'payments', label: `Платежи (${data.all_payments_count})` },
          ]}
          value={tab}
          onChange={(v) => setTab(v as TabKey)}
        />
      </div>

      {tab === 'info' && (
        <InfoTab
          cp={cp}
          aging={aging}
          isBuyer={isBuyer}
          openOrders={data.open_orders}
          openOrdersCount={data.open_orders_count}
          communications={data.communications}
          communicationsCount={data.communications_count}
          monthly={data.monthly_turnover}
          prepayments={data.prepayments}
          prepaymentsTotalFreeUzs={data.prepayments_total_free_uzs}
          customerId={id ?? null}
          onAddComm={() => setAdding(true)}
          onEditComm={(c) => setEditing(c)}
          onDeleteComm={(commId) => {
            if (confirm('Удалить касание?')) {
              deleteComm.mutate({ id: commId, customerId: id });
            }
          }}
          deletingComm={deleteComm.isPending}
        />
      )}
      {tab === 'docs' && <DocsTab rows={data.all_orders} />}
      {tab === 'payments' && <PaymentsTab rows={data.all_payments} />}

      {adding && id && (
        <CommunicationFormModal
          mode="add"
          customerId={id}
          customerName={cp.name}
          customerOpenOrders={data.open_orders.map((o) => ({
            id: o.id, doc_number: o.doc_number, outstanding_uzs: o.outstanding_uzs,
          }))}
          onClose={() => setAdding(false)}
        />
      )}
      {editing && (
        <CommunicationFormModal
          mode="edit"
          communication={editing}
          customerId={id}
          onClose={() => setEditing(null)}
        />
      )}
      {notifyOpen && id && (
        <NotifyDebtModal
          counterpartyId={id}
          counterpartyName={cp.name}
          hasPhone={Boolean(cp.phone)}
          onClose={() => setNotifyOpen(false)}
        />
      )}
    </>
  );
}

// ─── Инфо: реквизиты + открытые счета + касания + обороты ────────────────

function InfoTab({
  cp, aging, isBuyer, openOrders, openOrdersCount, communications, communicationsCount,
  monthly, prepayments, prepaymentsTotalFreeUzs,
  onAddComm, onEditComm, onDeleteComm, deletingComm,
}: {
  cp: import('@/hooks/useCounterparties').CounterpartyDebtSummary['counterparty'];
  aging: import('@/hooks/useCounterparties').CounterpartyDebtSummary['aging'];
  isBuyer: boolean;
  openOrders: import('@/hooks/useCounterparties').CounterpartyDebtSummary['open_orders'];
  openOrdersCount: number;
  communications: import('@/hooks/useCounterparties').CounterpartyDebtSummary['communications'];
  communicationsCount: number;
  monthly: import('@/hooks/useCounterparties').CounterpartyFullSummary['monthly_turnover'];
  prepayments: import('@/hooks/useCounterparties').CounterpartyDebtSummary['prepayments'];
  prepaymentsTotalFreeUzs: string;
  customerId: string | null;
  onAddComm: () => void;
  onEditComm: (c: SaleCommunication) => void;
  onDeleteComm: (id: string) => void;
  deletingComm: boolean;
}) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  // totalInvoiced — полный объём отгрузок (начисление), totalSales — реально
  // оплаченная клиентом часть (актуальные деньги). Долг между ними не двоится.
  const totalInvoiced = monthly.reduce((s, r) => s + parseFloat(r.sales_invoiced_uzs || '0'), 0);
  const totalSales = monthly.reduce((s, r) => s + parseFloat(r.sales_uzs || '0'), 0);
  const totalPurchases = monthly.reduce((s, r) => s + parseFloat(r.purchases_uzs || '0'), 0);

  return (
    <>
      {/* Реквизиты */}
      <Panel title="Реквизиты">
        <div style={{ padding: 12, display: 'grid', gridTemplateColumns: '160px 1fr', rowGap: 10, columnGap: 16 }}>
          <div className="sub">Код</div>
          <div className="mono">{cp.code}</div>
          <div className="sub">Тип</div>
          <div>{cp.kind === 'buyer' ? 'Покупатель' : cp.kind === 'supplier' ? 'Поставщик' : 'Прочее'}</div>
          {cp.specialization && (<><div className="sub">Специализация</div><div>{cp.specialization}</div></>)}
          {cp.inn && (<><div className="sub">ИНН</div><div className="mono">{cp.inn}</div></>)}
          {cp.phone && (<><div className="sub">Телефон</div><div className="mono">{cp.phone}</div></>)}
          {cp.email && (<><div className="sub">Email</div><div className="mono">{cp.email}</div></>)}
          {cp.address && (<><div className="sub">Адрес</div><div>{cp.address}</div></>)}
          {isBuyer && cp.credit_limit_uzs && (
            <>
              <div className="sub">Кредитный лимит</div>
              <div className="mono">{fmt(cp.credit_limit_uzs)} сум</div>
            </>
          )}
          {cp.notes && (
            <>
              <div className="sub">Примечание</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{cp.notes}</div>
            </>
          )}
        </div>
      </Panel>

      {/* Открытые счета — только если есть */}
      {openOrdersCount > 0 && (
        <>
          <div style={{ height: 12 }} />
          <Panel title={`Открытые счета (${openOrdersCount})`}>
            <DataTable
              rows={openOrders}
              rowKey={(o) => o.id}
              columns={[
                { key: 'doc', label: 'Документ', mono: true,
                  render: (o) => (
                    <Link href={`/sales/${o.id}`} style={{ color: 'var(--brand-orange)', textDecoration: 'none' }}>
                      {o.doc_number}
                    </Link>
                  ) },
                { key: 'date', label: 'Дата', mono: true, render: (o) => o.date },
                { key: 'due', label: 'Срок',
                  render: (o) => {
                    if (!o.due_date) return <span style={{ color: 'var(--fg-3)' }}>—</span>;
                    const due = new Date(o.due_date);
                    const days = Math.round((due.getTime() - today.getTime()) / 86400000);
                    return (
                      <span>
                        <span className="mono">{o.due_date}</span>
                        {days < 0 && <Badge tone="danger" style={{ marginLeft: 6 }}>просрочено {Math.abs(days)} дн</Badge>}
                      </span>
                    );
                  } },
                { key: 'out', label: 'Долг', align: 'right', mono: true,
                  cellStyle: { fontWeight: 600, color: 'var(--brand-orange)' },
                  render: (o) => fmt(o.outstanding_uzs) },
                { key: 'pay', label: '',
                  render: (o) => (
                    <Badge tone={PAY_TONE[o.payment_status] ?? 'neutral'}>
                      {PAY_LABEL[o.payment_status] ?? o.payment_status}
                    </Badge>
                  ) },
              ]}
            />
          </Panel>
        </>
      )}

      {/* Свободный кредит */}
      {prepayments && prepayments.length > 0 && (
        <>
          <div style={{ height: 12 }} />
          <Panel title={`Свободный кредит (предоплата): ${fmt(prepaymentsTotalFreeUzs)} сум`}>
            <DataTable
              rows={prepayments}
              rowKey={(p) => p.id}
              columns={[
                { key: 'doc', label: 'Документ', mono: true, render: (p) => p.doc_number },
                { key: 'date', label: 'Дата', mono: true, render: (p) => p.date },
                { key: 'amt', label: 'Сумма', mono: true, align: 'right', render: (p) => fmt(p.amount_uzs) },
                { key: 'free', label: 'Свободно', mono: true, align: 'right',
                  cellStyle: { fontWeight: 600, color: 'var(--success)' },
                  render: (p) => fmt(p.free_uzs) },
              ]}
            />
          </Panel>
        </>
      )}

      {/* Обороты */}
      {(totalInvoiced > 0 || totalPurchases > 0) && (
        <>
          <div style={{ height: 12 }} />
          <Panel title="Обороты за 12 месяцев">
            <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {isBuyer ? (
                <>
                  <div>
                    <div className="sub">Куплено всего</div>
                    <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>
                      {fmt(totalInvoiced)} <span style={{ fontSize: 13, fontWeight: 400 }}>сум</span>
                    </div>
                    <div className="sub" style={{ marginTop: 2 }}>
                      оплачено: {fmt(totalSales)} сум
                    </div>
                  </div>
                  <div>
                    <div className="sub">Заплатил</div>
                    <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>
                      {fmt(monthly.reduce((s, r) => s + parseFloat(r.payments_in_uzs || '0'), 0))}
                      <span style={{ fontSize: 13, fontWeight: 400 }}> сум</span>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <div className="sub">Куплено у поставщика</div>
                    <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>
                      {fmt(totalPurchases)} <span style={{ fontSize: 13, fontWeight: 400 }}>сум</span>
                    </div>
                  </div>
                  <div>
                    <div className="sub">Выплачено</div>
                    <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>
                      {fmt(monthly.reduce((s, r) => s + parseFloat(r.payments_out_uzs || '0'), 0))}
                      <span style={{ fontSize: 13, fontWeight: 400 }}> сум</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </Panel>
        </>
      )}

      {/* Касания */}
      {(communicationsCount > 0 || openOrders.length > 0) && (
        <>
          <div style={{ height: 12 }} />
          <Panel
            title={`Касания (${communicationsCount})`}
            tools={
              openOrders.length > 0 ? (
                <button className="btn btn-primary btn-sm" onClick={onAddComm}>
                  <Icon name="plus" size={12} /> Новое касание
                </button>
              ) : null
            }
          >
            {communicationsCount === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', fontSize: 12, color: 'var(--fg-3)' }}>
                Касаний не было.
              </div>
            ) : (
              <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {communications.slice(0, 10).map((c) => (
                  <div key={c.id} style={{
                    padding: 10, borderRadius: 6,
                    border: '1px solid var(--border)', background: 'var(--bg-card)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                        {new Date(c.contacted_at).toLocaleString('ru-RU', {
                          day: '2-digit', month: '2-digit', year: '2-digit',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </span>
                      <Badge tone="info">{c.method_display}</Badge>
                      <Badge tone={
                        c.outcome === 'promised' ? 'success' :
                        c.outcome === 'asked_defer' ? 'warn' :
                        c.outcome === 'refused' || c.outcome === 'wrong_number' ? 'danger' : 'neutral'
                      }>{c.outcome_display}</Badge>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                        по счёту {c.order_doc}
                      </span>
                      <div style={{ flex: 1 }} />
                      <button
                        className="btn btn-ghost btn-sm" style={{ padding: '2px 8px' }}
                        title="Редактировать"
                        onClick={() => onEditComm({ ...c, order: c.order_id } as unknown as SaleCommunication)}
                      >✎</button>
                      <button
                        className="btn btn-ghost btn-sm" style={{ padding: '2px 8px', color: 'var(--danger)' }}
                        title="Удалить" disabled={deletingComm}
                        onClick={() => onDeleteComm(c.id)}
                      >✕</button>
                    </div>
                    <div style={{ fontSize: 13, marginBottom: 4 }}>«{c.customer_response}»</div>
                    {c.internal_note && (
                      <div style={{
                        fontSize: 11, color: 'var(--fg-2)', marginBottom: 6,
                        padding: '4px 8px', background: 'var(--bg-soft)',
                        borderRadius: 4, fontStyle: 'italic',
                      }}>📝 {c.internal_note}</div>
                    )}
                    <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--fg-3)', flexWrap: 'wrap' }}>
                      {c.contacted_by_name && <span>{c.contacted_by_name}</span>}
                      {c.promised_pay_date && <span style={{ color: 'var(--brand-orange)' }}>✓ обещал к {c.promised_pay_date}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
}

// ─── Документы ────────────────────────────────────────────────────────────

function DocsTab({
  rows,
}: { rows: import('@/hooks/useCounterparties').CounterpartyFullSummary['all_orders'] }) {
  return (
    <Panel flush>
      <DataTable
        rows={rows}
        rowKey={(o) => o.id}
        emptyMessage="Документов нет."
        columns={[
          { key: 'kind', label: 'Тип',
            render: (o) => (
              <Badge tone={o.kind === 'sale' ? 'info' : 'neutral'}>
                {ORDER_KIND_LABEL[o.kind] ?? o.kind}
              </Badge>
            ) },
          { key: 'doc', label: 'Документ', mono: true,
            render: (o) => (
              <Link
                href={o.kind === 'sale' ? `/sales/${o.id}` : `/purchases/${o.id}`}
                style={{ color: 'var(--brand-orange)', textDecoration: 'none', fontWeight: 500 }}
              >
                {o.doc_number}
              </Link>
            ) },
          { key: 'date', label: 'Дата', mono: true, render: (o) => o.date },
          { key: 'status', label: 'Статус',
            render: (o) => (
              <Badge tone={o.status === 'confirmed' ? 'success' : o.status === 'cancelled' ? 'danger' : 'neutral'}>
                {ORDER_STATUS_LABEL[o.status] ?? o.status}
              </Badge>
            ) },
          { key: 'amount', label: 'Сумма', mono: true, align: 'right',
            render: (o) => fmt(o.amount_uzs) },
          { key: 'paid', label: 'Оплачено', mono: true, align: 'right',
            cellStyle: { color: 'var(--fg-3)' },
            render: (o) => fmt(o.paid_amount_uzs) },
          { key: 'out', label: 'Долг', mono: true, align: 'right',
            cellStyle: { fontWeight: 600 },
            render: (o) => {
              const v = parseFloat(o.outstanding_uzs);
              if (!Number.isFinite(v) || v === 0) return <span style={{ color: 'var(--fg-3)' }}>—</span>;
              return <span style={{ color: 'var(--brand-orange)' }}>{fmt(v)}</span>;
            } },
        ]}
      />
    </Panel>
  );
}

// ─── Платежи ──────────────────────────────────────────────────────────────

function PaymentsTab({
  rows,
}: { rows: import('@/hooks/useCounterparties').CounterpartyFullSummary['all_payments'] }) {
  return (
    <Panel flush>
      <DataTable
        rows={rows}
        rowKey={(p) => p.id}
        emptyMessage="Платежей нет."
        columns={[
          { key: 'doc', label: 'Документ', mono: true, render: (p) => p.doc_number },
          { key: 'date', label: 'Дата', mono: true, render: (p) => p.date },
          { key: 'dir', label: 'Направление',
            render: (p) => p.direction === 'in'
              ? <Badge tone="success">⬇ Поступление</Badge>
              : <Badge tone="warn">⬆ Расход</Badge> },
          { key: 'kind', label: 'Тип',
            render: (p) => <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{PAYMENT_KIND_LABEL[p.kind] ?? p.kind}</span> },
          { key: 'amount', label: 'Сумма', mono: true, align: 'right',
            cellStyle: { fontWeight: 600 },
            render: (p) => fmt(p.amount_uzs) },
          { key: 'status', label: 'Статус',
            render: (p) => (
              <Badge tone={p.status === 'posted' ? 'success' : p.status === 'cancelled' ? 'neutral' : 'warn'}>
                {p.status === 'posted' ? 'Проведён' : p.status === 'cancelled' ? 'Отменён' : p.status}
              </Badge>
            ) },
        ]}
      />
    </Panel>
  );
}
