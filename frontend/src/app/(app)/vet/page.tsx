'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import IncomingTransfersPanel from '@/components/IncomingTransfersPanel';
import OpexButton from '@/components/OpexButton';
import SellBatchButton, { OpenSaleFromModule } from '@/components/SellBatchButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TablePagination from '@/components/ui/TablePagination';
import { useHasLevel } from '@/hooks/usePermissions';
import { getFinancesVisible } from '@/lib/permissions';
import {
  drugsCrud,
  stockBatchesCrud,
  treatmentsCrud,
  useCancelTreatment,
  useRecallStockBatch,
  useReleaseQuarantine,
} from '@/hooks/useVet';
import type { VetDrug, VetStockBatch, VetStockStatus, VetTreatmentLog } from '@/types/auth';

import BarcodeLabel from '@/components/BarcodeLabel';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';

import AccessoriesPanel from './AccessoriesPanel';
import DrugModal from './DrugModal';
import ReceiveModal from './ReceiveModal';
import TreatmentModal from './TreatmentModal';

const STOCK_STATUS_LABEL: Record<VetStockStatus, string> = {
  available: 'Доступно',
  quarantine: 'Карантин',
  expiring_soon: 'Скоро истекает',
  expired: 'Истёк',
  depleted: 'Исчерпано',
  recalled: 'Отозвано',
};

const STOCK_STATUS_TONE: Record<VetStockStatus, 'success' | 'warn' | 'danger' | 'neutral' | 'info'> = {
  available: 'success',
  quarantine: 'warn',
  expiring_soon: 'warn',
  expired: 'danger',
  depleted: 'neutral',
  recalled: 'danger',
};

const DRUG_TYPE_LABEL: Record<string, string> = {
  vaccine: 'Вакцина',
  antibiotic: 'Антибиотик',
  vitamin: 'Витамин',
  electrolyte: 'Электролит',
  other: 'Прочее',
};

function daysUntil(dateISO: string): number {
  return Math.floor((new Date(dateISO).getTime() - Date.now()) / 86400000);
}

export default function VetPage() {
  const [tab, setTab] = useState<'stock' | 'drugs' | 'accessories'>('stock');
  const [stockStatus, setStockStatus] = useState('');
  const [stockSearch, setStockSearch] = useState('');
  const [stockSearchDraft, setStockSearchDraft] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selDrug, setSelDrug] = useState<VetDrug | null>(null);
  const [selStock, setSelStock] = useState<VetStockBatch | null>(null);
  const [selTr, setSelTr] = useState<VetTreatmentLog | null>(null);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [treatmentOpen, setTreatmentOpen] = useState(false);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('vet', 'rw');

  // KPI считаем по полному списку (до 2000), таблицу — по странице.
  const { data: drugs } = drugsCrud.useList({ is_active: 'true' });
  const { data: stock } = stockBatchesCrud.useList(
    stockStatus ? { status: stockStatus } : {},
  );

  const stockListFilter: Record<string, string | undefined> = {};
  if (stockStatus) stockListFilter.status = stockStatus;
  if (stockSearch) stockListFilter.search = stockSearch;
  const stockPage = stockBatchesCrud.useListPaginated(
    stockListFilter, page, pageSize,
  );
  const treatmentsPage = treatmentsCrud.useListPaginated({}, page, pageSize);
  const drugsPage = drugsCrud.useListPaginated({ is_active: 'true' }, page, pageSize);

  const stockRows = stockPage.data?.results ?? [];
  const stockLoading = stockPage.isLoading;
  const treatments = treatmentsPage.data?.results ?? [];
  const trLoading = treatmentsPage.isLoading;
  const drugRows = drugsPage.data?.results ?? [];

  const release = useReleaseQuarantine();
  const recall = useRecallStockBatch();
  const cancelTreatment = useCancelTreatment();
  const [recallFor, setRecallFor] = useState<VetStockBatch | null>(null);
  const [cancelTreatmentFor, setCancelTreatmentFor] = useState<VetTreatmentLog | null>(null);
  const [drugModalOpen, setDrugModalOpen] = useState(false);
  const [editingDrug, setEditingDrug] = useState<VetDrug | null>(null);

  const totals = useMemo(() => ({
    drugs: drugs?.length ?? 0,
    available: stock?.filter((s) => s.status === 'available').length ?? 0,
    expiring: stock?.filter((s) => s.status === 'expiring_soon' || (s.expiration_date && daysUntil(s.expiration_date) < 60)).length ?? 0,
    quarantine: stock?.filter((s) => s.status === 'quarantine').length ?? 0,
  }), [drugs, stock]);

  const handleRelease = (s: VetStockBatch) => {
    if (!confirm(`Выпустить лот ${s.lot_number} из карантина?`)) return;
    release.mutate({ id: s.id }, {
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Вет. аптека</h1>
          <div className="sub">Препараты · лоты на складе · журнал лечений</div>
        </div>
        <div className="actions">
          {canEdit && (
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setEditingDrug(null); setDrugModalOpen(true); }}
              >
                <Icon name="plus" size={14} /> Препарат
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => setReceiveOpen(true)}>
                <Icon name="plus" size={14} /> Приёмка лота
              </button>
              <OpexButton moduleCode="vet" suggestedContraCode="20.06" />
              <OpenSaleFromModule moduleCode="vet" />
            </>
          )}
        </div>
      </div>

      <IncomingTransfersPanel
        module="vet"
        subtitle="ждут приёма (закупки)"
        invalidateKeys={[['vet']]}
      />

      <div className="kpi-row">
        <KpiCard tone="orange" iconName="pharma" label="SKU препаратов" sub="активных" value={String(totals.drugs)} />
        <KpiCard tone="green" iconName="check" label="Доступно" sub="лотов" value={String(totals.available)} />
        <KpiCard tone="red" iconName="close" label="Скоро истекает" sub="&lt; 60 дней" value={String(totals.expiring)} />
        <KpiCard tone="blue" iconName="box" label="На карантине" sub="лотов" value={String(totals.quarantine)} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'stock', label: 'Лоты' },
            { value: 'drugs', label: 'SKU препаратов' },
            { value: 'accessories', label: 'Аксессуары' },
          ]}
          value={tab}
          onChange={(v) => { setTab(v as typeof tab); setPage(1); }}
        />
        {tab === 'stock' && (
          <>
            <select
              className="input"
              value={stockStatus}
              onChange={(e) => { setStockStatus(e.target.value); setPage(1); }}
              style={{ width: 180 }}
            >
              <option value="">Все статусы</option>
              {Object.entries(STOCK_STATUS_LABEL).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setStockSearch(stockSearchDraft.trim());
                setPage(1);
              }}
              style={{ display: 'flex', gap: 6, flex: 1, minWidth: 220 }}
            >
              <input
                className="input"
                placeholder="Поиск: имя препарата, SKU, lot, штрих-код, документ…"
                value={stockSearchDraft}
                onChange={(e) => setStockSearchDraft(e.target.value)}
                style={{ flex: 1 }}
              />
              {stockSearch && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setStockSearchDraft(''); setStockSearch(''); setPage(1); }}
                >
                  ✕
                </button>
              )}
              <button type="submit" className="btn btn-secondary btn-sm">Найти</button>
            </form>
          </>
        )}
      </div>

      {tab === 'stock' && (
        <Panel flush>
          <DataTable<VetStockBatch>
            isLoading={stockLoading}
            rows={stockRows}
            rowKey={(s) => s.id}
            emptyMessage={
              <EmptyState
                icon="bag"
                title="Препаратов на складе нет"
                description="Ветаптека учитывает остатки лекарств, вакцин и витаминов. Каждый лот фиксирует партию поступления с датой годности и карантином."
                steps={[
                  { label: 'Добавьте SKU препарата во вкладке «SKU препаратов»' },
                  { label: 'Нажмите «+ Приход» — выберите препарат, lot и дату годности' },
                  { label: 'Лот попадёт в карантин — выпустите после проверки документов' },
                  { label: 'После выпуска препарат доступен для записи лечений' },
                ]}
                action={{
                  label: 'Приход препарата',
                  onClick: () => setReceiveOpen(true),
                }}
                hint="Препараты с каренцией автоматически блокируют реализацию яиц и мяса до окончания периода ожидания."
              />
            }
            onRowClick={(s) => setSelStock(s)}
            rowProps={(s) => ({ active: selStock?.id === s.id })}
            columns={[
              { key: 'doc', label: 'Документ',
                render: (s) => <span className="badge id">{s.doc_number}</span> },
              { key: 'drug', label: 'Препарат',
                render: (s) => (
                  <>
                    <div style={{ fontSize: 12 }}>{s.drug_name ?? '—'}</div>
                    <div style={{ fontSize: 11, color: 'var(--fg-3)' }} className="mono">{s.drug_sku ?? ''}</div>
                  </>
                ) },
              { key: 'lot', label: 'Lot', mono: true, cellStyle: { fontSize: 12 },
                render: (s) => s.lot_number },
              { key: 'warehouse', label: 'Склад', mono: true, cellStyle: { fontSize: 12 },
                render: (s) => s.warehouse_code ?? '—' },
              { key: 'expire', label: 'Годен до', mono: true,
                render: (s) => (
                  <span style={{ fontSize: 12, color: daysUntil(s.expiration_date) < 60 ? 'var(--danger)' : 'var(--fg-2)' }}>
                    {s.expiration_date}
                  </span>
                ) },
              { key: 'qty', label: 'Остаток', align: 'right', mono: true,
                render: (s) => (
                  <>
                    {parseFloat(s.current_quantity).toLocaleString('ru-RU')}
                    {s.unit_code && <span style={{ color: 'var(--fg-3)', marginLeft: 4 }}>{s.unit_code}</span>}
                  </>
                ) },
              { key: 'status', label: 'Статус',
                render: (s) => (
                  <Badge tone={STOCK_STATUS_TONE[s.status]} dot>
                    {STOCK_STATUS_LABEL[s.status]}
                  </Badge>
                ) },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (s) => canEdit ? (
                  <RowActions
                    actions={[
                      {
                        label: 'Выпустить из карантина',
                        hidden: s.status !== 'quarantine',
                        disabled: release.isPending,
                        onClick: () => handleRelease(s),
                      },
                      {
                        label: 'Recall (отозвать)',
                        danger: true,
                        hidden: !(
                          s.status === 'available'
                          || s.status === 'expiring_soon'
                          || s.status === 'quarantine'
                        ),
                        disabled: recall.isPending,
                        onClick: () => setRecallFor(s),
                      },
                    ]}
                  />
                ) : null },
            ]}
          />
          {stockPage.data && (
            <TablePagination
              page={page}
              pageSize={pageSize}
              count={stockPage.data.count}
              hasPrev={Boolean(stockPage.data.previous)}
              hasNext={Boolean(stockPage.data.next)}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          )}
        </Panel>
      )}

      {/* Таб «Журнал лечений» удалён — лечение временно недоступно. */}

      {tab === 'drugs' && (
        <Panel flush>
          <DataTable<VetDrug>
            rows={drugRows}
            rowKey={(d) => d.id}
            emptyMessage={
              <EmptyState
                icon="box"
                title="SKU препаратов не добавлено"
                description="SKU — это справочник препаратов (вакцин, антибиотиков, витаминов). Без SKU нельзя оприходовать препарат на склад."
                steps={[
                  { label: 'Нажмите «+ Препарат» — введите название и тип (вакцина, антибиотик и т.д.)' },
                  { label: 'Укажите путь введения и срок каренции по умолчанию' },
                  { label: 'После сохранения SKU доступен для прихода на склад' },
                ]}
                action={{
                  label: 'Добавить препарат',
                  onClick: () => setDrugModalOpen(true),
                }}
                hint="SKU создаётся один раз — далее на него делаются все лотовые приходы с разными датами годности."
              />
            }
            onRowClick={(d) => setSelDrug(d)}
            rowProps={(d) => ({ active: selDrug?.id === d.id })}
            columns={[
              { key: 'sku', label: 'SKU', mono: true, cellStyle: { fontSize: 12 },
                render: (d) => d.nomenclature_sku ?? '—' },
              { key: 'name', label: 'Название', cellStyle: { fontWeight: 500 },
                render: (d) => d.nomenclature_name ?? '—' },
              { key: 'type', label: 'Тип', cellStyle: { fontSize: 12 },
                render: (d) => DRUG_TYPE_LABEL[d.drug_type] ?? d.drug_type },
              { key: 'route', label: 'Путь', cellStyle: { fontSize: 12 },
                render: (d) => d.administration_route },
              { key: 'karen', label: 'Каренция, дн', align: 'right', mono: true,
                render: (d) => d.default_withdrawal_days },
              { key: 'qty', label: 'Σ остаток', align: 'right', mono: true,
                cellStyle: { fontWeight: 600 },
                render: (d) => {
                  const n = parseFloat(d.total_qty || '0');
                  if (!n) return <span style={{ color: 'var(--fg-3)' }}>—</span>;
                  return (
                    <span style={{ color: 'var(--success)' }}>
                      {n.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
                      {d.unit_code && (
                        <span style={{ color: 'var(--fg-3)', marginLeft: 4, fontWeight: 400 }}>
                          {d.unit_code}
                        </span>
                      )}
                    </span>
                  );
                } },
              { key: 'status', label: 'Статус',
                render: (d) => d.is_active
                  ? <Badge tone="success" dot>Активен</Badge>
                  : <Badge tone="neutral" dot>Архив</Badge> },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (d) => canEdit ? (
                  <RowActions
                    actions={[
                      {
                        label: 'Редактировать',
                        onClick: () => { setEditingDrug(d); setDrugModalOpen(true); },
                      },
                    ]}
                  />
                ) : null },
            ]}
          />
          {drugsPage.data && (
            <TablePagination
              page={page}
              pageSize={pageSize}
              count={drugsPage.data.count}
              hasPrev={Boolean(drugsPage.data.previous)}
              hasNext={Boolean(drugsPage.data.next)}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          )}
        </Panel>
      )}

      {tab === 'accessories' && <AccessoriesPanel />}

      {selStock && (
        <DetailDrawer
          title={`Лот · ${selStock.lot_number}`}
          subtitle={`${selStock.drug_sku ?? '—'} · ${STOCK_STATUS_LABEL[selStock.status]}`}
          onClose={() => setSelStock(null)}
          actions={
            selStock.status === 'available' && parseFloat(selStock.current_quantity) > 0 ? (
              <SellBatchButton
                moduleCode="vet"
                sourceKind="vet_stock_batch"
                batchId={selStock.id}
                warehouseId={selStock.warehouse}
              />
            ) : undefined
          }
        >
          {selStock.barcode && (
            <div style={{
              padding: 12, marginBottom: 14,
              background: 'var(--bg-soft)', borderRadius: 6,
              border: '1px solid var(--border)',
            }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
                textTransform: 'uppercase', letterSpacing: '.04em',
                marginBottom: 8,
              }}>
                Штрих-код
              </div>

              {/* Визуальный Code128 SVG */}
              <div style={{ marginBottom: 10, overflowX: 'auto' }}>
                <BarcodeLabel
                  barcode={selStock.barcode}
                  drugName={selStock.drug_name}
                  lotNumber={selStock.lot_number}
                  expirationDate={selStock.expiration_date}
                />
              </div>

              {/* Кнопки */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    navigator.clipboard?.writeText(selStock.barcode!);
                    alert('Скопировано');
                  }}
                >
                  Копировать
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    const p = new URLSearchParams({
                      barcode: selStock.barcode!,
                      ...(selStock.drug_name ? { drug: selStock.drug_name } : {}),
                      ...(selStock.lot_number ? { lot: selStock.lot_number } : {}),
                      ...(selStock.expiration_date ? { exp: selStock.expiration_date } : {}),
                    });
                    window.open(`/print/vet-label?${p}`, '_blank');
                  }}
                >
                  Печать этикетки
                </button>
              </div>

              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
                Сканер открывает: <code>/scan/{selStock.barcode}</code>
              </div>
            </div>
          )}
          <KV
            items={[
              { k: 'Документ', v: selStock.doc_number, mono: true },
              { k: 'Препарат', v: `${selStock.drug_sku ?? '—'} · ${selStock.drug_name ?? ''}` },
              { k: 'Lot №', v: selStock.lot_number, mono: true },
              { k: 'Склад', v: selStock.warehouse_code ?? '—' },
              { k: 'Поставщик', v: selStock.supplier_name ?? '—' },
              { k: 'Получено', v: selStock.received_date, mono: true },
              {
                k: 'Годен до',
                v: (
                  <span style={{
                    color: selStock.is_expired
                      ? 'var(--danger)'
                      : selStock.is_expiring_soon
                      ? 'var(--warning)'
                      : 'var(--fg-1)',
                    fontWeight: selStock.is_expired || selStock.is_expiring_soon ? 600 : 400,
                  }}>
                    {selStock.expiration_date}
                    {selStock.days_to_expiry !== null && (
                      <span style={{ marginLeft: 6, fontSize: 11 }}>
                        ({selStock.days_to_expiry < 0
                          ? `истёк ${Math.abs(selStock.days_to_expiry)} дн назад`
                          : `${selStock.days_to_expiry} дн`})
                      </span>
                    )}
                  </span>
                ),
                mono: true,
              },
              { k: 'Количество нач.', v: `${selStock.quantity} ${selStock.unit_code ?? ''}`, mono: true },
              { k: 'Остаток', v: `${selStock.current_quantity} ${selStock.unit_code ?? ''}`, mono: true },
              ...(getFinancesVisible(selStock) && selStock.price_per_unit_uzs ? [{
                k: 'Цена за ед.',
                v: `${parseFloat(selStock.price_per_unit_uzs).toLocaleString('ru-RU')} UZS`,
                mono: true,
              }] : []),
              { k: 'Статус', v: <Badge tone={STOCK_STATUS_TONE[selStock.status]}>{STOCK_STATUS_LABEL[selStock.status]}</Badge> },
              ...(selStock.quarantine_until ? [{ k: 'Карантин до', v: selStock.quarantine_until, mono: true }] : []),
              ...(selStock.recalled_at ? [
                { k: 'Отозвано', v: new Date(selStock.recalled_at).toLocaleString('ru-RU'), mono: true },
                { k: 'Причина отзыва', v: selStock.recall_reason || '—' },
              ] : []),
            ]}
          />
        </DetailDrawer>
      )}

      {selDrug && (
        <DetailDrawer
          title={`${selDrug.nomenclature_sku ?? ''} · ${selDrug.nomenclature_name ?? ''}`}
          subtitle={DRUG_TYPE_LABEL[selDrug.drug_type] ?? selDrug.drug_type}
          onClose={() => setSelDrug(null)}
          actions={
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => { setEditingDrug(selDrug); setDrugModalOpen(true); }}
            >
              <Icon name="edit" size={12} /> Редактировать
            </button>
          }
        >
          {selDrug.barcode && (
            <div style={{
              padding: 12, marginBottom: 14,
              background: 'var(--bg-soft)', borderRadius: 6,
              border: '1px solid var(--border)',
            }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
                textTransform: 'uppercase', letterSpacing: '.04em',
                marginBottom: 8,
              }}>
                Штрих-код SKU (полка)
              </div>

              <div style={{ marginBottom: 10, overflowX: 'auto' }}>
                <BarcodeLabel
                  barcode={selDrug.barcode}
                  drugName={selDrug.nomenclature_name ?? selDrug.nomenclature_sku ?? undefined}
                  lotNumber={selDrug.nomenclature_sku ?? undefined}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    navigator.clipboard?.writeText(selDrug.barcode!);
                    alert('Скопировано');
                  }}
                >
                  Копировать
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    const p = new URLSearchParams({
                      barcode: selDrug.barcode!,
                      ...(selDrug.nomenclature_name ? { drug: selDrug.nomenclature_name } : {}),
                      ...(selDrug.nomenclature_sku ? { lot: selDrug.nomenclature_sku } : {}),
                    });
                    window.open(`/print/vet-label?${p}`, '_blank');
                  }}
                >
                  Печать этикетки
                </button>
              </div>

              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
                Этикетка для полки/каталога. Лоты имеют свои штрих-коды
                (на упаковке) — см. вкладку «Склад».
              </div>
            </div>
          )}
          <KV
            items={[
              { k: 'SKU', v: selDrug.nomenclature_sku ?? '—', mono: true },
              { k: 'Тип', v: DRUG_TYPE_LABEL[selDrug.drug_type] ?? selDrug.drug_type },
              { k: 'Путь введения', v: selDrug.administration_route },
              { k: 'Каренция', v: `${selDrug.default_withdrawal_days} дн` },
              {
                k: 'Температура хранения',
                v: (() => {
                  const fmt = (v: number | null) => v == null ? null : (v >= 0 ? `+${v}` : `${v}`);
                  const lo = fmt(selDrug.storage_temp_min_c);
                  const hi = fmt(selDrug.storage_temp_max_c);
                  if (lo == null && hi == null) return '—';
                  if (lo != null && hi != null) return `${lo} … ${hi} °C`;
                  return `${lo ?? hi} °C`;
                })(),
                mono: true,
              },
              ...(selDrug.storage_conditions
                ? [{ k: 'Доп. условия', v: selDrug.storage_conditions }]
                : []),
              { k: 'Статус', v: selDrug.is_active ? 'Активен' : 'Архив' },
              {
                k: 'Σ остаток',
                v: (() => {
                  const n = parseFloat(selDrug.total_qty || '0');
                  if (!n) return <span style={{ color: 'var(--fg-3)' }}>нет на складах</span>;
                  return (
                    <span style={{ color: 'var(--success)', fontWeight: 600 }} className="mono">
                      {n.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
                      {selDrug.unit_code && <span style={{ color: 'var(--fg-3)', marginLeft: 4, fontWeight: 400 }}>{selDrug.unit_code}</span>}
                    </span>
                  );
                })(),
              },
            ]}
          />

          {/* ── Лоты по складам ───────────────────────────────────────── */}
          {selDrug.lots_by_warehouse.length > 0 ? (
            <div style={{ marginTop: 14 }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
                textTransform: 'uppercase', letterSpacing: '.04em',
                marginBottom: 8,
              }}>
                Активные лоты по складам ({selDrug.lots_by_warehouse.length} складов)
              </div>
              {selDrug.lots_by_warehouse.map((g) => (
                <div key={g.warehouse_id} style={{
                  marginBottom: 10,
                  border: '1px solid var(--border)', borderRadius: 6,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    padding: '6px 10px', background: 'var(--bg-soft)',
                    fontSize: 12, fontWeight: 600,
                    display: 'flex', justifyContent: 'space-between',
                  }}>
                    <span><span className="mono">{g.warehouse_code}</span> · {g.warehouse_name}</span>
                    <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
                      {g.lots.length} {g.lots.length === 1 ? 'лот' : 'лота(ов)'}
                    </span>
                  </div>
                  <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ color: 'var(--fg-3)', fontSize: 11 }}>
                        <td style={{ padding: '4px 10px' }}>Lot · Документ</td>
                        <td style={{ padding: '4px 10px' }}>Срок</td>
                        <td style={{ padding: '4px 10px', textAlign: 'right' }}>Остаток</td>
                      </tr>
                    </thead>
                    <tbody>
                      {g.lots.map((lot) => {
                        const exp = lot.expiration_date ? new Date(lot.expiration_date) : null;
                        const days = exp
                          ? Math.floor((exp.getTime() - Date.now()) / 86400000)
                          : null;
                        const expColor = days == null ? 'var(--fg-3)'
                          : days < 30 ? 'var(--danger)'
                          : days < 90 ? 'var(--warning, var(--brand-orange))'
                          : 'var(--fg-2)';
                        return (
                          <tr key={lot.id} style={{ borderTop: '1px solid var(--border)' }}>
                            <td style={{ padding: '6px 10px' }}>
                              <div className="mono" style={{ fontWeight: 500 }}>{lot.lot_number}</div>
                              <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                                {lot.doc_number}
                              </div>
                            </td>
                            <td className="mono" style={{ padding: '6px 10px', color: expColor, fontSize: 11 }}>
                              {lot.expiration_date ?? '—'}
                              {days != null && (
                                <div style={{ fontSize: 10 }}>
                                  {days < 0 ? `просрочен ${-days} дн` : `${days} дн`}
                                </div>
                              )}
                            </td>
                            <td className="mono" style={{
                              padding: '6px 10px', textAlign: 'right', fontWeight: 600,
                            }}>
                              {parseFloat(lot.current_quantity).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
                              {selDrug.unit_code && <span style={{ color: 'var(--fg-3)', marginLeft: 4, fontWeight: 400 }}>{selDrug.unit_code}</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ) : (
            <div style={{
              marginTop: 14, padding: 12, fontSize: 12, color: 'var(--fg-3)',
              border: '1px dashed var(--border)', borderRadius: 6, textAlign: 'center',
            }}>
              Нет активных лотов на складах. Сделайте приёмку через
              «+ Приход» во вкладке «Склад».
            </div>
          )}
        </DetailDrawer>
      )}

      {selTr && (
        <DetailDrawer
          title={`Лечение · ${selTr.doc_number}`}
          subtitle={`${selTr.treatment_date} · ${selTr.target_block_code ?? '—'}`}
          onClose={() => setSelTr(null)}
        >
          <KV
            items={[
              { k: 'Документ', v: selTr.doc_number, mono: true },
              { k: 'Дата', v: selTr.treatment_date, mono: true },
              { k: 'Блок', v: selTr.target_block_code ?? '—', mono: true },
              { k: 'Партия', v: selTr.target_batch_doc ?? '—', mono: true },
              { k: 'Стадо', v: selTr.target_herd_doc ?? '—', mono: true },
              { k: 'Препарат', v: selTr.drug_sku ?? '—', mono: true },
              { k: 'Lot', v: selTr.stock_batch_lot ?? '—', mono: true },
              { k: 'Доза', v: selTr.dose_quantity, mono: true },
              { k: 'Голов', v: selTr.heads_treated.toLocaleString('ru-RU'), mono: true },
              { k: 'Каренция', v: `${selTr.withdrawal_period_days} дн` },
              { k: 'Показание', v: selTr.indication },
              {
                k: 'Состояние',
                v: selTr.cancelled_at
                  ? <Badge tone="danger" dot>Отменено</Badge>
                  : <Badge tone="success" dot>Проведено</Badge>,
              },
              ...(selTr.cancelled_at ? [
                { k: 'Отменено', v: new Date(selTr.cancelled_at).toLocaleString('ru-RU'), mono: true },
                { k: 'Причина отмены', v: selTr.cancel_reason || '—' },
              ] : []),
            ]}
          />
        </DetailDrawer>
      )}

      {receiveOpen && <ReceiveModal onClose={() => setReceiveOpen(false)} />}
      {treatmentOpen && <TreatmentModal onClose={() => setTreatmentOpen(false)} />}

      {drugModalOpen && (
        <DrugModal
          initial={editingDrug}
          onClose={() => { setDrugModalOpen(false); setEditingDrug(null); }}
        />
      )}

      {recallFor && (
        <ConfirmDeleteWithReason
          title="Отозвать лот?"
          subject={`${recallFor.doc_number} · ${recallFor.drug_name ?? ''} · Lot ${recallFor.lot_number}`}
          isPending={recall.isPending}
          onConfirm={async (reason) => {
            await recall.mutateAsync({ id: recallFor.id, reason });
            setRecallFor(null);
            if (selStock?.id === recallFor.id) setSelStock(null);
          }}
          onClose={() => setRecallFor(null)}
        />
      )}

      {cancelTreatmentFor && (
        <ConfirmDeleteWithReason
          title="Отменить лечение?"
          subject={`${cancelTreatmentFor.doc_number} · ${cancelTreatmentFor.drug_sku ?? ''} · ${cancelTreatmentFor.dose_quantity}`}
          isPending={cancelTreatment.isPending}
          onConfirm={async (reason) => {
            await cancelTreatment.mutateAsync({ id: cancelTreatmentFor.id, reason });
            setCancelTreatmentFor(null);
            if (selTr?.id === cancelTreatmentFor.id) setSelTr(null);
          }}
          onClose={() => setCancelTreatmentFor(null)}
        />
      )}
    </>
  );
}
