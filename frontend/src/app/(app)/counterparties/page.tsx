'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TgConnectModal from '@/components/ui/TgConnectModal';
import {
  useCounterparties,
  useDeleteCounterparty,
} from '@/hooks/useCounterparties';
import { useHasLevel } from '@/hooks/usePermissions';
import { useTgCounterpartyLink } from '@/hooks/useTgBot';
import type { Counterparty, CounterpartyKind } from '@/types/auth';

import CounterpartyModal from './CounterpartyModal';

function TgStatusButton({ counterparty, onOpenModal }: { counterparty: Counterparty; onOpenModal: () => void }) {
  const { data: link } = useTgCounterpartyLink(counterparty.id);
  const connected = Boolean(link);
  return (
    <button
      onClick={onOpenModal}
      title={connected ? `Telegram подключён${link?.tg_username ? `: @${link.tg_username}` : ''}` : 'Привязать Telegram'}
      className="btn btn-secondary btn-sm"
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        color: connected ? '#229ED9' : undefined,
      }}
    >
      {/* Telegram plane icon */}
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <path
          d="M22 2L11 13"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        />
        <path
          d="M22 2L15 22L11 13L2 9L22 2Z"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        />
      </svg>
      {connected ? 'TG подключён' : 'Привязать TG'}
    </button>
  );
}

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

function fmtBalance(v: string): { text: string; color: string } {
  const n = parseFloat(v || '0');
  const text = n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
  if (n > 0) return { text: `+${text}`, color: 'var(--success)' };
  if (n < 0) return { text, color: 'var(--danger)' };
  return { text, color: 'var(--fg-1)' };
}

export default function CounterpartiesPage() {
  const [kind, setKind] = useState('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [sel, setSel] = useState<Counterparty | null>(null);
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

  const { data, isLoading, error, refetch, isFetching } = useCounterparties(filter);
  const del = useDeleteCounterparty();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
  };

  const handleEdit = (c: Counterparty) => {
    setEditing(c);
    setModalOpen(true);
  };

  const handleDelete = (c: Counterparty) => {
    if (!confirm(`Удалить «${c.name}»?`)) return;
    del.mutate(c.id, {
      onSuccess: () => {
        if (sel?.id === c.id) setSel(null);
      },
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
          onChange={(v) => setKind(v)}
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
          rows={data}
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
          onRowClick={(r) => setSel(r)}
          rowProps={(r) => ({ active: sel?.id === r.id })}
          columns={[
            { key: 'code', label: 'Код',
              render: (r) => <span className="badge id">{r.code}</span> },
            { key: 'name', label: 'Наименование', cellStyle: { fontWeight: 500 },
              render: (r) => r.name },
            { key: 'kind', label: 'Тип',
              render: (r) => <Badge tone={kindTone(r.kind)}>{KIND_LABEL[r.kind]}</Badge> },
            { key: 'spec', label: 'Специализация',
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (r) => r.specialization || '—' },
            { key: 'inn', label: 'ИНН', mono: true,
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (r) => r.inn || '—' },
            { key: 'balance', label: 'Сальдо, UZS', align: 'right', mono: true,
              render: (r) => {
                const bal = fmtBalance(r.balance_uzs);
                return <span style={{ fontWeight: 600, color: bal.color }}>{bal.text}</span>;
              } },
            { key: 'status', label: 'Статус',
              render: (r) => r.is_active
                ? <Badge tone="success" dot>Активен</Badge>
                : <Badge tone="neutral" dot>Заблокирован</Badge> },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (r) => canEdit ? (
                <RowActions
                  actions={[
                    { label: 'Редактировать', onClick: () => handleEdit(r) },
                    {
                      label: 'Удалить',
                      danger: true,
                      disabled: del.isPending,
                      onClick: () => handleDelete(r),
                    },
                  ]}
                />
              ) : null },
          ]}
        />
      </Panel>

      {sel && (
        <DetailDrawer
          title={sel.name}
          subtitle={`${sel.code} · ${KIND_LABEL[sel.kind]} · ИНН ${sel.inn || '—'}`}
          onClose={() => setSel(null)}
          actions={
            canEdit ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <TgStatusButton counterparty={sel} onOpenModal={() => setTgModal(sel)} />
                <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(sel)}>
                  Редактировать
                </button>
              </div>
            ) : null
          }
        >
          <KV
            items={[
              { k: 'Код', v: sel.code, mono: true },
              { k: 'Тип', v: <Badge tone={kindTone(sel.kind)}>{KIND_LABEL[sel.kind]}</Badge> },
              { k: 'ИНН', v: sel.inn || '—', mono: true },
              { k: 'Телефон', v: sel.phone || '—' },
              { k: 'Email', v: sel.email || '—' },
              { k: 'Специализация', v: sel.specialization || '—' },
              { k: 'Сальдо, UZS', v: fmtBalance(sel.balance_uzs).text, mono: true },
              {
                k: 'Статус',
                v: sel.is_active ? (
                  <Badge tone="success" dot>Активен</Badge>
                ) : (
                  <Badge tone="neutral" dot>Заблокирован</Badge>
                ),
              },
              ...(sel.address ? [{ k: 'Адрес', v: sel.address }] : []),
              ...(sel.notes ? [{ k: 'Примечание', v: sel.notes }] : []),
            ]}
          />
        </DetailDrawer>
      )}

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
          onSaved={(c) => {
            if (sel?.id === c.id) setSel(c);
          }}
        />
      )}
    </>
  );
}
