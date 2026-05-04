'use client';

import Panel from '@/components/ui/Panel';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useOrganizationModules,
  useToggleOrganizationModule,
} from '@/hooks/useOrganizationModules';

const KIND_LABEL: Record<string, string> = {
  core: 'Ядро',
  matochnik: 'Маточник',
  incubation: 'Инкубация',
  feedlot: 'Фабрика откорма',
  slaughter: 'Убойня',
  feed: 'Корма',
  vet: 'Вет. аптека',
  stock: 'Склад',
  ledger: 'Проводки',
  reports: 'Отчёты',
  purchases: 'Закупки',
  admin: 'Администрирование',
};

export default function ModulesSection() {
  const { data, isLoading, error } = useOrganizationModules();
  const toggle = useToggleOrganizationModule();
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('admin', 'rw');

  if (isLoading) {
    return (
      <Panel title="Модули">
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
      </Panel>
    );
  }
  if (error) {
    return (
      <Panel title="Модули">
        <div style={{ padding: 16, color: 'var(--danger)' }}>
          Ошибка: {error.message}
        </div>
      </Panel>
    );
  }

  const rows = data ?? [];

  return (
    <Panel title="Модули">
      {!canEdit && (
        <div
          style={{
            marginBottom: 12,
            padding: 8,
            fontSize: 12,
            color: 'var(--fg-3)',
            background: 'var(--bg-soft)',
            borderRadius: 4,
          }}
        >
          Только просмотр. Для переключения модулей нужны права администратора.
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rows.map((row) => {
          const busy = toggle.isPending && toggle.variables?.id === row.id;
          return (
            <div
              key={row.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto',
                gap: 12,
                padding: '10px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: row.is_enabled ? 'var(--bg-card)' : 'var(--bg-soft)',
                opacity: row.is_enabled ? 1 : 0.7,
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {row.module_name}{' '}
                  <span
                    className="mono"
                    style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 6 }}
                  >
                    {row.module_code}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  {KIND_LABEL[row.module_kind] ?? row.module_kind}
                  {row.enabled_at && row.is_enabled
                    ? ` · активен с ${new Date(row.enabled_at).toLocaleDateString('ru')}`
                    : ''}
                </div>
              </div>

              <button
                className={`btn ${row.is_enabled ? 'btn-ghost' : 'btn-primary'}`}
                onClick={() => toggle.mutate({ id: row.id, is_enabled: !row.is_enabled })}
                disabled={!canEdit || busy}
              >
                {busy ? '…' : row.is_enabled ? 'Отключить' : 'Включить'}
              </button>
            </div>
          );
        })}
      </div>

      {toggle.error && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {toggle.error.message}
        </div>
      )}
    </Panel>
  );
}
