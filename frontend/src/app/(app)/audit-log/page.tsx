'use client';

import { useMemo, useState } from 'react';

import ExportCsvButton from '@/components/ExportCsvButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Sparkline from '@/components/ui/Sparkline';
import { useAuditLog, useAuditStats } from '@/hooks/useAuditLog';
import { useModules } from '@/hooks/useModules';
import { useMemberships } from '@/hooks/useRbac';
import type { AuditLogEntry } from '@/types/auth';

import AuditDetailDrawer from './AuditDetailDrawer';
import AuditUserActivityDrawer from './AuditUserActivityDrawer';

const ACTIONS: { value: string; label: string }[] = [
  { value: 'create',            label: 'Создание' },
  { value: 'update',            label: 'Изменение' },
  { value: 'delete',            label: 'Удаление' },
  { value: 'post',              label: 'Проведение' },
  { value: 'unpost',            label: 'Сторно' },
  { value: 'login',             label: 'Вход' },
  { value: 'logout',            label: 'Выход' },
  { value: 'permission_change', label: 'Изменение прав' },
  { value: 'export',            label: 'Экспорт' },
  { value: 'import',            label: 'Импорт' },
  { value: 'other',             label: 'Прочее' },
];

const ACTION_LABEL: Record<string, string> = Object.fromEntries(
  ACTIONS.map((a) => [a.value, a.label]),
);

const ACTION_TONE: Record<string, 'success' | 'info' | 'danger' | 'warn' | 'neutral'> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
  post: 'success',
  unpost: 'warn',
  login: 'neutral',
  permission_change: 'warn',
};

const PAGE_SIZE = 50;

type TabKey = 'feed' | 'users' | 'modules';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'feed',    label: 'События' },
  { key: 'users',   label: 'По пользователям' },
  { key: 'modules', label: 'По модулям' },
];

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function firstDayOfMonthISO(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

export default function AuditPage() {
  const { data: modules } = useModules();
  const { data: memberships } = useMemberships();

  const [tab, setTab] = useState<TabKey>('feed');

  // Multi-select для action: пустой массив = все.
  const [actions, setActions] = useState<string[]>([]);
  const [moduleId, setModuleId] = useState('');
  const [actorId, setActorId] = useState('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [dateFrom, setDateFrom] = useState(firstDayOfMonthISO());
  const [dateTo, setDateTo] = useState(todayISO());
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);
  const [profileUser, setProfileUser] = useState<{ id: string; email: string } | null>(null);

  const filter = useMemo(
    () => ({
      actions: actions.length > 0 ? actions : undefined,
      module: moduleId || undefined,
      actor: actorId || undefined,
      date_after: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
      date_before: dateTo ? `${dateTo}T23:59:59Z` : undefined,
      search: search || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [actions, moduleId, actorId, dateFrom, dateTo, search, page],
  );

  const { data, isLoading, error, refetch, isFetching } = useAuditLog(filter);
  const rows = data?.results ?? [];

  // Stats: теперь реальные KPI за период (не за страницу).
  const statsFilter = useMemo(
    () => ({ ...filter, page: undefined, page_size: undefined }),
    [filter],
  );
  const { data: stats } = useAuditStats(statsFilter);

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
  };

  const csvUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (actions.length > 0) params.set('action__in', actions.join(','));
    if (moduleId) params.set('module', moduleId);
    if (actorId) params.set('actor', actorId);
    if (dateFrom) params.set('date_after', `${dateFrom}T00:00:00Z`);
    if (dateTo) params.set('date_before', `${dateTo}T23:59:59Z`);
    if (search) params.set('search', search);
    const qs = params.toString();
    return qs ? `/api/audit/export/?${qs}` : '/api/audit/export/';
  }, [actions, moduleId, actorId, dateFrom, dateTo, search]);

  const totalPages = Math.max(1, Math.ceil((data?.count ?? 0) / PAGE_SIZE));

  const dailyValues = (stats?.daily ?? []).map((d) => d.count);
  const totalActionsForBar =
    Object.values(stats?.by_action ?? {}).reduce((s, n) => s + n, 0) || 1;
  const totalModulesForBar =
    (stats?.by_module ?? []).reduce((s, m) => s + m.count, 0) || 1;

  const toggleAction = (code: string) => {
    setActions((prev) =>
      prev.includes(code) ? prev.filter((x) => x !== code) : [...prev, code],
    );
    setPage(1);
  };

  const resetFilters = () => {
    setActions([]);
    setModuleId('');
    setActorId('');
    setSearch('');
    setDraftSearch('');
    setDateFrom(firstDayOfMonthISO());
    setDateTo(todayISO());
    setPage(1);
  };

  const openProfile = (userId: string, email: string) => {
    setProfileUser({ id: userId, email });
  };

  const jumpToUserFeed = (userId: string) => {
    setActorId(userId);
    setTab('feed');
    setPage(1);
    setProfileUser(null);
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Журнал аудита</h1>
          <div className="sub">
            Все действия пользователей · KPI и топы за выбранный период
          </div>
        </div>
        <div className="actions">
          <ExportCsvButton url={csvUrl} filename="audit-log.csv" />
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} />
            {isFetching ? '…' : 'Обновить'}
          </button>
        </div>
      </div>

      {/* KPI: теперь из /stats/ — за весь период, не за страницу */}
      <div className="kpi-row">
        <KpiCard
          tone="orange"
          iconName="book"
          label="Записей"
          sub={`${dateFrom} — ${dateTo}`}
          value={String(stats?.total ?? data?.count ?? 0)}
        />
        <KpiCard
          tone="blue"
          iconName="users"
          label="Пользователей"
          sub="за период"
          value={String(stats?.unique_actors ?? 0)}
        />
        <KpiCard
          tone="orange"
          iconName="check"
          label="Изменений прав"
          sub="за период"
          value={String(stats?.by_action.permission_change ?? 0)}
        />
        <KpiCard
          tone="red"
          iconName="close"
          label="Удалений"
          sub="за период"
          value={String(stats?.by_action.delete ?? 0)}
        />
      </div>

      {/* Фильтры — общий для всех табов */}
      <div className="filter-bar">
        <div className="filter-cell">
          <label>С</label>
          <input
            className="input"
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          />
        </div>
        <div className="filter-cell">
          <label>По</label>
          <input
            className="input"
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          />
        </div>
        <div className="filter-cell">
          <label>Пресет</label>
          <div className="filter-presets">
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(7)); setDateTo(todayISO()); setPage(1); }}>7 дн</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(30)); setDateTo(todayISO()); setPage(1); }}>30 дн</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(90)); setDateTo(todayISO()); setPage(1); }}>90 дн</button>
          </div>
        </div>
        <div className="filter-cell" style={{ minWidth: 180 }}>
          <label>Модуль</label>
          <select className="input" value={moduleId} onChange={(e) => { setModuleId(e.target.value); setPage(1); }}>
            <option value="">Все модули</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
        <div className="filter-cell" style={{ minWidth: 200 }}>
          <label>Пользователь</label>
          <select className="input" value={actorId} onChange={(e) => { setActorId(e.target.value); setPage(1); }}>
            <option value="">Все</option>
            {memberships?.map((m) => (
              <option key={m.id} value={m.user}>
                {m.user_email}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-cell" style={{ flex: 1, minWidth: 220 }}>
          <label>Поиск</label>
          <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
              placeholder="email, объект, описание, IP…"
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-secondary btn-sm">Найти</button>
          </form>
        </div>
        <div className="filter-cell">
          <label>&nbsp;</label>
          <button className="btn btn-ghost btn-sm" onClick={resetFilters}>
            Сбросить
          </button>
        </div>
      </div>

      {/* Multi-select chips для action — над контентом таба */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          marginBottom: 12,
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em', marginRight: 4 }}>
          Действия:
        </span>
        {ACTIONS.map((a) => {
          const active = actions.includes(a.value);
          return (
            <button
              key={a.value}
              onClick={() => toggleAction(a.value)}
              className="btn btn-sm"
              style={{
                background: active ? 'var(--brand-orange)' : 'var(--bg-card)',
                color: active ? '#fff' : 'var(--fg-2)',
                border: '1px solid var(--border)',
                padding: '4px 10px',
                fontSize: 12,
              }}
            >
              {a.label}
              {stats?.by_action[a.value] != null && stats.by_action[a.value] > 0 && (
                <span style={{ marginLeft: 6, opacity: 0.7 }}>
                  · {stats.by_action[a.value]}
                </span>
              )}
            </button>
          );
        })}
        {actions.length > 0 && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setActions([]); setPage(1); }}>
            ✕ Снять
          </button>
        )}
      </div>

      {/* Табы */}
      <div className="profile-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={'profile-tab' + (tab === t.key ? ' active' : '')}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ─── ТАБ: События ──────────────────────────────────────────── */}
      {tab === 'feed' && (
        <Panel flush>
          <DataTable<AuditLogEntry>
            isLoading={isLoading}
            rows={rows}
            rowKey={(r) => r.id}
            error={error}
            emptyMessage="Нет записей за выбранный период."
            onRowClick={(r) => setSelected(r)}
            rowProps={(r) => ({ active: selected?.id === r.id })}
            columns={[
              { key: 'time', label: 'Время', mono: true,
                cellStyle: { fontSize: 12, color: 'var(--fg-2)', whiteSpace: 'nowrap' },
                render: (r) => new Date(r.occurred_at).toLocaleString('ru-RU') },
              { key: 'actor', label: 'Пользователь',
                cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                render: (r) =>
                  r.actor && r.actor_email ? (
                    <button
                      className="btn-link"
                      onClick={(e) => { e.stopPropagation(); openProfile(r.actor!, r.actor_email!); }}
                      style={{ background: 'none', border: 'none', padding: 0, color: 'var(--brand-orange)', cursor: 'pointer', fontSize: 12 }}
                    >
                      {r.actor_email}
                    </button>
                  ) : '—'
              },
              { key: 'module', label: 'Модуль', mono: true,
                cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                render: (r) => r.module_code ?? '—' },
              { key: 'action', label: 'Действие',
                render: (r) => <Badge tone={ACTION_TONE[r.action] ?? 'neutral'}>{ACTION_LABEL[r.action] ?? r.action}</Badge> },
              { key: 'entity', label: 'Объект',
                cellStyle: { fontSize: 12 },
                render: (r) => r.entity_repr || (r.entity_type ?? '—') },
              { key: 'verb', label: 'Описание',
                cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                render: (r) => r.action_verb || '—' },
              { key: 'ip', label: 'IP', mono: true,
                cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                render: (r) => r.ip_address ?? '—' },
              { key: 'actions', label: '', align: 'right',
                render: (r) => (
                  <RowActions
                    actions={[
                      { label: 'Подробнее', onClick: () => setSelected(r) },
                      ...(r.actor && r.actor_email
                        ? [{ label: 'Профиль юзера', onClick: () => openProfile(r.actor!, r.actor_email!) }]
                        : []),
                    ]}
                  />
                ) },
            ]}
          />
          {data && data.count > PAGE_SIZE && (
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', padding: '8px 12px',
              borderTop: '1px solid var(--border)',
              fontSize: 12, color: 'var(--fg-3)',
            }}>
              <span>
                Стр. {page} из {totalPages} · всего {data.count}
              </span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={!data.previous}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  ← Назад
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={!data.next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Вперёд →
                </button>
              </div>
            </div>
          )}
        </Panel>
      )}

      {/* ─── ТАБ: По пользователям ─────────────────────────────────── */}
      {tab === 'users' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} className="audit-grid">
          <Panel title="Топ-10 пользователей" flush>
            {!stats || stats.top_actors.length === 0 ? (
              <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-3)' }}>
                Нет данных за выбранный период.
              </div>
            ) : (
              <table className="kv-table" style={{ width: '100%' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ fontSize: 11, color: 'var(--fg-3)', textAlign: 'left', padding: '8px 10px' }}>Email · ФИО</th>
                    <th style={{ fontSize: 11, color: 'var(--fg-3)', textAlign: 'right', padding: '8px 10px' }}>Действий</th>
                    <th style={{ width: 120, padding: '8px 10px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top_actors.map((a) => (
                    <tr key={a.user_id} style={{ borderBottom: '1px solid var(--border-soft)' }}>
                      <td style={{ padding: '8px 10px' }}>
                        <div style={{ fontSize: 13, color: 'var(--fg-1)', fontWeight: 500 }}>
                          {a.email}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                          {a.full_name || '—'}
                        </div>
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', fontSize: 13, color: 'var(--fg-2)' }}>
                        {a.count}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => openProfile(a.user_id, a.email)}
                        >
                          Профиль →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Panel title="Активность по дням">
              {dailyValues.length === 0 ? (
                <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-3)' }}>
                  Нет данных за выбранный период.
                </div>
              ) : (
                <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <Sparkline values={dailyValues} width={420} height={70} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--fg-3)' }}>
                    <span>{stats?.daily[0]?.date}</span>
                    <span>макс/день: {Math.max(...dailyValues)}</span>
                    <span>{stats?.daily[stats.daily.length - 1]?.date}</span>
                  </div>
                </div>
              )}
            </Panel>

            <Panel title="Распределение по типам">
              {!stats || Object.keys(stats.by_action).length === 0 ? (
                <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-3)' }}>
                  Нет данных.
                </div>
              ) : (
                <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(stats.by_action)
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
                              background: ACTION_TONE[code] === 'danger' ? 'var(--danger)'
                                : ACTION_TONE[code] === 'warn' ? 'var(--warn)'
                                : ACTION_TONE[code] === 'success' ? 'var(--success)'
                                : 'var(--brand-orange)',
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
          </div>
        </div>
      )}

      {/* ─── ТАБ: По модулям ───────────────────────────────────────── */}
      {tab === 'modules' && (
        <Panel title="Топ модулей по активности" flush>
          {!stats || stats.by_module.length === 0 ? (
            <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-3)' }}>
              Нет данных за выбранный период.
            </div>
          ) : (
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {stats.by_module.map((m) => (
                <div key={m.code} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ minWidth: 160, fontSize: 13, fontFamily: 'var(--font-mono)' }}>
                    {m.code}
                  </div>
                  <div style={{ flex: 1, height: 10, background: 'var(--bg-soft)', borderRadius: 4, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${(m.count / totalModulesForBar) * 100}%`,
                        height: '100%',
                        background: 'var(--brand-orange)',
                      }}
                    />
                  </div>
                  <div style={{ minWidth: 60, fontSize: 12, textAlign: 'right', color: 'var(--fg-2)' }}>
                    {m.count}
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      const mod = modules?.find((mm) => mm.code === m.code);
                      if (mod) {
                        setModuleId(mod.id);
                        setTab('feed');
                        setPage(1);
                      }
                    }}
                  >
                    В ленту →
                  </button>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {selected && (
        <AuditDetailDrawer
          entry={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {profileUser && (
        <AuditUserActivityDrawer
          userId={profileUser.id}
          userEmail={profileUser.email}
          dateAfter={filter.date_after}
          dateBefore={filter.date_before}
          onClose={() => setProfileUser(null)}
          onJumpToFeed={() => jumpToUserFeed(profileUser.id)}
        />
      )}
    </>
  );
}
