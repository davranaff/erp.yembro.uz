'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';

import DateRangeFilter from '@/components/DateRangeFilter';
import ExportCsvButton from '@/components/ExportCsvButton';
import DataTable from '@/components/ui/DataTable';
import Panel from '@/components/ui/Panel';
import { useGlLedger, type GlLedgerEntry } from '@/hooks/useReports';
import { useSubaccounts } from '@/hooks/useAccounts';


function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function fmtMoney(v: string | null): string {
  if (!v) return '';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}


export default function GlLedgerPage() {
  const sp = useSearchParams();
  const [subaccount, setSubaccount] = useState(sp.get('subaccount') ?? '');
  const [dateFrom, setDateFrom] = useState(sp.get('date_from') ?? startOfMonth());
  const [dateTo, setDateTo] = useState(sp.get('date_to') ?? isoToday());

  const { data: subs } = useSubaccounts();
  const { data, isLoading, error } = useGlLedger({
    subaccount,
    date_from: dateFrom,
    date_to: dateTo,
  });

  const csvUrl = subaccount
    ? `/api/accounting/reports/gl-ledger/?subaccount=${subaccount}&date_from=${dateFrom}&date_to=${dateTo}`
    : '';

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Главная книга</h1>
          <div className="sub">
            История проводок по субсчёту с накопительным остатком
            {data && (
              <> · <strong>{data.subaccount_code}</strong> · {data.subaccount_name}</>
            )}
          </div>
        </div>
        <div className="actions">
          {subaccount && (
            <ExportCsvButton
              url={csvUrl}
              filename={`gl-${data?.subaccount_code ?? 'unknown'}-${dateFrom}-${dateTo}.csv`}
            />
          )}
        </div>
      </div>

      <Panel title="Фильтры" flush>
        <div style={{ padding: 12, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div className="field" style={{ marginBottom: 0, minWidth: 280 }}>
            <label style={{ fontSize: 11 }}>Субсчёт *</label>
            <select
              className="input"
              value={subaccount}
              onChange={(e) => setSubaccount(e.target.value)}
            >
              <option value="">— выберите —</option>
              {subs?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} · {s.name}
                </option>
              ))}
            </select>
          </div>
          <DateRangeFilter
            dateFrom={dateFrom}
            dateTo={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
          />
        </div>
      </Panel>

      {data && (
        <div className="kpi-row" style={{ marginTop: 12 }}>
          <div style={{
            flex: 1, padding: 14, background: 'var(--bg-card, #fff)',
            border: '1px solid var(--border)', borderRadius: 6,
          }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Начальный остаток</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'monospace' }}>
              {fmtMoney(data.opening_balance) || '0'} сум
            </div>
          </div>
          <div style={{
            flex: 1, padding: 14, background: 'var(--bg-card, #fff)',
            border: '1px solid var(--border)', borderRadius: 6,
          }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Σ Дебет</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'monospace', color: 'var(--info)' }}>
              {fmtMoney(data.total_debit) || '0'}
            </div>
          </div>
          <div style={{
            flex: 1, padding: 14, background: 'var(--bg-card, #fff)',
            border: '1px solid var(--border)', borderRadius: 6,
          }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Σ Кредит</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'monospace', color: 'var(--warning)' }}>
              {fmtMoney(data.total_credit) || '0'}
            </div>
          </div>
          <div style={{
            flex: 1, padding: 14, background: 'var(--bg-card, #fff)',
            border: '2px solid var(--brand-orange)', borderRadius: 6,
          }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Конечный остаток</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'monospace' }}>
              {fmtMoney(data.closing_balance) || '0'} сум
            </div>
          </div>
        </div>
      )}

      <Panel title={`Проводки · ${data?.entries.length ?? 0}`} flush>
        <DataTable<GlLedgerEntry>
          isLoading={isLoading}
          rows={data?.entries ?? []}
          rowKey={(e) => e.entry_id}
          error={error}
          emptyMessage={subaccount ? "Нет проводок за период." : "Выберите субсчёт."}
          columns={[
            { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
              render: (e) => e.entry_date },
            { key: 'doc', label: 'Документ', mono: true,
              render: (e) => <span className="badge id">{e.doc_number}</span> },
            { key: 'desc', label: 'Описание', cellStyle: { fontSize: 12 },
              render: (e) => e.description || '—' },
            { key: 'd', label: 'Дебет', align: 'right', mono: true,
              cellStyle: { color: 'var(--info)' },
              render: (e) => fmtMoney(e.debit_amount) || '' },
            { key: 'c', label: 'Кредит', align: 'right', mono: true,
              cellStyle: { color: 'var(--warning)' },
              render: (e) => fmtMoney(e.credit_amount) || '' },
            { key: 'run', label: 'Остаток', align: 'right', mono: true,
              cellStyle: { fontWeight: 600 },
              render: (e) => fmtMoney(e.running_balance) },
            { key: 'cp', label: 'Контрагент', cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (e) => e.counterparty_name ?? '—' },
            { key: 'mod', label: 'Модуль', mono: true, cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (e) => e.module_code ?? '—' },
          ]}
        />
      </Panel>
    </>
  );
}
