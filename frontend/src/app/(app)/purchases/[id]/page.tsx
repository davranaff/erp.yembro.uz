'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import { usePurchaseOrderSummary } from '@/hooks/usePurchases';

const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик', confirmed: 'Проведён', cancelled: 'Отменён',
};

const PAY_LABEL: Record<string, string> = {
  unpaid: 'Не оплачен', partial: 'Частично', paid: 'Оплачен', overpaid: 'Переплата',
};

const PAY_TONE: Record<string, 'neutral' | 'success' | 'warn' | 'info'> = {
  unpaid: 'neutral', partial: 'warn', paid: 'success', overpaid: 'info',
};

function fmt(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'number' ? v : parseFloat(v);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

export default function PurchaseDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  const { data, isLoading, error } = usePurchaseOrderSummary(id);

  if (isLoading) return <div className="page-hdr"><div><h1>Загружаем…</h1></div></div>;
  if (error) return (
    <div style={{ padding: 16, margin: 16, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6 }}>
      Не удалось загрузить: {error.message}
    </div>
  );
  if (!data) return null;

  const o = data.order;
  const isFx = o.currency_code && o.currency_code !== 'UZS';
  const outstanding = parseFloat(o.outstanding_uzs);

  return (
    <>
      <div className="page-hdr">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => router.push('/purchases')}>
              <Icon name="chevron-left" size={12} /> К списку
            </button>
          </div>
          <h1>
            Закуп{' '}
            <span className="mono" style={{ fontSize: 18, color: 'var(--fg-3)' }}>{o.doc_number}</span>
          </h1>
          <div className="sub" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Badge tone={o.status === 'confirmed' ? 'success' : o.status === 'cancelled' ? 'danger' : 'neutral'}>
              {STATUS_LABEL[o.status] ?? o.status}
            </Badge>
            {o.payment_status && (
              <Badge tone={PAY_TONE[o.payment_status] ?? 'neutral'}>
                {PAY_LABEL[o.payment_status] ?? o.payment_status}
              </Badge>
            )}
            <span className="mono">от {o.date}</span>
            {o.due_date && <span className="mono" style={{ color: 'var(--fg-3)' }}>· срок {o.due_date}</span>}
          </div>
          <div className="sub" style={{ marginTop: 4 }}>
            Поставщик:{' '}
            {o.counterparty_id ? (
              <Link
                href={`/counterparties/${o.counterparty_id}`}
                style={{ color: 'var(--brand-orange)', textDecoration: 'none', fontWeight: 500 }}
              >
                {o.counterparty_name} ({o.counterparty_code})
              </Link>
            ) : '—'}
          </div>
        </div>
      </div>

      {/* Один большой блок: К оплате */}
      <div style={{
        marginTop: 4,
        padding: '20px 24px',
        borderRadius: 8,
        background: outstanding > 0
          ? 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
          : 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)',
        border: '1px solid',
        borderColor: outstanding > 0 ? '#f59e0b' : '#10b981',
      }}>
        <div style={{ fontSize: 12, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          {outstanding > 0 ? 'Должны заплатить' : 'Полностью оплачено'}
        </div>
        <div style={{
          fontSize: 36, fontWeight: 700, fontFamily: 'var(--mono, monospace)',
          color: outstanding > 0 ? '#92400e' : '#065f46',
          marginTop: 4,
        }}>
          {fmt(outstanding)} <span style={{ fontSize: 18, fontWeight: 500 }}>сум</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 8 }}>
          Сумма закупа: <b>{fmt(o.amount_uzs)}</b> сум · Уже оплачено: <b>{fmt(o.paid_amount_uzs)}</b> сум
          {isFx && <> · {fmt(o.amount_foreign)} {o.currency_code} @ {fmt(o.exchange_rate)}</>}
        </div>
      </div>

      {o.notes && (
        <div style={{
          marginTop: 12, padding: 10, borderRadius: 6,
          background: 'var(--bg-soft)', fontSize: 13, color: 'var(--fg-2)',
        }}>
          📝 {o.notes}
        </div>
      )}

      {/* Состав */}
      <div style={{ height: 14 }} />
      <Panel title={`Состав (${data.items.length})`} flush>
        <DataTable
          rows={data.items}
          rowKey={(it) => it.id}
          emptyMessage="Состав не задан."
          columns={[
            { key: 'name', label: 'Товар', render: (it) => it.nomenclature_name || '—' },
            { key: 'qty', label: 'Кол-во', mono: true, align: 'right',
              render: (it) => fmt(it.quantity) },
            { key: 'price', label: 'Цена', mono: true, align: 'right',
              render: (it) => fmt(it.unit_price_uzs) },
            { key: 'total', label: 'Сумма', mono: true, align: 'right',
              cellStyle: { fontWeight: 600 },
              render: (it) => fmt(it.line_total_uzs) },
          ]}
        />
      </Panel>

      {/* Оплаты */}
      {data.payments.length > 0 && (
        <>
          <div style={{ height: 12 }} />
          <Panel title={`Оплаты (${data.payments.length})`} flush>
            <DataTable
              rows={data.payments}
              rowKey={(p) => p.allocation_id}
              columns={[
                { key: 'doc', label: 'Документ', mono: true, render: (p) => p.doc_number },
                { key: 'date', label: 'Дата', mono: true, render: (p) => p.date },
                { key: 'channel', label: 'Канал',
                  render: (p) => p.channel === 'cash' ? 'Наличные'
                    : p.channel === 'transfer' ? 'Перечисление'
                    : p.channel === 'click' ? 'Click' : p.channel },
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
        </>
      )}

      {/* Файлы */}
      {data.attachments.length > 0 && (
        <>
          <div style={{ height: 12 }} />
          <Panel title={`Файлы (${data.attachments.length})`}>
            <div style={{ padding: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
              {data.attachments.map((a) => (
                <a
                  key={a.id} href={a.file ?? '#'} target="_blank" rel="noopener noreferrer"
                  style={{
                    padding: 10, borderRadius: 6,
                    border: '1px solid var(--border)',
                    color: 'var(--fg-1)', textDecoration: 'none',
                    fontSize: 13,
                  }}
                >
                  📎 {a.name || 'файл'}
                </a>
              ))}
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
