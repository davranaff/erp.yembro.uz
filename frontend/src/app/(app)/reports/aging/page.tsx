'use client';

import { useMemo, useState } from 'react';

import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import { useAgingReport, type AgingRow } from '@/hooks/useReports';

function fmtMoney(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function fmtMoneyFull(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

const BUCKETS = [
  { key: 'current' as const,  label: 'Текущие',   tone: 'info' as const,    desc: 'не просрочено' },
  { key: 'b_0_30' as const,   label: '0-30 дн',   tone: 'warn' as const,    desc: 'до месяца' },
  { key: 'b_31_60' as const,  label: '31-60 дн',  tone: 'warn' as const,    desc: '1-2 мес' },
  { key: 'b_61_90' as const,  label: '61-90 дн',  tone: 'danger' as const,  desc: '2-3 мес' },
  { key: 'b_90_plus' as const, label: '90+ дн',   tone: 'danger' as const,  desc: 'критично' },
] as const;

/**
 * AR aging report — старение дебиторки.
 *
 * Показывает кто и сколько должен, разбито по бакетам просрочки.
 * Топ должников сверху (по убыванию total). Кнопка-фильтр «только с
 * просрочкой» прячет клиентов у которых вся задолженность ещё в `current`.
 */
export default function AgingReportPage() {
  const { data, isLoading, error } = useAgingReport();
  const [overdueOnly, setOverdueOnly] = useState(false);

  const rows = useMemo<AgingRow[]>(() => {
    const all = data?.rows ?? [];
    return overdueOnly ? all.filter((r) => r.has_overdue) : all;
  }, [data, overdueOnly]);

  const top20 = useMemo<AgingRow[]>(
    () => (data?.rows ?? []).slice(0, 20),
    [data],
  );

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Старение дебиторки</h1>
          <div className="sub">
            Непогашенные продажи по бакетам просрочки
            {data?.as_of && <> · на <strong>{data.as_of}</strong></>}
          </div>
        </div>
      </div>

      {/* ── KPI: суммы по бакетам ─────────────────────────── */}
      <div className="kpi-row">
        {BUCKETS.map((b) => {
          const v = data?.summary[b.key] ?? '0';
          const isHot = b.key === 'b_61_90' || b.key === 'b_90_plus';
          return (
            <KpiCard
              key={b.key}
              tone={isHot ? 'red' : b.key === 'current' ? 'green' : 'orange'}
              iconName="bag"
              label={b.label}
              sub={b.desc}
              value={isLoading ? '…' : fmtMoney(v) + ' сум'}
            />
          );
        })}
      </div>

      <div className="kpi-row" style={{ marginTop: 8 }}>
        <KpiCard
          tone="orange"
          iconName="chart"
          label="Всего долгов"
          sub={`${data?.summary.customers_count ?? 0} клиентов`}
          value={data ? fmtMoneyFull(data.summary.total) : '…'}
        />
        <KpiCard
          tone="red"
          iconName="bag"
          label="С просрочкой"
          sub="клиентов"
          value={String(data?.summary.overdue_customers_count ?? 0)}
        />
      </div>

      {error && (
        <div style={{
          marginTop: 14, padding: 10, background: '#fef2f2',
          color: 'var(--danger)', borderRadius: 6, fontSize: 13,
        }}>
          Не удалось загрузить отчёт: {error.message}
        </div>
      )}

      {/* ── Таблица должников ─────────────────────────────── */}
      <Panel
        title={`Должники (${rows.length})`}
        tools={
          <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => setOverdueOnly(e.target.checked)}
            />
            только с просрочкой
          </label>
        }
        style={{ marginTop: 14 }}
      >
        <DataTable<AgingRow>
          rows={rows}
          isLoading={isLoading}
          rowKey={(r) => r.counterparty_id}
          emptyMessage={overdueOnly ? 'Нет должников с просрочкой' : 'Дебиторской задолженности нет.'}
          columns={[
            {
              key: 'name',
              label: 'Клиент',
              render: (r) => (
                <div>
                  <div style={{ fontWeight: 500 }}>{r.name}</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{r.code}</div>
                </div>
              ),
            },
            {
              key: 'orders_count',
              label: 'Счетов',
              align: 'right',
              width: 70,
              render: (r) => <span className="mono">{r.orders_count}</span>,
            },
            { key: 'current',   label: 'Текущие',   align: 'right', mono: true,
              render: (r) => fmtMoney(r.current) },
            { key: 'b_0_30',    label: '0-30',      align: 'right', mono: true,
              render: (r) => fmtMoney(r.b_0_30) },
            { key: 'b_31_60',   label: '31-60',     align: 'right', mono: true,
              render: (r) => fmtMoney(r.b_31_60) },
            { key: 'b_61_90',   label: '61-90',     align: 'right', mono: true,
              cellStyle: { color: 'var(--danger)' },
              render: (r) => fmtMoney(r.b_61_90) },
            { key: 'b_90_plus', label: '90+',       align: 'right', mono: true,
              cellStyle: { color: 'var(--danger)', fontWeight: 600 },
              render: (r) => fmtMoney(r.b_90_plus) },
            {
              key: 'oldest',
              label: 'Макс. просрочка',
              align: 'right',
              width: 130,
              render: (r) => r.oldest_overdue_days > 0 ? (
                <Badge tone={r.oldest_overdue_days > 90 ? 'danger' : r.oldest_overdue_days > 30 ? 'warn' : 'info'}>
                  {r.oldest_overdue_days} дн
                </Badge>
              ) : <span style={{ color: 'var(--fg-3)' }}>—</span>,
            },
            {
              key: 'total',
              label: 'Итого',
              align: 'right',
              mono: true,
              cellStyle: { fontWeight: 600 },
              render: (r) => fmtMoney(r.total),
            },
          ]}
        />
      </Panel>

      {/* ── Топ-20 ────────────────────────────────────────── */}
      {top20.length > 0 && (
        <Panel
          title="Топ-20 по сумме долга"
          style={{ marginTop: 14 }}
        >
          <div style={{ padding: 12, fontSize: 12, color: 'var(--fg-3)' }}>
            {top20.length === rows.length
              ? 'Все клиенты ниже уже отсортированы по убыванию долга.'
              : 'Сосредоточьтесь на этих 20 клиентах — на них приходится основная сумма дебиторки.'}
          </div>
        </Panel>
      )}
    </>
  );
}
