'use client';

import Badge from '@/components/ui/Badge';

/**
 * Рендер AuditLog.diff в человекочитаемой форме.
 *
 * Backend (apps/audit/services/diff.py) пишет три формата:
 *   - {field: {before: X, after: Y}}  — изменения существующего объекта
 *   - {_created: {field: value, ...}} — создание (single key marker)
 *   - {_deleted: {field: value, ...}} — удаление
 *
 * Снапшот плоский: FKs хранятся как '<name>_id' → строка-pk.
 */

interface DiffEntry {
  before: unknown;
  after: unknown;
}

type Diff = Record<string, unknown>;

// Поля, которые служебные и в UI пользы не несут — спрятать.
const HIDDEN_FIELDS = new Set([
  'updated_at',
  'created_at',
  'id',
]);

// Человекочитаемые лейблы для часто меняющихся полей. Без матчинга
// показываем raw имя в monospace.
const FIELD_LABEL: Record<string, string> = {
  status: 'Статус',
  payment_status: 'Статус оплаты',
  doc_number: 'Номер документа',
  date: 'Дата',
  amount_uzs: 'Сумма (UZS)',
  amount_foreign: 'Сумма (валюта)',
  exchange_rate: 'Курс',
  exchange_rate_source_id: 'Источник курса',
  paid_amount_uzs: 'Оплачено (UZS)',
  notes: 'Заметки',
  posted_at: 'Время проведения',
  warehouse_id: 'Склад',
  warehouse_to_id: 'Склад-получатель',
  warehouse_from_id: 'Склад-источник',
  counterparty_id: 'Контрагент',
  currency_id: 'Валюта',
  module_id: 'Модуль',
  organization_id: 'Организация',
  current_quantity: 'Остаток',
  current_quantity_kg: 'Остаток (кг)',
  bags_remaining: 'Мешков остаток',
  credit_override_reason: 'Причина override',
  cost_uzs: 'Себестоимость',
  cost_per_unit_uzs: 'Себестоимость/ед.',
  quantity: 'Кол-во',
  unit_price_uzs: 'Цена/ед.',
};

function labelFor(field: string): string {
  return FIELD_LABEL[field] ?? field;
}

function isFieldLikelyId(field: string): boolean {
  // _id поля — это сериализованные FK (см. snapshot_model). Показываем
  // как pk-строку, без попыток резолвить — drill-down делается через
  // вкладку «Контекст».
  return field.endsWith('_id');
}

function formatValue(v: unknown, field: string): React.ReactNode {
  if (v === null || v === undefined) {
    return <span style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>—</span>;
  }
  if (typeof v === 'boolean') return v ? 'да' : 'нет';
  if (typeof v === 'string') {
    if (v === '') return <span style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>—</span>;
    // ISO дата/время
    if (/^\d{4}-\d{2}-\d{2}T/.test(v)) {
      const d = new Date(v);
      if (!Number.isNaN(d.getTime())) {
        return (
          <span className="mono" style={{ fontSize: 12 }}>
            {d.toLocaleString('ru-RU')}
          </span>
        );
      }
    }
    if (isFieldLikelyId(field)) {
      // FK pk показываем короче: первые 8 символов UUID — этого хватает
      // глазами свериться. Полный pk на hover.
      return (
        <span className="mono" title={v} style={{ fontSize: 12 }}>
          {v.length > 12 ? v.slice(0, 8) + '…' : v}
        </span>
      );
    }
    return <span style={{ wordBreak: 'break-word' }}>{v}</span>;
  }
  return (
    <span className="mono" style={{ fontSize: 12 }}>
      {JSON.stringify(v)}
    </span>
  );
}

function isDiffEntry(v: unknown): v is DiffEntry {
  return (
    typeof v === 'object' && v !== null
    && ('before' in (v as Record<string, unknown>))
    && ('after' in (v as Record<string, unknown>))
  );
}

function DiffRow({
  field, before, after, mode,
}: {
  field: string;
  before: unknown;
  after: unknown;
  mode: 'change' | 'create' | 'delete';
}) {
  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      <td style={{
        padding: '8px 12px', verticalAlign: 'top',
        fontWeight: 500, whiteSpace: 'nowrap',
        color: FIELD_LABEL[field] ? 'var(--fg-1)' : 'var(--fg-2)',
      }}>
        {labelFor(field)}
        {!FIELD_LABEL[field] && (
          <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
            {field}
          </div>
        )}
      </td>
      <td style={{
        padding: '8px 12px', verticalAlign: 'top',
        textDecoration: mode === 'delete' ? 'line-through' : undefined,
        color: mode === 'create' ? 'var(--fg-3)' : 'var(--fg-1)',
      }}>
        {mode === 'create' ? (
          <span style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>—</span>
        ) : (
          formatValue(before, field)
        )}
      </td>
      <td style={{
        padding: '8px 6px', verticalAlign: 'top',
        color: 'var(--fg-3)', textAlign: 'center', width: 24,
      }}>
        →
      </td>
      <td style={{
        padding: '8px 12px', verticalAlign: 'top',
        color: mode === 'delete' ? 'var(--fg-3)' : 'var(--fg-1)',
        fontWeight: mode === 'change' ? 500 : undefined,
      }}>
        {mode === 'delete' ? (
          <span style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>удалено</span>
        ) : (
          formatValue(after, field)
        )}
      </td>
    </tr>
  );
}

export default function DiffTable({ diff }: { diff: Diff }) {
  // Создание/удаление — один корневой маркер.
  if ('_created' in diff && typeof diff._created === 'object') {
    const fields = diff._created as Record<string, unknown>;
    const rows = Object.entries(fields).filter(([f]) => !HIDDEN_FIELDS.has(f));
    return (
      <div>
        <div style={{ padding: '8px 12px', background: 'var(--success-soft)' }}>
          <Badge tone="success">Создано</Badge>
        </div>
        <DiffTableBody rows={rows.map(([f, v]) => ({ field: f, before: null, after: v, mode: 'create' as const }))} />
      </div>
    );
  }
  if ('_deleted' in diff && typeof diff._deleted === 'object') {
    const fields = diff._deleted as Record<string, unknown>;
    const rows = Object.entries(fields).filter(([f]) => !HIDDEN_FIELDS.has(f));
    return (
      <div>
        <div style={{ padding: '8px 12px', background: 'var(--danger-soft, #fde2e2)' }}>
          <Badge tone="danger">Удалено</Badge>
        </div>
        <DiffTableBody rows={rows.map(([f, v]) => ({ field: f, before: v, after: null, mode: 'delete' as const }))} />
      </div>
    );
  }

  // Обычные изменения.
  const rows = Object.entries(diff)
    .filter(([f, v]) => !HIDDEN_FIELDS.has(f) && isDiffEntry(v))
    .map(([f, v]) => {
      const entry = v as DiffEntry;
      return { field: f, before: entry.before, after: entry.after, mode: 'change' as const };
    });

  if (rows.length === 0) {
    return (
      <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
        Нет изменённых полей (всё попало в HIDDEN_FIELDS — обычно это
        служебные `updated_at` / `id`).
      </div>
    );
  }

  return <DiffTableBody rows={rows} />;
}

function DiffTableBody({
  rows,
}: {
  rows: { field: string; before: unknown; after: unknown; mode: 'change' | 'create' | 'delete' }[];
}) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
      <thead>
        <tr style={{ background: 'var(--bg-soft)', borderBottom: '1px solid var(--border)' }}>
          <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--fg-3)', fontWeight: 500 }}>
            Поле
          </th>
          <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--fg-3)', fontWeight: 500 }}>
            Было
          </th>
          <th />
          <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--fg-3)', fontWeight: 500 }}>
            Стало
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <DiffRow key={r.field} {...r} />
        ))}
      </tbody>
    </table>
  );
}
