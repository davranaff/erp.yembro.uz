'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useAllBalances } from '@/hooks/usePayroll';
import { useHasLevel } from '@/hooks/usePermissions';

import QuickAdjustmentPopover from './QuickAdjustmentPopover';

const COMP_LABEL: Record<string, string> = {
  monthly_salary: 'Оклад',
  per_shift: 'Смена',
  per_hour: 'Час',
};

const RUS_MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн',
                    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

function fmt(n: number | string | null | undefined): string {
  const v = typeof n === 'number' ? n : Number(n ?? 0);
  if (!Number.isFinite(v)) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(v);
}

function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function fmtMonth(ym: string): string {
  const [y, m] = ym.split('-');
  return `${RUS_MONTHS[parseInt(m, 10) - 1]} '${y.slice(2)}`;
}

export default function PayrollBalancesPage() {
  const today = new Date();
  const [asOf, setAsOf] = useState(ymd(today));
  const [includeInactive, setIncludeInactive] = useState(false);
  const [popover, setPopover] = useState<{
    employeeId: string;
    employeeName: string;
    kind: 'bonus' | 'deduction';
    anchor: { top: number; left: number };
  } | null>(null);

  const hasLevel = useHasLevel();
  const canAdjust = hasLevel('hr', 'rw');

  const { data, isLoading, error } = useAllBalances(asOf, includeInactive);
  const rows = data?.rows ?? [];
  const totals = data?.totals;
  const monthly = data?.monthly_fund ?? [];

  const openPopover = (
    e: React.MouseEvent<HTMLButtonElement>,
    employeeId: string,
    employeeName: string,
    kind: 'bonus' | 'deduction',
  ) => {
    const r = e.currentTarget.getBoundingClientRect();
    // Открываем попап под кнопкой и слегка левее, чтобы не вываливался за край.
    setPopover({
      employeeId, employeeName, kind,
      anchor: { top: r.bottom + 4, left: Math.max(8, r.right - 280) },
    });
  };

  // KPI
  const totalDebt = rows
    .filter((r) => Number(r.balance_uzs) > 0)
    .reduce((s, r) => s + Number(r.balance_uzs), 0);
  const totalOverpaid = rows
    .filter((r) => Number(r.balance_uzs) < 0)
    .reduce((s, r) => s + Math.abs(Number(r.balance_uzs)), 0);

  // Текущий месяц — последний элемент monthly_fund
  const currentMonth = monthly[monthly.length - 1];
  const monthAccrued = currentMonth ? Number(currentMonth.accrued_uzs) : 0;
  const monthPaid = currentMonth ? Number(currentMonth.paid_uzs) : 0;

  // Max для масштабирования графика
  const maxFund = useMemo(() => {
    const all = monthly.flatMap((m) => [Number(m.accrued_uzs), Number(m.paid_uzs)]);
    return Math.max(...all, 1);
  }, [monthly]);

  const att = totals?.attendance_month;
  const totalDays = att
    ? att.work + att.overtime + att.vacation + att.sick_leave + att.absence + att.day_off + att.holiday
    : 0;
  const workedDays = att ? att.work + att.overtime : 0;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Аналитика зарплаты</h1>
          <div className="sub">Фонд ЗП, явка и долги по сотрудникам</div>
        </div>
        <div className="actions" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ fontSize: 12, color: 'var(--fg-2)' }}>
            На дату:&nbsp;
            <input
              className="input"
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              style={{ width: 150 }}
            />
          </label>
          <label style={{ fontSize: 12, color: 'var(--fg-2)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            Включая уволенных
          </label>
        </div>
      </div>

      {/* Большие KPI: текущий месяц и долги */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 12 }}>
        <KpiCard
          label="Фонд ЗП в этом месяце"
          sub="начислено сотрудникам"
          value={fmt(monthAccrued)} valueSuffix="сум" tone="blue"
        />
        <KpiCard
          label="Выплачено в этом месяце"
          sub="из кассы"
          value={fmt(monthPaid)} valueSuffix="сум" tone="green"
        />
        <KpiCard
          label="Должны выплатить"
          sub={`${rows.filter((r) => Number(r.balance_uzs) > 0).length} сотруд.`}
          value={fmt(totalDebt)} valueSuffix="сум"
          tone={totalDebt > 0 ? 'orange' : 'blue'}
        />
        <KpiCard
          label="Переплачено"
          sub={`${rows.filter((r) => Number(r.balance_uzs) < 0).length} сотруд.`}
          value={fmt(totalOverpaid)} valueSuffix="сум"
          tone={totalOverpaid > 0 ? 'red' : 'blue'}
        />
      </div>

      {/* Явка по компании в текущем месяце */}
      {att && (
        <Panel title={`Явка в этом месяце — всего ${totalDays} дней`} style={{ marginBottom: 12 }}>
          <div style={{ padding: 16, display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
            <AttendanceChip label="Отработано" value={workedDays} color="#16a34a" total={totalDays} />
            <AttendanceChip label="Отпуск" value={att.vacation} color="#0ea5e9" total={totalDays} />
            <AttendanceChip label="Больничный" value={att.sick_leave} color="#ea580c" total={totalDays} />
            <AttendanceChip label="Прогул" value={att.absence} color="#dc2626" total={totalDays} />
            <AttendanceChip label="Праздник" value={att.holiday} color="#a855f7" total={totalDays} />
          </div>
        </Panel>
      )}

      {/* График фонда ЗП по 12 месяцам */}
      {monthly.length > 0 && (
        <Panel title="Фонд ЗП по месяцам (последние 12)" style={{ marginBottom: 12 }}>
          <div style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 200 }}>
              {monthly.map((m) => {
                const accrued = Number(m.accrued_uzs);
                const paid = Number(m.paid_uzs);
                const accruedH = maxFund > 0 ? Math.max(2, (accrued / maxFund) * 160) : 0;
                const paidH = maxFund > 0 ? Math.max(0, (paid / maxFund) * 160) : 0;
                return (
                  <div key={m.month} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                    <div style={{ display: 'flex', flex: 1, alignItems: 'flex-end', gap: 3, width: '100%', justifyContent: 'center' }}>
                      <div
                        title={`Начислено: ${fmt(accrued)}`}
                        style={{ width: 14, height: accruedH, background: '#3b82f6', borderRadius: '3px 3px 0 0' }}
                      />
                      <div
                        title={`Выплачено: ${fmt(paid)}`}
                        style={{ width: 14, height: paidH, background: '#16a34a', borderRadius: '3px 3px 0 0' }}
                      />
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>{fmtMonth(m.month)}</div>
                  </div>
                );
              })}
            </div>
            <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 11, color: 'var(--fg-2)' }}>
              <span><span style={{ display: 'inline-block', width: 12, height: 8, background: '#3b82f6', verticalAlign: 'middle' }} /> Начислено</span>
              <span><span style={{ display: 'inline-block', width: 12, height: 8, background: '#16a34a', verticalAlign: 'middle' }} /> Выплачено</span>
            </div>
          </div>
        </Panel>
      )}

      {/* Список сотрудников */}
      <Panel title="По сотрудникам" flush>
        <DataTable
          isLoading={isLoading}
          rows={rows}
          rowKey={(r) => r.employee_id}
          error={error}
          emptyMessage="Нет данных."
          columns={[
            { key: 'name', label: 'Сотрудник',
              render: (r) => (
                <Link href={`/people/${r.employee_id}`} style={{ color: 'inherit', textDecoration: 'none', fontWeight: 500 }}>
                  {r.full_name || '—'}
                </Link>
              ) },
            { key: 'pos', label: 'Должность', cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (r) => r.position_title || '—' },
            { key: 'comp', label: 'Тип',
              render: (r) => r.compensation_type
                ? <Badge tone="info">{COMP_LABEL[r.compensation_type] ?? r.compensation_type}</Badge>
                : <span style={{ color: 'var(--fg-3)' }}>—</span> },
            { key: 'work', label: 'Отработано', mono: true, align: 'right',
              cellStyle: { fontSize: 12 },
              render: (r) => {
                const w = r.attendance_month.work + r.attendance_month.overtime;
                return w > 0 ? `${w} дн` : '—';
              } },
            { key: 'absent', label: 'Пропущено', mono: true, align: 'right',
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (r) => {
                const a = r.attendance_month;
                const miss = a.vacation + a.sick_leave + a.absence;
                if (miss === 0) return '—';
                const parts = [];
                if (a.vacation) parts.push(`${a.vacation} отп.`);
                if (a.sick_leave) parts.push(`${a.sick_leave} б/л`);
                if (a.absence) parts.push(`${a.absence} прог.`);
                return parts.join(', ');
              } },
            { key: 'paid', label: 'Выплачено', mono: true, align: 'right',
              render: (r) => fmt(r.paid_total) },
            { key: 'balance', label: 'Баланс', mono: true, align: 'right',
              render: (r) => {
                const v = Number(r.balance_uzs);
                const tone = v > 0 ? '#16a34a' : v < 0 ? '#dc2626' : 'var(--fg-2)';
                return <span style={{ color: tone, fontWeight: 600 }}>{fmt(v)}</span>;
              } },
            { key: 'status', label: '',
              render: (r) => r.is_active
                ? <Badge tone="success" dot>Активен</Badge>
                : <Badge tone="neutral" dot>Уволен</Badge> },
            ...(canAdjust ? [{
              key: 'quick', label: 'Сегодня', align: 'right' as const,
              render: (r: typeof rows[number]) => r.is_active
                ? (
                  <span style={{ display: 'inline-flex', gap: 4 }}>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={(e) => openPopover(e, r.employee_id, r.full_name || '—', 'bonus')}
                      title="Добавить премию / доплату за сегодня"
                      style={{
                        background: '#16a34a', color: '#fff', borderColor: '#16a34a',
                        padding: '2px 8px', fontWeight: 700, minWidth: 28,
                      }}
                    >+</button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={(e) => openPopover(e, r.employee_id, r.full_name || '—', 'deduction')}
                      title="Удержать (штраф / опоздание)"
                      style={{
                        background: '#dc2626', color: '#fff', borderColor: '#dc2626',
                        padding: '2px 8px', fontWeight: 700, minWidth: 28,
                      }}
                    >−</button>
                  </span>
                )
                : <span style={{ color: 'var(--fg-3)' }}>—</span>,
            }] : []),
          ]}
        />
      </Panel>

      {popover && (
        <QuickAdjustmentPopover
          employeeId={popover.employeeId}
          employeeName={popover.employeeName}
          kind={popover.kind}
          anchor={popover.anchor}
          onClose={() => setPopover(null)}
        />
      )}
    </>
  );
}

function AttendanceChip({
  label, value, color, total,
}: { label: string; value: number; color: string; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 2 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>дн · {pct}%</div>
      </div>
      <div style={{
        marginTop: 6, height: 4, background: 'var(--bg-soft)',
        borderRadius: 2, overflow: 'hidden',
      }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color }} />
      </div>
    </div>
  );
}
