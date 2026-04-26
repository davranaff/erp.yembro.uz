'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useAccounts, useDeleteSubaccount } from '@/hooks/useAccounts';
import { useModules } from '@/hooks/useModules';
import { useHasLevel } from '@/hooks/usePermissions';
import type { GLAccount, GLSubaccount } from '@/types/auth';

import SubaccountModal from './SubaccountModal';

/**
 * Плоская строка таблицы плана счетов — либо родительский счёт,
 * либо субсчёт под развёрнутым родителем.
 */
type AccountRow =
  | { kind: 'account'; account: GLAccount }
  | { kind: 'sub'; sub: GLSubaccount; parent: GLAccount };

type AccountType = 'asset' | 'liability' | 'equity' | 'income' | 'expense' | 'service' | 'contra';

const TYPE_LABEL: Record<string, string> = {
  asset: 'Актив',
  liability: 'Пассив',
  equity: 'Капитал',
  income: 'Доход',
  expense: 'Расход',
  service: 'Служебный',
  contra: 'Контр-счёт',
};

const TYPE_COLOR: Record<string, string> = {
  asset: 'var(--success)',
  liability: 'var(--danger)',
  equity: 'var(--info)',
  income: 'var(--kpi-green)',
  expense: 'var(--warning)',
  service: 'var(--fg-3)',
  contra: 'var(--fg-3)',
};

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows
    .map((r) =>
      r
        .map((cell) => {
          const s = cell ?? '';
          if (/[,"\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
          return s;
        })
        .join(','),
    )
    .join('\n');
  // BOM + UTF-8 — корректное открытие в Excel
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

export default function AccountsPage() {
  const router = useRouter();
  const { data, isLoading, error, refetch, isFetching } = useAccounts();
  const { data: modules } = useModules();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | AccountType>('all');
  const [moduleFilter, setModuleFilter] = useState<string>('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<GLSubaccount | null>(null);
  const [defaultAccountId, setDefaultAccountId] = useState<string | undefined>();

  const hasLevel = useHasLevel();
  // Редактировать план счетов могут пользователи с уровнем «Ввод документов»
  // и выше. `admin` слишком жёсткий — это уровень «Администратор модуля».
  const canEdit = hasLevel('ledger', 'rw');

  const deleteMut = useDeleteSubaccount();

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const handleAddToAccount = (accountId: string) => {
    setEditing(null);
    setDefaultAccountId(accountId);
    setModalOpen(true);
    setExpanded((prev) => {
      const n = new Set(prev);
      n.add(accountId);
      return n;
    });
  };

  const handleEdit = (e: React.MouseEvent, sub: GLSubaccount) => {
    e.stopPropagation();
    setEditing(sub);
    setDefaultAccountId(undefined);
    setModalOpen(true);
  };

  const handleDelete = (e: React.MouseEvent, sub: GLSubaccount) => {
    e.stopPropagation();
    if (!window.confirm(`Удалить субсчёт ${sub.code} "${sub.name}"?`)) return;
    deleteMut.mutate(sub.id, {
      onError: (err: Error) => alert('Не удалось удалить: ' + err.message),
    });
  };

  const openInLedger = (e: React.MouseEvent, sub: GLSubaccount) => {
    e.stopPropagation();
    router.push(`/reports/gl-ledger?subaccount=${sub.id}`);
  };

  // Применяем все фильтры
  const filtered = useMemo(() => {
    const rows = data ?? [];
    const s = search.trim().toLowerCase();

    return rows.filter((acc) => {
      // Type filter
      if (typeFilter !== 'all' && acc.type !== typeFilter) return false;

      // Module filter — счёт виден если хоть один его субсчёт принадлежит этому модулю
      if (moduleFilter) {
        const hasModule = (acc.subaccounts ?? []).some(
          (sub) => sub.module === moduleFilter,
        );
        if (!hasModule) return false;
      }

      // Search
      if (s) {
        if (acc.code.includes(s)) return true;
        if (acc.name.toLowerCase().includes(s)) return true;
        return (acc.subaccounts ?? []).some(
          (sub) => sub.code.includes(s) || sub.name.toLowerCase().includes(s),
        );
      }

      return true;
    });
  }, [data, search, typeFilter, moduleFilter]);

  /** Плоский список строк для DataTable: account, затем его subs если развёрнут.
   *  При активном module-фильтре показываем только подходящие субсчёта. */
  const flatRows = useMemo<AccountRow[]>(() => {
    const out: AccountRow[] = [];
    for (const acc of filtered) {
      out.push({ kind: 'account', account: acc });
      if (expanded.has(acc.id)) {
        for (const sub of (acc.subaccounts ?? [])) {
          // Если включён module-фильтр — показываем только субсчёта этого модуля
          if (moduleFilter && sub.module !== moduleFilter) continue;
          out.push({ kind: 'sub', sub, parent: acc });
        }
      }
    }
    return out;
  }, [filtered, expanded, moduleFilter]);

  // KPI: считаем по всему списку (без учёта фильтров) — это «обзор системы»
  const kpi = useMemo(() => {
    const all = data ?? [];
    const totalAccounts = all.length;
    const totalSubs = all.reduce((s, a) => s + (a.subaccounts?.length ?? 0), 0);
    const byType: Record<string, number> = {};
    for (const a of all) {
      byType[a.type] = (byType[a.type] ?? 0) + 1;
    }
    return { totalAccounts, totalSubs, byType };
  }, [data]);

  const expandAll = () => {
    setExpanded(new Set(filtered.map((a) => a.id)));
  };
  const collapseAll = () => setExpanded(new Set());

  const handleExport = () => {
    if (!data) return;
    const rows: string[][] = [['Счёт', 'Наименование', 'Тип', 'Субсчёт', 'Название субсчёта', 'Модуль']];
    for (const acc of filtered) {
      // Сама строка счёта (без субсчёта)
      rows.push([acc.code, acc.name, TYPE_LABEL[acc.type] ?? acc.type, '', '', '']);
      // Субсчёта (с учётом module-фильтра)
      for (const sub of (acc.subaccounts ?? [])) {
        if (moduleFilter && sub.module !== moduleFilter) continue;
        rows.push([acc.code, acc.name, TYPE_LABEL[acc.type] ?? acc.type, sub.code, sub.name, sub.module_code ?? '']);
      }
    }
    downloadCsv('plan-schetov.csv', rows);
  };

  const allExpanded = filtered.length > 0 && filtered.every((a) => expanded.has(a.id));

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>План счетов</h1>
          <div className="sub">
            Счета компании + субсчета модулей{canEdit ? ' · можно добавлять / редактировать' : ' · только чтение'}
          </div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleExport}
            disabled={!data || data.length === 0}
            title="Скачать CSV"
          >
            <Icon name="download" size={14} /> CSV
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} />
            {isFetching ? '…' : 'Обновить'}
          </button>
          {canEdit && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => { setEditing(null); setDefaultAccountId(undefined); setModalOpen(true); }}
            >
              <Icon name="plus" size={14} /> Новый субсчёт
            </button>
          )}
        </div>
      </div>

      {/* KPI */}
      <div className="kpi-row" style={{ marginBottom: 12 }}>
        <KpiCard
          tone="orange"
          iconName="book"
          label="Счетов"
          sub="верхнего уровня"
          value={String(kpi.totalAccounts)}
        />
        <KpiCard
          tone="blue"
          iconName="box"
          label="Субсчетов"
          sub="всего по компании"
          value={String(kpi.totalSubs)}
        />
        <KpiCard
          tone="green"
          iconName="chart"
          label="Активов"
          sub="по типу"
          value={String(kpi.byType.asset ?? 0)}
        />
        <KpiCard
          tone="red"
          iconName="users"
          label="Расходов"
          sub="по типу"
          value={String(kpi.byType.expense ?? 0)}
        />
      </div>

      <div
        style={{
          padding: 10,
          background: 'var(--info-soft)',
          border: '1px solid var(--info)',
          borderRadius: 4,
          fontSize: 12,
          marginBottom: 16,
          color: '#1E4D80',
        }}
      >
        <b>Как читать:</b> счёт верхнего уровня — общий для компании. Субсчёт{' '}
        <span className="mono">XX.YY</span> закреплён за конкретным модулем — его
        движения автоматически фильтруются по <span className="mono">module_id</span>.
        Клик по строке счёта раскроет субсчета. Клик «📊» на субсчёте откроет Главную книгу.
        {canEdit
          ? ' Верхние счета зашиты миграцией, но свои субсчёта можно добавлять через кнопку «Новый субсчёт».'
          : ' План счетов инициализируется миграцией при установке системы; ручное редактирование отключено.'}
      </div>

      {/* Фильтры */}
      <div className="filter-bar">
        <div className="filter-cell" style={{ flex: 1, minWidth: 220 }}>
          <label>Поиск</label>
          <input
            className="input"
            placeholder="по коду или названию…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-cell" style={{ minWidth: 200 }}>
          <label>Тип счёта</label>
          <select
            className="input"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}
          >
            <option value="all">Все типы</option>
            <option value="asset">Активы</option>
            <option value="liability">Пассивы</option>
            <option value="equity">Капитал</option>
            <option value="income">Доходы</option>
            <option value="expense">Расходы</option>
            <option value="service">Служебные</option>
            <option value="contra">Контр-счета</option>
          </select>
        </div>
        <div className="filter-cell" style={{ minWidth: 200 }}>
          <label>Модуль (по субсчётам)</label>
          <select
            className="input"
            value={moduleFilter}
            onChange={(e) => setModuleFilter(e.target.value)}
          >
            <option value="">Все модули</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-cell">
          <label>Раскрытие</label>
          <Seg
            options={[
              { value: 'collapse', label: 'Свернуть' },
              { value: 'expand',   label: 'Развернуть всё' },
            ]}
            value={allExpanded ? 'expand' : 'collapse'}
            onChange={(v) => v === 'expand' ? expandAll() : collapseAll()}
          />
        </div>
      </div>

      <Panel
        title={`План счетов · ${filtered.length} счетов / ${flatRows.filter((r) => r.kind === 'sub').length} субсчетов в выборке`}
        flush
      >
        <DataTable<AccountRow>
          isLoading={isLoading}
          rows={flatRows}
          rowKey={(r) => r.kind === 'account' ? `acc-${r.account.id}` : `sub-${r.sub.id}`}
          error={error}
          emptyMessage="План счетов пуст или ничего не найдено по фильтрам."
          onRowClick={(r) => {
            if (r.kind === 'account' && (r.account.subaccounts?.length ?? 0) > 0) {
              toggle(r.account.id);
            }
          }}
          rowProps={(r) => r.kind === 'account'
            ? {
                style: {
                  background: 'var(--bg-subtle)',
                  fontWeight: 600,
                  cursor: (r.account.subaccounts?.length ?? 0) > 0 ? 'pointer' : 'default',
                },
              }
            : {}
          }
          columns={[
            { key: 'code', label: 'Счёт', mono: true, width: 120,
              render: (r) => r.kind === 'account'
                ? r.account.code
                : <span style={{ paddingLeft: 28, color: 'var(--fg-2)' }}>{r.sub.code}</span> },
            { key: 'name', label: 'Наименование',
              render: (r) => r.kind === 'account'
                ? r.account.name
                : <span style={{ fontSize: 12 }}>{r.sub.name}</span> },
            { key: 'type', label: 'Тип / Модуль', width: 160,
              render: (r) => {
                if (r.kind === 'account') {
                  const t = r.account.type;
                  return (
                    <span style={{ fontSize: 12, color: TYPE_COLOR[t] ?? 'var(--fg-2)' }}>
                      {TYPE_LABEL[t] ?? t}
                    </span>
                  );
                }
                return r.sub.module_code ? (
                  <span
                    className="mono"
                    style={{
                      fontSize: 11,
                      padding: '2px 6px',
                      background: 'var(--brand-orange-soft, rgba(232,117,26,0.10))',
                      color: 'var(--brand-orange)',
                      borderRadius: 4,
                    }}
                  >
                    {r.sub.module_code}
                  </span>
                ) : (
                  <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>—</span>
                );
              } },
            { key: 'actions', label: '', align: 'right', width: 140,
              render: (r) => {
                if (r.kind === 'account') {
                  const subs = r.account.subaccounts ?? [];
                  const isOpen = expanded.has(r.account.id);
                  return (
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'flex-end', fontSize: 12, color: 'var(--fg-3)' }}>
                      {canEdit && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={(e) => { e.stopPropagation(); handleAddToAccount(r.account.id); }}
                          title={`Добавить субсчёт к ${r.account.code}`}
                          style={{ padding: '2px 6px', fontSize: 11 }}
                        >
                          <Icon name="plus" size={10} />
                        </button>
                      )}
                      <span className="mono" title="Субсчетов">{subs.length}</span>
                      {subs.length > 0 && (
                        <Icon name={isOpen ? 'chevron-down' : 'chevron-right'} size={12} />
                      )}
                    </div>
                  );
                }
                // Субсчёт: drill-down (всем) + edit/delete (только canEdit)
                return (
                  <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end', alignItems: 'center' }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => openInLedger(e, r.sub)}
                      title="Открыть Главную книгу по этому субсчёту"
                      style={{ padding: '2px 6px', fontSize: 11 }}
                    >
                      <Icon name="book" size={12} />
                    </button>
                    {canEdit && (
                      <RowActions
                        actions={[
                          {
                            label: 'Открыть в ГК',
                            onClick: (e) => openInLedger(e, r.sub),
                          },
                          {
                            label: 'Редактировать',
                            onClick: (e) => handleEdit(e, r.sub),
                          },
                          {
                            label: 'Удалить',
                            danger: true,
                            disabled: deleteMut.isPending,
                            onClick: (e) => handleDelete(e, r.sub),
                          },
                        ]}
                      />
                    )}
                  </div>
                );
              } },
          ]}
        />
      </Panel>

      {modalOpen && (
        <SubaccountModal
          initial={editing}
          accounts={data ?? []}
          defaultAccountId={defaultAccountId}
          onClose={() => { setModalOpen(false); setEditing(null); setDefaultAccountId(undefined); }}
        />
      )}
    </>
  );
}
