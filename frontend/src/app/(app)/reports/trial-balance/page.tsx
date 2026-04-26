'use client';

import { useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import DateRangeFilter from '@/components/DateRangeFilter';
import ExportCsvButton from '@/components/ExportCsvButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import { useTrialBalance, type TrialBalanceRow } from '@/hooks/useReports';


function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function fmtMoney(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

const TYPE_LABEL: Record<string, string> = {
  asset: 'Актив',
  liability: 'Пассив',
  equity: 'Капитал',
  income: 'Доход',
  expense: 'Расход',
  service: 'Служ.',
};

const TYPE_TONE: Record<string, 'info' | 'warn' | 'success' | 'danger' | 'neutral'> = {
  asset: 'info',
  liability: 'warn',
  equity: 'neutral',
  income: 'success',
  expense: 'danger',
  service: 'neutral',
};


export default function TrialBalancePage() {
  const router = useRouter();
  const sp = useSearchParams();
  const [dateFrom, setDateFrom] = useState(sp.get('date_from') ?? startOfMonth());
  const [dateTo, setDateTo] = useState(sp.get('date_to') ?? isoToday());
  const [moduleCode, setModuleCode] = useState(sp.get('module_code') ?? '');
  const [typeFilter, setTypeFilter] = useState('');

  const { data, isLoading, error } = useTrialBalance({
    date_from: dateFrom,
    date_to: dateTo,
    module_code: moduleCode || undefined,
  });

  const rows = useMemo(() => {
    if (!data) return [];
    if (!typeFilter) return data.rows;
    return data.rows.filter((r) => r.account_type === typeFilter);
  }, [data, typeFilter]);

  const totals = useMemo(() => {
    if (!rows.length) return { d: 0, c: 0 };
    let d = 0, c = 0;
    for (const r of rows) {
      d += parseFloat(r.debit_turnover) || 0;
      c += parseFloat(r.credit_turnover) || 0;
    }
    return { d, c };
  }, [rows]);

  const handleRowClick = (r: TrialBalanceRow) => {
    router.push(
      `/reports/gl-ledger?subaccount=${r.subaccount_id}&date_from=${dateFrom}&date_to=${dateTo}`,
    );
  };

  const csvUrl = `/api/accounting/reports/trial-balance/?date_from=${dateFrom}&date_to=${dateTo}`
    + (moduleCode ? `&module_code=${moduleCode}` : '');

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Оборотная ведомость</h1>
          <div className="sub">
            Остатки и обороты за период · клик по строке → главная книга по счёту
          </div>
        </div>
        <div className="actions">
          <ExportCsvButton
            url={csvUrl}
            filename={`trial-balance-${dateFrom}-${dateTo}.csv`}
          />
        </div>
      </div>

      <Panel title="Фильтры" flush>
        <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <DateRangeFilter
            dateFrom={dateFrom}
            dateTo={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
          />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label style={{ fontSize: 11 }}>Модуль</label>
              <input
                className="input"
                value={moduleCode}
                onChange={(e) => setModuleCode(e.target.value)}
                placeholder="feedlot / slaughter / vet / ..."
                style={{ width: 200 }}
              />
            </div>
            <Seg
              options={[
                { value: '', label: 'Все' },
                { value: 'asset', label: 'Активы' },
                { value: 'liability', label: 'Пассивы' },
                { value: 'income', label: 'Доходы' },
                { value: 'expense', label: 'Расходы' },
              ]}
              value={typeFilter}
              onChange={setTypeFilter}
            />
          </div>
        </div>
      </Panel>

      <Panel
        title={`Строки · ${rows.length}`}
        tools={
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Σ Дт: <strong>{totals.d.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</strong>
            {' · '}
            Σ Кт: <strong>{totals.c.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</strong>
          </div>
        }
        flush
      >
        <DataTable<TrialBalanceRow>
          isLoading={isLoading}
          rows={rows}
          rowKey={(r) => r.subaccount_id}
          error={error}
          emptyMessage="Нет данных за выбранный период."
          onRowClick={handleRowClick}
          columns={[
            { key: 'sub', label: 'Субсчёт', mono: true,
              render: (r) => <strong>{r.subaccount_code}</strong> },
            { key: 'name', label: 'Название',
              render: (r) => r.subaccount_name },
            { key: 'type', label: 'Тип',
              render: (r) => <Badge tone={TYPE_TONE[r.account_type] ?? 'neutral'} dot>{TYPE_LABEL[r.account_type] ?? r.account_type}</Badge> },
            { key: 'mod', label: 'Модуль', mono: true, cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (r) => r.module_code ?? '—' },
            { key: 'open', label: 'Нач. остаток', align: 'right', mono: true,
              render: (r) => fmtMoney(r.opening_balance) },
            { key: 'd', label: 'Оборот Дт', align: 'right', mono: true,
              cellStyle: { color: 'var(--info)' },
              render: (r) => fmtMoney(r.debit_turnover) },
            { key: 'c', label: 'Оборот Кт', align: 'right', mono: true,
              cellStyle: { color: 'var(--warning)' },
              render: (r) => fmtMoney(r.credit_turnover) },
            { key: 'close', label: 'Кон. остаток', align: 'right', mono: true,
              cellStyle: { fontWeight: 700 },
              render: (r) => fmtMoney(r.closing_balance) },
          ]}
        />
      </Panel>
    </>
  );
}
