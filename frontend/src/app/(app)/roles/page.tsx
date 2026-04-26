'use client';

import { useMemo, useState } from 'react';

import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useAssignUserRole,
  useCreateRole,
  useMemberships,
  useRolesCrud,
  useUserRoles,
} from '@/hooks/useRbac';
import { ApiError } from '@/lib/api';
import type { RoleFull } from '@/types/auth';

import RoleDetailDrawer from './RoleDetailDrawer';
import UserOverridesPanel from './UserOverridesPanel';

type Tab = 'roles' | 'overrides';

export default function RolesPage() {
  const { data: roles, isLoading, error } = useRolesCrud();
  const { data: allAssignments } = useUserRoles();
  const createRole = useCreateRole();

  const [tab, setTab] = useState<Tab>('roles');
  const [search, setSearch] = useState('');
  const [selectedRole, setSelectedRole] = useState<RoleFull | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('admin', 'rw');

  const assignmentCount = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of allAssignments ?? []) {
      m.set(a.role, (m.get(a.role) ?? 0) + 1);
    }
    return m;
  }, [allAssignments]);

  const filteredRoles = useMemo(() => {
    const list = roles ?? [];
    if (!search) return list;
    const q = search.toLowerCase();
    return list.filter(
      (r) =>
        r.code.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        (r.description ?? '').toLowerCase().includes(q),
    );
  }, [roles, search]);

  if (isLoading) {
    return (
      <>
        <div className="page-hdr">
          <div>
            <h1>Роли и права</h1>
          </div>
        </div>
        <div style={{ padding: 24, color: 'var(--fg-3)' }}>Загрузка…</div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <div className="page-hdr">
          <div>
            <h1>Роли и права</h1>
          </div>
        </div>
        <div style={{ padding: 24, color: 'var(--danger)' }}>
          Ошибка: {error.message}
          {error.status === 403 && (
            <div style={{ marginTop: 8, fontSize: 12 }}>
              Нужен уровень «admin» на модуль «Администрирование».
            </div>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Роли и права</h1>
          <div className="sub">
            Роли · матрица доступов · назначения · индивидуальные исключения
          </div>
        </div>
        <div className="actions">
          {tab === 'roles' && canEdit && (
            <>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setAssignOpen(true)}
              >
                <Icon name="users" size={14} /> Назначить роль
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setCreateOpen(true)}
              >
                <Icon name="plus" size={14} /> Новая роль
              </button>
            </>
          )}
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'roles',     label: 'Роли' },
            { value: 'overrides', label: 'Исключения' },
          ]}
          value={tab}
          onChange={(v) => setTab(v as Tab)}
        />
      </div>

      {tab === 'roles' && (
        <>
          <div className="filter-bar">
            <div className="filter-cell" style={{ flex: 1, minWidth: 240 }}>
              <label>Поиск по ролям</label>
              <input
                className="input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="код / название / описание…"
              />
            </div>
          </div>

          <Panel title={`Роли · ${filteredRoles.length}`} flush>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {filteredRoles.map((r) => {
                const count = assignmentCount.get(r.id) ?? 0;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedRole(r)}
                    style={{
                      padding: 12,
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.background =
                        'var(--bg-soft)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.background = 'transparent';
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          marginBottom: 2,
                        }}
                      >
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{r.name}</div>
                        {r.is_system && (
                          <span
                            style={{
                              fontSize: 9,
                              color: 'var(--fg-3)',
                              border: '1px solid var(--border)',
                              padding: '0 4px',
                              borderRadius: 3,
                            }}
                          >
                            sys
                          </span>
                        )}
                        {!r.is_active && (
                          <span
                            style={{
                              fontSize: 9,
                              color: 'var(--danger)',
                              border: '1px solid var(--danger)',
                              padding: '0 4px',
                              borderRadius: 3,
                            }}
                          >
                            off
                          </span>
                        )}
                      </div>
                      <div
                        className="mono"
                        style={{ fontSize: 11, color: 'var(--fg-3)' }}
                      >
                        {r.code} · {r.permissions.length} модулей
                        {r.description ? ` · ${r.description}` : ''}
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--fg-3)',
                        textAlign: 'right',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {count} {count === 1 ? 'назначение' : 'назначений'}
                    </div>
                    <Icon name="arrow-right" size={14} />
                  </div>
                );
              })}
              {filteredRoles.length === 0 && (
                <div style={{ padding: 24, color: 'var(--fg-3)', fontSize: 12 }}>
                  {search
                    ? 'Ролей по запросу не найдено.'
                    : 'Роли ещё не созданы.'}
                </div>
              )}
            </div>
          </Panel>
        </>
      )}

      {tab === 'overrides' && <UserOverridesPanel />}

      {selectedRole && (
        <RoleDetailDrawer
          role={selectedRole}
          onClose={() => setSelectedRole(null)}
        />
      )}

      {createOpen && (
        <CreateRoleModal
          onClose={() => setCreateOpen(false)}
          onSubmit={async (vars) => {
            try {
              const created = await createRole.mutateAsync(vars);
              setSelectedRole(created);
              setCreateOpen(false);
            } catch {
              /* ошибка видна в create.error */
            }
          }}
          pending={createRole.isPending}
          error={createRole.error}
        />
      )}

      {assignOpen && (
        <AssignRoleModal
          roles={roles ?? []}
          onClose={() => setAssignOpen(false)}
        />
      )}
    </>
  );
}

/* ─── Sub-components ───────────────────────────────────────────────────── */

function CreateRoleModal({
  onClose,
  onSubmit,
  pending,
  error,
}: {
  onClose: () => void;
  onSubmit: (vars: { code: string; name: string; description: string; is_active: boolean }) => void;
  pending: boolean;
  error: ApiError | null;
}) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const fieldErrors = (error instanceof ApiError && error.status === 400)
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  return (
    <Modal
      title="Новая роль"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={!code || !name || pending}
            onClick={() =>
              onSubmit({ code: code.trim(), name: name.trim(), description, is_active: true })
            }
          >
            {pending ? 'Создание…' : 'Создать'}
          </button>
        </>
      }
    >
      <div className="field">
        <label>Код (уникален) *</label>
        <input
          className="input mono"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="TECHNOLOG"
        />
        {fieldErrors.code && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {fieldErrors.code.join(' · ')}
          </div>
        )}
      </div>
      <div className="field">
        <label>Название *</label>
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Технолог"
        />
        {fieldErrors.name && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {fieldErrors.name.join(' · ')}
          </div>
        )}
      </div>
      <div className="field">
        <label>Описание</label>
        <input
          className="input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}

function AssignRoleModal({
  roles,
  onClose,
}: {
  roles: RoleFull[];
  onClose: () => void;
}) {
  const { data: memberships, isLoading: mLoading } = useMemberships();
  const assign = useAssignUserRole();
  const [membershipId, setMembershipId] = useState('');
  const [roleId, setRoleId] = useState(roles[0]?.id ?? '');

  return (
    <Modal
      title="Назначить роль"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={!membershipId || !roleId || assign.isPending}
            onClick={() =>
              assign.mutate(
                { membership: membershipId, role: roleId },
                { onSuccess: onClose },
              )
            }
          >
            {assign.isPending ? 'Назначение…' : 'Назначить'}
          </button>
        </>
      }
    >
      <div className="field">
        <label>Пользователь</label>
        <select
          className="input"
          value={membershipId}
          onChange={(e) => setMembershipId(e.target.value)}
          disabled={mLoading}
        >
          <option value="">— выберите —</option>
          {memberships?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.user_full_name} · {m.user_email}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>Роль</label>
        <select
          className="input"
          value={roleId}
          onChange={(e) => setRoleId(e.target.value)}
        >
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name} ({r.code})
            </option>
          ))}
        </select>
      </div>
      {assign.error && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>
          Ошибка: {assign.error.message}
        </div>
      )}
    </Modal>
  );
}
