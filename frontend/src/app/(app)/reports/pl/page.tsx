'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';

import DateRangeFilter from '@/components/DateRangeFilter';
import ExportCsvButton from '@/components/ExportCsvButton';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { usePlReport, type PlRow } from '@/hooks/useReports';


function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function fmtMoney(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

function fmtAmount(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}


export default function PlReportPage() {
  const sp = useSearchParams();
  const [dateFrom, setDateFrom] = useState(sp.get('date_from') ?? startOfMonth());
  const [dateTo, setDateTo] = useState(sp.get('date_to') ?? isoToday());

  const { data, isLoading, error } = usePlReport({ date_from: dateFrom, date_to: dateTo });

  const csvUrl = `/api/accounting/reports/pl/?date_from=${dateFrom}&date_to=${dateTo}`;

  const profitNum = data ? parseFloat(data.profit) : 0;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Прибыль и убыток</h1>
          <div className="sub">
            P&L отчёт · период <strong>{dateFrom}</strong> — <strong>{dateTo}</strong>
          </div>
        </div>
        <div className="actions">
          <ExportCsvButton url={csvUrl} filename={`pl-${dateFrom}-${dateTo}.csv`} />
        </div>
      </div>

      <Panel title="Период" flush>
        <div style={{ padding: 12 }}>
          <DateRangeFilter
            dateFrom={dateFrom}
            dateTo={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
          />
        </div>
      </Panel>

      <div className="kpi-row" style={{ marginTop: 12 }}>
        <KpiCard
          tone="green"
          iconName="chart"
          label="Выручка"
          sub={data ? `${data.revenue.length} статьи` : ''}
          value={data ? fmtMoney(data.total_revenue) : '…'}
        />
        <KpiCard
          tone="red"
          iconName="bag"
          label="Расходы"
          sub={data ? `${data.expense.length} статьи` : ''}
          value={data ? fmtMoney(data.total_expense) : '…'}
        />
        <KpiCard
          tone={profitNum >= 0 ? 'green' : 'red'}
          iconName={profitNum >= 0 ? 'check' : 'close'}
          label={profitNum >= 0 ? 'Прибыль' : 'Убыток'}
          sub="за период"
          value={data ? fmtMoney(data.profit) : '…'}
        />
      </div>

      <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="Доходы" flush>
          <DataTable<PlRow>
            isLoading={isLoading}
            rows={data?.revenue ?? []}
            rowKey={(r) => r.subaccount_id}
            error={error}
            emptyMessage="Нет доходов за период."
            columns={[
              { key: 'sub', label: 'Счёт', mono: true,
                render: (r) => <strong>{r.subaccount_code}</strong> },
              { key: 'name', label: 'Название',
                render: (r) => r.subaccount_name },
              { key: 'mod', label: 'По модулям', cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                render: (r) => Object.entries(r.by_module).length > 0
                  ? Object.entries(r.by_module).map(([k, v]) =>
                    `${k}=${parseFloat(v).toLocaleString('ru-RU')}`
                  ).join(' · ')
                  : '—' },
              { key: 'amt', label: 'Сумма', align: 'right', mono: true,
                cellStyle: { fontWeight: 700, color: 'var(--success)' },
                render: (r) => fmtAmount(r.amount) },
            ]}
          />
        </Panel>

        <Panel title="Расходы" flush>
          <DataTable<PlRow>
            isLoading={isLoading}
            rows={data?.expense ?? []}
            rowKey={(r) => r.subaccount_id}
            error={error}
            emptyMessage="Нет расходов за период."
            columns={[
              { key: 'sub', label: 'Счёт', mono: true,
                render: (r) => <strong>{r.subaccount_code}</strong> },
              { key: 'name', label: 'Название',
                render: (r) => r.subaccount_name },
              { key: 'mod', label: 'По модулям', cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                render: (r) => Object.entries(r.by_module).length > 0
                  ? Object.entries(r.by_module).map(([k, v]) =>
                    `${k}=${parseFloat(v).toLocaleString('ru-RU')}`
                  ).join(' · ')
                  : '—' },
              { key: 'amt', label: 'Сумма', align: 'right', mono: true,
                cellStyle: { fontWeight: 700, color: 'var(--danger)' },
                render: (r) => fmtAmount(r.amount) },
            ]}
          />
        </Panel>
      </div>
    </>
  );
}
