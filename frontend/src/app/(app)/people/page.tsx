'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TablePagination from '@/components/ui/TablePagination';
import { useTerminatePerson, usePeoplePaginated } from '@/hooks/usePeople';
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

const COMP_TYPE_LABEL: Record<string, string> = {
  monthly_salary: 'Оклад',
  per_shift: 'Смена',
  per_hour: 'Час',
};

function fmtUzs(value: string | null) {
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

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
  const hrVisible = hasLevel('hr', 'r');

  const filter = useMemo(
    () => ({
      is_active: isActive || undefined,
      work_status: workStatus || undefined,
      search: search || undefined,
      include_compensation: hrVisible || undefined,
      include_balance: hrVisible || undefined,
    }),
    [isActive, workStatus, search, hrVisible],
  );

  const { data: pageData, isLoading, error, refetch, isFetching } = usePeoplePaginated(filter, page, pageSize);
  const data = pageData?.results ?? [];
  const terminate = useTerminatePerson();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
  };

  const handleEdit = (m: MembershipRow) => {
    setEditing(m);
    setModalOpen(true);
  };

  const handleDeactivate = async (m: MembershipRow) => {
    if (!confirm(`Уволить «${m.user_full_name}»?\n\nАккаунт сохранится, ставка и график будут закрыты сегодня.`)) return;
    try {
      const res = await terminate.mutateAsync({ id: m.id });
      const balance = Number(res.balance_at_termination);
      if (balance > 0) {
        alert(`Уволен. Долг сотруднику: ${balance.toLocaleString('ru-RU')} сум.`);
      } else if (balance < 0) {
        alert(`Уволен. Переплата: ${Math.abs(balance).toLocaleString('ru-RU')} сум.`);
      }
    } catch (err) {
      alert(`Не удалось: ${(err as Error).message}`);
    }
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
          columns={[
            { key: 'emp', label: 'Сотрудник',
              render: (p) => (
                <Link
                  href={`/people/${p.id}`}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', color: 'inherit' }}
                >
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
                </Link>
              ) },
            { key: 'pos', label: 'Должность', cellStyle: { fontSize: 12 },
              render: (p) => p.position_title || '—' },
            { key: 'email', label: 'Email', mono: true,
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (p) => p.user_email ?? '—' },
            { key: 'phone', label: 'Телефон', mono: true,
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (p) => p.work_phone || '—' },
            ...(hrVisible ? [
              { key: 'comp', label: 'Тип оплаты',
                render: (p: MembershipRow) => p.compensation_type
                  ? <Badge tone="info">{COMP_TYPE_LABEL[p.compensation_type] ?? p.compensation_type}</Badge>
                  : <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>—</span> },
              { key: 'rate', label: 'Ставка', mono: true, align: 'right' as const,
                cellStyle: { fontSize: 12 },
                render: (p: MembershipRow) => {
                  if (!p.current_rate_uzs) return '—';
                  const native = `${fmtUzs(p.current_rate_uzs)} ${p.current_rate_currency ?? ''}`.trim();
                  const isFx = p.current_rate_currency && p.current_rate_currency !== 'UZS';
                  if (isFx && p.current_rate_uzs_equiv) {
                    return (
                      <span title={`≈ ${fmtUzs(p.current_rate_uzs_equiv)} сум`}>
                        {native}
                        <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                          ≈ {fmtUzs(p.current_rate_uzs_equiv)} сум
                        </div>
                      </span>
                    );
                  }
                  return native;
                } },
              { key: 'balance', label: 'Баланс', mono: true, align: 'right' as const,
                cellStyle: { fontSize: 12 },
                render: (p: MembershipRow) => {
                  const v = p.balance_uzs;
                  if (v === null || v === undefined || v === '') return '—';
                  const n = Number(v);
                  if (!Number.isFinite(n)) return '—';
                  const tone = n > 0 ? 'var(--accent-success)' : n < 0 ? 'var(--accent-warn)' : 'var(--fg-2)';
                  return <span style={{ color: tone }}>{fmtUzs(v)}</span>;
                } },
            ] : []),
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
                    { label: 'Открыть', onClick: () => { window.location.href = `/people/${p.id}`; } },
                    { label: 'Редактировать', onClick: () => handleEdit(p) },
                    {
                      label: 'Уволить',
                      danger: true,
                      hidden: !p.is_active,
                      disabled: terminate.isPending,
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
