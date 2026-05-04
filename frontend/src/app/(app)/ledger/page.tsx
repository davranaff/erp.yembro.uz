'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useAccounts } from '@/hooks/useAccounts';
import { useDashboardSummary } from '@/hooks/useDashboard';
import { useJournalEntries } from '@/hooks/useJournalEntries';
import { useModules } from '@/hooks/useModules';
import type { JournalEntry } from '@/types/auth';

function fmtMoney(v: string | null | undefined) {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

function fmtDate(d: string) {
  try {
    return new Date(d).toLocaleDateString('ru', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    });
  } catch {
    return d;
  }
}

function moduleTone(code: string | null): 'warn' | 'info' | 'success' | 'neutral' {
  if (code === 'incubation') return 'warn';
  if (code === 'feedlot' || code === 'matochnik') return 'info';
  if (code === 'slaughter') return 'success';
  return 'neutral';
}

function firstDayOfMonthISO(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function LedgerPage() {
  const [moduleId, setModuleId] = useState('');
  const [dateAfter, setDateAfter] = useState<string>(firstDayOfMonthISO());
  const [dateBefore, setDateBefore] = useState<string>(todayISO());
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [sel, setSel] = useState<JournalEntry | null>(null);

  const filter = useMemo(
    () => ({
      module: moduleId || undefined,
      search: search || undefined,
      entry_date_after: dateAfter || undefined,
      entry_date_before: dateBefore || undefined,
      limit: 200,
    }),
    [moduleId, search, dateAfter, dateBefore],
  );

  const { data, isLoading, error, refetch, isFetching } = useJournalEntries(filter);
  const { data: modules } = useModules();
  const { data: summary } = useDashboardSummary();
  const { data: accounts } = useAccounts();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
  };

  const totalDebit = useMemo(() => {
    if (!data) return 0;
    return data.reduce((acc, r) => acc + parseFloat(r.amount_uzs || '0'), 0);
  }, [data]);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Проводки</h1>
          <div className="sub">
            Журнал бухгалтерских проводок · двойная запись ·{' '}
            <a href="/reports" style={{ color: 'var(--brand-orange)' }}>
              отчёты →
            </a>
          </div>
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
          tone="blue"
          iconName="book"
          label="Проводок (период)"
          sub={data ? `${dateAfter}..${dateBefore}` : '—'}
          value={data ? String(data.length) : '—'}
          meta="лимит 200"
        />
        <KpiCard
          tone="orange"
          iconName="factory"
          label="Оборот Дт"
          sub="за период"
          value={totalDebit.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}
          valueSuffix="UZS"
          meta={
            summary?.kpis.purchases_confirmed_uzs
              ? `закупы: ${fmtMoney(summary.kpis.purchases_confirmed_uzs)}`
              : ''
          }
        />
        <KpiCard
          tone="green"
          iconName="check"
          label="Платежи вход."
          sub="текущий месяц"
          value={summary ? fmtMoney(summary.kpis.payments_in_uzs) : '—'}
          valueSuffix="UZS"
        />
        <KpiCard
          tone="red"
          iconName="close"
          label="Кредиторка"
          sub="должны поставщикам"
          value={summary ? fmtMoney(summary.kpis.creditor_balance_uzs) : '—'}
          valueSuffix="UZS"
        />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select
          className="input"
          value={moduleId}
          onChange={(e) => setModuleId(e.target.value)}
          style={{ width: 180 }}
        >
          <option value="">Все модули</option>
          {modules?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <input
          className="input"
          type="date"
          value={dateAfter}
          onChange={(e) => setDateAfter(e.target.value)}
          style={{ width: 150 }}
        />
        <input
          className="input"
          type="date"
          value={dateBefore}
          onChange={(e) => setDateBefore(e.target.value)}
          style={{ width: 150 }}
        />
        <div style={{ flex: 1, minWidth: 200 }}>
          <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              placeholder="Поиск по документу, описанию…"
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-secondary btn-sm">
              Найти
            </button>
          </form>
        </div>
      </div>

      <Panel flush>
        <DataTable<JournalEntry>
          isLoading={isLoading}
          rows={data}
          rowKey={(e) => e.id}
          error={error}
          emptyMessage="Нет проводок за выбранный период."
          onRowClick={(e) => setSel(e)}
          rowProps={(e) => ({ active: sel?.id === e.id })}
          columns={[
            { key: 'doc', label: 'Документ',
              render: (e) => <span className="badge id">{e.doc_number}</span> },
            { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
              render: (e) => fmtDate(e.entry_date) },
            { key: 'module', label: 'Модуль',
              render: (e) => (
                <Badge tone={moduleTone(e.module_code)}>
                  {e.module_code ?? '—'}
                </Badge>
              ) },
            { key: 'dt', label: 'Дт', mono: true,
              cellStyle: { fontSize: 12, fontWeight: 600, color: 'var(--success)' },
              render: (e) => e.debit_code },
            { key: 'kt', label: 'Кт', mono: true,
              cellStyle: { fontSize: 12, fontWeight: 600, color: 'var(--danger)' },
              render: (e) => e.credit_code },
            { key: 'amount', label: 'Сумма, UZS', align: 'right', mono: true,
              cellStyle: { fontSize: 13, fontWeight: 600 },
              render: (e) => fmtMoney(e.amount_uzs) },
            { key: 'desc', label: 'Назначение',
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (e) => e.description },
          ]}
        />
      </Panel>

      {sel && (
        <DetailDrawer
          title={'Проводка · ' + sel.doc_number}
          subtitle={
            fmtDate(sel.entry_date) +
            ' · ' +
            (sel.module_code ?? '—') +
            ' · Дт ' +
            sel.debit_code +
            ' — Кт ' +
            sel.credit_code
          }
          onClose={() => setSel(null)}
        >
          <KV
            items={[
              { k: 'Документ', v: sel.doc_number, mono: true },
              { k: 'Дата', v: fmtDate(sel.entry_date), mono: true },
              {
                k: 'Модуль',
                v: <Badge tone={moduleTone(sel.module_code)}>{sel.module_code ?? '—'}</Badge>,
              },
              { k: 'Сумма', v: fmtMoney(sel.amount_uzs) + ' UZS', mono: true },
              { k: 'Дт (счёт)', v: sel.debit_code ?? '—', mono: true },
              { k: 'Кт (счёт)', v: sel.credit_code ?? '—', mono: true },
              ...(sel.currency_code
                ? [
                    { k: 'Валюта', v: sel.currency_code, mono: true },
                    { k: 'Сумма в валюте', v: sel.amount_foreign ?? '—', mono: true },
                    { k: 'Курс', v: sel.exchange_rate ?? '—', mono: true },
                  ]
                : []),
              ...(sel.counterparty_name
                ? [{ k: 'Контрагент', v: sel.counterparty_name }]
                : []),
              ...(sel.batch_doc_number
                ? [{ k: 'Партия', v: sel.batch_doc_number, mono: true }]
                : []),
              { k: 'Назначение', v: sel.description },
            ]}
          />
          <Panel title="Двойная запись" flush>
            <DataTable<{ side: 'dt' | 'kt'; code: string | null | undefined; desc: string; amount: string | null | undefined }>
              rows={[
                { side: 'dt', code: sel.debit_code, desc: sel.description, amount: sel.amount_uzs },
                { side: 'kt', code: sel.credit_code, desc: sel.description, amount: sel.amount_uzs },
              ]}
              rowKey={(r) => r.side}
              columns={[
                { key: 'code', label: 'Счёт', mono: true,
                  render: (r) => r.code },
                { key: 'side', label: 'Сторона',
                  render: (r) => r.side === 'dt'
                    ? <Badge tone="success">Дт</Badge>
                    : <Badge tone="danger">Кт</Badge> },
                { key: 'desc', label: 'Описание', cellStyle: { fontSize: 12 },
                  render: (r) => r.desc },
                { key: 'amount', label: 'Сумма, UZS', align: 'right', mono: true,
                  render: (r) => fmtMoney(r.amount) },
              ]}
            />
          </Panel>
          <div style={{ marginTop: 12, display: 'flex', gap: 8, fontSize: 12 }}>
            <a
              href={`/reports/gl-ledger?subaccount=${sel.debit_subaccount}&date_from=${dateAfter}&date_to=${dateBefore}`}
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--info)' }}
            >
              ▸ GL по Дт {sel.debit_code}
            </a>
            <a
              href={`/reports/gl-ledger?subaccount=${sel.credit_subaccount}&date_from=${dateAfter}&date_to=${dateBefore}`}
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--warning)' }}
            >
              ▸ GL по Кт {sel.credit_code}
            </a>
          </div>
          {accounts && accounts.length > 0 && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 8 }}>
              В плане счетов всего {accounts.length} счетов.{' '}
              <a href="/settings" style={{ color: 'var(--brand-orange)' }}>
                Открыть
              </a>
            </div>
          )}
        </DetailDrawer>
      )}
    </>
  );
}
