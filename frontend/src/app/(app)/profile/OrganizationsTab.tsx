'use client';

import Panel from '@/components/ui/Panel';
import { useAuth } from '@/contexts/AuthContext';
import type { Membership } from '@/types/auth';

const DIRECTION_LABEL: Record<string, string> = {
  broiler: 'Бройлер',
  egg: 'Яичное',
  mixed: 'Смешанное',
};

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен',
  vacation: 'Отпуск',
  sick_leave: 'Больничный',
  terminated: 'Уволен',
};

function permissionsSummary(perms: Record<string, string>): string {
  const entries = Object.entries(perms).filter(([, lvl]) => lvl !== 'none');
  if (entries.length === 0) return 'нет прав';
  return `${entries.length} модулей`;
}

export default function OrganizationsTab() {
  const { user, org, setOrg } = useAuth();

  if (!user) return null;
  const memberships = user.memberships ?? [];

  const handleSwitch = (m: Membership) => {
    setOrg({ code: m.organization.code, name: m.organization.name });
  };

  return (
    <Panel title="Организации">
      {memberships.length === 0 && (
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>
          У вас нет активных организаций.
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {memberships.map((m) => {
          const active = org?.code === m.organization.code;
          return (
            <div
              key={m.id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'auto 1fr auto',
                gap: 12,
                alignItems: 'center',
                padding: 10,
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: active ? 'var(--bg-soft)' : 'var(--bg-card)',
                outline: active ? '1px solid var(--brand-orange)' : 'none',
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 6,
                  background: 'var(--brand-orange)',
                  color: 'white',
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: 14,
                  fontWeight: 700,
                }}
              >
                {m.organization.code.slice(0, 2).toUpperCase()}
              </div>

              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {m.organization.name}
                  {active && (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 11,
                        color: 'var(--brand-orange)',
                        fontWeight: 500,
                      }}
                    >
                      · активная
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  {[
                    m.position_title || '—',
                    DIRECTION_LABEL[m.organization.direction] ?? m.organization.direction,
                    STATUS_LABEL[m.work_status] ?? m.work_status,
                    permissionsSummary(m.module_permissions),
                  ].join(' · ')}
                </div>
              </div>

              <button
                className="btn btn-ghost"
                onClick={() => handleSwitch(m)}
                disabled={active}
              >
                {active ? 'Выбрана' : 'Переключиться'}
              </button>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
