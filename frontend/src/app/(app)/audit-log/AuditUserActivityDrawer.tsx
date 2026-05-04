'use client';

import { useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';
import Sparkline from '@/components/ui/Sparkline';
import { useAuditUserActivity } from '@/hooks/useAuditLog';

interface Props {
  userId: string;
  userEmail: string;
  dateAfter: string | undefined;
  dateBefore: string | undefined;
  onClose: () => void;
  /** Кликом по строке в "последних событиях" — переключиться на ленту с фильтром по этому юзеру. */
  onJumpToFeed: () => void;
}

const ACTION_LABEL: Record<string, string> = {
  create: 'Создание',
  update: 'Изменение',
  delete: 'Удаление',
  post: 'Проведение',
  unpost: 'Сторно',
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

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU');
}

export default function AuditUserActivityDrawer({
  userId,
  userEmail,
  dateAfter,
  dateBefore,
  onClose,
  onJumpToFeed,
}: Props) {
  const [tab, setTab] = useState<'overview' | 'modules' | 'recent' | 'security'>('overview');

  const { data, isLoading, error } = useAuditUserActivity(userId, {
    date_after: dateAfter,
    date_before: dateBefore,
  });

  const dailyValues = (data?.daily ?? []).map((d) => d.count);
  const totalActionsForBar =
    Object.values(data?.by_action ?? {}).reduce((s, n) => s + n, 0) || 1;

  return (
    <DetailDrawer
      title={`Активность · ${userEmail}`}
      subtitle={
        data?.user.full_name
          ? `${data.user.full_name} · ${data.total} действий за период`
          : 'Загрузка…'
      }
      tabs={[
        { key: 'overview', label: 'Обзор' },
        { key: 'modules', label: 'Модули', count: data?.by_module.length ?? 0 },
        { key: 'recent', label: 'Последние', count: data?.recent.length ?? 0 },
        { key: 'security', label: 'IP / вход' },
      ]}
      activeTab={tab}
      onTab={(k) => setTab(k as typeof tab)}
      onClose={onClose}
      actions={
        <button className="btn btn-secondary btn-sm" onClick={onJumpToFeed}>
          В ленту →
        </button>
      }
    >
      {isLoading && (
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
      )}
      {error && (
        <div style={{ padding: 16, color: 'var(--danger)' }}>
          Ошибка: {String(error.message ?? error)}
        </div>
      )}

      {data && tab === 'overview' && (
        <>
          <KV
            items={[
              { k: 'Email', v: data.user.email, mono: true },
              { k: 'ФИО', v: data.user.full_name },
              { k: 'Действий за период', v: String(data.total) },
              { k: 'Логинов', v: String(data.logins) },
              { k: 'Первое событие', v: fmtDateTime(data.first_event), mono: true },
              { k: 'Последнее событие', v: fmtDateTime(data.last_event), mono: true },
            ]}
          />

          <Panel title="Активность по дням" style={{ marginBottom: 12 }}>
            {dailyValues.length === 0 ? (
              <div style={{ padding: 12, fontSize: 13, color: 'var(--fg-3)' }}>
                Нет данных за выбранный период.
              </div>
            ) : (
              <div style={{ padding: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
                <Sparkline values={dailyValues} width={280} height={56} />
                <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                  {data.daily[0]?.date} — {data.daily[data.daily.length - 1]?.date}
                  <br />
                  макс/день: {Math.max(...dailyValues)}
                </div>
              </div>
            )}
          </Panel>

          <Panel title="По типам действий">
            {Object.keys(data.by_action).length === 0 ? (
              <div style={{ padding: 12, fontSize: 13, color: 'var(--fg-3)' }}>
                Нет действий за период.
              </div>
            ) : (
              <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(data.by_action)
                  .sort((a, b) => b[1] - a[1])
                  .map(([code, count]) => (
                    <div key={code} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ minWidth: 130, fontSize: 12 }}>
                        {ACTION_LABEL[code] ?? code}
                      </div>
                      <div style={{ flex: 1, height: 8, background: 'var(--bg-soft)', borderRadius: 4, overflow: 'hidden' }}>
                        <div
                          style={{
                            width: `${(count / totalActionsForBar) * 100}%`,
                            height: '100%',
                            background: 'var(--brand-orange)',
                          }}
                        />
                      </div>
                      <div style={{ minWidth: 36, fontSize: 12, textAlign: 'right', color: 'var(--fg-2)' }}>
                        {count}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </Panel>
        </>
      )}

      {data && tab === 'modules' && (
        <Panel title="Активность по модулям и сущностям">
          <div style={{ padding: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 6 }}>
              Модули
            </div>
            {data.by_module.length === 0 ? (
              <div style={{ padding: 8, fontSize: 13, color: 'var(--fg-3)' }}>
                Нет данных.
              </div>
            ) : (
              <table className="kv-table" style={{ width: '100%', marginBottom: 16 }}>
                <tbody>
                  {data.by_module.map((m) => (
                    <tr key={m.code}>
                      <td style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                        {m.code}
                      </td>
                      <td style={{ fontSize: 12, textAlign: 'right', color: 'var(--fg-2)' }}>
                        {m.count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 6 }}>
              Сущности (топ-10)
            </div>
            {data.by_entity.length === 0 ? (
              <div style={{ padding: 8, fontSize: 13, color: 'var(--fg-3)' }}>
                Нет данных.
              </div>
            ) : (
              <table className="kv-table" style={{ width: '100%' }}>
                <tbody>
                  {data.by_entity.map((e) => (
                    <tr key={e.entity_type}>
                      <td style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                        {e.entity_type}
                      </td>
                      <td style={{ fontSize: 12, textAlign: 'right', color: 'var(--fg-2)' }}>
                        {e.count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Panel>
      )}

      {data && tab === 'recent' && (
        <Panel title="Последние 20 событий">
          {data.recent.length === 0 ? (
            <div style={{ padding: 12, fontSize: 13, color: 'var(--fg-3)' }}>
              Событий нет.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {data.recent.map((r) => (
                <div
                  key={r.id}
                  style={{
                    padding: '8px 10px',
                    borderBottom: '1px solid var(--border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <Badge tone={ACTION_TONE[r.action] ?? 'neutral'}>
                      {ACTION_LABEL[r.action] ?? r.action}
                    </Badge>
                    <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                      {fmtDateTime(r.occurred_at)}
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-1)' }}>
                    {r.entity_repr || r.entity_type || '—'}
                  </div>
                  {r.action_verb && (
                    <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                      {r.action_verb}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {data && tab === 'security' && (
        <>
          <KV
            items={[
              { k: 'Логинов за период', v: String(data.logins) },
              { k: 'Уникальных IP', v: String(data.unique_ips.length) },
            ]}
          />
          <Panel title="IP-адреса (топ-10)">
            {data.unique_ips.length === 0 ? (
              <div style={{ padding: 12, fontSize: 13, color: 'var(--fg-3)' }}>
                Нет записей с IP за выбранный период.
              </div>
            ) : (
              <table className="kv-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ fontSize: 11, color: 'var(--fg-3)', textAlign: 'left', padding: '6px 10px' }}>IP</th>
                    <th style={{ fontSize: 11, color: 'var(--fg-3)', textAlign: 'right', padding: '6px 10px' }}>Действий</th>
                  </tr>
                </thead>
                <tbody>
                  {data.unique_ips.map((it) => (
                    <tr key={it.ip}>
                      <td style={{ fontSize: 12, fontFamily: 'var(--font-mono)', padding: '6px 10px' }}>
                        {it.ip}
                      </td>
                      <td style={{ fontSize: 12, textAlign: 'right', padding: '6px 10px', color: 'var(--fg-2)' }}>
                        {it.count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </DetailDrawer>
  );
}
