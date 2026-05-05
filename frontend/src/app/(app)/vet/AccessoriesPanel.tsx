'use client';

import { useState } from 'react';

import BarcodeLabel from '@/components/BarcodeLabel';
import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import TablePagination from '@/components/ui/TablePagination';
import { accessoriesCrud } from '@/hooks/useVet';
import { useHasLevel } from '@/hooks/usePermissions';
import { useStockMovements } from '@/hooks/useStockMovements';
import type { VetAccessory } from '@/types/auth';

import AccessoryFormModal from './AccessoryFormModal';
import AccessoryReceiveModal from './AccessoryReceiveModal';

function fmt(uzs: string | null | undefined): string {
  if (uzs == null || uzs === '') return '—';
  const n = parseFloat(uzs);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

/**
 * Панель «Аксессуары» в /vet — товары для перепродажи (миски, поилки и т.п.).
 *
 * CRUD на карточку + кнопка «Приёмка» (отдельный сервис receive_vet_accessory
 * с пересчётом weighted-avg cost). Продажа идёт через стандартный
 * SaleOrderModal (новая опция vet_accessory).
 */
export default function AccessoriesPanel() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const { data: pageData, isLoading } = accessoriesCrud.useListPaginated(
    { ordering: 'nomenclature__sku' }, page, pageSize,
  );
  const data = pageData?.results ?? [];
  const del = accessoriesCrud.useDelete();
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('vet', 'rw');

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<VetAccessory | null>(null);
  const [receiving, setReceiving] = useState<VetAccessory | null>(null);
  const [sel, setSel] = useState<VetAccessory | null>(null);
  // Свежая копия выбранного аксессуара (после receive remount/refresh).
  // Берём из data чтобы остаток обновился без закрытия drawer.
  const selFresh = sel ? data.find((a) => a.id === sel.id) ?? sel : null;

  const handleDelete = (a: VetAccessory) => {
    if (!confirm(`Удалить ${a.nomenclature_name ?? a.nomenclature_sku}?`)) return;
    del.mutate(a.id, {
      onError: (err) => alert('Не удалось удалить: ' + err.message),
      onSuccess: () => setSel(null),
    });
  };

  return (
    <>
      <Panel
        flush
        tools={canEdit ? (
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setCreateOpen(true)}
          >
            <Icon name="plus" size={12} /> Новый аксессуар
          </button>
        ) : null}
      >
        <DataTable<VetAccessory>
          isLoading={isLoading}
          rows={data}
          rowKey={(a) => a.id}
          onRowClick={(a) => setSel(a)}
          rowProps={(a) => ({ active: sel?.id === a.id })}
          emptyMessage="Аксессуаров ещё нет — добавьте первый (миска, поилка, переноска…)"
          columns={[
            {
              key: 'sku',
              label: 'SKU',
              mono: true,
              render: (a) => (
                <span style={{ fontWeight: 500 }}>{a.nomenclature_sku ?? '—'}</span>
              ),
            },
            {
              key: 'name',
              label: 'Наименование',
              render: (a) => a.nomenclature_name ?? '—',
            },
            {
              key: 'wh',
              label: 'Склад',
              mono: true,
              cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (a) => a.warehouse_code ?? '—',
            },
            {
              key: 'qty',
              label: 'Остаток',
              align: 'right',
              mono: true,
              render: (a) => `${parseFloat(a.current_quantity).toLocaleString('ru-RU')} ${a.unit_code ?? ''}`,
            },
            {
              key: 'cost',
              label: 'Себестоимость',
              align: 'right',
              mono: true,
              cellStyle: { fontSize: 12 },
              render: (a) => a.cost_per_unit_uzs == null ? '—' : fmt(a.cost_per_unit_uzs),
            },
            {
              key: 'price',
              label: 'Цена продажи',
              align: 'right',
              mono: true,
              cellStyle: { fontWeight: 600, color: 'var(--brand-orange)' },
              render: (a) => fmt(a.sale_price_uzs),
            },
            {
              key: 'barcode',
              label: 'Штрих-код',
              mono: true,
              cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (a) => a.barcode ?? '—',
            },
            {
              key: 'status',
              label: '',
              render: (a) => a.is_active
                ? null
                : <Badge tone="neutral">Отключён</Badge>,
            },
            {
              key: 'actions',
              label: '',
              align: 'right',
              width: 60,
              render: (a) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'Принять (+ к остатку)',
                      onClick: () => setReceiving(a),
                    },
                    {
                      label: 'Редактировать',
                      onClick: () => setEditing(a),
                    },
                    {
                      label: 'Удалить',
                      danger: true,
                      hidden: parseFloat(a.current_quantity) > 0,
                      onClick: () => handleDelete(a),
                    },
                  ]}
                />
              ) : null,
            },
          ]}
        />
        {pageData && (
          <TablePagination
            page={page} pageSize={pageSize} count={pageData.count}
            hasPrev={Boolean(pageData.previous)} hasNext={Boolean(pageData.next)}
            onPageChange={setPage} onPageSizeChange={setPageSize}
          />
        )}
      </Panel>

      {selFresh && (
        <AccessoryDrawer
          accessory={selFresh}
          canEdit={canEdit}
          onClose={() => setSel(null)}
          onReceive={() => setReceiving(selFresh)}
          onEdit={() => setEditing(selFresh)}
          onDelete={() => handleDelete(selFresh)}
        />
      )}

      {(createOpen || editing) && (
        <AccessoryFormModal
          initial={editing}
          onClose={() => { setCreateOpen(false); setEditing(null); }}
        />
      )}

      {receiving && (
        <AccessoryReceiveModal
          accessory={receiving}
          onClose={() => setReceiving(null)}
        />
      )}
    </>
  );
}


function AccessoryDrawer({
  accessory, canEdit, onClose, onReceive, onEdit, onDelete,
}: {
  accessory: VetAccessory;
  canEdit: boolean;
  onClose: () => void;
  onReceive: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { data: movements, isLoading } = useStockMovements({
    nomenclature: accessory.nomenclature,
    module_code: 'vet',
    limit: 50,
  });

  // Фильтруем движения только по этому аксессуару (через source_object_id).
  // Источник — сам аксессуар (для receive INCOMING) или продажа (OUTGOING),
  // поэтому фильтр по source_object_id неточен — используем nomenclature
  // как proxy. На практике у вет-номенклатуры аксессуаров уникальная,
  // поэтому почти всегда совпадает 1:1.
  const filtered = (movements ?? []).filter(
    (m) => m.warehouse_from === accessory.warehouse
        || m.warehouse_to === accessory.warehouse,
  );

  const fmt = (uzs: string | null | undefined): string => {
    if (uzs == null || uzs === '') return '—';
    const n = parseFloat(uzs);
    if (Number.isNaN(n)) return '—';
    return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
  };

  return (
    <DetailDrawer
      title={accessory.nomenclature_name ?? accessory.nomenclature_sku ?? 'Аксессуар'}
      subtitle={`${accessory.nomenclature_sku ?? ''} · склад ${accessory.warehouse_code ?? '—'}`}
      onClose={onClose}
      actions={canEdit ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={onReceive}
          >
            <Icon name="plus" size={12} /> Принять
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onEdit}
          >
            Редактировать
          </button>
          {parseFloat(accessory.current_quantity) === 0 && (
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--danger)' }}
              onClick={onDelete}
            >
              Удалить
            </button>
          )}
        </div>
      ) : undefined}
    >
      {accessory.barcode && (
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

          <div style={{ marginBottom: 10, overflowX: 'auto' }}>
            <BarcodeLabel
              barcode={accessory.barcode}
              drugName={accessory.nomenclature_name ?? accessory.nomenclature_sku ?? undefined}
              lotNumber={accessory.nomenclature_sku ?? undefined}
            />
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                navigator.clipboard?.writeText(accessory.barcode!);
                alert('Скопировано');
              }}
            >
              Копировать
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => {
                const p = new URLSearchParams({
                  barcode: accessory.barcode!,
                  ...(accessory.nomenclature_name ? { drug: accessory.nomenclature_name } : {}),
                  ...(accessory.nomenclature_sku ? { lot: accessory.nomenclature_sku } : {}),
                });
                window.open(`/print/vet-label?${p}`, '_blank');
              }}
            >
              Печать этикетки
            </button>
          </div>

          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
            Сканер открывает: <code>/scan/{accessory.barcode}</code>
          </div>
        </div>
      )}

      <KV
        cols={2}
        items={[
          { k: 'Остаток',
            v: <span className="mono">{accessory.current_quantity} {accessory.unit_code ?? ''}</span> },
          { k: 'Себестоимость, сум',
            v: accessory.cost_per_unit_uzs == null
              ? <span style={{ color: 'var(--fg-3)' }}>скрыто (нет vet.r)</span>
              : <span className="mono">{fmt(accessory.cost_per_unit_uzs)}</span> },
          { k: 'Цена продажи, сум',
            v: <span className="mono" style={{ color: 'var(--brand-orange)', fontWeight: 600 }}>
              {fmt(accessory.sale_price_uzs)}
            </span> },
          { k: 'Стоимость склада',
            v: accessory.cost_per_unit_uzs == null
              ? <span style={{ color: 'var(--fg-3)' }}>—</span>
              : <span className="mono">
                  {fmt(String(parseFloat(accessory.cost_per_unit_uzs) * parseFloat(accessory.current_quantity)))}
                </span> },
          { k: 'Штрих-код', v: <span className="mono">{accessory.barcode ?? '—'}</span> },
          { k: 'Статус',
            v: accessory.is_active
              ? <Badge tone="success" dot>Активен</Badge>
              : <Badge tone="neutral" dot>Отключён</Badge> },
        ]}
      />

      {accessory.notes && (
        <div style={{
          marginTop: 12, padding: 10, fontSize: 12,
          background: 'var(--bg-soft)', borderRadius: 6,
        }}>
          {accessory.notes}
        </div>
      )}

      <div style={{ marginTop: 14, fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
        История движений ({filtered.length})
      </div>

      {isLoading && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Загружаем…</div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div style={{
          padding: 12, fontSize: 12, color: 'var(--fg-3)',
          textAlign: 'center', border: '1px dashed var(--border)', borderRadius: 6,
        }}>
          Движений пока нет. Нажмите «Принять» чтобы пополнить остаток.
        </div>
      )}

      {filtered.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {filtered.map((m) => (
            <div
              key={m.id}
              style={{
                padding: '6px 10px', fontSize: 12, borderRadius: 4,
                border: '1px solid var(--border)', display: 'flex',
                alignItems: 'center', gap: 8, flexWrap: 'wrap',
              }}
            >
              <Badge tone={m.kind === 'incoming' ? 'success' : m.kind === 'outgoing' ? 'warn' : 'info'}>
                {m.kind === 'incoming' ? '+ Приход' : m.kind === 'outgoing' ? '− Расход' : 'Перемещение'}
              </Badge>
              <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                {m.doc_number}
              </span>
              <span className="mono">{parseFloat(m.quantity).toLocaleString('ru-RU')} {accessory.unit_code ?? ''}</span>
              <span style={{ color: 'var(--fg-3)' }}>·</span>
              <span className="mono">{fmt(m.amount_uzs)} сум</span>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                {new Date(m.date).toLocaleDateString('ru-RU')}
              </span>
            </div>
          ))}
        </div>
      )}
    </DetailDrawer>
  );
}
