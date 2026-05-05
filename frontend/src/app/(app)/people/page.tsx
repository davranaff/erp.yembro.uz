'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TablePagination from '@/components/ui/TablePagination';
import { useDeactivatePerson, usePeoplePaginated } from '@/hooks/usePeople';
import { useHasLevel } from '@/hooks/usePermissions';
import type { MembershipRow } from '@/types/auth';

import PersonModal from './PersonModal';

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен',
  vacation: 'Отпуск',
  sick_leave: 'Больничный',
  terminated: 'Уволен',
};

const STATUS_TONE: Record<string, 'success' | 'warn' | 'neutral' | 'info'> = {
  active: 'success',
  vacation: 'info',
  sick_leave: 'warn',
  terminated: 'neutral',
};

function initials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

export default function PeoplePage() {
  const [isActive, setIsActive] = useState('true');
  const [workStatus, setWorkStatus] = useState('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<MembershipRow | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('admin', 'rw');

  const filter = useMemo(
    () => ({
      is_active: isActive || undefined,
      work_status: workStatus || undefined,
      search: search || undefined,
    }),
    [isActive, workStatus, search],
  );

  const { data: pageData, isLoading, error, refetch, isFetching } = usePeoplePaginated(filter, page, pageSize);
  const data = pageData?.results ?? [];
  const deactivate = useDeactivatePerson();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
  };

  const handleEdit = (m: MembershipRow) => {
    setEditing(m);
    setModalOpen(true);
  };

  const handleDeactivate = (m: MembershipRow) => {
    if (!confirm(`Уволить «${m.user_full_name}»?\n\nАккаунт сохранится, но membership деактивируется.`)) return;
    deactivate.mutate(m.id, {
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Сотрудники</h1>
          <div className="sub">
            Штат компании · {pageData?.count ?? 0} человек · назначение ролей — в разделе «Роли и права»
          </div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} />
            {isFetching ? '…' : 'Обновить'}
          </button>
          {canEdit && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                setEditing(null);
                setModalOpen(true);
              }}
            >
              <Icon name="plus" size={14} />
              Добавить сотрудника
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: 'true',  label: 'Активные' },
            { value: 'false', label: 'Неактивные' },
            { value: '',      label: 'Все' },
          ]}
          value={isActive}
          onChange={(v) => { setIsActive(v); setPage(1); }}
        />
        <select
          className="input"
          value={workStatus}
          onChange={(e) => { setWorkStatus(e.target.value); setPage(1); }}
          style={{ width: 180 }}
        >
          <option value="">Любой статус</option>
          <option value="active">Активен</option>
          <option value="vacation">Отпуск</option>
          <option value="sick_leave">Больничный</option>
          <option value="terminated">Уволен</option>
        </select>
        <div style={{ flex: 1, minWidth: 200 }}>
          <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              placeholder="Поиск по ФИО / email / должности…"
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-secondary btn-sm">
              Найти
            </button>
          </form>
        </div>
      </div>

      <Panel flush>
        <DataTable<MembershipRow>
          isLoading={isLoading}
          rows={data}
          rowKey={(p) => p.id}
          error={error}
          emptyMessage={
            <>
              Нет сотрудников.{' '}
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setEditing(null); setModalOpen(true); }}
                style={{ marginLeft: 8 }}
              >
                Добавить первого
              </button>
            </>
          }
          onRowClick={(p) => handleEdit(p)}
          columns={[
            { key: 'emp', label: 'Сотрудник',
              render: (p) => (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      background: 'var(--brand-yellow-soft)',
                      color: 'var(--fg-1)',
                      display: 'grid',
                      placeItems: 'center',
                      fontSize: 11,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    {initials(p.user_full_name ?? '')}
                  </div>
                  <span style={{ fontWeight: 500 }}>{p.user_full_name ?? '—'}</span>
                </div>
              ) },
            { key: 'pos', label: 'Должность', cellStyle: { fontSize: 12 },
              render: (p) => p.position_title || '—' },
            { key: 'email', label: 'Email', mono: true,
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (p) => p.user_email ?? '—' },
            { key: 'phone', label: 'Телефон', mono: true,
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (p) => p.work_phone || '—' },
            { key: 'status', label: 'Статус',
              render: (p) => (
                <Badge tone={STATUS_TONE[p.work_status] ?? 'neutral'} dot>
                  {STATUS_LABEL[p.work_status] ?? p.work_status}
                </Badge>
              ) },
            { key: 'active', label: 'Активность',
              render: (p) => p.is_active
                ? <Badge tone="success" dot>Активен</Badge>
                : <Badge tone="neutral" dot>Деактивирован</Badge> },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (p) => canEdit ? (
                <RowActions
                  actions={[
                    { label: 'Редактировать', onClick: () => handleEdit(p) },
                    {
                      label: 'Уволить',
                      danger: true,
                      hidden: !p.is_active,
                      disabled: deactivate.isPending,
                      onClick: () => handleDeactivate(p),
                    },
                  ]}
                />
              ) : null },
          ]}
        />
        {pageData && (
          <TablePagination
            page={page}
            pageSize={pageSize}
            count={pageData.count}
            hasPrev={Boolean(pageData.previous)}
            hasNext={Boolean(pageData.next)}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        )}
      </Panel>

      {modalOpen && (
        <PersonModal
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
