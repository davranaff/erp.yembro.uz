'use client';

import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import {
  useDeleteOverride,
  useUserOverrides,
  type UserModuleAccessOverride,
} from '@/hooks/useRbac';
import type { ModuleLevel } from '@/types/auth';

import OverrideModal from './OverrideModal';

const LEVEL_TONE: Record<ModuleLevel, 'neutral' | 'info' | 'success' | 'warn'> = {
  none: 'neutral',
  r: 'info',
  rw: 'success',
  admin: 'warn',
};

const LEVEL_LABEL: Record<ModuleLevel, string> = {
  none: '— нет доступа',
  r: 'R',
  rw: 'RW',
  admin: 'Admin',
};

export default function UserOverridesPanel() {
  const { data: overrides, isLoading, error } = useUserOverrides();
  const remove = useDeleteOverride();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<UserModuleAccessOverride | null>(null);

  const handleDelete = (o: UserModuleAccessOverride) => {
    if (
      !confirm(
        'Снять исключение для ' +
          (o.user_email ?? '?') +
          ' на модуль ' +
          (o.module_code ?? '?') +
          '?',
      )
    ) {
      return;
    }
    remove.mutate(o.id);
  };

  return (
    <>
      <Panel
        title={`Исключения · ${overrides?.length ?? 0}`}
        flush
        tools={
          <button
            className="btn btn-primary btn-sm"
            onClick={() => {
              setEditing(null);
              setModalOpen(true);
            }}
          >
            <Icon name="plus" size={14} /> Новое исключение
          </button>
        }
      >
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-3)',
            padding: '8px 12px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          Индивидуальные доступы перекрывают права роли. Например —
          интерим-замена, временное ограничение, расширение прав без выдачи
          новой роли.
        </div>
        <DataTable<UserModuleAccessOverride>
          isLoading={isLoading}
          rows={overrides}
          rowKey={(o) => o.id}
          error={error}
          emptyMessage="Исключений нет."
          columns={[
            { key: 'user', label: 'Пользователь',
              render: (o) => o.user_email ?? '—' },
            { key: 'module', label: 'Модуль', mono: true,
              cellStyle: { fontSize: 12 },
              render: (o) => o.module_code ?? '—' },
            { key: 'level', label: 'Уровень',
              render: (o) => (
                <Badge tone={LEVEL_TONE[o.level]}>{LEVEL_LABEL[o.level]}</Badge>
              ) },
            { key: 'reason', label: 'Причина',
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (o) => o.reason || '—' },
            { key: 'created', label: 'Создано', mono: true,
              cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (o) => new Date(o.created_at).toLocaleString('ru-RU') },
            { key: 'actions', label: '', align: 'right',
              render: (o) => (
                <RowActions
                  actions={[
                    {
                      label: 'Изменить',
                      onClick: () => {
                        setEditing(o);
                        setModalOpen(true);
                      },
                    },
                    {
                      label: 'Снять',
                      danger: true,
                      disabled: remove.isPending,
                      onClick: () => handleDelete(o),
                    },
                  ]}
                />
              ) },
          ]}
        />
      </Panel>

      {modalOpen && (
        <OverrideModal
          initial={editing}
          onClose={() => {
            setModalOpen(false);
            setEditing(null);
          }}
        />
      )}
    </>
  );
}
