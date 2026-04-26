'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useSubaccounts } from '@/hooks/useAccounts';
import { expenseArticlesCrud } from '@/hooks/useExpenseArticles';
import { useModules } from '@/hooks/useModules';
import { useHasLevel } from '@/hooks/usePermissions';
import { ApiError } from '@/lib/api';
import type { ExpenseArticle, ExpenseArticleKind } from '@/types/auth';

const KIND_LABEL: Record<ExpenseArticleKind, string> = {
  expense: 'Расход',
  income: 'Доход',
  salary: 'Зарплата',
  transfer: 'Перевод',
};

const KIND_TONE: Record<ExpenseArticleKind, 'danger' | 'success' | 'warn' | 'neutral'> = {
  expense: 'danger',
  income: 'success',
  salary: 'warn',
  transfer: 'neutral',
};

export default function ExpenseArticlesSection() {
  const [kind, setKind] = useState<'all' | ExpenseArticleKind>('all');
  const [includeArchived, setIncludeArchived] = useState(false);
  const [editing, setEditing] = useState<ExpenseArticle | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('ledger', 'rw');

  const filter: Record<string, string> = {};
  if (kind !== 'all') filter.kind = kind;
  if (!includeArchived) filter.is_active = 'true';

  const { data: articles, isLoading } = expenseArticlesCrud.useList(filter);
  const del = expenseArticlesCrud.useDelete();

  const handleDelete = (a: ExpenseArticle) => {
    if (!window.confirm(
      `Удалить статью «${a.code} · ${a.name}»?\n` +
      `Если она использовалась в платежах — будет ошибка PROTECT.\n` +
      `Лучше деактивировать (is_active=false).`,
    )) return;
    del.mutate(a.id, { onError: (err) => alert(err.message) });
  };

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Статьи расходов/доходов</h2>
        <div style={{ fontSize: 13, color: 'var(--fg-3)', marginTop: 4 }}>
          Аналитический справочник поверх плана счетов. Используется в OPEX-модалке
          и в отчётах. Один субсчёт ГК (например 26.01) можно детализировать в статьях
          «Газ», «Электричество», «Вода» — это даст разрез аналитики, не раздувая
          план счетов.
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: 'all', label: 'Все' },
            { value: 'expense', label: 'Расходы' },
            { value: 'income', label: 'Доходы' },
            { value: 'salary', label: 'Зарплата' },
            { value: 'transfer', label: 'Прочее' },
          ]}
          value={kind}
          onChange={(v) => setKind(v as typeof kind)}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-2)' }}>
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
          />
          Показать архивные
        </label>
        {canEdit && (
          <div style={{ marginLeft: 'auto' }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => { setEditing(null); setModalOpen(true); }}
            >
              <Icon name="plus" size={14} /> Новая статья
            </button>
          </div>
        )}
      </div>

      <Panel flush>
        <DataTable<ExpenseArticle>
          isLoading={isLoading}
          rows={articles}
          rowKey={(a) => a.id}
          emptyMessage="Статей нет."
          columns={[
            {
              key: 'code', label: 'Код', mono: true,
              render: (a) => a.code,
            },
            {
              key: 'name', label: 'Наименование',
              render: (a) => (
                <>
                  {a.parent_code && (
                    <span style={{ color: 'var(--fg-3)', fontSize: 11, marginRight: 4 }}>
                      {a.parent_code} ›
                    </span>
                  )}
                  {a.name}
                </>
              ),
            },
            {
              key: 'kind', label: 'Тип',
              render: (a) => <Badge tone={KIND_TONE[a.kind]} dot>{KIND_LABEL[a.kind]}</Badge>,
            },
            {
              key: 'sub', label: 'Субсчёт по умолчанию', mono: true, cellStyle: { fontSize: 12 },
              render: (a) => a.default_subaccount_code
                ? `${a.default_subaccount_code} · ${a.default_subaccount_name ?? ''}`
                : '—',
            },
            {
              key: 'mod', label: 'Модуль', mono: true, cellStyle: { fontSize: 12 },
              render: (a) => a.default_module_code ?? '—',
            },
            {
              key: 'active', label: 'Статус',
              render: (a) => a.is_active
                ? <Badge tone="success" dot>Активна</Badge>
                : <Badge tone="neutral" dot>Архив</Badge>,
            },
            {
              key: 'actions', label: '', width: 60, align: 'right',
              render: (a) => canEdit ? (
                <RowActions
                  actions={[
                    { label: 'Редактировать', onClick: () => { setEditing(a); setModalOpen(true); } },
                    {
                      label: 'Удалить',
                      danger: true,
                      disabled: del.isPending,
                      onClick: () => handleDelete(a),
                    },
                  ]}
                />
              ) : null,
            },
          ]}
        />
      </Panel>

      {modalOpen && (
        <ExpenseArticleModal
          initial={editing}
          existing={articles ?? []}
          onClose={() => { setModalOpen(false); setEditing(null); }}
        />
      )}
    </>
  );
}

interface ModalProps {
  initial?: ExpenseArticle | null;
  existing: ExpenseArticle[];
  onClose: () => void;
}

function ExpenseArticleModal({ initial, existing, onClose }: ModalProps) {
  const isEdit = Boolean(initial);
  const create = expenseArticlesCrud.useCreate();
  const update = expenseArticlesCrud.useUpdate();
  const { data: subaccounts } = useSubaccounts();
  const { data: modules } = useModules();

  const [code, setCode] = useState(initial?.code ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [kind, setKind] = useState<ExpenseArticleKind>(initial?.kind ?? 'expense');
  const [subId, setSubId] = useState(initial?.default_subaccount ?? '');
  const [moduleId, setModuleId] = useState(initial?.default_module ?? '');
  const [parentId, setParentId] = useState(initial?.parent ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  // Возможные родители — статьи того же типа, исключая саму себя
  const parentOptions = useMemo(() => {
    return existing.filter((a) =>
      a.kind === kind && (!initial || a.id !== initial.id) && !a.parent,
    );
  }, [existing, kind, initial]);

  // Субсчёта расходов/доходов (исключаем кассу/банк/AP/AR — они не для статей)
  const subOptions = useMemo(() => {
    if (!subaccounts) return [];
    const excluded = new Set(['50.01', '51.01', '60.01', '60.02', '62.01', '62.02']);
    return subaccounts.filter((s) => !excluded.has(s.code)).sort((a, b) => a.code.localeCompare(b.code));
  }, [subaccounts]);

  const canSubmit = code && name && !create.isPending && !update.isPending;

  const handleSave = async () => {
    const payload = {
      code,
      name,
      kind,
      default_subaccount: subId || null,
      default_module: moduleId || null,
      parent: parentId || null,
      is_active: isActive,
      notes,
    };
    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch { /* */ }
  };

  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title={isEdit ? `Статья · ${initial?.code}` : 'Новая статья'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={handleSave}>
            {(create.isPending || update.isPending) ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Код *</label>
          <input
            className="input mono"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="GAS"
            disabled={isEdit}
          />
          {getErr('code') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('code')}</div>}
        </div>

        <div className="field">
          <label>Тип *</label>
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value as ExpenseArticleKind)}>
            <option value="expense">Расход</option>
            <option value="income">Доход</option>
            <option value="salary">Зарплата</option>
            <option value="transfer">Перевод/прочее</option>
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Наименование *</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Газ"
          />
          {getErr('name') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('name')}</div>}
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Субсчёт ГК по умолчанию</label>
          <select className="input" value={subId} onChange={(e) => setSubId(e.target.value)}>
            <option value="">— не задан —</option>
            {subOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} · {s.name}
                {s.module_code ? ` · [${s.module_code}]` : ''}
              </option>
            ))}
          </select>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            При выборе этой статьи в OPEX-модалке субсчёт подставится автоматически.
          </div>
        </div>

        <div className="field">
          <label>Модуль (опц.)</label>
          <select className="input" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
            <option value="">— не привязан —</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Родительская статья (опц.)</label>
          <select className="input" value={parentId} onChange={(e) => setParentId(e.target.value)}>
            <option value="">— нет —</option>
            {parentOptions.map((p) => (
              <option key={p.id} value={p.id}>{p.code} · {p.name}</option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Активна
          </label>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметки</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
