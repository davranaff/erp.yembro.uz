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
import TablePagination from '@/components/ui/TablePagination';
import { useModules } from '@/hooks/useModules';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useDeleteManualMovement,
  useDeleteWarehouse,
  useStockMovementsPaginated,
  useStockMovementsStats,
  useWarehouses,
} from '@/hooks/useStockMovements';
import type { StockMovement, StockMovementKind, WarehouseRef } from '@/types/auth';

import RawBatchModal from '../feed/RawBatchModal';
import EditMovementModal from './EditMovementModal';
import PromoteToRawBatchModal from './PromoteToRawBatchModal';
import StockMovementModal from './StockMovementModal';
import WarehouseBalanceDrawer from './WarehouseBalanceDrawer';
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

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
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
  const [tab, setTab] = useState<Tab>('warehouses');

  // Movements tab state
  const [kind, setKind] = useState<string>('');
  const [moduleCode, setModuleCode] = useState<string>('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [nomenclatureId, setNomenclatureId] = useState('');
  const [nomenclatureLabel, setNomenclatureLabel] = useState('');
  // По умолчанию показываем сегодняшний день. Пустая строка = «все даты»
  // (можно переключиться кнопкой). UX-паттерн совпадает со «сводкой дня».
  const [date, setDate] = useState<string>(todayISO());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sel, setSel] = useState<StockMovement | null>(null);
  const [showMovementModal, setShowMovementModal] = useState(false);
  const [editMovement, setEditMovement] = useState<StockMovement | null>(null);
  const [promoteMovement, setPromoteMovement] = useState<StockMovement | null>(null);
  const [rawBatchPrefill, setRawBatchPrefill] = useState<{
    nomenclature?: string;
    warehouse?: string;
    supplier?: string;
    quantity?: string;
    price_per_unit?: string;
  } | null>(null);

  // Warehouses tab state
  const [warehouseEdit, setWarehouseEdit] = useState<WarehouseRef | null>(null);
  const [warehouseBalance, setWarehouseBalance] = useState<WarehouseRef | null>(null);
  const [showWarehouseModal, setShowWarehouseModal] = useState(false);
  const [whSearch, setWhSearch] = useState('');

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('stock', 'rw');

  const filter = useMemo(
    () => ({
      kind: kind || undefined,
      module_code: moduleCode || undefined,
      // Используем единый фильтр `warehouse` (Q OR на бэкенде по
      // warehouse_from + warehouse_to), чтобы не терять INCOMING-движения.
      warehouse: warehouseId || undefined,
      nomenclature: nomenclatureId || undefined,
      search: search || undefined,
      // Дневной фильтр: бэк ждёт ISO datetime, ограничиваем интервалом
      // [день 00:00, день 23:59:59]. Пустой `date` = «все даты».
      date_after: date ? `${date}T00:00:00` : undefined,
      date_before: date ? `${date}T23:59:59` : undefined,
    }),
    [kind, moduleCode, warehouseId, nomenclatureId, search, date],
  );

  const { data: pageData, isLoading, error, refetch, isFetching } = useStockMovementsPaginated(filter, page, pageSize);
  const data = pageData?.results ?? [];
  const { data: stats } = useStockMovementsStats(filter);
  const { data: warehouses } = useWarehouses({ is_active: '' });
  const { data: modules } = useModules();
  const deleteMovement = useDeleteManualMovement();
  const deleteWarehouse = useDeleteWarehouse();

  const csvUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (filter.kind) params.set('kind', filter.kind);
    if (filter.module_code) params.set('module_code', filter.module_code);
    if (filter.warehouse) params.set('warehouse', filter.warehouse);
    if (filter.search) params.set('search', filter.search);
    if (filter.date_after) params.set('date_after', filter.date_after);
    if (filter.date_before) params.set('date_before', filter.date_before);
    const qs = params.toString();
    return qs
      ? `/api/warehouses/movements/?${qs}`
      : '/api/warehouses/movements/';
  }, [filter]);

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
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
            { value: 'warehouses', label: 'Склады' },
            { value: 'movements',  label: 'Движения' },
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

          {/* Date navigation — паттерн из /feed/dashboard:
              «← пред | <date> | Сегодня | след →». Пустая дата = «все даты». */}
          <div style={{
            display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8,
            marginBottom: 12, padding: 10, background: 'var(--bg-soft)', borderRadius: 6,
          }}>
            <button
              className="btn btn-secondary btn-sm"
              disabled={!date}
              onClick={() => { setDate((d) => shiftDate(d || todayISO(), -1)); setPage(1); }}
            >
              ← пред
            </button>
            <input
              className="input mono"
              type="date"
              value={date}
              onChange={(e) => { setDate(e.target.value); setPage(1); }}
              style={{ width: 160 }}
            />
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => { setDate(todayISO()); setPage(1); }}
            >
              Сегодня
            </button>
            <button
              className="btn btn-secondary btn-sm"
              disabled={!date}
              onClick={() => { setDate((d) => shiftDate(d || todayISO(), 1)); setPage(1); }}
            >
              след →
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => { setDate(''); setPage(1); }}
              disabled={!date}
              title="Показать движения за все даты"
            >
              Все даты
            </button>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>
              {date
                ? new Date(date).toLocaleDateString('ru-RU', {
                    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
                  })
                : 'все даты'}
            </span>
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
              onChange={(v) => { setKind(v); setPage(1); }}
            />
            <select
              className="input"
              value={moduleCode}
              onChange={(e) => { setModuleCode(e.target.value); setPage(1); }}
              style={{ width: 200 }}
            >
              <option value="">Все модули</option>
              {modules?.filter((m) => m.is_active).map((m) => (
                <option key={m.id} value={m.code}>
                  {m.name}
                </option>
              ))}
            </select>
            <select
              className="input"
              value={warehouseId}
              onChange={(e) => { setWarehouseId(e.target.value); setPage(1); }}
              style={{ width: 240 }}
            >
              <option value="">Все склады</option>
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

          {/* Filter chip — показываем когда зашли через клик из drawer'а
              «Остатки склада». Юзер сразу видит на чём фильтр и может сбросить. */}
          {(nomenclatureId || warehouseId) && (
            <div style={{
              display: 'flex', alignItems: 'center', flexWrap: 'wrap',
              gap: 8, padding: 8, marginBottom: 12,
              background: 'var(--bg-soft)', borderRadius: 6,
              border: '1px dashed var(--brand-orange)',
            }}>
              <span style={{
                fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
                textTransform: 'uppercase', letterSpacing: '.04em',
              }}>
                Фильтр:
              </span>
              {nomenclatureLabel && (
                <Badge tone="warn">📦 {nomenclatureLabel}</Badge>
              )}
              {warehouseId && warehouses && (
                <Badge tone="info">
                  🏬 {warehouses.find((w) => w.id === warehouseId)?.code ?? '—'}
                </Badge>
              )}
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setNomenclatureId('');
                  setNomenclatureLabel('');
                  setWarehouseId('');
                  setPage(1);
                }}
                style={{ marginLeft: 'auto', fontSize: 11 }}
              >
                Сбросить
              </button>
            </div>
          )}

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
                  render: (m) => {
                    if (!canEdit) return null;
                    // Promote доступен только для manual INCOMING + KORM-* (кроме XALTA)
                    const isFeedRaw = m.module_code === 'feed'
                      && Boolean(m.nomenclature_sku?.startsWith('KORM-'))
                      && !m.nomenclature_sku?.startsWith('KORM-XALTA');
                    const canPromote = m.is_manual
                      && m.kind === 'incoming'
                      && isFeedRaw;
                    return (
                      <RowActions
                        actions={[
                          ...(canPromote ? [{
                            label: '→ Сделать партией сырья',
                            onClick: () => setPromoteMovement(m),
                          }] : []),
                          {
                            label: m.is_manual
                              ? 'Изменить'
                              : 'Создано документом — нельзя править',
                            disabled: !m.is_manual,
                            onClick: () => setEditMovement(m),
                          },
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
                    );
                  } },
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
              onRowClick={(w) => setWarehouseBalance(w)}
              rowProps={(w) => ({ active: warehouseBalance?.id === w.id })}
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
          onSwitchToFeedRaw={(prefill) => {
            setShowMovementModal(false);
            setRawBatchPrefill(prefill);
          }}
        />
      )}

      {rawBatchPrefill && (
        <RawBatchModal
          prefill={rawBatchPrefill}
          onClose={() => setRawBatchPrefill(null)}
        />
      )}

      {editMovement && (
        <EditMovementModal
          movement={editMovement}
          onClose={() => setEditMovement(null)}
          onSaved={(m) => { if (sel?.id === m.id) setSel(m); }}
        />
      )}

      {promoteMovement && (
        <PromoteToRawBatchModal
          movement={promoteMovement}
          onClose={() => setPromoteMovement(null)}
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

      {warehouseBalance && (
        <WarehouseBalanceDrawer
          warehouse={warehouseBalance}
          onClose={() => setWarehouseBalance(null)}
          onRowClick={(row) => {
            // Клик по строке → открыть Движения с фильтром по этой
            // номенклатуре + этому складу.
            setNomenclatureId(row.nomenclature_id);
            setNomenclatureLabel(`${row.sku} · ${row.name}`);
            setWarehouseId(warehouseBalance.id);
            setPage(1);
            setTab('movements');
            setWarehouseBalance(null);
          }}
        />
      )}
    </>
  );
}
