'use client';

import { useState } from 'react';

import Panel from '@/components/ui/Panel';
import Icon from '@/components/ui/Icon';
import { useAccounts } from '@/hooks/useAccounts';

const TYPE_LABEL: Record<string, string> = {
  asset: 'Активный',
  liability: 'Пассивный',
  equity: 'Капитал',
  income: 'Доход',
  expense: 'Расход',
  contra: 'Контр-счёт',
};

export default function AccountsSection() {
  const { data, isLoading, error } = useAccounts();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (isLoading) {
    return (
      <Panel title="План счетов">
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
      </Panel>
    );
  }
  if (error) {
    return (
      <Panel title="План счетов">
        <div style={{ padding: 16, color: 'var(--danger)' }}>
          Ошибка: {error.message}
        </div>
      </Panel>
    );
  }

  const rows = data ?? [];

  return (
    <Panel title={`План счетов · ${rows.length} счетов`}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '100px 1fr 160px 80px',
          gap: 6,
          fontSize: 11,
          color: 'var(--fg-3)',
          padding: '0 10px 8px',
          borderBottom: '1px solid var(--border)',
          textTransform: 'uppercase',
          letterSpacing: '.05em',
        }}
      >
        <div>Код</div>
        <div>Название</div>
        <div>Тип</div>
        <div style={{ textAlign: 'right' }}>Субсчетов</div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {rows.map((acc) => {
          const isOpen = expanded.has(acc.id);
          const subs = acc.subaccounts ?? [];
          return (
            <div key={acc.id} style={{ borderBottom: '1px solid var(--border)' }}>
              <div
                onClick={() => subs.length && toggle(acc.id)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '100px 1fr 160px 80px',
                  gap: 6,
                  alignItems: 'center',
                  padding: 10,
                  cursor: subs.length ? 'pointer' : 'default',
                }}
              >
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                  {acc.code}
                </div>
                <div style={{ fontSize: 13 }}>{acc.name}</div>
                <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  {TYPE_LABEL[acc.type] ?? acc.type}
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 12,
                    color: 'var(--fg-3)',
                    textAlign: 'right',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'flex-end',
                    gap: 4,
                  }}
                >
                  {subs.length}
                  {subs.length > 0 && (
                    <Icon name={isOpen ? 'chevron-down' : 'chevron-right'} size={12} />
                  )}
                </div>
              </div>

              {isOpen && subs.length > 0 && (
                <div style={{ padding: '0 10px 10px 30px', background: 'var(--bg-soft)' }}>
                  {subs.map((s) => (
                    <div
                      key={s.id}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '100px 1fr 140px',
                        gap: 6,
                        padding: '6px 0',
                        fontSize: 12,
                      }}
                    >
                      <span className="mono" style={{ color: 'var(--fg-2)' }}>
                        {s.code}
                      </span>
                      <span>{s.name}</span>
                      <span style={{ color: 'var(--fg-3)' }}>
                        {s.module_code ? `модуль: ${s.module_code}` : '—'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {rows.length === 0 && (
        <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
          План счетов пуст.
        </div>
      )}
    </Panel>
  );
}
