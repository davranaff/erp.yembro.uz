'use client';

import { useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';
import type { AuditLogEntry } from '@/types/auth';

import DiffTable from './DiffTable';

interface Props {
  entry: AuditLogEntry;
  onClose: () => void;
}

const ACTION_LABEL: Record<string, string> = {
  create: 'Создание',
  update: 'Изменение',
  delete: 'Удаление',
  post: 'Проведение',
  unpost: 'Отмена проведения',
  login: 'Вход',
  logout: 'Выход',
  export: 'Экспорт',
  import: 'Импорт',
  permission_change: 'Изменение прав',
  other: 'Прочее',
};

const ACTION_TONE: Record<string, 'success' | 'info' | 'danger' | 'warn' | 'neutral'> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
  post: 'success',
  unpost: 'warn',
  login: 'neutral',
  permission_change: 'warn',
};

/**
 * Если знаем content_type → возвращаем route для drill-down. Известные
 * сущности захардкожены, остальные показываются без ссылки.
 */
function entityRoute(entityType: string | null | undefined): string | null {
  if (!entityType) return null;
  const map: Record<string, string> = {
    purchaseorder: '/purchases',
    saleorder: '/sales',
    payment: '/finance/cashbox',
    journalentry: '/ledger',
    stockmovement: '/stock',
    role: '/roles',
    counterparty: '/counterparties',
    nomenclatureitem: '/nomenclature',
    batch: '/traceability',
    warehouse: '/stock',
  };
  return map[entityType] ?? null;
}

export default function AuditDetailDrawer({ entry, onClose }: Props) {
  const [tab, setTab] = useState<'overview' | 'diff' | 'context'>('overview');
  const hasDiff = entry.diff != null && Object.keys(entry.diff).length > 0;
  const route = entityRoute(entry.entity_type);

  return (
    <DetailDrawer
      title={'Аудит · ' + (ACTION_LABEL[entry.action] ?? entry.action)}
      subtitle={
        new Date(entry.occurred_at).toLocaleString('ru-RU') +
        ' · ' +
        (entry.actor_email ?? '—') +
        (entry.module_code ? ' · ' + entry.module_code : '')
      }
      tabs={[
        { key: 'overview', label: 'Обзор' },
        { key: 'diff', label: 'Diff', count: hasDiff ? Object.keys(entry.diff!).length : 0 },
        { key: 'context', label: 'Контекст' },
      ]}
      activeTab={tab}
      onTab={(k) => setTab(k as typeof tab)}
      onClose={onClose}
    >
      {tab === 'overview' && (
        <KV
          items={[
            {
              k: 'Время',
              v: new Date(entry.occurred_at).toLocaleString('ru-RU'),
              mono: true,
            },
            { k: 'Пользователь', v: entry.actor_email ?? '—' },
            {
              k: 'Действие',
              v: (
                <Badge tone={ACTION_TONE[entry.action] ?? 'neutral'}>
                  {ACTION_LABEL[entry.action] ?? entry.action}
                </Badge>
              ),
            },
            { k: 'Модуль', v: entry.module_code ?? '—', mono: true },
            { k: 'Тип объекта', v: entry.entity_type ?? '—', mono: true },
            { k: 'Объект', v: entry.entity_repr || '—' },
            { k: 'Описание', v: entry.action_verb || '—' },
            { k: 'IP', v: entry.ip_address ?? '—', mono: true },
            { k: 'User-Agent', v: entry.user_agent || '—' },
          ]}
        />
      )}

      {tab === 'diff' && (
        <Panel title="Изменения полей" flush>
          {!hasDiff ? (
            <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
              Diff не записан для этого события. Backend начал писать
              diff в audit_log() недавно — для старых записей поле NULL.
              Также diff не пишется на action <code>login</code> и подобных,
              где нет «до/после».
            </div>
          ) : (
            <DiffTable diff={entry.diff as Record<string, unknown>} />
          )}
        </Panel>
      )}

      {tab === 'context' && (
        <>
          <KV
            items={[
              { k: 'Сущность', v: entry.entity_type ?? '—', mono: true },
              { k: 'ID объекта', v: entry.entity_object_id ?? '—', mono: true },
              { k: 'Snapshot', v: entry.entity_repr || '—' },
            ]}
          />
          {route && entry.entity_object_id && (
            <a
              href={`${route}?id=${entry.entity_object_id}`}
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 8 }}
            >
              Открыть в модуле {entry.entity_type} →
            </a>
          )}
          {!route && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 8 }}>
              Для типа <code>{entry.entity_type ?? '—'}</code> drill-down не
              настроен. ID объекта виден выше — найдите его вручную.
            </div>
          )}
        </>
      )}
    </DetailDrawer>
  );
}
