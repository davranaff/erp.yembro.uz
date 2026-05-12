'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TablePagination from '@/components/ui/TablePagination';
import TgConnectModal from '@/components/ui/TgConnectModal';
import {
  useCounterpartiesPaginated,
  useDeleteCounterparty,
} from '@/hooks/useCounterparties';
import { useHasLevel } from '@/hooks/usePermissions';
import type { Counterparty, CounterpartyKind } from '@/types/auth';

import CounterpartyModal from './CounterpartyModal';

const KIND_LABEL: Record<CounterpartyKind, string> = {
  supplier: 'Поставщик',
  buyer: 'Покупатель',
  other: 'Прочее',
};

function kindTone(kind: CounterpartyKind): 'success' | 'neutral' | 'info' {
  if (kind === 'buyer') return 'success';
  if (kind === 'other') return 'info';
  return 'neutral';
}

function fmtBalance(
  v: string, kind: string,
): { text: string; sub: string; color: string } {
  const n = parseFloat(v || '0');
  const abs = Math.abs(n).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
  if (n === 0) {
    return { text: '0', sub: 'нет расчётов', color: 'var(--fg-3)' };
  }
  // Семантика знака зависит от роли:
  //   buyer  : + клиент нам должен (зелёный),  − у нас его предоплата (синий)
  //   supplier: + мы ему должны (красный),     − его предоплата (синий)
  //   other  : чистый знак (как есть)
  if (kind === 'buyer') {
    if (n > 0) return { text: `+${abs}`, sub: 'должен нам', color: 'var(--success)' };
    return { text: `−${abs}`,           sub: 'предоплата', color: 'var(--info)' };
  }
  if (kind === 'supplier') {
    if (n > 0) return { text: `+${abs}`, sub: 'мы должны', color: 'var(--danger)' };
    return { text: `−${abs}`,           sub: 'наша предоплата', color: 'var(--info)' };
  }
  if (n > 0) return { text: `+${abs}`, sub: '', color: 'var(--success)' };
  return { text: `−${abs}`, sub: '', color: 'var(--danger)' };
}

export default function CounterpartiesPage() {
  const router = useRouter();
  const [kind, setKind] = useState('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Counterparty | null>(null);
  const [tgModal, setTgModal] = useState<Counterparty | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('core', 'rw');

  const filter = useMemo(
    () => ({
      kind: kind || undefined,
      search: search || undefined,
    }),
    [kind, search],
  );

  const { data, isLoading, error, refetch, isFetching } = useCounterpartiesPaginated(
    filter, page, pageSize,
  );
  const rows = data?.results ?? [];
  const del = useDeleteCounterparty();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
  };

  const handleEdit = (c: Counterparty) => {
    setEditing(c);
    setModalOpen(true);
  };

  const handleDelete = (c: Counterparty) => {
    if (!confirm(`Удалить «${c.name}»?`)) return;
    del.mutate(c.id, {
      onError: (err) => alert(`Не удалось удалить: ${err.message}`),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Контрагенты</h1>
          <div className="sub">Общий справочник компании · доступен всем модулям</div>
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
              Новый контрагент
            </button>
          )}
        </div>
      </div>

      <div
        style={{
          padding: 10,
          background: 'var(--warning-soft)',
          border: '1px solid var(--warning)',
          borderRadius: 4,
          fontSize: 12,
          marginBottom: 16,
          color: '#6A4500',
        }}
      >
        <b>Общий справочник.</b> Одна карточка = один контрагент для всей компании. С одним поставщиком работают и модуль «Корма», и склад, и бухгалтерия — это исключает дубли и бардак в отчётности.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: '',         label: 'Все' },
            { value: 'supplier', label: 'Поставщики' },
            { value: 'buyer',    label: 'Покупатели' },
            { value: 'other',    label: 'Прочие' },
          ]}
          value={kind}
          onChange={(v) => { setKind(v); setPage(1); }}
        />
        <div style={{ flex: 1, minWidth: 200 }}>
          <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              placeholder="Поиск по коду / названию / ИНН…"
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
        <DataTable<Counterparty>
          isLoading={isLoading}
          rows={rows}
          rowKey={(r) => r.id}
          error={error}
          emptyMessage={
            <>
              Нет контрагентов.{' '}
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setEditing(null); setModalOpen(true); }}
                style={{ marginLeft: 8 }}
              >
                Создать первого
              </button>
            </>
          }
          onRowClick={(r) => router.push(`/counterparties/${r.id}`)}
          columns={[
            { key: 'code', label: 'Код',
              render: (r) => <span className="badge id">{r.code}</span> },
            { key: 'name', label: 'Наименование', cellStyle: { fontWeight: 500 },
              render: (r) => r.name },
            { key: 'kind', label: 'Тип',
              render: (r) => <Badge tone={kindTone(r.kind)}>{KIND_LABEL[r.kind]}</Badge> },
            { key: 'balance', label: 'Баланс, UZS', align: 'right', mono: true,
              render: (r) => {
                const bal = fmtBalance(r.balance_uzs, r.kind);
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                    <span style={{ fontWeight: 700, color: bal.color, fontSize: 13 }}>
                      {bal.text}
                    </span>
                    {bal.sub && (
                      <span style={{
                        fontSize: 10, color: 'var(--fg-3)',
                        textTransform: 'uppercase', letterSpacing: '.04em',
                      }}>
                        {bal.sub}
                      </span>
                    )}
                  </div>
                );
              } },
            { key: 'status', label: 'Статус',
              render: (r) => r.is_active
                ? <Badge tone="success" dot>Активен</Badge>
                : <Badge tone="neutral" dot>Заблокирован</Badge> },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (r) => (
                <RowActions
                  actions={[
                    {
                      label: 'Открыть карточку',
                      onClick: () => router.push(`/counterparties/${r.id}`),
                    },
                    {
                      label: 'Привязать Telegram',
                      onClick: () => setTgModal(r),
                    },
                    ...(canEdit ? [
                      { label: 'Редактировать', onClick: () => handleEdit(r) },
                      {
                        label: 'Удалить',
                        danger: true,
                        disabled: del.isPending,
                        onClick: () => handleDelete(r),
                      },
                    ] : []),
                  ]}
                />
              ) },
          ]}
        />
        {data && (
          <TablePagination
            page={page}
            pageSize={pageSize}
            count={data.count}
            hasPrev={Boolean(data.previous)}
            hasNext={Boolean(data.next)}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        )}
      </Panel>

      {tgModal && (
        <TgConnectModal
          mode="counterparty"
          counterpartyId={tgModal.id}
          counterpartyName={tgModal.name}
          onClose={() => setTgModal(null)}
        />
      )}

      {modalOpen && (
        <CounterpartyModal
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
