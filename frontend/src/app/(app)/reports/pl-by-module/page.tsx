'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';

import DateRangeFilter from '@/components/DateRangeFilter';
import ExportCsvButton from '@/components/ExportCsvButton';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { usePlByModule, type PlModuleRow } from '@/hooks/useReports';


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


export default function PlByModulePage() {
  const sp = useSearchParams();
  const [dateFrom, setDateFrom] = useState(sp.get('date_from') ?? startOfMonth());
  const [dateTo, setDateTo] = useState(sp.get('date_to') ?? isoToday());

  const { data, isLoading, error } = usePlByModule({
    date_from: dateFrom,
    date_to: dateTo,
  });

  const csvUrl = `/api/accounting/reports/pl-by-module/?date_from=${dateFrom}&date_to=${dateTo}`;

  const profitNum = data ? parseFloat(data.total_profit) : 0;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Прибыль по модулям</h1>
          <div className="sub">
            Кто заработал, кто проел · период{' '}
            <strong>{dateFrom}</strong> — <strong>{dateTo}</strong>
          </div>
        </div>
        <div className="actions">
          <ExportCsvButton
            url={csvUrl}
            filename={`pl-by-module-${dateFrom}-${dateTo}.csv`}
          />
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
          label="Доход всего"
          sub={data ? `${data.rows.length} модулей` : ''}
          value={data ? fmtMoney(data.total_revenue) : '…'}
        />
        <KpiCard
          tone="red"
          iconName="bag"
          label="Расход всего"
          sub="за период"
          value={data ? fmtMoney(data.total_expense) : '…'}
        />
        <KpiCard
          tone={profitNum >= 0 ? 'green' : 'red'}
          iconName={profitNum >= 0 ? 'check' : 'close'}
          label={profitNum >= 0 ? 'Прибыль' : 'Убыток'}
          sub="за период"
          value={data ? fmtMoney(data.total_profit) : '…'}
        />
      </div>

      <Panel title="Разбивка по модулям" flush style={{ marginTop: 14 }}>
        <DataTable<PlModuleRow>
          isLoading={isLoading}
          rows={data?.rows ?? []}
          rowKey={(r) => r.module_code}
          error={error}
          emptyMessage={
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: 13 }}>
              За выбранный период проводок с привязкой к модулям нет.
              Если все доходы/расходы видны в общем P&L, но здесь пусто —
              значит, операции не были тегированы модулем (поле «Модуль»
              в форме «Касса и банк» / автоматически в сервисах).
            </div>
          }
          columns={[
            { key: 'module', label: 'Модуль',
              render: (r) => (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <strong>{r.module_name}</strong>
                  <span style={{ fontSize: 11, color: 'var(--fg-3)' }} className="mono">
                    {r.module_code === '—' ? 'без модуля' : r.module_code}
                  </span>
                </div>
              ),
            },
            { key: 'revenue', label: 'Доход', align: 'right', mono: true,
              cellStyle: { color: 'var(--success)' },
              render: (r) => fmtAmount(r.revenue) },
            { key: 'expense', label: 'Расход', align: 'right', mono: true,
              cellStyle: { color: 'var(--danger)' },
              render: (r) => fmtAmount(r.expense) },
            { key: 'profit', label: 'Прибыль', align: 'right', mono: true,
              cellStyle: { fontWeight: 700 },
              render: (r) => {
                const n = parseFloat(r.profit);
                if (Number.isNaN(n) || n === 0) return '—';
                return (
                  <span style={{ color: n >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                    {n >= 0 ? '+' : ''}{n.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
                  </span>
                );
              },
            },
          ]}
        />
      </Panel>

      <div style={{
        marginTop: 12, padding: 10, fontSize: 11, color: 'var(--fg-3)',
        background: 'var(--bg-soft)', borderRadius: 6,
      }}>
        Тег модуля ставится автоматически бизнес-сервисами (продажа, закуп,
        падёж, расход корма, межмодульная передача) и вручную в форме
        «Касса и банк → Приход/Расход → Модуль». Проводки без тега попадают
        в строку «Без модуля».
      </div>
    </>
  );
}
