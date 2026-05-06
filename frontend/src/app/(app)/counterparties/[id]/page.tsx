'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useCounterpartyDebtSummary } from '@/hooks/useCounterparties';
import { useDeleteCommunicationWithDebtRefresh } from '@/hooks/useSales';
import type { SaleCommunication } from '@/types/auth';

import CommunicationFormModal from '../../sales/CommunicationFormModal';

function fmt(uzs: string | null | undefined): string {
  if (uzs == null || uzs === '') return '—';
  const n = parseFloat(uzs);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function fmtFull(uzs: string | null | undefined): string {
  return fmt(uzs) + (fmt(uzs) === '—' ? '' : ' сум');
}

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

/**
 * Карточка контрагента (debt card).
 *
 * Полный обзор по клиенту: реквизиты, кредитная политика, дебиторка с aging,
 * открытые счета, история всех касаний. Цель — открыл одну страницу,
 * понял что делать.
 */
export default function CounterpartyDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  const { data, isLoading, error } = useCounterpartyDebtSummary(id);
  const [tab, setTab] = useState<'orders' | 'comms'>('orders');
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<SaleCommunication | null>(null);
  const deleteComm = useDeleteCommunicationWithDebtRefresh();

  if (isLoading) {
    return (
      <div className="page-hdr">
        <div><h1>Загружаем…</h1></div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: 16, margin: 16, background: '#fef2f2',
        color: 'var(--danger)', borderRadius: 6,
      }}>
        Не удалось загрузить карточку: {error.message}
      </div>
    );
  }

  if (!data) return null;

  const cp = data.counterparty;
  const aging = data.aging;
  const credit = data.credit;
  const isBuyer = cp.kind === 'buyer';
  const utilization = data.credit_utilization_pct;

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return (
    <>
      <div className="page-hdr">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => router.push('/counterparties')}
            >
              <Icon name="chevron-left" size={12} /> К списку
            </button>
          </div>
          <h1>
            {cp.name}{' '}
            <span className="mono" style={{ fontSize: 16, color: 'var(--fg-3)' }}>
              · {cp.code}
            </span>
          </h1>
          <div className="sub" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Badge tone={isBuyer ? 'info' : 'neutral'}>
              {cp.kind === 'buyer' ? 'Покупатель' : cp.kind === 'supplier' ? 'Поставщик' : 'Прочее'}
            </Badge>
            {!cp.is_active && <Badge tone="danger">Заблокирован</Badge>}
            {cp.inn && <span className="mono">ИНН {cp.inn}</span>}
            {cp.phone && <span>· {cp.phone}</span>}
            {cp.email && <span>· {cp.email}</span>}
          </div>
        </div>
      </div>

      {/* ── KPI ─────────────────────────────────────────────── */}
      {isBuyer && (
        <>
          <div className="kpi-row">
            <KpiCard
              tone={aging?.has_overdue ? 'red' : aging?.total ? 'orange' : 'green'}
              iconName="bag"
              label="Текущий долг"
              sub={aging ? `${aging.orders_count} счетов` : 'нет долгов'}
              value={fmtFull(credit.current_debt_uzs)}
            />
            <KpiCard
              tone={cp.credit_limit_uzs ? 'blue' : 'orange'}
              iconName="chart"
              label="Кредитный лимит"
              sub={cp.credit_limit_uzs ? 'из политики' : 'не задан'}
              value={cp.credit_limit_uzs ? fmtFull(cp.credit_limit_uzs) : '—'}
            />
            <KpiCard
              tone={
                utilization == null ? 'blue' :
                utilization >= 100 ? 'red' :
                utilization >= 80 ? 'orange' : 'green'
              }
              iconName="chart"
              label="Утилизация лимита"
              sub={utilization != null ? '% занятого лимита' : '—'}
              value={utilization != null ? `${utilization}%` : '—'}
            />
            <KpiCard
              tone={
                aging && aging.oldest_overdue_days > 90 ? 'red' :
                aging && aging.oldest_overdue_days > 30 ? 'orange' :
                aging && aging.oldest_overdue_days > 0 ? 'orange' : 'green'
              }
              iconName="bag"
              label="Макс. просрочка"
              sub={cp.max_overdue_days != null ? `лимит ${cp.max_overdue_days} дн` : 'без лимита'}
              value={aging ? `${aging.oldest_overdue_days} дн` : '—'}
            />
          </div>

          {/* ── Кредитный гейт — состояние ─────────────────── */}
          {!credit.ok && (
            <div style={{
              marginTop: 12, padding: 12, borderRadius: 6,
              background: '#fef2f2', border: '1px solid var(--danger)',
              fontSize: 12, color: 'var(--danger)',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                ⚠ Новые продажи этому клиенту автоматически блокируются:
              </div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {credit.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}

          {/* ── Aging-разбивка ──────────────────────────────── */}
          {aging && (
            <Panel
              title="Старение долга"
              style={{ marginTop: 14 }}
            >
              <div style={{ padding: 12 }}>
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
                  gap: 8, fontSize: 12,
                }}>
                  <AgingBucket label="Текущие" value={aging.current} tone="info" desc="не просрочено" />
                  <AgingBucket label="0-30 дн" value={aging.b_0_30} tone="warn" desc="до месяца" />
                  <AgingBucket label="31-60 дн" value={aging.b_31_60} tone="warn" desc="1-2 мес" />
                  <AgingBucket label="61-90 дн" value={aging.b_61_90} tone="danger" desc="2-3 мес" />
                  <AgingBucket label="90+ дн" value={aging.b_90_plus} tone="danger" desc="критично" />
                </div>
              </div>
            </Panel>
          )}

          {/* ── Стартовые предоплаты (free credit) ──────────── */}
          {data.prepayments && data.prepayments.length > 0 && (
            <Panel
              title={`Свободный кредит: ${fmtFull(data.prepayments_total_free_uzs)}`}
              style={{ marginTop: 14 }}
            >
              <div style={{ padding: 12 }}>
                <div style={{
                  fontSize: 12, color: 'var(--fg-3)', marginBottom: 10,
                }}>
                  Стартовые предоплаты, перенесённые при миграции. Кассир может
                  применить часть к новой продаже/закупу через кнопку
                  «Применить предоплату» в карточке документа.
                </div>
                <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: 'var(--fg-3)', fontSize: 11, textAlign: 'left' }}>
                      <th style={{ padding: '6px 12px' }}>Документ</th>
                      <th style={{ padding: '6px 12px' }}>Дата</th>
                      <th style={{ padding: '6px 12px' }}>Направление</th>
                      <th style={{ padding: '6px 12px', textAlign: 'right' }}>Сумма</th>
                      <th style={{ padding: '6px 12px', textAlign: 'right' }}>Использовано</th>
                      <th style={{ padding: '6px 12px', textAlign: 'right' }}>Свободно</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.prepayments.map((p) => (
                      <tr key={p.id} style={{ borderTop: '1px solid var(--border)' }}>
                        <td className="mono" style={{ padding: '8px 12px', fontWeight: 500 }}>
                          {p.doc_number}
                        </td>
                        <td className="mono" style={{ padding: '8px 12px', fontSize: 12 }}>
                          {p.date}
                        </td>
                        <td style={{ padding: '8px 12px', fontSize: 12 }}>
                          {p.direction === 'in' ? '⬇️ от клиента' : '⬆️ поставщику'}
                        </td>
                        <td className="mono" style={{ padding: '8px 12px', textAlign: 'right' }}>
                          {fmt(p.amount_uzs)}
                        </td>
                        <td className="mono" style={{
                          padding: '8px 12px', textAlign: 'right',
                          color: 'var(--fg-3)',
                        }}>
                          {fmt(p.used_uzs)}
                        </td>
                        <td className="mono" style={{
                          padding: '8px 12px', textAlign: 'right',
                          color: 'var(--success)', fontWeight: 600,
                        }}>
                          {fmt(p.free_uzs)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}

      {/* ── Tabs: открытые счета / касания ────────────────── */}
      <div style={{
        display: 'flex', gap: 4, marginTop: 14, marginBottom: 8,
        borderBottom: '1px solid var(--border)',
      }}>
        <TabBtn active={tab === 'orders'} onClick={() => setTab('orders')}>
          Открытые счета ({data.open_orders_count})
        </TabBtn>
        <TabBtn active={tab === 'comms'} onClick={() => setTab('comms')}>
          История касаний ({data.communications_count})
        </TabBtn>
      </div>

      {tab === 'orders' && (
        <Panel title="Непогашенные продажи">
          <DataTable
            rows={data.open_orders}
            rowKey={(o) => o.id}
            emptyMessage="Открытых счетов нет."
            columns={[
              {
                key: 'doc',
                label: 'Документ',
                render: (o) => (
                  <Link
                    href={`/sales?doc=${o.doc_number}`}
                    className="mono"
                    style={{ color: 'var(--brand-orange)', textDecoration: 'none', fontWeight: 500 }}
                  >
                    {o.doc_number}
                  </Link>
                ),
              },
              { key: 'date', label: 'Дата', mono: true,
                render: (o) => o.date },
              {
                key: 'due',
                label: 'Срок оплаты',
                render: (o) => {
                  if (!o.due_date) return <span style={{ color: 'var(--fg-3)' }}>не задан</span>;
                  const due = new Date(o.due_date);
                  const days = Math.round((due.getTime() - today.getTime()) / 86400000);
                  return (
                    <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                      <span className="mono">{o.due_date}</span>
                      {days < 0 && <Badge tone="danger">просрочено {Math.abs(days)} дн</Badge>}
                      {days === 0 && <Badge tone="warn">сегодня</Badge>}
                      {days > 0 && days <= 7 && <Badge tone="warn">через {days} дн</Badge>}
                    </span>
                  );
                },
              },
              { key: 'amount', label: 'Сумма', align: 'right', mono: true,
                render: (o) => fmt(o.amount_uzs) },
              { key: 'paid', label: 'Оплачено', align: 'right', mono: true,
                render: (o) => fmt(o.paid_amount_uzs) },
              { key: 'outstanding', label: 'Долг', align: 'right', mono: true,
                cellStyle: { fontWeight: 600, color: 'var(--brand-orange)' },
                render: (o) => fmt(o.outstanding_uzs) },
              { key: 'pay', label: 'Статус',
                render: (o) => (
                  <Badge tone={PAY_TONE[o.payment_status] ?? 'neutral'}>
                    {PAY_LABEL[o.payment_status] ?? o.payment_status}
                  </Badge>
                ) },
            ]}
          />
        </Panel>
      )}

      {tab === 'comms' && (
        <Panel
          title="История общения"
          tools={
            data.open_orders.length > 0 ? (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setAdding(true)}
              >
                <Icon name="plus" size={12} /> Новое касание
              </button>
            ) : (
              <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                Нет открытых счетов — некуда привязать
              </span>
            )
          }
        >
          {data.communications.length === 0 ? (
            <div style={{
              padding: 24, textAlign: 'center',
              fontSize: 12, color: 'var(--fg-3)',
            }}>
              Касаний по этому клиенту ещё не было.
              {data.open_orders.length > 0 && ' Нажмите «Новое касание» чтобы зафиксировать первый звонок.'}
            </div>
          ) : (
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.communications.map((c) => (
                <div
                  key={c.id}
                  style={{
                    padding: 10, borderRadius: 6,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-card)',
                  }}
                >
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
                      c.outcome === 'refused' || c.outcome === 'wrong_number' ? 'danger' :
                      'neutral'
                    }>{c.outcome_display}</Badge>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                      по счёту {c.order_doc}
                    </span>
                    <div style={{ flex: 1 }} />
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ padding: '2px 8px' }}
                      title="Редактировать"
                      onClick={() => setEditing({
                        ...c,
                        order: c.order_id,
                      } as unknown as SaleCommunication)}
                    >
                      ✎
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ padding: '2px 8px', color: 'var(--danger)' }}
                      title="Удалить"
                      disabled={deleteComm.isPending}
                      onClick={() => {
                        if (confirm('Удалить это касание? Действие нельзя отменить.')) {
                          deleteComm.mutate({ id: c.id, customerId: id });
                        }
                      }}
                    >
                      ✕
                    </button>
                  </div>
                  <div style={{ fontSize: 13, marginBottom: 4 }}>
                    «{c.customer_response}»
                  </div>
                  {c.internal_note && (
                    <div style={{
                      fontSize: 11, color: 'var(--fg-2)', marginBottom: 6,
                      padding: '4px 8px', background: 'var(--bg-soft)',
                      borderRadius: 4, fontStyle: 'italic',
                    }}>
                      📝 {c.internal_note}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--fg-3)', flexWrap: 'wrap' }}>
                    {c.contacted_by_name && <span>{c.contacted_by_name}</span>}
                    {c.promised_pay_date && (
                      <span style={{ color: 'var(--brand-orange)' }}>
                        ✓ обещал к {c.promised_pay_date}
                      </span>
                    )}
                    {c.expected_pay_date && (
                      <span style={{ color: 'var(--brand-orange)' }}>
                        🎯 жду к {c.expected_pay_date}
                      </span>
                    )}
                    {c.next_action_date && <span>↺ перезвонить {c.next_action_date}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {adding && id && (
        <CommunicationFormModal
          mode="add"
          customerId={id}
          customerName={cp.name}
          customerOpenOrders={data.open_orders.map((o) => ({
            id: o.id,
            doc_number: o.doc_number,
            outstanding_uzs: o.outstanding_uzs,
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
    </>
  );
}

function AgingBucket({
  label, value, tone, desc,
}: {
  label: string;
  value: string;
  tone: 'info' | 'warn' | 'danger';
  desc: string;
}) {
  const isEmpty = parseFloat(value) === 0;
  const color =
    isEmpty ? 'var(--fg-3)' :
    tone === 'danger' ? 'var(--danger)' :
    tone === 'warn' ? 'var(--brand-orange)' : 'var(--fg-1)';
  return (
    <div style={{
      padding: 8, borderRadius: 4, border: '1px solid var(--border)',
      background: isEmpty ? 'var(--bg-soft)' : 'var(--bg-card)',
    }}>
      <div style={{ fontSize: 10, color: 'var(--fg-3)', textTransform: 'uppercase' }}>{label}</div>
      <div className="mono" style={{ fontSize: 14, fontWeight: 600, color }}>
        {fmt(value)}
      </div>
      <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>{desc}</div>
    </div>
  );
}

function TabBtn({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 14px', fontSize: 13,
        background: 'transparent', border: 'none',
        borderBottom: active ? '2px solid var(--brand-orange)' : '2px solid transparent',
        color: active ? 'var(--brand-orange)' : 'var(--fg-2)',
        cursor: 'pointer', fontWeight: active ? 600 : 400,
      }}
    >
      {children}
    </button>
  );
}
