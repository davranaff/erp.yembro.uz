'use client';

import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import { useSubaccounts } from '@/hooks/useAccounts';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useExecuteRun,
  usePayrollRuns,
  usePreviewRun,
} from '@/hooks/usePayroll';
import type { PayrollRunPreviewRow } from '@/types/payroll';

const TYPE_LABEL: Record<string, string> = {
  advance: 'Аванс',
  salary: 'ЗП',
  bonus: 'Премия',
  correction: 'Корректировка',
};

function fmt(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === '') return '—';
  const v = typeof n === 'number' ? n : Number(n);
  if (!Number.isFinite(v)) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(v);
}

function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function PayrollRunsPage() {
  const { data: runs = [], isLoading } = usePayrollRuns();
  const hasLevel = useHasLevel();
  const canExecute = hasLevel('hr', 'rw');
  const [showWizard, setShowWizard] = useState(false);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Ведомости на выплату</h1>
          <div className="sub">Массовая выплата ЗП всем сотрудникам с долгом за период</div>
        </div>
        {canExecute && (
          <div className="actions">
            <button className="btn btn-primary btn-sm" onClick={() => setShowWizard(true)}>
              <Icon name="plus" size={14} /> Запустить ведомость
            </button>
          </div>
        )}
      </div>

      <Panel flush>
        <DataTable
          isLoading={isLoading}
          rows={runs}
          rowKey={(r) => r.id}
          emptyMessage="Ведомостей пока не было. Используйте «Запустить ведомость» для массовой выплаты."
          columns={[
            { key: 'period', label: 'Период', mono: true,
              render: (r) => `${r.period_from} — ${r.period_to}` },
            { key: 'type', label: 'Тип',
              render: (r) => <Badge tone="info">{TYPE_LABEL[r.payout_type] ?? r.payout_type}</Badge> },
            { key: 'count', label: 'Сотрудников', align: 'right',
              render: (r) => String(r.employees_count) },
            { key: 'amount', label: 'Сумма', mono: true, align: 'right',
              render: (r) => `${fmt(r.total_amount_uzs)} сум` },
            { key: 'status', label: 'Статус',
              render: (r) => (
                <Badge tone={r.status === 'executed' ? 'success' : r.status === 'cancelled' ? 'neutral' : 'warn'}>
                  {r.status}
                </Badge>
              ) },
            { key: 'date', label: 'Выполнено', mono: true, cellStyle: { fontSize: 12 },
              render: (r) => r.executed_at ? r.executed_at.slice(0, 16).replace('T', ' ') : '—' },
            { key: 'notes', label: 'Заметка', render: (r) => r.notes || '—' },
          ]}
        />
      </Panel>

      {showWizard && <RunWizard onClose={() => setShowWizard(false)} />}
    </>
  );
}

function RunWizard({ onClose }: { onClose: () => void }) {
  const today = new Date();
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const [periodFrom, setPeriodFrom] = useState(ymd(monthStart));
  const [periodTo, setPeriodTo] = useState(ymd(today));
  const [payoutType, setPayoutType] = useState<'advance' | 'salary' | 'bonus' | 'correction'>('salary');
  const [cashId, setCashId] = useState('');
  const [previewRows, setPreviewRows] = useState<PayrollRunPreviewRow[] | null>(null);
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState('');

  const { data: subaccounts = [] } = useSubaccounts();
  const cashOptions = subaccounts.filter(
    (s) => s.code.startsWith('50.') || s.code.startsWith('51.'),
  );
  const preview = usePreviewRun();
  const execute = useExecuteRun();

  const onPreview = () => {
    preview.mutate({ period_from: periodFrom, period_to: periodTo }, {
      onSuccess: (data) => {
        setPreviewRows(data.rows);
        // По умолчанию выплачиваем весь долг
        const m: Record<string, string> = {};
        data.rows.forEach((r) => { m[r.employee_id] = r.due_uzs; });
        setAmounts(m);
        setExcluded(new Set());
      },
      onError: (e) => alert(e.message),
    });
  };

  const onExecute = () => {
    if (!cashId) { alert('Выберите кассу.'); return; }
    if (!previewRows) { alert('Сначала Preview.'); return; }
    const employee_amounts: Record<string, string> = {};
    previewRows.forEach((r) => {
      if (excluded.has(r.employee_id)) return;
      const amt = amounts[r.employee_id] ?? r.due_uzs;
      const num = Number(amt.replace(/\s/g, ''));
      if (num > 0) employee_amounts[r.employee_id] = String(num);
    });
    if (Object.keys(employee_amounts).length === 0) {
      alert('Нет сотрудников для выплаты.');
      return;
    }
    execute.mutate({
      period_from: periodFrom,
      period_to: periodTo,
      cash_subaccount: cashId,
      payout_type: payoutType,
      employee_amounts,
      notes,
    }, {
      onSuccess: () => onClose(),
      onError: (e) => alert(e.message),
    });
  };

  const totalSelected = previewRows
    ? previewRows
        .filter((r) => !excluded.has(r.employee_id))
        .reduce((s, r) => s + Number((amounts[r.employee_id] ?? r.due_uzs).replace(/\s/g, '')), 0)
    : 0;

  return (
    <Modal
      title="Массовая ведомость"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>Отмена</button>
          {!previewRows ? (
            <button className="btn btn-primary btn-sm" onClick={onPreview} disabled={preview.isPending}>
              {preview.isPending ? '…' : 'Предпросмотр'}
            </button>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={onExecute} disabled={execute.isPending}>
              {execute.isPending ? 'Выплачиваем…' : `Выплатить ${fmt(totalSelected)} сум`}
            </button>
          )}
        </>
      }
    >
      <div style={{ display: 'grid', gap: 10 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <label>Период с</label>
            <input className="input" type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
          </div>
          <div>
            <label>Период по</label>
            <input className="input" type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
          <div>
            <label>Тип</label>
            <select className="input" value={payoutType} onChange={(e) => setPayoutType(e.target.value as never)}>
              <option value="advance">Аванс</option>
              <option value="salary">ЗП</option>
              <option value="bonus">Премия</option>
            </select>
          </div>
          <div>
            <label>Касса</label>
            <select className="input" value={cashId} onChange={(e) => setCashId(e.target.value)}>
              <option value="">— выбрать —</option>
              {cashOptions.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label>Заметка</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="например: ЗП за май" />
        </div>

        {previewRows !== null && (
          <div style={{ marginTop: 8, maxHeight: 300, overflowY: 'auto', border: '1px solid var(--bord-1)', borderRadius: 4 }}>
            <table style={{ width: '100%', fontSize: 13 }}>
              <thead style={{ background: 'var(--bg-soft)', position: 'sticky', top: 0 }}>
                <tr>
                  <th style={{ textAlign: 'left', padding: 6 }}>
                    <input
                      type="checkbox"
                      checked={excluded.size === 0}
                      onChange={(e) => {
                        if (e.target.checked) setExcluded(new Set());
                        else setExcluded(new Set(previewRows.map((r) => r.employee_id)));
                      }}
                    />
                  </th>
                  <th style={{ textAlign: 'left', padding: 6 }}>Сотрудник</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>Долг</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>К выплате</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.length === 0 && (
                  <tr><td colSpan={4} style={{ padding: 12, textAlign: 'center', color: 'var(--fg-3)' }}>
                    Нет сотрудников с положительным балансом за этот период.
                  </td></tr>
                )}
                {previewRows.map((r) => {
                  const isExcl = excluded.has(r.employee_id);
                  return (
                    <tr key={r.employee_id} style={{ opacity: isExcl ? 0.4 : 1 }}>
                      <td style={{ padding: 6 }}>
                        <input
                          type="checkbox"
                          checked={!isExcl}
                          onChange={() => {
                            const next = new Set(excluded);
                            if (isExcl) next.delete(r.employee_id);
                            else next.add(r.employee_id);
                            setExcluded(next);
                          }}
                        />
                      </td>
                      <td style={{ padding: 6 }}>{r.full_name}</td>
                      <td style={{ padding: 6, textAlign: 'right', fontFamily: 'var(--mono)' }}>
                        {fmt(r.balance_uzs)}
                      </td>
                      <td style={{ padding: 6, textAlign: 'right' }}>
                        <input
                          className="input"
                          style={{ width: 110, textAlign: 'right' }}
                          value={amounts[r.employee_id] ?? r.due_uzs}
                          disabled={isExcl}
                          onChange={(e) =>
                            setAmounts({ ...amounts, [r.employee_id]: e.target.value })
                          }
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Modal>
  );
}
