'use client';

import Panel from '@/components/ui/Panel';
import { useModules } from '@/hooks/useModules';
import { useRoles, type Role } from '@/hooks/useRoles';

const LEVEL_LABEL: Record<string, string> = {
  none: '—',
  r: 'R',
  rw: 'RW',
  admin: 'A',
};

const LEVEL_COLOR: Record<string, string> = {
  none: 'var(--fg-3)',
  r: 'var(--info)',
  rw: 'var(--success)',
  admin: 'var(--brand-orange)',
};

function levelFor(role: Role, moduleCode: string): string {
  const found = role.permissions.find((p) => p.module_code === moduleCode);
  return found?.level ?? 'none';
}

export default function RolesSection() {
  const { data: roles, isLoading, error } = useRoles();
  const { data: modules } = useModules();

  if (isLoading) {
    return (
      <Panel title="Роли и права">
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
      </Panel>
    );
  }
  if (error) {
    return (
      <Panel title="Роли и права">
        <div style={{ padding: 16, color: 'var(--danger)' }}>
          Ошибка: {error.message}
        </div>
      </Panel>
    );
  }

  const rolesList = roles ?? [];
  const modulesList = (modules ?? []).filter((m) => m.is_active);

  return (
    <Panel title={`Роли и права · ${rolesList.length} ролей`}>
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginBottom: 10,
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <span>R — чтение</span>
        <span>RW — запись</span>
        <span>A — админ</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 12,
            minWidth: 600,
          }}
        >
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th
                style={{
                  textAlign: 'left',
                  padding: 8,
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: '.05em',
                }}
              >
                Модуль
              </th>
              {rolesList.map((r) => (
                <th
                  key={r.id}
                  style={{
                    textAlign: 'center',
                    padding: 8,
                    fontSize: 11,
                    fontWeight: 600,
                    color: 'var(--fg-3)',
                    textTransform: 'uppercase',
                    letterSpacing: '.05em',
                  }}
                  title={r.description}
                >
                  {r.name}
                  {r.is_system && (
                    <div style={{ fontSize: 9, color: 'var(--fg-muted)', fontWeight: 400 }}>
                      системная
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {modulesList.map((m) => (
              <tr key={m.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '8px', fontSize: 12 }}>
                  <div style={{ fontWeight: 500 }}>{m.name}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                    {m.code}
                  </div>
                </td>
                {rolesList.map((r) => {
                  const lv = levelFor(r, m.code);
                  return (
                    <td
                      key={`${r.id}-${m.id}`}
                      style={{
                        textAlign: 'center',
                        padding: 8,
                        color: LEVEL_COLOR[lv] ?? 'var(--fg-3)',
                        fontWeight: lv === 'none' ? 400 : 700,
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {LEVEL_LABEL[lv] ?? '—'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 16, fontSize: 11, color: 'var(--fg-3)' }}>
        Редактирование ролей и переопределения прав пользователей — через страницу{' '}
        <a href="/roles" style={{ color: 'var(--brand-orange)' }}>
          Роли и права
        </a>
        .
      </div>
    </Panel>
  );
}
