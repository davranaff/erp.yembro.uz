'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import OpexButton from '@/components/OpexButton';
import SellBatchButton, { OpenSaleFromModule } from '@/components/SellBatchButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  drugsCrud,
  stockBatchesCrud,
  treatmentsCrud,
  useCancelTreatment,
  useRecallStockBatch,
  useReleaseQuarantine,
} from '@/hooks/useVet';
import type { VetDrug, VetStockBatch, VetStockStatus, VetTreatmentLog } from '@/types/auth';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';

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
  const [tab, setTab] = useState<'stock' | 'treatments' | 'drugs'>('stock');
  const [stockStatus, setStockStatus] = useState('');
  const [selDrug, setSelDrug] = useState<VetDrug | null>(null);
  const [selStock, setSelStock] = useState<VetStockBatch | null>(null);
  const [selTr, setSelTr] = useState<VetTreatmentLog | null>(null);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [treatmentOpen, setTreatmentOpen] = useState(false);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('vet', 'rw');

  const { data: drugs } = drugsCrud.useList({ is_active: 'true' });
  const { data: stock, isLoading: stockLoading } = stockBatchesCrud.useList(
    stockStatus ? { status: stockStatus } : {},
  );
  const { data: treatments, isLoading: trLoading } = treatmentsCrud.useList();

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
              <button className="btn btn-primary btn-sm" onClick={() => setTreatmentOpen(true)}>
                <Icon name="pharma" size={14} /> Назначить лечение
              </button>
            </>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard tone="orange" iconName="pharma" label="SKU препаратов" sub="активных" value={String(totals.drugs)} />
        <KpiCard tone="green" iconName="check" label="Доступно" sub="лотов" value={String(totals.available)} />
        <KpiCard tone="red" iconName="close" label="Скоро истекает" sub="&lt; 60 дней" value={String(totals.expiring)} />
        <KpiCard tone="blue" iconName="box" label="На карантине" sub="лотов" value={String(totals.quarantine)} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'stock', label: 'Склад' },
            { value: 'treatments', label: 'Журнал лечений' },
            { value: 'drugs', label: 'SKU препаратов' },
          ]}
          value={tab}
          onChange={(v) => setTab(v as typeof tab)}
        />
        {tab === 'stock' && (
          <select className="input" value={stockStatus} onChange={(e) => setStockStatus(e.target.value)} style={{ width: 180 }}>
            <option value="">Все статусы</option>
            {Object.entries(STOCK_STATUS_LABEL).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        )}
      </div>

      {tab === 'stock' && (
        <Panel flush>
          <DataTable<VetStockBatch>
            isLoading={stockLoading}
            rows={stock}
            rowKey={(s) => s.id}
            emptyMessage="Нет лотов."
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
        </Panel>
      )}

      {tab === 'treatments' && (
        <Panel flush>
          <DataTable<VetTreatmentLog>
            isLoading={trLoading}
            rows={treatments}
            rowKey={(t) => t.id}
            emptyMessage="Нет записей лечения."
            onRowClick={(t) => setSelTr(t)}
            rowProps={(t) => ({ active: selTr?.id === t.id })}
            columns={[
              { key: 'doc', label: 'Документ',
                render: (t) => <span className="badge id">{t.doc_number}</span> },
              { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => t.treatment_date },
              { key: 'block', label: 'Блок', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => t.target_block_code ?? '—' },
              { key: 'drug', label: 'Препарат', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => t.drug_sku ?? '—' },
              { key: 'lot', label: 'Lot', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => t.stock_batch_lot ?? '—' },
              { key: 'dose', label: 'Доза', align: 'right', mono: true,
                render: (t) => parseFloat(t.dose_quantity).toLocaleString('ru-RU') },
              { key: 'heads', label: 'Голов', align: 'right', mono: true,
                render: (t) => t.heads_treated.toLocaleString('ru-RU') },
              { key: 'karen', label: 'Каренция', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => t.withdrawal_period_days > 0 ? `${t.withdrawal_period_days} дн` : '—' },
              { key: 'state', label: 'Состояние',
                render: (t) => t.cancelled_at
                  ? <Badge tone="danger" dot>Отменено</Badge>
                  : <Badge tone="success" dot>Проведено</Badge> },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (t) => canEdit ? (
                  <RowActions
                    actions={[
                      {
                        label: 'Отменить',
                        danger: true,
                        hidden: Boolean(t.cancelled_at),
                        disabled: cancelTreatment.isPending,
                        onClick: () => setCancelTreatmentFor(t),
                      },
                    ]}
                  />
                ) : null },
            ]}
          />
        </Panel>
      )}

      {tab === 'drugs' && (
        <Panel flush>
          <DataTable<VetDrug>
            rows={drugs}
            rowKey={(d) => d.id}
            emptyMessage="Нет SKU препаратов."
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
        </Panel>
      )}

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
                marginBottom: 4,
              }}>
                Штрих-код
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <code style={{
                  flex: 1, fontSize: 16, fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                  background: 'var(--bg-card, #fff)',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  letterSpacing: '0.06em',
                }}>
                  {selStock.barcode}
                </code>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    navigator.clipboard?.writeText(selStock.barcode!);
                    alert('Скопировано');
                  }}
                >
                  Копировать
                </button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
                Public-страница: <code>/scan/{selStock.barcode}</code>
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
              { k: 'Цена за ед.', v: `${parseFloat(selStock.price_per_unit_uzs).toLocaleString('ru-RU')} UZS`, mono: true },
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
          <KV
            items={[
              { k: 'SKU', v: selDrug.nomenclature_sku ?? '—', mono: true },
              { k: 'Тип', v: DRUG_TYPE_LABEL[selDrug.drug_type] ?? selDrug.drug_type },
              { k: 'Путь введения', v: selDrug.administration_route },
              { k: 'Каренция', v: `${selDrug.default_withdrawal_days} дн` },
              { k: 'Условия хранения', v: selDrug.storage_conditions || '—' },
              { k: 'Статус', v: selDrug.is_active ? 'Активен' : 'Архив' },
            ]}
          />
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
