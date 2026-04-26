'use client';

import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useHolding } from '@/hooks/useHolding';
import type { HoldingCompany } from '@/types/auth';

const DIRECTION_LABEL: Record<string, string> = {
  broiler: 'Бройлер',
  egg: 'Яичное',
  mixed: 'Смешанное',
};

function fmtMoney(v: string | null | undefined) {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function firstDayOfMonthISO(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function firstDayOfQuarterISO(): string {
  const d = new Date();
  const q = Math.floor(d.getMonth() / 3);
  return new Date(d.getFullYear(), q * 3, 1).toISOString().slice(0, 10);
}

function firstDayOfYearISO(): string {
  return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function HoldingPage() {
  const [periodFrom, setPeriodFrom] = useState<string>(firstDayOfMonthISO());
  const [periodTo, setPeriodTo] = useState<string>(todayISO());

  const { data, isLoading, error, refetch, isFetching } = useHolding({
    period_from: periodFrom,
    period_to: periodTo,
  });

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Холдинг · консолидация</h1>
          <div className="sub">Сводный вид по всем компаниям пользователя</div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} />
            {isFetching ? '…' : 'Обновить'}
          </button>
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard
          tone="orange"
          iconName="building"
          label="Компаний"
          sub="в холдинге"
          value={data ? String(data.totals.companies) : '—'}
          meta="доступные"
        />
        <KpiCard
          tone="blue"
          iconName="factory"
          label="Модулей всего"
          sub="по компаниям"
          value={data ? String(data.totals.modules) : '—'}
        />
        <KpiCard
          tone="green"
          iconName="chart"
          label="Закупов (период)"
          sub={`${periodFrom}..${periodTo}`}
          value={data ? fmtMoney(data.totals.purchases_confirmed_uzs) : '—'}
          valueSuffix="UZS"
        />
        <KpiCard
          tone="red"
          iconName="close"
          label="Кредиторка"
          sub="всё время (не period-scoped)"
          value={data ? fmtMoney(data.totals.creditor_balance_uzs) : '—'}
          valueSuffix="UZS"
        />
      </div>

      <div className="filter-bar">
        <div className="filter-cell">
          <label>С</label>
          <input
            className="input"
            type="date"
            value={periodFrom}
            onChange={(e) => setPeriodFrom(e.target.value)}
          />
        </div>
        <div className="filter-cell">
          <label>По</label>
          <input
            className="input"
            type="date"
            value={periodTo}
            onChange={(e) => setPeriodTo(e.target.value)}
          />
        </div>
        <div className="filter-cell">
          <label>Пресет</label>
          <div className="filter-presets">
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => { setPeriodFrom(firstDayOfMonthISO()); setPeriodTo(todayISO()); }}
            >
              Месяц
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => { setPeriodFrom(firstDayOfQuarterISO()); setPeriodTo(todayISO()); }}
            >
              Квартал
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => { setPeriodFrom(firstDayOfYearISO()); setPeriodTo(todayISO()); }}
            >
              Год · YTD
            </button>
          </div>
        </div>
      </div>

      <Panel title="Компании холдинга" flush>
        <DataTable<HoldingCompany>
          isLoading={isLoading}
          rows={data?.companies}
          rowKey={(c) => c.id}
          error={error}
          emptyMessage="У вас нет доступа ни к одной организации."
          columns={[
            { key: 'code', label: 'Код',
              render: (c) => <span className="badge id">{c.code}</span> },
            { key: 'name', label: 'Компания', cellStyle: { fontWeight: 600 },
              render: (c) => c.name },
            { key: 'dir', label: 'Направление',
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (c) => DIRECTION_LABEL[c.direction] ?? c.direction },
            { key: 'purchases', label: 'Закупы', align: 'right', mono: true,
              render: (c) => fmtMoney(c.purchases_confirmed_uzs) },
            { key: 'in', label: 'Платежи вх.', align: 'right', mono: true,
              cellStyle: { color: 'var(--success)' },
              render: (c) => fmtMoney(c.payments_in_uzs) },
            { key: 'out', label: 'Платежи исх.', align: 'right', mono: true,
              cellStyle: { color: 'var(--danger)' },
              render: (c) => fmtMoney(c.payments_out_uzs) },
            { key: 'cred', label: 'Кредиторка', align: 'right', mono: true,
              cellStyle: { fontWeight: 600 },
              render: (c) => fmtMoney(c.creditor_balance_uzs) },
            { key: 'batches', label: 'Партий', align: 'right', mono: true,
              render: (c) => c.active_batches },
            { key: 'modules', label: 'Модулей', align: 'right', mono: true,
              render: (c) => c.modules_count },
            { key: 'status', label: 'Статус',
              render: (c) => {
                const creditor = parseFloat(c.creditor_balance_uzs || '0');
                const tone: 'success' | 'warn' = creditor > 0 ? 'warn' : 'success';
                return <Badge tone={tone} dot>{creditor > 0 ? 'Есть долг' : 'Норма'}</Badge>;
              } },
          ]}
        />
      </Panel>

      <div
        style={{
          padding: 10,
          background: 'var(--bg-subtle)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          fontSize: 12,
          color: 'var(--fg-3)',
          marginTop: 12,
        }}
      >
        <b style={{ color: 'var(--fg-1)' }}>Изоляция данных компаний — железная.</b>{' '}
        Этот экран — единственное место, где директор холдинга видит агрегаты сразу по нескольким компаниям. Операционные данные одной компании недоступны из контекста другой.
      </div>
    </>
  );
}
