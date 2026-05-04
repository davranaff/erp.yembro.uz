'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { useModules } from '@/hooks/useModules';
import {
  useDeleteRole,
  useMemberships,
  useRemoveUserRole,
  useUpdateRole,
  useUpsertRolePermission,
  useUserRoles,
} from '@/hooks/useRbac';
import type { ModuleLevel, RoleFull, UserRoleAssignment } from '@/types/auth';

interface Props {
  role: RoleFull;
  onClose: () => void;
}

const LEVELS: ModuleLevel[] = ['none', 'r', 'rw', 'admin'];
const LEVEL_LABEL: Record<ModuleLevel, string> = {
  none: '—',
  r: 'R',
  rw: 'RW',
  admin: 'A',
};
const LEVEL_COLOR: Record<ModuleLevel, string> = {
  none: 'var(--fg-muted)',
  r: 'var(--info)',
  rw: 'var(--success)',
  admin: 'var(--brand-orange)',
};
const LEVEL_BG: Record<ModuleLevel, string> = {
  none: 'transparent',
  r: 'var(--info-soft)',
  rw: 'var(--success-soft)',
  admin: 'var(--brand-orange-soft)',
};

function cycleLevel(current: ModuleLevel): ModuleLevel {
  return LEVELS[(LEVELS.indexOf(current) + 1) % LEVELS.length];
}

export default function RoleDetailDrawer({ role, onClose }: Props) {
  const [tab, setTab] = useState<'overview' | 'matrix' | 'assignments'>('overview');

  const { data: modules } = useModules();
  const { data: allAssignments } = useUserRoles();
  const { data: memberships } = useMemberships();
  const updateRole = useUpdateRole();
  const deleteRole = useDeleteRole();
  const upsertPermission = useUpsertRolePermission();
  const removeUserRole = useRemoveUserRole();

  const modulesList = (modules ?? []).filter((m) => m.is_active);
  const assignments = useMemo(
    () => (allAssignments ?? []).filter((a) => a.role === role.id),
    [allAssignments, role.id],
  );
  const membershipEmail = useMemo(
    () => new Map((memberships ?? []).map((m) => [m.id, m.user_email])),
    [memberships],
  );

  const handleToggleCell = (
    moduleId: string,
    current: ModuleLevel,
    existingId: string | null,
  ) => {
    const next = cycleLevel(current);
    upsertPermission.mutate({
      role: role.id,
      module: moduleId,
      level: next,
      existing_id: existingId,
    });
  };

  const handleDelete = () => {
    if (!confirm('Удалить роль ' + role.name + '?')) return;
    deleteRole.mutate(role.id, {
      onSuccess: () => onClose(),
    });
  };

  const handleToggleActive = () => {
    updateRole.mutate({
      id: role.id,
      patch: { is_active: !role.is_active },
    });
  };

  return (
    <DetailDrawer
      title={'Роль · ' + role.name}
      subtitle={
        role.code +
        ' · ' +
        role.permissions.length +
        ' модулей · ' +
        assignments.length +
        ' назначений' +
        (role.is_system ? ' · system' : '')
      }
      tabs={[
        { key: 'overview',    label: 'Обзор' },
        { key: 'matrix',      label: 'Матрица прав', count: role.permissions.length },
        { key: 'assignments', label: 'Назначения',   count: assignments.length },
      ]}
      activeTab={tab}
      onTab={(k) => setTab(k as typeof tab)}
      onClose={onClose}
      actions={
        <>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleToggleActive}
            disabled={updateRole.isPending || role.is_system}
          >
            {role.is_active ? 'Деактивировать' : 'Активировать'}
          </button>
          {!role.is_system && (
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--danger)' }}
              onClick={handleDelete}
              disabled={deleteRole.isPending}
            >
              Удалить
            </button>
          )}
        </>
      }
    >
      {tab === 'overview' && (
        <KV
          items={[
            { k: 'Код', v: role.code, mono: true },
            { k: 'Название', v: role.name },
            { k: 'Описание', v: role.description || '—' },
            {
              k: 'Тип',
              v: role.is_system ? (
                <Badge tone="warn">Системная</Badge>
              ) : (
                <Badge tone="info">Пользовательская</Badge>
              ),
            },
            {
              k: 'Статус',
              v: role.is_active ? (
                <Badge tone="success">Активна</Badge>
              ) : (
                <Badge tone="neutral">Отключена</Badge>
              ),
            },
            { k: 'Модулей с правами', v: String(role.permissions.length), mono: true },
            { k: 'Назначений', v: String(assignments.length), mono: true },
          ]}
        />
      )}

      {tab === 'matrix' && (
        <Panel flush>
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-3)',
              padding: '8px 12px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            Клик по ячейке переключает уровень: — → R → RW → A → —
          </div>
          <div style={{ overflowX: 'auto', padding: 12 }}>
            <table className="matrix">
              <thead>
                <tr>
                  <th className="rowhead">Модуль</th>
                  <th style={{ textAlign: 'center' }}>Уровень</th>
                </tr>
              </thead>
              <tbody>
                {modulesList.map((m) => {
                  const found = role.permissions.find(
                    (p) => p.module_code === m.code,
                  );
                  const lvl: ModuleLevel = (found?.level as ModuleLevel) ?? 'none';
                  const existingId = found?.id ?? null;
                  const busy =
                    upsertPermission.isPending &&
                    upsertPermission.variables?.role === role.id &&
                    upsertPermission.variables?.module === m.id;
                  return (
                    <tr key={m.id}>
                      <td className="rowhead">
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{m.name}</div>
                        <div
                          className="mono"
                          style={{ fontSize: 10, color: 'var(--fg-3)' }}
                        >
                          {m.code}
                        </div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <button
                          onClick={() => handleToggleCell(m.id, lvl, existingId)}
                          disabled={busy || role.is_system}
                          style={{
                            background: LEVEL_BG[lvl],
                            color: LEVEL_COLOR[lvl],
                            fontFamily: 'var(--font-mono)',
                            fontSize: 12,
                            fontWeight: 700,
                            padding: '4px 12px',
                            border: '1px solid ' + LEVEL_COLOR[lvl],
                            borderRadius: 4,
                            cursor: role.is_system ? 'not-allowed' : 'pointer',
                            minWidth: 50,
                            opacity: role.is_system ? 0.5 : 1,
                          }}
                          title={
                            role.is_system
                              ? 'Системная роль — изменение заблокировано'
                              : 'Клик для смены уровня'
                          }
                        >
                          {busy ? '…' : LEVEL_LABEL[lvl]}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {tab === 'assignments' && (
        <Panel title={`Назначения · ${assignments.length}`} flush>
          <DataTable<UserRoleAssignment>
            rows={assignments}
            rowKey={(a) => a.id}
            emptyMessage="Роль никому не назначена."
            columns={[
              { key: 'user', label: 'Пользователь',
                render: (a) => a.user_email ?? membershipEmail.get(a.membership) ?? '—' },
              { key: 'assigned', label: 'Назначена', mono: true,
                cellStyle: { fontSize: 12, color: 'var(--fg-3)' },
                render: (a) => new Date(a.assigned_at).toLocaleString('ru') },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (a) => (
                  <RowActions
                    actions={[
                      {
                        label: 'Снять роль',
                        danger: true,
                        disabled: removeUserRole.isPending,
                        onClick: () => {
                          if (confirm('Снять роль с пользователя?')) {
                            removeUserRole.mutate(a.id);
                          }
                        },
                      },
                    ]}
                  />
                ) },
            ]}
          />
        </Panel>
      )}
    </DetailDrawer>
  );
}
