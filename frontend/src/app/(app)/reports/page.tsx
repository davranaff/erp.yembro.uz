'use client';

import { useState } from 'react';
import Link from 'next/link';

import DateRangeFilter from '@/components/DateRangeFilter';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useDashboardArSummary } from '@/hooks/useDashboard';
import { usePlReport } from '@/hooks/useReports';


function fmtMoney(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}


export default function ReportsHomePage() {
  const [dateFrom, setDateFrom] = useState(startOfMonth());
  const [dateTo, setDateTo] = useState(isoToday());

  const { data: pl } = usePlReport({ date_from: dateFrom, date_to: dateTo });
  const { data: ar } = useDashboardArSummary(90);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Отчёты</h1>
          <div className="sub">
            Бухгалтерская и управленческая отчётность · период{' '}
            <strong>{dateFrom}</strong> — <strong>{dateTo}</strong>
          </div>
        </div>
      </div>

      <Panel title="Период отчётов" flush>
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
          tone="blue"
          iconName="chart"
          label="Выручка"
          sub="за период"
          value={pl ? fmtMoney(pl.total_revenue) : '…'}
        />
        <KpiCard
          tone="orange"
          iconName="bag"
          label="Расходы"
          sub="за период"
          value={pl ? fmtMoney(pl.total_expense) : '…'}
        />
        <KpiCard
          tone={pl && parseFloat(pl.profit) >= 0 ? 'green' : 'red'}
          iconName={pl && parseFloat(pl.profit) >= 0 ? 'check' : 'close'}
          label="Прибыль"
          sub="за период"
          value={pl ? fmtMoney(pl.profit) : '…'}
        />
        <KpiCard
          tone="orange"
          iconName="book"
          label="P&L позиций"
          sub="доход + расход"
          value={pl ? String((pl.revenue.length + pl.expense.length)) : '…'}
        />
      </div>

      {/* ── AR snapshot row ──────────────────────────────── */}
      {ar && (
        <div className="kpi-row" style={{ marginTop: 8 }}>
          <KpiCard
            tone={parseFloat(ar.total_overdue_uzs) > 0 ? 'red' : 'green'}
            iconName="bag"
            label="Дебиторка"
            sub={`${ar.customers_count} клиентов`}
            value={fmtMoney(ar.total_ar_uzs)}
          />
          <KpiCard
            tone="red"
            iconName="bag"
            label="Просрочено"
            sub={`${ar.overdue_customers_count} клиентов с просрочкой`}
            value={fmtMoney(ar.total_overdue_uzs)}
          />
          <KpiCard
            tone="blue"
            iconName="chart"
            label={`DSO (${ar.dso_window_days} дн)`}
            sub="средний срок инкассации"
            value={ar.dso_days != null ? `${ar.dso_days} дн` : '—'}
          />
          <KpiCard
            tone="orange"
            iconName="bag"
            label="Топ-должник"
            sub={ar.top_debtors[0]?.name ?? '—'}
            value={ar.top_debtors[0] ? fmtMoney(ar.top_debtors[0].total) : '—'}
          />
        </div>
      )}

      <div className="grid-3" style={{ marginTop: 14 }}>
        <ReportCard
          href={`/reports/trial-balance?date_from=${dateFrom}&date_to=${dateTo}`}
          title="Оборотная ведомость"
          subtitle="ОСВ по плану счетов"
          desc="По каждому субсчёту: начальный остаток, оборот Дт, оборот Кт, конечный остаток. Для аудита и сверок."
          icon="chart"
        />
        <ReportCard
          href={`/reports/gl-ledger?date_from=${dateFrom}&date_to=${dateTo}`}
          title="Главная книга"
          subtitle="GL ledger по выбранному счёту"
          desc="Детальная история проводок по конкретному субсчёту с накопительным остатком."
          icon="book"
        />
        <ReportCard
          href={`/reports/pl?date_from=${dateFrom}&date_to=${dateTo}`}
          title="Прибыль и убыток"
          subtitle="P&L отчёт"
          desc="Доходы − расходы = прибыль. Разрезы по модулям и статьям."
          icon="chart"
        />
        <ReportCard
          href={`/reports/pl-by-module?date_from=${dateFrom}&date_to=${dateTo}`}
          title="Прибыль по модулям"
          subtitle="Кто сколько заработал"
          desc="Та же P&L, но в разрезе модулей: маточник, откорм, инкубация, убойня, корма, вет."
          icon="chart"
        />
        <ReportCard
          href="/reports/feed-shrinkage"
          title="Потери от усушки"
          subtitle="Списания по корму"
          desc="Сколько сырья и готового корма потеряно от усушки за период. Разрезы по ингредиенту или складу."
          icon="bag"
        />
        <ReportCard
          href="/reports/aging"
          title="Старение дебиторки"
          subtitle="AR aging — кто сколько должен"
          desc="Непогашенные продажи разбиты по бакетам просрочки: 0-30 / 31-60 / 61-90 / 90+ дней. Топ должников и сводка."
          icon="bag"
        />
      </div>
    </>
  );
}


function ReportCard({
  href, title, subtitle, desc, icon,
}: {
  href: string; title: string; subtitle: string; desc: string; icon: string;
}) {
  return (
    <Link
      href={href}
      style={{
        display: 'block',
        padding: 16,
        borderRadius: 8,
        border: '1px solid var(--border)',
        background: 'var(--bg-card, #fff)',
        textDecoration: 'none',
        color: 'var(--fg-1)',
        transition: 'all .15s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <Icon name={icon} size={18} />
        <strong style={{ fontSize: 15 }}>{title}</strong>
      </div>
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>
        {subtitle}
      </div>
      <div style={{ fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.4 }}>
        {desc}
      </div>
      <div style={{
        marginTop: 10, fontSize: 12, fontWeight: 600,
        color: 'var(--brand-orange)',
      }}>
        Открыть →
      </div>
    </Link>
  );
}
