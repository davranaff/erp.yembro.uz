'use client';

import { useState } from 'react';

import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useModuleKpi } from '@/hooks/useDashboard';

import CashflowChart from './CashflowChart';

function fmt(v: string | number | null | undefined, opts: { short?: boolean } = {}): string {
  if (v == null) return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  if (opts.short) {
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(0) + 'K';
  }
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function monthStartIso(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

const DATE_INPUT_STYLE: React.CSSProperties = {
  fontSize: 12,
  padding: '3px 8px',
  border: '1px solid var(--border)',
  borderRadius: 4,
  background: 'var(--bg-input, var(--bg-soft))',
  color: 'var(--fg-1)',
  outline: 'none',
};

interface Props {
  moduleCode: string;
  moduleName: string;
}

export default function ModuleSection({ moduleCode, moduleName }: Props) {
  const [from, setFrom] = useState<string>(monthStartIso);
  const [to, setTo] = useState<string>(todayIso);

  const { data, isLoading, error } = useModuleKpi(moduleCode, from, to);

  const balance = data ? parseFloat(data.balance_uzs) : 0;
  const isNegBal = balance < 0;
  const netFlow = data
    ? parseFloat(data.payments_in_uzs) - parseFloat(data.payments_out_uzs)
    : 0;

  return (
    <Panel
      title={moduleName}
      style={{ marginBottom: 12 }}
      tools={
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="date"
            value={from}
            max={to}
            onChange={(e) => setFrom(e.target.value)}
            style={DATE_INPUT_STYLE}
          />
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>—</span>
          <input
            type="date"
            value={to}
            min={from}
            max={todayIso()}
            onChange={(e) => setTo(e.target.value)}
            style={DATE_INPUT_STYLE}
          />
        </div>
      }
    >
      {isLoading && (
        <div style={{ padding: '14px 16px', fontSize: 13, color: 'var(--fg-3)' }}>
          Загрузка…
        </div>
      )}
      {error && (
        <div style={{ padding: '14px 16px', fontSize: 13, color: 'var(--danger)' }}>
          Ошибка: {error.message}
        </div>
      )}
      {data && (
        <div>
          {/* ── 4 KPI tiles ── */}
          <div className="kpi-row" style={{ padding: '12px 12px 0' }}>
            <KpiCard
              tone="green"
              iconName="download"
              label="Поступления"
              sub="за период"
              value={fmt(data.payments_in_uzs)}
              valueSuffix="UZS"
            />
            <KpiCard
              tone="red"
              iconName="arrow-right"
              label="Расходы"
              sub="за период"
              value={fmt(data.payments_out_uzs)}
              valueSuffix="UZS"
            />
            <KpiCard
              tone={isNegBal ? 'red' : 'orange'}
              iconName="bag"
              label="Остаток"
              sub="всё время"
              value={`${isNegBal ? '−' : ''}${fmt(Math.abs(balance))}`}
              valueSuffix="UZS"
              meta={netFlow !== 0 ? `поток: ${netFlow >= 0 ? '+' : '−'}${fmt(Math.abs(netFlow), { short: true })}` : undefined}
            />
            <KpiCard
              tone="blue"
              iconName="users"
              label="Долги клиентов"
              sub="непогашенные продажи"
              value={fmt(data.ar_uzs)}
              valueSuffix="UZS"
            />
          </div>

          {/* ── Mini cashflow chart ── */}
          {data.cashflow.length > 1 && (
            <div style={{ padding: '8px 12px 12px' }}>
              <CashflowChart points={data.cashflow} />
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
