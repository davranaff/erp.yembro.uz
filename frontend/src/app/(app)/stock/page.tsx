'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import ExportCsvButton from '@/components/ExportCsvButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useDeleteManualMovement,
  useDeleteWarehouse,
  useStockMovements,
  useStockMovementsStats,
  useWarehouses,
} from '@/hooks/useStockMovements';
import type { StockMovement, StockMovementKind, WarehouseRef } from '@/types/auth';

import StockMovementModal from './StockMovementModal';
import WarehouseModal from './WarehouseModal';

const KIND_LABEL: Record<StockMovementKind, string> = {
  incoming: 'Приход',
  outgoing: 'Расход',
  transfer: 'Перемещение',
  write_off: 'Списание',
};

const KIND_TONE: Record<StockMovementKind, 'success' | 'neutral' | 'info' | 'warn'> = {
  incoming: 'success',
  outgoing: 'neutral',
  transfer: 'info',
  write_off: 'warn',
};

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('ru', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function fmtMoney(v: string | null | undefined) {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

function signedQty(m: StockMovement): { text: string; color: string } {
  const q = m.quantity;
  if (m.kind === 'incoming') return { text: `+${q}`, color: 'var(--success)' };
  if (m.kind === 'outgoing' || m.kind === 'write_off')
    return { text: `−${q}`, color: 'var(--danger)' };
  return { text: q, color: 'var(--fg-1)' };
}

function fmtMoneyShort(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
  return n.toFixed(0);
}

type Tab = 'movements' | 'warehouses';

export default function StockPage() {
  const [tab, setTab] = useState<Tab>('movements');

  // Movements tab state
  const [kind, setKind] = useState<string>('');
  const [moduleCode, setModuleCode] = useState<string>('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [sel, setSel] = useState<StockMovement | null>(null);
  const [showMovementModal, setShowMovementModal] = useState(false);

  // Warehouses tab state
  const [warehouseEdit, setWarehouseEdit] = useState<WarehouseRef | null>(null);
  const [showWarehouseModal, setShowWarehouseModal] = useState(false);
  const [whSearch, setWhSearch] = useState('');

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('stock', 'rw');

  const filter = useMemo(
    () => ({
      kind: kind || undefined,
      module_code: moduleCode || undefined,
      warehouse_from: warehouseId || undefined,
      search: search || undefined,
      limit: 200,
    }),
    [kind, moduleCode, warehouseId, search],
  );

  const { data, isLoading, error, refetch, isFetching } = useStockMovements(filter);
  const { data: stats } = useStockMovementsStats(filter);
  const { data: warehouses } = useWarehouses({ is_active: '' });
  const deleteMovement = useDeleteManualMovement();
  const deleteWarehouse = useDeleteWarehouse();

  const csvUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (filter.kind) params.set('kind', filter.kind);
    if (filter.module_code) params.set('module_code', filter.module_code);
    if (filter.warehouse_from) params.set('warehouse_from', filter.warehouse_from);
    if (filter.search) params.set('search', filter.search);
    const qs = params.toString();
    return qs
      ? `/api/warehouses/movements/?${qs}`
      : '/api/warehouses/movements/';
  }, [filter]);

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
  };

  const handleDeleteMovement = async (m: StockMovement) => {
    if (!confirm(`Удалить движение ${m.doc_number}?`)) return;
    try {
      await deleteMovement.mutateAsync(m.id);
      if (sel?.id === m.id) setSel(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Не удалось удалить движение';
      alert(msg);
    }
  };

  const handleDeleteWarehouse = async (w: WarehouseRef) => {
    if (!confirm(`Удалить склад ${w.code} · ${w.name}?\nДействие необратимо, если по складу есть движения — удаление будет заблокировано.`)) return;
    try {
      await deleteWarehouse.mutateAsync(w.id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Не удалось удалить склад';
      alert(msg);
    }
  };

  const filteredWarehouses = useMemo(() => {
    if (!warehouses) return [];
    if (!whSearch) return warehouses;
    const q = whSearch.toLowerCase();
    return warehouses.filter(
      (w) =>
        w.code.toLowerCase().includes(q) ||
        w.name.toLowerCase().includes(q) ||
        (w.module_name ?? '').toLowerCase().includes(q),
    );
  }, [warehouses, whSearch]);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Склад и движения</h1>
          <div className="sub">Сквозной журнал по всем модулям и складам</div>
        </div>
        <div className="actions">
          {tab === 'movements' && (
            <>
              <ExportCsvButton url={csvUrl} filename="stock-movements.csv" />
              {canEdit && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setShowMovementModal(true)}
                >
                  <Icon name="plus" size={14} />
                  Новое движение
                </button>
              )}
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => refetch()}
                disabled={isFetching}
              >
                <Icon name="chart" size={14} />
                {isFetching ? '…' : 'Обновить'}
              </button>
            </>
          )}
          {tab === 'warehouses' && canEdit && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                setWarehouseEdit(null);
                setShowWarehouseModal(true);
              }}
            >
              <Icon name="plus" size={14} />
              Новый склад
            </button>
          )}
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'movements',  label: 'Движения' },
            { value: 'warehouses', label: 'Склады' },
          ]}
          value={tab}
          onChange={(v) => setTab(v as Tab)}
        />
      </div>

      {tab === 'movements' && (
        <>
          <div className="kpi-row" style={{ marginBottom: 12 }}>
            <KpiCard
              tone="orange"
              iconName="chart"
              label="Движений"
              sub="по фильтру"
              value={stats ? String(stats.total_count) : '…'}
            />
            <KpiCard
              tone="green"
              iconName="check"
              label="Приход"
              sub={stats ? `${stats.by_kind.incoming.count} док.` : ''}
              value={stats ? fmtMoneyShort(stats.by_kind.incoming.amount_uzs) : '…'}
            />
            <KpiCard
              tone="blue"
              iconName="bag"
              label="Расход"
              sub={stats ? `${stats.by_kind.outgoing.count} док.` : ''}
              value={stats ? fmtMoneyShort(stats.by_kind.outgoing.amount_uzs) : '…'}
            />
            <KpiCard
              tone="red"
              iconName="close"
              label="Списано"
              sub={stats ? `${stats.by_kind.write_off.count} док.` : ''}
              value={stats ? fmtMoneyShort(stats.by_kind.write_off.amount_uzs) : '…'}
            />
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <Seg
              options={[
                { value: '',          label: 'Все' },
                { value: 'incoming',  label: 'Приход' },
                { value: 'outgoing',  label: 'Расход' },
                { value: 'transfer',  label: 'Перемещение' },
                { value: 'write_off', label: 'Списание' },
              ]}
              value={kind}
              onChange={(v) => setKind(v)}
            />
            <input
              className="input"
              value={moduleCode}
              onChange={(e) => setModuleCode(e.target.value)}
              placeholder="Модуль (feedlot/slaughter/...)"
              style={{ width: 200 }}
            />
            <select
              className="input"
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              style={{ width: 240 }}
            >
              <option value="">Все склады (источник)</option>
              {warehouses?.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} · {w.name}
                </option>
              ))}
            </select>
            <div style={{ flex: 1, minWidth: 200 }}>
              <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
                <input
                  className="input"
                  placeholder="Поиск по документу, номенклатуре…"
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
            <DataTable<StockMovement>
              isLoading={isLoading}
              rows={data}
              rowKey={(m) => m.id}
              error={error}
              emptyMessage="Нет движений по выбранным фильтрам."
              onRowClick={(m) => setSel(m)}
              rowProps={(m) => ({ active: sel?.id === m.id })}
              columns={[
                { key: 'doc', label: 'Документ',
                  render: (m) => <span className="badge id">{m.doc_number}</span> },
                { key: 'date', label: 'Дата', mono: true,
                  cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                  render: (m) => fmtDate(m.date) },
                { key: 'kind', label: 'Тип',
                  render: (m) => <Badge tone={KIND_TONE[m.kind]}>{KIND_LABEL[m.kind]}</Badge> },
                { key: 'loc', label: 'Модуль / склад', cellStyle: { fontSize: 12 },
                  render: (m) => (
                    <>
                      <div style={{ fontWeight: 500 }}>{m.module_code ?? '—'}</div>
                      <div style={{ color: 'var(--fg-3)' }}>
                        {m.warehouse_from_code ?? m.warehouse_to_code ?? '—'}
                      </div>
                    </>
                  ) },
                { key: 'nom', label: 'Номенклатура', cellStyle: { fontSize: 12 },
                  render: (m) => (
                    <>
                      <div>{m.nomenclature_name ?? '—'}</div>
                      <div style={{ color: 'var(--fg-3)', fontSize: 11 }}>
                        {m.nomenclature_sku ?? ''}
                      </div>
                    </>
                  ) },
                { key: 'qty', label: 'Количество', align: 'right', mono: true,
                  render: (m) => {
                    const qty = signedQty(m);
                    return <span style={{ color: qty.color, fontWeight: 600 }}>{qty.text}</span>;
                  } },
                { key: 'amount', label: 'Сумма, UZS', align: 'right', mono: true,
                  render: (m) => fmtMoney(m.amount_uzs) },
                { key: 'who', label: 'Контрагент / партия',
                  cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                  render: (m) => m.counterparty_name ?? m.batch_doc_number ?? '—' },
                { key: 'actions', label: '', align: 'right',
                  render: (m) => canEdit ? (
                    <RowActions
                      actions={[
                        {
                          label: m.is_manual
                            ? 'Удалить'
                            : 'Создано документом — нельзя удалить',
                          danger: m.is_manual,
                          disabled: !m.is_manual,
                          onClick: () => handleDeleteMovement(m),
                        },
                      ]}
                    />
                  ) : null },
              ]}
            />
          </Panel>
        </>
      )}

      {tab === 'warehouses' && (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <input
              className="input"
              placeholder="Поиск по коду, названию, модулю…"
              value={whSearch}
              onChange={(e) => setWhSearch(e.target.value)}
              style={{ flex: 1, minWidth: 280 }}
            />
          </div>

          <Panel flush>
            <DataTable<WarehouseRef>
              rows={filteredWarehouses}
              rowKey={(w) => w.id}
              emptyMessage="Складов пока нет. Нажмите «Новый склад»."
              columns={[
                { key: 'code', label: 'Код', mono: true,
                  render: (w) => <span className="badge id">{w.code}</span> },
                { key: 'name', label: 'Название', render: (w) => w.name },
                { key: 'module', label: 'Модуль', cellStyle: { fontSize: 12 },
                  render: (w) => w.module_name ?? '—' },
                { key: 'gl', label: 'Субсчёт по умолчанию', mono: true,
                  cellStyle: { fontSize: 12, color: 'var(--fg-3)' },
                  render: (w) => w.default_gl_subaccount_code ?? '—' },
                { key: 'status', label: 'Статус',
                  render: (w) => (
                    <Badge tone={w.is_active ? 'success' : 'neutral'}>
                      {w.is_active ? 'Активен' : 'Отключён'}
                    </Badge>
                  ) },
                { key: 'actions', label: '', align: 'right',
                  render: (w) => canEdit ? (
                    <RowActions
                      actions={[
                        {
                          label: 'Править',
                          onClick: () => {
                            setWarehouseEdit(w);
                            setShowWarehouseModal(true);
                          },
                        },
                        {
                          label: 'Удалить',
                          danger: true,
                          onClick: () => handleDeleteWarehouse(w),
                        },
                      ]}
                    />
                  ) : null },
              ]}
            />
          </Panel>
        </>
      )}

      {sel && (
        <DetailDrawer
          title={'Движение · ' + sel.doc_number}
          subtitle={
            KIND_LABEL[sel.kind] +
            ' · ' +
            fmtDate(sel.date) +
            ' · ' +
            (sel.module_code ?? '—')
          }
          onClose={() => setSel(null)}
        >
          <KV
            items={[
              { k: 'Документ', v: sel.doc_number, mono: true },
              { k: 'Дата', v: fmtDate(sel.date), mono: true },
              {
                k: 'Тип',
                v: <Badge tone={KIND_TONE[sel.kind]}>{KIND_LABEL[sel.kind]}</Badge>,
              },
              { k: 'Модуль', v: sel.module_code ?? '—' },
              {
                k: 'Номенклатура',
                v: `${sel.nomenclature_sku ?? '—'} · ${sel.nomenclature_name ?? '—'}`,
              },
              { k: 'Количество', v: sel.quantity, mono: true },
              { k: 'Цена за ед.', v: fmtMoney(sel.unit_price_uzs), mono: true },
              { k: 'Сумма', v: fmtMoney(sel.amount_uzs) + ' UZS', mono: true },
              ...(sel.warehouse_from_code
                ? [{ k: 'Со склада', v: sel.warehouse_from_code }]
                : []),
              ...(sel.warehouse_to_code
                ? [{ k: 'На склад', v: sel.warehouse_to_code }]
                : []),
              ...(sel.counterparty_name
                ? [{ k: 'Контрагент', v: sel.counterparty_name }]
                : []),
              ...(sel.batch_doc_number
                ? [{ k: 'Партия', v: sel.batch_doc_number, mono: true }]
                : []),
              {
                k: 'Источник',
                v: sel.is_manual ? 'Ручное движение' : 'Создано документом-источником',
              },
            ]}
          />
          {sel.is_manual && (
            <div style={{ marginTop: 12 }}>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => handleDeleteMovement(sel)}
              >
                Удалить движение
              </button>
            </div>
          )}
        </DetailDrawer>
      )}

      {showMovementModal && (
        <StockMovementModal
          onClose={() => setShowMovementModal(false)}
        />
      )}

      {showWarehouseModal && (
        <WarehouseModal
          initial={warehouseEdit}
          onClose={() => {
            setShowWarehouseModal(false);
            setWarehouseEdit(null);
          }}
        />
      )}
    </>
  );
}
