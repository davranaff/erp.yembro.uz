'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useSubaccounts } from '@/hooks/useAccounts';
import { useModules } from '@/hooks/useModules';
import {
  paymentsCrud,
  useCancelPayment,
  usePostPayment,
  useReversePayment,
} from '@/hooks/usePayments';
import { useHasLevel } from '@/hooks/usePermissions';
import type { Payment, PaymentKind, PaymentStatus } from '@/types/auth';

import OpexModal from './OpexModal';
import PaymentDrawer from './PaymentDrawer';

const KIND_LABEL: Record<PaymentKind, string> = {
  counterparty: 'Контрагент',
  opex: 'Расход',
  income: 'Доход',
  salary: 'Зарплата',
  internal: 'Перемещение',
};

const KIND_TONE: Record<PaymentKind, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  counterparty: 'info',
  opex: 'danger',
  income: 'success',
  salary: 'warn',
  internal: 'neutral',
};

const STATUS_LABEL: Record<PaymentStatus, string> = {
  draft: 'Черновик',
  confirmed: 'Подтверждён',
  posted: 'Проведён',
  cancelled: 'Отменён',
};

const STATUS_TONE: Record<PaymentStatus, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  draft: 'neutral',
  confirmed: 'info',
  posted: 'success',
  cancelled: 'danger',
};

function fmtUzs(v: string | number | null | undefined, short = false): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  if (short && Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'М';
  if (short && Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'К';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoISO(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

type StatusTab = 'all' | 'posted' | 'draft' | 'cancelled';

export default function CashboxPage() {
  const [accountCode, setAccountCode] = useState<'all' | '50.01' | '51.01'>('all');
  const [dateFrom, setDateFrom] = useState(daysAgoISO(30));
  const [dateTo, setDateTo] = useState(todayISO());
  const [moduleId, setModuleId] = useState('');
  const [statusTab, setStatusTab] = useState<StatusTab>('posted');
  const [opexOpen, setOpexOpen] = useState<false | 'out' | 'in'>(false);
  const [drawerPayment, setDrawerPayment] = useState<Payment | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('ledger', 'rw');

  const { data: subs } = useSubaccounts();
  const { data: modules } = useModules();
  const post = usePostPayment();
  const cancel = useCancelPayment();
  const reverse = useReversePayment();
  const remove = paymentsCrud.useDelete();

  // Фильтрованный список платежей
  const filter: Record<string, string> = {};
  if (statusTab !== 'all') filter.status = statusTab;
  if (accountCode !== 'all' && subs) {
    const s = subs.find((x) => x.code === accountCode);
    if (s) filter.cash_subaccount = s.id;
  }
  if (moduleId) filter.module = moduleId;

  const { data: payments, isLoading } = paymentsCrud.useList(filter);

  // Для KPI/балансов всегда нужны posted (без зависимости от вкладки)
  const { data: postedPayments } = paymentsCrud.useList({ status: 'posted' });

  // Клиентская фильтрация по дате (поскольку там нет прямого фильтра)
  const filteredPayments = useMemo(() => {
    if (!payments) return [];
    return payments.filter((p) => {
      if (dateFrom && p.date < dateFrom) return false;
      if (dateTo && p.date > dateTo) return false;
      return true;
    });
  }, [payments, dateFrom, dateTo]);

  // KPI: остаток кассы, остаток банка, приход и расход за период
  // Считаем по всем posted-платежам, независимо от текущей вкладки.
  const kpi = useMemo(() => {
    if (!postedPayments) return null;
    let cashBalance = 0;
    let bankBalance = 0;
    let periodIn = 0;
    let periodOut = 0;
    for (const p of postedPayments) {
      const amt = parseFloat(p.amount_uzs || '0');
      if (Number.isNaN(amt)) continue;
      const code = p.cash_subaccount_code;
      const isCash = code === '50.01';
      const isBank = code === '51.01';
      const delta = p.direction === 'in' ? amt : -amt;
      if (isCash) cashBalance += delta;
      if (isBank) bankBalance += delta;
      if (p.date >= dateFrom && p.date <= dateTo) {
        if (p.direction === 'in') periodIn += amt;
        else periodOut += amt;
      }
    }
    return { cashBalance, bankBalance, periodIn, periodOut };
  }, [postedPayments, dateFrom, dateTo]);

  const handlePost = async (p: Payment) => {
    if (!window.confirm('Провести платёж ' + p.doc_number + '? Будет создана проводка в ГК.')) return;
    try {
      await post.mutateAsync({ id: p.id });
    } catch (e) {
      alert('Не удалось провести: ' + (e instanceof Error ? e.message : ''));
    }
  };

  const handleCancel = async (p: Payment) => {
    if (!window.confirm('Отменить платёж ' + p.doc_number + '?')) return;
    try {
      await cancel.mutateAsync({ id: p.id, body: { reason: '' } });
    } catch (e) {
      alert('Не удалось отменить: ' + (e instanceof Error ? e.message : ''));
    }
  };

  const handleReverse = async (p: Payment) => {
    const reason = window.prompt('Причина сторнирования (необязательно):');
    if (reason === null) return;
    try {
      await reverse.mutateAsync({ id: p.id, body: { reason } });
    } catch (e) {
      alert('Не удалось сторнировать: ' + (e instanceof Error ? e.message : ''));
    }
  };

  const handleDelete = async (p: Payment) => {
    if (!window.confirm('Удалить черновик ' + p.doc_number + ' безвозвратно?')) return;
    try {
      await remove.mutateAsync(p.id);
    } catch (e) {
      alert('Не удалось удалить: ' + (e instanceof Error ? e.message : ''));
    }
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Касса и банк</h1>
          <div className="sub">Движения наличных (50.01) и расчётного счёта (51.01) · приход/расход по модулям</div>
        </div>
        <div className="actions">
          {canEdit && (
            <>
              <button className="btn btn-secondary btn-sm" onClick={() => setOpexOpen('in')}>
                <Icon name="download" size={14} /> Приход
              </button>
              <button className="btn btn-primary btn-sm" onClick={() => setOpexOpen('out')}>
                <Icon name="arrow-right" size={14} /> Расход
              </button>
            </>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard
          tone={kpi && kpi.cashBalance >= 0 ? 'green' : 'red'}
          iconName="bag"
          label="Касса 50.01"
          sub="текущий остаток"
          value={kpi ? fmtUzs(kpi.cashBalance) + ' сум' : '—'}
        />
        <KpiCard
          tone={kpi && kpi.bankBalance >= 0 ? 'green' : 'red'}
          iconName="book"
          label="Расчётный счёт 51.01"
          sub="текущий остаток"
          value={kpi ? fmtUzs(kpi.bankBalance) + ' сум' : '—'}
        />
        <KpiCard
          tone="blue"
          iconName="download"
          label="Приход за период"
          sub={`${dateFrom} — ${dateTo}`}
          value={kpi ? fmtUzs(kpi.periodIn, true) : '—'}
        />
        <KpiCard
          tone="red"
          iconName="arrow-right"
          label="Расход за период"
          sub={`${dateFrom} — ${dateTo}`}
          value={kpi ? fmtUzs(kpi.periodOut, true) : '—'}
        />
      </div>

      {/* Статус-табы */}
      <div style={{ marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'posted',    label: 'Проведённые' },
            { value: 'draft',     label: 'Черновики' },
            { value: 'cancelled', label: 'Отменённые' },
            { value: 'all',       label: 'Все' },
          ]}
          value={statusTab}
          onChange={(v) => setStatusTab(v as StatusTab)}
        />
      </div>

      {/* Фильтры */}
      <div className="filter-bar">
        <div className="filter-cell">
          <label>Счёт</label>
          <Seg
            options={[
              { value: 'all', label: 'Касса + Банк' },
              { value: '50.01', label: 'Только касса' },
              { value: '51.01', label: 'Только банк' },
            ]}
            value={accountCode}
            onChange={(v) => setAccountCode(v as typeof accountCode)}
          />
        </div>
        <div className="filter-cell">
          <label>С</label>
          <input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="filter-cell">
          <label>По</label>
          <input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="filter-cell" style={{ minWidth: 200 }}>
          <label>Модуль</label>
          <select className="input" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
            <option value="">Все</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
        <div className="filter-cell">
          <label>Пресет</label>
          <div className="filter-presets">
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(daysAgoISO(7)); setDateTo(todayISO()); }}>7 дн</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(daysAgoISO(30)); setDateTo(todayISO()); }}>30 дн</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(daysAgoISO(90)); setDateTo(todayISO()); }}>90 дн</button>
          </div>
        </div>
      </div>

      <Panel flush>
        <DataTable<Payment>
          isLoading={isLoading}
          rows={filteredPayments}
          rowKey={(p) => p.id}
          emptyMessage="Движений нет за выбранный период."
          onRowClick={(p) => setDrawerPayment(p)}
          rowProps={(p) => ({ active: drawerPayment?.id === p.id })}
          columns={[
            { key: 'date', label: 'Дата', mono: true,
              cellStyle: { fontSize: 12 },
              render: (p) => p.date },
            { key: 'doc', label: 'Документ', mono: true,
              cellStyle: { fontSize: 12 },
              render: (p) => p.doc_number },
            { key: 'kind', label: 'Тип',
              render: (p) => <Badge tone={KIND_TONE[p.kind]}>{KIND_LABEL[p.kind]}</Badge> },
            { key: 'direction', label: 'Направ.',
              render: (p) => p.direction === 'in'
                ? <span style={{ color: 'var(--success)' }}>⬇️ IN</span>
                : <span style={{ color: 'var(--danger)' }}>⬆️ OUT</span> },
            { key: 'module', label: 'Модуль', mono: true, muted: true,
              render: (p) => p.module_code ?? '—' },
            { key: 'who', label: 'Контрагент / Статья',
              cellStyle: { fontSize: 12 },
              render: (p) => p.counterparty_name ?? (
                p.contra_subaccount_code
                  ? <span className="mono" style={{ color: 'var(--fg-2)' }}>
                      {p.contra_subaccount_code} · {p.contra_subaccount_name}
                    </span>
                  : '—'
              ) },
            { key: 'account', label: 'Счёт', mono: true, muted: true,
              render: (p) => p.cash_subaccount_code ?? '—' },
            {
              key: 'amount', label: 'Сумма', align: 'right', mono: true,
              cellStyle: { fontWeight: 600 },
              render: (p) => (
                <span style={{ color: p.direction === 'in' ? 'var(--success)' : 'var(--danger)' }}>
                  {p.direction === 'in' ? '+' : '−'}{fmtUzs(p.amount_uzs)}
                </span>
              ),
            },
            { key: 'status', label: 'Статус',
              render: (p) => <Badge tone={STATUS_TONE[p.status]}>{STATUS_LABEL[p.status]}</Badge> },
            { key: 'actions', label: '', align: 'right',
              render: (p) => (
                <RowActions
                  actions={[
                    {
                      label: 'Подробнее',
                      onClick: () => setDrawerPayment(p),
                    },
                    {
                      label: 'Провести',
                      hidden: !canEdit || !(p.status === 'draft' || p.status === 'confirmed'),
                      disabled: post.isPending,
                      onClick: () => handlePost(p),
                    },
                    {
                      label: 'Отменить',
                      hidden: !canEdit || !(p.status === 'draft' || p.status === 'confirmed'),
                      disabled: cancel.isPending,
                      onClick: () => handleCancel(p),
                    },
                    {
                      label: 'Сторно',
                      danger: true,
                      hidden: !canEdit || p.status !== 'posted',
                      disabled: reverse.isPending,
                      onClick: () => handleReverse(p),
                    },
                    {
                      label: 'Удалить черновик',
                      danger: true,
                      hidden: !canEdit || p.status !== 'draft',
                      disabled: remove.isPending,
                      onClick: () => handleDelete(p),
                    },
                  ]}
                />
              ) },
          ]}
        />
      </Panel>

      {opexOpen !== false && (
        <OpexModal
          preselect={{ direction: opexOpen }}
          onClose={() => setOpexOpen(false)}
        />
      )}

      {drawerPayment && (
        <PaymentDrawer
          payment={drawerPayment}
          onClose={() => setDrawerPayment(null)}
        />
      )}
    </>
  );
}
