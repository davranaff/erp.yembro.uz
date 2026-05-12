'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TablePagination from '@/components/ui/TablePagination';
import { useDeleteSubaccount, useSubaccounts } from '@/hooks/useAccounts';
import { useModules } from '@/hooks/useModules';
import {
  paymentsCrud,
  useCancelPayment,
  usePostPayment,
  useReversePayment,
} from '@/hooks/usePayments';
import { useHasLevel } from '@/hooks/usePermissions';
import type { GLSubaccount, Payment, PaymentKind, PaymentStatus } from '@/types/auth';

import CashAccountModal from '../CashAccountModal';
import OpexModal from '../OpexModal';
import PaymentDrawer from '../PaymentDrawer';

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

export default function CashboxDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [dateFrom, setDateFrom] = useState(daysAgoISO(30));
  const [dateTo, setDateTo] = useState(todayISO());
  const [statusTab, setStatusTab] = useState<StatusTab>('posted');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [opexOpen, setOpexOpen] = useState<false | 'out' | 'in'>(false);
  const [editingAccount, setEditingAccount] = useState<GLSubaccount | null>(null);
  const [drawerPayment, setDrawerPayment] = useState<Payment | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('ledger', 'rw');
  const isOrgAdmin = hasLevel('admin', 'admin') || hasLevel('ledger', 'admin');

  const { data: subs } = useSubaccounts();
  const { data: modules } = useModules();
  const acc = useMemo(() => subs?.find((s) => s.id === id), [subs, id]);
  const isBank = acc?.code.startsWith('51.') ?? false;
  const moduleName = useMemo(() => {
    if (!acc?.module) return null;
    return modules?.find((m) => m.id === acc.module)?.name ?? null;
  }, [acc, modules]);

  const post = usePostPayment();
  const cancel = useCancelPayment();
  const reverse = useReversePayment();
  const remove = paymentsCrud.useDelete();
  const deleteSubaccount = useDeleteSubaccount();

  // Все платежи по этой кассе (для расчёта баланса — нужны все posted, без
  // фильтра по периоду).
  const { data: postedPaymentsForAccount } = paymentsCrud.useList({
    status: 'posted',
    cash_subaccount: id,
  });

  const balance = useMemo(() => {
    if (!postedPaymentsForAccount) return 0;
    let sum = 0;
    for (const p of postedPaymentsForAccount) {
      const amt = parseFloat(p.amount_uzs || '0');
      if (Number.isNaN(amt)) continue;
      sum += p.direction === 'in' ? amt : -amt;
    }
    return sum;
  }, [postedPaymentsForAccount]);

  const periodTotals = useMemo(() => {
    let periodIn = 0;
    let periodOut = 0;
    if (!postedPaymentsForAccount) return { periodIn, periodOut };
    for (const p of postedPaymentsForAccount) {
      if (p.date < dateFrom || p.date > dateTo) continue;
      const amt = parseFloat(p.amount_uzs || '0');
      if (Number.isNaN(amt)) continue;
      if (p.direction === 'in') periodIn += amt;
      else periodOut += amt;
    }
    return { periodIn, periodOut };
  }, [postedPaymentsForAccount, dateFrom, dateTo]);

  // Список платежей для таблицы — с учётом статус-вкладки.
  const filter = useMemo(() => {
    const f: Record<string, string> = { cash_subaccount: id };
    if (statusTab !== 'all') f.status = statusTab;
    return f;
  }, [id, statusTab]);

  const { data: pageData, isLoading } = paymentsCrud.useListPaginated(
    filter, page, pageSize,
  );
  const payments = pageData?.results ?? [];

  const filteredPayments = useMemo(() => {
    if (!payments) return [];
    return payments.filter((p) => {
      if (dateFrom && p.date < dateFrom) return false;
      if (dateTo && p.date > dateTo) return false;
      return true;
    });
  }, [payments, dateFrom, dateTo]);

  const handlePost = async (p: Payment) => {
    if (!window.confirm('Провести платёж ' + p.doc_number + '? Будет создана проводка в ГК.')) return;
    try { await post.mutateAsync({ id: p.id }); }
    catch (e) { alert('Не удалось провести: ' + (e instanceof Error ? e.message : '')); }
  };

  const handleCancel = async (p: Payment) => {
    if (!window.confirm('Отменить платёж ' + p.doc_number + '?')) return;
    try { await cancel.mutateAsync({ id: p.id, body: { reason: '' } }); }
    catch (e) { alert('Не удалось отменить: ' + (e instanceof Error ? e.message : '')); }
  };

  const handleReverse = async (p: Payment) => {
    const reason = window.prompt('Причина сторнирования (необязательно):');
    if (reason === null) return;
    try { await reverse.mutateAsync({ id: p.id, body: { reason } }); }
    catch (e) { alert('Не удалось сторнировать: ' + (e instanceof Error ? e.message : '')); }
  };

  const handleDelete = async (p: Payment) => {
    if (!window.confirm('Удалить черновик ' + p.doc_number + ' безвозвратно?')) return;
    try { await remove.mutateAsync(p.id); }
    catch (e) { alert('Не удалось удалить: ' + (e instanceof Error ? e.message : '')); }
  };

  const handleDeleteAccount = async () => {
    if (!acc) return;
    if (balance !== 0) {
      alert('Нельзя удалить кассу с ненулевым балансом.');
      return;
    }
    if (!window.confirm(
      `Удалить кассу/счёт ${acc.code} «${acc.name}»? ` +
      'Если есть привязанные платежи — удаление невозможно.',
    )) return;
    try {
      await deleteSubaccount.mutateAsync(acc.id);
      router.push('/finance/cashbox');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Не удалось удалить');
    }
  };

  if (subs && !acc) {
    return (
      <div style={{ padding: 24 }}>
        <Link href="/finance/cashbox" className="btn btn-ghost btn-sm">
          <Icon name="chevron-left" size={14} /> Назад к кассам
        </Link>
        <div style={{
          marginTop: 16, padding: 16,
          background: 'var(--danger-soft, #FEF2F2)',
          color: 'var(--danger)', borderRadius: 6,
        }}>
          Касса не найдена или у вас нет к ней доступа.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-hdr">
        <div>
          <div style={{ marginBottom: 6 }}>
            <Link
              href="/finance/cashbox"
              style={{
                fontSize: 12, color: 'var(--fg-3)', textDecoration: 'none',
                display: 'inline-flex', alignItems: 'center', gap: 4,
              }}
            >
              <Icon name="chevron-left" size={12} />
              Все кассы
            </Link>
          </div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{isBank ? '🏦' : '💵'}</span>
            <span>{acc?.name ?? '…'}</span>
          </h1>
          <div className="sub">
            <span className="mono">{acc?.code}</span>
            {' · '}{isBank ? 'Расчётный счёт' : 'Касса'}
            {moduleName && ` · модуль ${moduleName}`}
          </div>
        </div>
        <div className="actions">
          {isOrgAdmin && acc && (
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setEditingAccount(acc)}
                title="Изменить название/модуль кассы"
              >
                <Icon name="edit" size={14} /> Редактировать
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={handleDeleteAccount}
                disabled={deleteSubaccount.isPending || balance !== 0}
                style={{ color: 'var(--danger)' }}
                title={balance !== 0
                  ? 'Нельзя удалить кассу с ненулевым балансом'
                  : 'Удалить кассу'}
              >
                <Icon name="close" size={14} /> Удалить
              </button>
            </>
          )}
          {canEdit && (
            <>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setOpexOpen('in')}
                disabled={!acc}
              >
                <Icon name="download" size={14} /> Приход
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setOpexOpen('out')}
                disabled={!acc}
              >
                <Icon name="arrow-right" size={14} /> Расход
              </button>
            </>
          )}
        </div>
      </div>

      {/* KPI: текущий баланс + период */}
      <div className="kpi-row">
        <KpiCard
          tone={balance >= 0 ? 'green' : 'red'}
          iconName={isBank ? 'book' : 'bag'}
          label="Текущий баланс"
          sub={acc?.code}
          value={postedPaymentsForAccount ? fmtUzs(balance) + ' сум' : '—'}
        />
        <KpiCard
          tone="blue"
          iconName="download"
          label="Приход за период"
          sub={`${dateFrom} — ${dateTo}`}
          value={postedPaymentsForAccount ? fmtUzs(periodTotals.periodIn, true) : '—'}
        />
        <KpiCard
          tone="red"
          iconName="arrow-right"
          label="Расход за период"
          sub={`${dateFrom} — ${dateTo}`}
          value={postedPaymentsForAccount ? fmtUzs(periodTotals.periodOut, true) : '—'}
        />
        <KpiCard
          tone="orange"
          iconName="chart"
          label="Сальдо за период"
          sub={`${dateFrom} — ${dateTo}`}
          value={postedPaymentsForAccount
            ? fmtUzs(periodTotals.periodIn - periodTotals.periodOut, true)
            : '—'}
        />
      </div>

      {/* Статус-табы */}
      <div style={{ marginBottom: 12, marginTop: 12 }}>
        <Seg
          options={[
            { value: 'posted',    label: 'Проведённые' },
            { value: 'draft',     label: 'Черновики' },
            { value: 'cancelled', label: 'Отменённые' },
            { value: 'all',       label: 'Все' },
          ]}
          value={statusTab}
          onChange={(v) => { setStatusTab(v as StatusTab); setPage(1); }}
        />
      </div>

      {/* Фильтры по дате */}
      <div className="filter-bar">
        <div className="filter-cell">
          <label>С</label>
          <input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="filter-cell">
          <label>По</label>
          <input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
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
          emptyMessage="Движений по этой кассе нет за выбранный период."
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
                    { label: 'Подробнее', onClick: () => setDrawerPayment(p) },
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
        {pageData && (
          <TablePagination
            page={page}
            pageSize={pageSize}
            count={pageData.count}
            hasPrev={Boolean(pageData.previous)}
            hasNext={Boolean(pageData.next)}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        )}
      </Panel>

      {opexOpen !== false && acc && (
        <OpexModal
          preselect={{
            direction: opexOpen,
            cashSubaccountId: acc.id,
            moduleCode: acc.module_code ?? undefined,
          }}
          onClose={() => setOpexOpen(false)}
        />
      )}

      {editingAccount && (
        <CashAccountModal
          initial={editingAccount}
          onClose={() => setEditingAccount(null)}
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
