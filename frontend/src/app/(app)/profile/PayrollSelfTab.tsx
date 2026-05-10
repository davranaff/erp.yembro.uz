'use client';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useMyPayroll } from '@/hooks/usePayroll';

const PAYOUT_TYPE_LABEL: Record<string, string> = {
  advance: 'Аванс',
  salary: 'ЗП',
  bonus: 'Премия',
  correction: 'Корректировка',
};

const ADJ_KIND_LABEL: Record<string, string> = {
  bonus: 'Премия',
  deduction: 'Удержание',
  correction_plus: 'Доначисление',
  correction_minus: 'Сторно',
};

function fmt(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n);
}

export default function PayrollSelfTab() {
  const { data, isLoading, error } = useMyPayroll();

  if (isLoading) return <Panel><div style={{ padding: 16 }}>Загружаем…</div></Panel>;
  if (error) return (
    <Panel><div style={{ padding: 16, color: 'var(--danger)' }}>{error.message}</div></Panel>
  );
  if (!data) return null;

  const { balance, rates, payouts, adjustments } = data;
  const balanceNum = Number(balance.balance_uzs);
  const balanceTone = balanceNum > 0 ? 'green' : balanceNum < 0 ? 'orange' : 'blue';

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
        <KpiCard label="Начислено всего" value={fmt(balance.accrued_total)} valueSuffix="сум" />
        <KpiCard label="Выплачено" value={fmt(balance.paid_total)} valueSuffix="сум" />
        <KpiCard label="К получению" value={fmt(balance.balance_uzs)} valueSuffix="сум" tone={balanceTone} />
      </div>

      <Panel title="Текущая ставка">
        <DataTable
          rows={rates.slice(0, 5)}
          rowKey={(r) => r.id}
          emptyMessage="Ставка ещё не назначена."
          columns={[
            { key: 'amount', label: 'Сумма', mono: true, align: 'right',
              render: (r) => `${fmt(r.amount)} ${r.currency_code ?? ''}` },
            { key: 'from', label: 'С', mono: true, render: (r) => r.effective_from },
            { key: 'to', label: 'По', mono: true,
              render: (r) => r.effective_to || <Badge tone="success">текущая</Badge> },
            { key: 'reason', label: 'Причина', render: (r) => r.reason || '—' },
          ]}
        />
      </Panel>

      <div style={{ height: 12 }} />

      <Panel title="История выплат">
        <DataTable
          rows={payouts}
          rowKey={(p) => p.id}
          emptyMessage="Выплат ещё не было."
          columns={[
            { key: 'doc', label: 'Документ', mono: true,
              render: (p) => p.payment_doc_number || '—' },
            { key: 'type', label: 'Тип',
              render: (p) => <Badge tone="info">{PAYOUT_TYPE_LABEL[p.type] ?? p.type}</Badge> },
            { key: 'amount', label: 'Сумма', mono: true, align: 'right',
              render: (p) => fmt(p.amount_uzs) },
            { key: 'period', label: 'Период', mono: true,
              render: (p) => `${p.period_from} — ${p.period_to}` },
            { key: 'status', label: 'Статус',
              render: (p) => (
                <Badge tone={p.payment_status === 'posted' ? 'success' : 'warn'}>
                  {p.payment_status ?? '—'}
                </Badge>
              ) },
          ]}
        />
      </Panel>

      {adjustments.length > 0 && (
        <>
          <div style={{ height: 12 }} />
          <Panel title="Корректировки и удержания">
            <DataTable
              rows={adjustments}
              rowKey={(a) => a.id}
              columns={[
                { key: 'kind', label: 'Тип',
                  render: (a) => {
                    const positive = a.kind === 'bonus' || a.kind === 'correction_plus';
                    return <Badge tone={positive ? 'success' : 'warn'}>{ADJ_KIND_LABEL[a.kind] ?? a.kind}</Badge>;
                  } },
                { key: 'date', label: 'Дата', mono: true, render: (a) => a.effective_date },
                { key: 'amount', label: 'Сумма', mono: true, align: 'right',
                  render: (a) => fmt(a.amount_uzs) },
                { key: 'reason', label: 'Причина', render: (a) => a.reason || '—' },
              ]}
            />
          </Panel>
        </>
      )}
    </>
  );
}
