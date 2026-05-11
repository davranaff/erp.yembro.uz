'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import { useCurrenciesSorted } from '@/hooks/useCurrencyRates';
import {
  useApplyTemplate,
  useBulkSetKind,
  useCancelPayout,
  useCompensationPlanForEmployee,
  useCreateAdjustment,
  useCreateRate,
  useCreateWorkSchedule,
  useDeleteAdjustment,
  useDeleteWorkSchedule,
  useDeleteWorkShift,
  useEmployeeAdjustments,
  useEmployeeBalance,
  useEmployeeCalendar,
  useEmployeePayouts,
  useSalaryRates,
  useSaveCompensationPlan,
  useSaveWorkShift,
  useScheduleTemplates,
  useWorkSchedules,
} from '@/hooks/usePayroll';
import { usePerson, useTerminatePerson } from '@/hooks/usePeople';
import { useHasLevel } from '@/hooks/usePermissions';
import type { WorkShiftKind } from '@/types/payroll';

import PayoutModal from './PayoutModal';
import WorkStatsRow from './WorkStatsRow';

type TabKey = 'info' | 'timesheet' | 'salary';

const KIND_LABEL: Record<WorkShiftKind, string> = {
  work: 'Работа',
  overtime: 'Переработка',
  vacation: 'Отпуск',
  sick_leave: 'Больничный',
  absence: 'Прогул',
  day_off: 'Выходной',
  holiday: 'Праздник',
};

const KIND_COLOR: Record<WorkShiftKind, string> = {
  work: '#86efac',
  overtime: '#16a34a',
  vacation: '#7dd3fc',
  sick_leave: '#fdba74',
  absence: '#fca5a5',
  day_off: '#e5e7eb',
  holiday: '#d8b4fe',
};

const COMP_TYPE_LABEL: Record<string, string> = {
  monthly_salary: 'Оклад в месяц',
  per_shift: 'Ставка за смену',
  per_hour: 'Ставка за час',
};

const PAYOUT_TYPE_LABEL: Record<string, string> = {
  advance: 'Аванс',
  salary: 'Зарплата',
  bonus: 'Премия',
  correction: 'Корректировка',
};

const ADJ_KIND_LABEL: Record<string, string> = {
  bonus: 'Премия',
  deduction: 'Удержание',
  correction_plus: 'Доначисление',
  correction_minus: 'Сторно',
};

const ADJ_POSITIVE = new Set(['bonus', 'correction_plus']);

function fmt(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n);
}

function ymd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

const monthNames = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

export default function PersonDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;
  const hasLevel = useHasLevel();
  const hrRw = hasLevel('hr', 'rw');
  const isAdmin = hasLevel('admin', 'admin');

  const [tab, setTab] = useState<TabKey>('info');
  const [showPayoutModal, setShowPayoutModal] = useState(false);

  const { data: person, isLoading } = usePerson(id);
  const { data: balance } = useEmployeeBalance(id);
  const terminate = useTerminatePerson();

  const handleTerminate = async () => {
    if (!person) return;
    if (!confirm(`Уволить «${person.user_full_name}»?\n\nГрафик и ставка будут закрыты сегодня.`)) return;
    try {
      const res = await terminate.mutateAsync({ id: person.id });
      const bal = Number(res.balance_at_termination);
      if (bal > 0) {
        alert(`Уволен. Должны выплатить: ${bal.toLocaleString('ru-RU')} сум`);
      } else if (bal < 0) {
        alert(`Уволен. Переплачено: ${Math.abs(bal).toLocaleString('ru-RU')} сум`);
      } else {
        alert('Уволен. Долгов нет.');
      }
    } catch (e) {
      alert((e as Error).message);
    }
  };

  if (isLoading) return <div className="page-hdr"><div><h1>Загружаем…</h1></div></div>;
  if (!person) return <div className="page-hdr"><div><h1>Сотрудник не найден</h1></div></div>;

  const balanceVal = balance ? Number(balance.balance_uzs) : 0;
  const accruedVal = balance ? Number(balance.accrued_total) : 0;
  const paidVal = balance ? Number(balance.paid_total) : 0;
  // «Осталось выплатить» — сколько компания должна (если +) или сотрудник переплачен (если −).
  const oweAmount = balanceVal;

  return (
    <>
      <div className="page-hdr">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => router.push('/people')}>
              <Icon name="chevron-left" size={12} /> К списку
            </button>
          </div>
          <h1>{person.user_full_name || '—'}</h1>
          <div className="sub" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Badge tone={person.is_active ? 'success' : 'neutral'} dot>
              {person.is_active ? 'Активен' : 'Уволен'}
            </Badge>
            {person.position_title && <span>· {person.position_title}</span>}
            {person.user_email && <span className="mono">· {person.user_email}</span>}
          </div>
        </div>
        <div className="actions">
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => window.open(`/people/${person.id}/payslip`, '_blank')}
          >
            Расчётный лист
          </button>
          {hrRw && person.is_active && (
            <button className="btn btn-primary btn-sm" onClick={() => setShowPayoutModal(true)}>
              <Icon name="plus" size={14} /> Платить
            </button>
          )}
          {isAdmin && person.is_active && (
            <button className="btn btn-ghost btn-sm" onClick={handleTerminate} disabled={terminate.isPending}>
              {terminate.isPending ? '…' : 'Уволить'}
            </button>
          )}
        </div>
      </div>

      {/* ── Блок «Сколько осталось выплатить» ── показываем только если
          баланс ненулевой. При oweAmount == 0 ничего не рисуем, чтобы не
          забивать страницу банальным «Расчёт чистый». ── */}
      {oweAmount !== 0 && (
        <div style={{
          marginTop: 4,
          padding: '20px 24px',
          borderRadius: 8,
          background: oweAmount > 0
            ? 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
            : 'linear-gradient(135deg, #fed7aa 0%, #fdba74 100%)',
          border: '1px solid',
          borderColor: oweAmount > 0 ? '#f59e0b' : '#ea580c',
        }}>
          <div style={{ fontSize: 12, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {oweAmount > 0 ? 'Должны выплатить' : 'Переплачено сотруднику'}
          </div>
          <div style={{
            fontSize: 36, fontWeight: 700, fontFamily: 'var(--mono, monospace)',
            color: oweAmount > 0 ? '#92400e' : '#9a3412',
            marginTop: 4,
          }}>
            {fmt(Math.abs(oweAmount))} <span style={{ fontSize: 18, fontWeight: 500 }}>сум</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 8 }}>
            Заработал к сегодня: <b>{fmt(accruedVal)}</b> сум · Уже выплачено: <b>{fmt(paidVal)}</b> сум
          </div>
        </div>
      )}

      <WorkStatsRow employeeId={person.id} />

      <div style={{ marginTop: 14, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'info', label: 'Инфо' },
            { value: 'timesheet', label: 'Табель' },
            { value: 'salary', label: 'Зарплата' },
          ]}
          value={tab}
          onChange={(v) => setTab(v as TabKey)}
        />
      </div>

      {tab === 'info' && <InfoTab person={person} hrRw={hrRw} />}
      {tab === 'timesheet' && <TimesheetTab employeeId={person.id} hrRw={hrRw} />}
      {tab === 'salary' && (
        <SalaryTab
          employeeId={person.id}
          hrRw={hrRw}
          onPay={() => setShowPayoutModal(true)}
        />
      )}

      {showPayoutModal && (
        <PayoutModal
          employeeId={person.id}
          employeeName={person.user_full_name || ''}
          onClose={() => setShowPayoutModal(false)}
        />
      )}
    </>
  );
}

// ─── Инфо: реквизиты + тип оплаты + ставка + график ──────────────────────

function InfoTab({
  person, hrRw,
}: {
  person: { id: string; user_email: string | null; work_phone: string; position_title: string; joined_at: string };
  hrRw: boolean;
}) {
  const employeeId = person.id;
  const { data: plan } = useCompensationPlanForEmployee(employeeId);
  const { data: rates = [] } = useSalaryRates(employeeId);
  const { data: schedules = [] } = useWorkSchedules(employeeId);
  const { data: templates = [] } = useScheduleTemplates();
  const { data: currencies = [] } = useCurrenciesSorted();

  const savePlan = useSaveCompensationPlan();
  const createRate = useCreateRate();
  const createSchedule = useCreateWorkSchedule();
  const deleteSchedule = useDeleteWorkSchedule();

  const [compType, setCompType] = useState(plan?.compensation_type || 'monthly_salary');
  const [planCurrency, setPlanCurrency] = useState(plan?.currency || '');
  const [rateAmount, setRateAmount] = useState('');
  const [rateCurrency, setRateCurrency] = useState('');
  const [rateFrom, setRateFrom] = useState(ymd(new Date()));

  const [tplId, setTplId] = useState('');
  const [schedFrom, setSchedFrom] = useState(ymd(startOfMonth(new Date())));

  useEffect(() => {
    if (plan) {
      setCompType(plan.compensation_type);
      setPlanCurrency(plan.currency);
      setRateCurrency((c) => c || plan.currency);
    } else if (currencies.length) {
      const uzs = currencies.find((c) => c.code === 'UZS') || currencies[0];
      setPlanCurrency((c) => c || uzs.id);
      setRateCurrency((c) => c || uzs.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan?.id, currencies.length]);

  const currentRate = rates.find((r) => !r.effective_to);
  const activeSchedule = schedules.find((s) => !s.effective_to);

  const handleSavePlan = () => {
    savePlan.mutate({
      id: plan?.id,
      employee: employeeId,
      compensation_type: compType as 'monthly_salary' | 'per_shift' | 'per_hour',
      currency: planCurrency,
    }, { onError: (e) => alert(e.message) });
  };

  const handleAddRate = () => {
    const amount = rateAmount.replace(/\s/g, '');
    if (!amount || Number(amount) <= 0) { alert('Введите сумму больше 0'); return; }
    createRate.mutate({
      employee: employeeId,
      amount,
      currency: rateCurrency || planCurrency,
      effective_from: rateFrom,
    }, {
      onSuccess: () => setRateAmount(''),
      onError: (e) => alert(e.message),
    });
  };

  const handleAssignSchedule = () => {
    if (!tplId) { alert('Выберите график'); return; }
    createSchedule.mutate({
      employee: employeeId,
      template: tplId,
      effective_from: schedFrom,
    }, { onError: (e) => alert(e.message) });
  };

  return (
    <>
      {/* Контактные данные */}
      <Panel title="Контакты">
        <div style={{ padding: 12, display: 'grid', gridTemplateColumns: '160px 1fr', rowGap: 10, columnGap: 16 }}>
          <div className="sub">Email</div>
          <div className="mono">{person.user_email || '—'}</div>
          <div className="sub">Телефон</div>
          <div className="mono">{person.work_phone || '—'}</div>
          <div className="sub">Должность</div>
          <div>{person.position_title || '—'}</div>
          <div className="sub">Принят</div>
          <div className="mono">{person.joined_at?.slice(0, 10) || '—'}</div>
        </div>
      </Panel>

      <div style={{ height: 12 }} />

      {/* Текущая ставка крупно */}
      <Panel title="Текущая ставка">
        <div style={{ padding: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--mono, monospace)' }}>
              {currentRate
                ? `${fmt(currentRate.amount)} ${currentRate.currency_code ?? ''}`
                : '— не задана —'}
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 4 }}>
              {plan ? COMP_TYPE_LABEL[plan.compensation_type] : 'тип оплаты не задан'}
              {currentRate ? ` · с ${currentRate.effective_from}` : ''}
            </div>
          </div>
        </div>

        {hrRw && (
          <div style={{ padding: 12, borderTop: '1px solid var(--bord-1)', background: 'var(--bg-soft)' }}>
            <div style={{ fontSize: 12, color: 'var(--fg-2)', marginBottom: 8 }}>Изменить ставку:</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Тип</label>
                <select
                  className="input" value={compType}
                  onChange={(e) => setCompType(e.target.value as never)}
                  style={{ width: 180, display: 'block' }}
                >
                  <option value="monthly_salary">Оклад в месяц</option>
                  <option value="per_shift">За смену</option>
                  <option value="per_hour">За час</option>
                </select>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={handleSavePlan} disabled={savePlan.isPending}>
                Сохранить тип
              </button>
              <div style={{ flex: 1 }} />
              <div>
                <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Сумма</label>
                <input
                  className="input" value={rateAmount}
                  onChange={(e) => setRateAmount(e.target.value)}
                  placeholder="3 000 000"
                  style={{ width: 140, display: 'block' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Валюта</label>
                <select
                  className="input" value={rateCurrency}
                  onChange={(e) => setRateCurrency(e.target.value)}
                  style={{ width: 90, display: 'block' }}
                >
                  {currencies.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>С даты</label>
                <input
                  className="input" type="date" value={rateFrom}
                  onChange={(e) => setRateFrom(e.target.value)}
                  style={{ width: 150, display: 'block' }}
                />
              </div>
              <button className="btn btn-primary btn-sm" onClick={handleAddRate} disabled={createRate.isPending}>
                Установить
              </button>
            </div>
          </div>
        )}

        {rates.length > 1 && (
          <details style={{ borderTop: '1px solid var(--bord-1)', padding: 12 }}>
            <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--fg-2)' }}>
              История ставок ({rates.length})
            </summary>
            <DataTable
              rows={rates}
              rowKey={(r) => r.id}
              columns={[
                { key: 'amount', label: 'Сумма', mono: true, align: 'right',
                  render: (r) => `${fmt(r.amount)} ${r.currency_code ?? ''}` },
                { key: 'from', label: 'С', mono: true, render: (r) => r.effective_from },
                { key: 'to', label: 'По', mono: true,
                  render: (r) => r.effective_to || <Badge tone="success">текущая</Badge> },
              ]}
            />
          </details>
        )}
      </Panel>

      <div style={{ height: 12 }} />

      {/* График */}
      <Panel title="График работы">
        <div style={{ padding: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 500 }}>
            {activeSchedule
              ? activeSchedule.template_code || '—'
              : '— график не назначен —'}
          </div>
          {activeSchedule && (
            <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 4 }}>
              с {activeSchedule.effective_from}
              {activeSchedule.effective_to ? ` по ${activeSchedule.effective_to}` : ''}
            </div>
          )}
        </div>
        {hrRw && (
          <div style={{ padding: 12, borderTop: '1px solid var(--bord-1)', background: 'var(--bg-soft)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Шаблон</label>
              <select
                className="input" value={tplId}
                onChange={(e) => setTplId(e.target.value)}
                style={{ width: 220, display: 'block' }}
              >
                <option value="">— выбрать —</option>
                {templates.filter((t) => t.is_active).map((t) => (
                  <option key={t.id} value={t.id}>{t.code} · {t.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>С даты</label>
              <input
                className="input" type="date" value={schedFrom}
                onChange={(e) => setSchedFrom(e.target.value)}
                style={{ width: 150, display: 'block' }}
              />
            </div>
            <button className="btn btn-primary btn-sm" onClick={handleAssignSchedule} disabled={createSchedule.isPending}>
              Назначить
            </button>
            {activeSchedule && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  if (confirm('Удалить текущий график?')) {
                    deleteSchedule.mutate(activeSchedule.id, { onError: (e) => alert(e.message) });
                  }
                }}
              >
                Снять
              </button>
            )}
          </div>
        )}
      </Panel>
    </>
  );
}

// ─── Табель ───────────────────────────────────────────────────────────────

function TimesheetTab({
  employeeId, hrRw,
}: { employeeId: string; hrRw: boolean }) {
  const today = new Date();
  const [month, setMonth] = useState({ y: today.getFullYear(), m: today.getMonth() });
  const monthStart = new Date(month.y, month.m, 1);
  const monthEnd = endOfMonth(monthStart);
  const fromStr = ymd(monthStart);
  const toStr = ymd(monthEnd);
  const { data: cal } = useEmployeeCalendar(employeeId, fromStr, toStr);
  const { data: templates = [] } = useScheduleTemplates();
  const apply = useApplyTemplate();
  const saveShift = useSaveWorkShift();
  const delShift = useDeleteWorkShift();
  const bulkSet = useBulkSetKind();
  const [editing, setEditing] = useState<{ date: string; id?: string; kind: WorkShiftKind } | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const expectedByDate = new Map<string, { kind: WorkShiftKind }>();
  cal?.expected.forEach((e) => expectedByDate.set(e.date, { kind: e.kind }));
  const actualByDate = new Map<string, { id: string; kind: WorkShiftKind }>();
  cal?.actual.forEach((a) => actualByDate.set(a.date, { id: a.id, kind: a.kind }));

  const firstWeekday = (monthStart.getDay() + 6) % 7;
  const daysInMonth = monthEnd.getDate();
  const cells: Array<{ date: string | null; day: number | null }> = [];
  for (let i = 0; i < firstWeekday; i++) cells.push({ date: null, day: null });
  for (let d = 1; d <= daysInMonth; d++) {
    const dt = new Date(month.y, month.m, d);
    cells.push({ date: ymd(dt), day: d });
  }

  const handleApply = () => {
    const tpl = templates.find((t) => t.is_active);
    if (!tpl) { alert('Сначала создайте шаблон в /payroll/templates'); return; }
    apply.mutate({
      employee: employeeId, template: tpl.id,
      from_date: fromStr, to_date: toStr,
    }, {
      onError: (e) => alert(e.message),
      onSuccess: (r) => alert(`Создано смен: ${r.created}`),
    });
  };

  const applyBulkKind = (k: WorkShiftKind) => {
    if (selected.size === 0) { alert('Выделите дни'); return; }
    bulkSet.mutate({
      employee: employeeId,
      dates: Array.from(selected).sort(),
      kind: k,
    }, {
      onSuccess: () => { setSelected(new Set()); setSelectMode(false); },
      onError: (e) => alert(e.message),
    });
  };

  return (
    <Panel
      title={`${monthNames[month.m]} ${month.y}`}
      tools={
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setMonth((p) => p.m === 0 ? { y: p.y - 1, m: 11 } : { y: p.y, m: p.m - 1 })}>←</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setMonth({ y: today.getFullYear(), m: today.getMonth() })}>Сегодня</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setMonth((p) => p.m === 11 ? { y: p.y + 1, m: 0 } : { y: p.y, m: p.m + 1 })}>→</button>
          {hrRw && (
            <>
              <button className="btn btn-secondary btn-sm" onClick={handleApply} disabled={apply.isPending}>
                Заполнить по графику
              </button>
              <button
                className={selectMode ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm'}
                onClick={() => { setSelectMode(!selectMode); setSelected(new Set()); }}
              >
                {selectMode ? `Выделено: ${selected.size}` : 'Выбрать дни'}
              </button>
              {selectMode && selected.size > 0 && (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={() => applyBulkKind('vacation')}>→ Отпуск</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => applyBulkKind('sick_leave')}>→ Больничный</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => applyBulkKind('absence')}>→ Прогул</button>
                </>
              )}
            </>
          )}
        </div>
      }
    >
      <div style={{ padding: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, marginBottom: 8 }}>
          {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((w) => (
            <div key={w} style={{ textAlign: 'center', fontSize: 11, color: 'var(--fg-3)', padding: '4px 0' }}>{w}</div>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6 }}>
          {cells.map((c, idx) => {
            if (!c.date) return <div key={idx} style={{ minHeight: 92 }} />;
            const actual = actualByDate.get(c.date);
            const expected = expectedByDate.get(c.date);
            const kind = actual?.kind || expected?.kind || null;
            const color = kind ? KIND_COLOR[kind] : 'transparent';
            const dimmed = !actual && !!expected;
            const isSelected = selected.has(c.date);
            return (
              <button
                key={c.date}
                type="button"
                onClick={() => {
                  if (!hrRw) return;
                  if (selectMode) {
                    const next = new Set(selected);
                    if (isSelected) next.delete(c.date!);
                    else next.add(c.date!);
                    setSelected(next);
                  } else {
                    setEditing({ date: c.date!, id: actual?.id, kind: kind || 'work' });
                  }
                }}
                style={{
                  minHeight: 92,
                  background: color,
                  border: isSelected ? '3px solid #ea580c' : '1px solid var(--bord-1)',
                  borderRadius: 6,
                  padding: 10,
                  cursor: hrRw ? 'pointer' : 'default',
                  opacity: dimmed ? 0.55 : 1,
                  textAlign: 'left',
                  fontFamily: 'inherit',
                  boxShadow: isSelected
                    ? '0 0 0 2px rgba(234, 88, 12, 0.2), 0 4px 8px rgba(234, 88, 12, 0.25)'
                    : 'none',
                  transform: isSelected ? 'scale(1.02)' : 'none',
                  transition: 'transform 100ms, box-shadow 100ms',
                  position: 'relative',
                }}
                title={kind ? KIND_LABEL[kind] : ''}
              >
                {isSelected && (
                  <div style={{
                    position: 'absolute', top: 4, right: 6,
                    fontSize: 14, color: '#ea580c', fontWeight: 700,
                  }}>✓</div>
                )}
                <div style={{ fontWeight: 700, fontSize: 16 }}>{c.day}</div>
                {kind && (
                  <div style={{ fontSize: 11, marginTop: 4, color: 'var(--fg-1)' }}>
                    {KIND_LABEL[kind]}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {editing && (
        <ShiftEditModal
          state={editing}
          onSave={(payload) => {
            saveShift.mutateAsync({
              id: editing.id,
              employee: editing.id ? undefined : employeeId,
              shift_date: editing.id ? undefined : editing.date,
              kind: payload.kind,
              hours: payload.hours,
              notes: payload.notes,
            }).then(() => setEditing(null)).catch((e) => alert(e.message));
          }}
          onDelete={() => {
            if (!editing.id) return;
            delShift.mutate(editing.id, {
              onSuccess: () => setEditing(null),
              onError: (e) => alert(e.message),
            });
          }}
          onClose={() => setEditing(null)}
        />
      )}
    </Panel>
  );
}

function ShiftEditModal({
  state, onSave, onDelete, onClose,
}: {
  state: { date: string; id?: string; kind: WorkShiftKind };
  onSave: (p: { kind: WorkShiftKind; hours: string | null; notes: string }) => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<WorkShiftKind>(state.kind);
  const [hours, setHours] = useState('');
  const [notes, setNotes] = useState('');
  return (
    <Modal
      title={state.date}
      onClose={onClose}
      footer={
        <>
          {state.id && (
            <button className="btn btn-ghost btn-sm" onClick={onDelete}>Удалить</button>
          )}
          <button className="btn btn-primary btn-sm" onClick={() => onSave({ kind, hours: hours || null, notes })}>
            Сохранить
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gap: 10 }}>
        <label>Что было в этот день</label>
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value as WorkShiftKind)}>
          {(Object.keys(KIND_LABEL) as WorkShiftKind[]).map((k) => (
            <option key={k} value={k}>{KIND_LABEL[k]}</option>
          ))}
        </select>
        <label>Часов (если отличается от стандарта)</label>
        <input className="input" inputMode="decimal" value={hours} onChange={(e) => setHours(e.target.value)} placeholder="например 8" />
        <label>Заметка</label>
        <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
    </Modal>
  );
}

// ─── Зарплата: выплаты + корректировки ───────────────────────────────────

function SalaryTab({
  employeeId, hrRw, onPay,
}: { employeeId: string; hrRw: boolean; onPay: () => void }) {
  const { data: payouts = [] } = useEmployeePayouts(employeeId);
  const { data: adjustments = [] } = useEmployeeAdjustments(employeeId);
  const hasLevel = useHasLevel();
  const isAdmin = hasLevel('admin', 'admin');
  const cancel = useCancelPayout();
  const createAdj = useCreateAdjustment();
  const delAdj = useDeleteAdjustment();

  const today = ymd(new Date());
  const [adjOpen, setAdjOpen] = useState(false);
  const [adjKind, setAdjKind] = useState<'bonus' | 'deduction'>('bonus');
  const [adjAmount, setAdjAmount] = useState('');
  const [adjDate, setAdjDate] = useState(today);
  const [adjReason, setAdjReason] = useState('');

  const handleCancel = (id: string) => {
    const reason = prompt('Причина отмены:') || '';
    if (!confirm('Отменить выплату? Деньги вернутся в кассу.')) return;
    cancel.mutate({ id, reason }, { onError: (e) => alert(e.message) });
  };

  const handleCreateAdj = () => {
    const amt = adjAmount.replace(/\s/g, '');
    if (!amt || Number(amt) <= 0) { alert('Введите сумму больше 0'); return; }
    createAdj.mutate({
      employee: employeeId,
      kind: adjKind,
      effective_date: adjDate,
      amount_uzs: amt,
      reason: adjReason,
    }, {
      onSuccess: () => {
        setAdjOpen(false);
        setAdjAmount('');
        setAdjReason('');
      },
      onError: (e) => alert(e.message),
    });
  };

  return (
    <>
      <Panel
        title="Выплаты"
        tools={hrRw ? <button className="btn btn-primary btn-sm" onClick={onPay}><Icon name="plus" size={14} /> Платить</button> : null}
      >
        <DataTable
          rows={payouts}
          rowKey={(p) => p.id}
          emptyMessage="Выплат пока не было."
          columns={[
            { key: 'doc', label: 'Документ', mono: true, render: (p) => p.payment_doc_number || '—' },
            { key: 'type', label: 'Тип', render: (p) => <Badge tone="info">{PAYOUT_TYPE_LABEL[p.type] ?? p.type}</Badge> },
            { key: 'amount', label: 'Сумма', mono: true, align: 'right', render: (p) => fmt(p.amount_uzs) },
            { key: 'period', label: 'За период', mono: true, render: (p) => `${p.period_from} — ${p.period_to}` },
            { key: 'status', label: 'Статус', render: (p) => (
              <Badge tone={p.payment_status === 'cancelled' ? 'neutral' : p.payment_status === 'posted' ? 'success' : 'warn'}>
                {p.payment_status === 'posted' ? 'Выплачено' : p.payment_status === 'cancelled' ? 'Отменено' : p.payment_status}
              </Badge>
            ) },
            ...(isAdmin ? [{ key: 'act', label: '', width: 90, align: 'right' as const,
              render: (p: import('@/types/payroll').PayrollPayout) => (
                p.payment_status === 'posted' ? (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleCancel(p.id)} disabled={cancel.isPending}>
                    Отменить
                  </button>
                ) : null
              ),
            }] : []),
          ]}
        />
      </Panel>

      <div style={{ height: 12 }} />

      <Panel
        title="Премии и удержания"
        tools={
          hrRw ? (
            <button className="btn btn-ghost btn-sm" onClick={() => setAdjOpen(!adjOpen)}>
              {adjOpen ? 'Скрыть' : '+ Добавить'}
            </button>
          ) : null
        }
      >
        {hrRw && adjOpen && (
          <div style={{ padding: 12, background: 'var(--bg-soft)', borderBottom: '1px solid var(--bord-1)', display: 'grid', gridTemplateColumns: '140px 140px 160px 1fr 110px', gap: 8, alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Тип</label>
              <select className="input" value={adjKind} onChange={(e) => setAdjKind(e.target.value as never)}>
                <option value="bonus">Премия (+)</option>
                <option value="deduction">Удержание (−)</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Дата</label>
              <input className="input" type="date" value={adjDate} onChange={(e) => setAdjDate(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Сумма</label>
              <input className="input" inputMode="decimal" value={adjAmount} onChange={(e) => setAdjAmount(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)' }}>Причина</label>
              <input className="input" value={adjReason} onChange={(e) => setAdjReason(e.target.value)} placeholder="за что" />
            </div>
            <button className="btn btn-primary btn-sm" onClick={handleCreateAdj} disabled={createAdj.isPending}>
              Сохранить
            </button>
          </div>
        )}
        <DataTable
          rows={adjustments}
          rowKey={(a) => a.id}
          emptyMessage="Премий и удержаний нет."
          columns={[
            { key: 'kind', label: 'Тип', render: (a) => (
              <Badge tone={ADJ_POSITIVE.has(a.kind) ? 'success' : 'warn'}>
                {ADJ_KIND_LABEL[a.kind] ?? a.kind}
              </Badge>
            ) },
            { key: 'date', label: 'Дата', mono: true, render: (a) => a.effective_date },
            { key: 'amount', label: 'Сумма', mono: true, align: 'right',
              render: (a) => {
                const sign = ADJ_POSITIVE.has(a.kind) ? '+' : '−';
                const color = ADJ_POSITIVE.has(a.kind) ? 'var(--accent-success)' : 'var(--accent-warn)';
                return <span style={{ color }}>{sign}{fmt(a.amount_uzs)}</span>;
              } },
            { key: 'reason', label: 'Причина', render: (a) => a.reason || '—' },
            ...(hrRw ? [{ key: 'act', label: '', width: 80, align: 'right' as const,
              render: (a: import('@/types/payroll').PayrollAdjustment) => (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    if (!confirm('Удалить?')) return;
                    delAdj.mutate(a.id, { onError: (e) => alert(e.message) });
                  }}
                >Удалить</button>
              ),
            }] : []),
          ]}
        />
      </Panel>
    </>
  );
}
