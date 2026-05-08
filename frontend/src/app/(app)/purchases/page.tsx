'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import TablePagination from '@/components/ui/TablePagination';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  purchasesCrud,
  useConfirmPurchase,
  useReversePurchase,
} from '@/hooks/usePurchases';
import type {
  PurchaseItem,
  PurchaseOrder,
  PurchasePaymentStatus,
  PurchaseStatus,
} from '@/types/auth';

import PayPurchaseModal from './PayPurchaseModal';
import PurchaseAttachmentsModal from './PurchaseAttachmentsModal';
import PurchaseOrderModal from './PurchaseOrderModal';

const STATUS_LABEL: Record<PurchaseStatus, string> = {
  draft: 'Черновик',
  confirmed: 'Проведён',
  paid: 'Оплачен',
  cancelled: 'Отменён',
};

const STATUS_TONE: Record<PurchaseStatus, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  draft: 'neutral',
  confirmed: 'success',
  paid: 'info',
  cancelled: 'danger',
};

const PAY_LABEL: Record<PurchasePaymentStatus, string> = {
  unpaid: 'Не оплачен',
  partial: 'Частично',
  paid: 'Оплачен',
  overpaid: 'Переплата',
};

const PAY_TONE: Record<PurchasePaymentStatus, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  unpaid: 'neutral',
  partial: 'warn',
  paid: 'success',
  overpaid: 'info',
};

function fmtUzs(v: string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

function fmtItemQty(it: PurchaseItem): string {
  const q = parseFloat(it.quantity || '0');
  if (Number.isNaN(q) || q === 0) return '';
  const qStr = q.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
  return it.unit_code ? `${qStr} ${it.unit_code}` : qStr;
}

/** Краткая сводка позиций под doc_number: «Кукуруза 500 кг, Соя 200 кг + ещё 1». */
function summarizeItems(items: PurchaseItem[] | undefined): string {
  if (!items || items.length === 0) return 'Без позиций';
  const head = items.slice(0, 2).map((it) => {
    const name = it.nomenclature_name || it.nomenclature_sku || '—';
    const qty = fmtItemQty(it);
    return qty ? `${name} ${qty}` : name;
  });
  const more = items.length - head.length;
  return more > 0 ? `${head.join(', ')} + ещё ${more}` : head.join(', ');
}

export default function PurchasesPage() {
  const [tab, setTab] = useState<'all' | PurchaseStatus>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PurchaseOrder | null>(null);
  const [payingOrder, setPayingOrder] = useState<PurchaseOrder | null>(null);
  const [filesFor, setFilesFor] = useState<PurchaseOrder | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('purchases', 'rw');

  const filter = useMemo(
    () => (tab === 'all' ? {} : { status: tab }),
    [tab],
  );

  const { data: pageData, isLoading } = purchasesCrud.useListPaginated(filter, page, pageSize);
  const orders = pageData?.results ?? [];
  const { data: allOrders } = purchasesCrud.useList(filter);

  const confirmMutation = useConfirmPurchase();
  const reverseMutation = useReversePurchase();

  const totals = useMemo(() => {
    const list = allOrders ?? [];
    const confirmed = list.filter(
      (o) => o.status === 'confirmed' || o.status === 'paid',
    );
    const spend = confirmed.reduce((s, o) => s + parseFloat(o.amount_uzs || '0'), 0);
    const payable = confirmed.reduce(
      (s, o) => s + (parseFloat(o.amount_uzs || '0') - parseFloat(o.paid_amount_uzs || '0')),
      0,
    );
    const fxCount = confirmed.filter((o) => o.currency_code && o.currency_code !== 'UZS').length;
    return {
      count: pageData?.count ?? list.length,
      spend,
      payable,
      fxCount,
    };
  }, [allOrders, pageData]);

  const handleConfirm = (o: PurchaseOrder) => {
    if (!window.confirm(
      'Провести закуп ' + (o.doc_number || 'б/н') +
      '?\nБудет снят FX-snapshot курса и созданы проводки ГК.',
    )) return;
    confirmMutation.mutate({ id: o.id }, {
      onError: (err) => alert('Не удалось провести: ' + err.message),
    });
  };

  const handleReverse = (o: PurchaseOrder) => {
    const reason = window.prompt('Причина сторно (необязательно):');
    if (reason === null) return;
    reverseMutation.mutate({ id: o.id, body: { reason } }, {
      onError: (err) => alert('Не удалось сторнировать: ' + err.message),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Закупки</h1>
          <div className="sub">
            Приходы от поставщиков · FX-курс фиксируется при проведении
          </div>
        </div>
        <div className="actions">
          {canEdit && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => { setEditing(null); setModalOpen(true); }}
            >
              <Icon name="plus" size={14} /> Новая закупка
            </button>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard
          tone="orange"
          iconName="bag"
          label="Всего"
          sub="документов"
          value={String(totals.count)}
        />
        <KpiCard
          tone="blue"
          iconName="chart"
          label="Оборот закупа"
          sub="проведено"
          value={fmtUzs(String(totals.spend))}
        />
        <KpiCard
          tone="red"
          iconName="users"
          label="Мы должны"
          sub="не оплачено"
          value={fmtUzs(String(totals.payable))}
        />
        <KpiCard
          tone="green"
          iconName="book"
          label="В валюте"
          sub="из проведённых"
          value={String(totals.fxCount)}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'all', label: 'Все' },
            { value: 'draft', label: 'Черновики' },
            { value: 'confirmed', label: 'Проведённые' },
            { value: 'paid', label: 'Оплаченные' },
            { value: 'cancelled', label: 'Отменённые' },
          ]}
          value={tab}
          onChange={(v) => { setTab(v as typeof tab); setPage(1); }}
        />
      </div>

      <Panel flush>
        <DataTable<PurchaseOrder>
          isLoading={isLoading}
          rows={orders}
          rowKey={(o) => o.id}
          emptyMessage="Закупов нет. Нажмите «Новая закупка» чтобы оприходовать приход."
          columns={[
            {
              key: 'doc_number', label: 'Документ', mono: true,
              render: (o) => (
                <div>
                  <div>{o.doc_number || '—'}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-sans)', marginTop: 2 }}>
                    {summarizeItems(o.items)}
                  </div>
                </div>
              ),
            },
            { key: 'date', label: 'Дата', render: (o) => o.date },
            {
              key: 'counterparty', label: 'Поставщик',
              render: (o) => o.counterparty_name ?? '—',
            },
            {
              key: 'amount', label: 'Сумма', align: 'right', mono: true,
              render: (o) => (
                <>
                  {fmtUzs(o.amount_uzs)}
                  {o.currency_code && o.currency_code !== 'UZS' && o.amount_foreign && (
                    <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                      {parseFloat(o.amount_foreign).toLocaleString('ru-RU')} {o.currency_code}
                      {o.exchange_rate && ` @ ${parseFloat(o.exchange_rate).toLocaleString('ru-RU')}`}
                    </div>
                  )}
                </>
              ),
            },
            {
              key: 'status', label: 'Статус',
              render: (o) => <Badge tone={STATUS_TONE[o.status]}>{STATUS_LABEL[o.status]}</Badge>,
            },
            {
              key: 'pay', label: 'Оплата',
              render: (o) => (o.status === 'confirmed' || o.status === 'paid')
                ? <Badge tone={PAY_TONE[o.payment_status]}>{PAY_LABEL[o.payment_status]}</Badge>
                : '—',
            },
            {
              key: 'actions', label: '', align: 'right', width: 60,
              render: (o) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'Править',
                      hidden: o.status !== 'draft',
                      onClick: () => { setEditing(o); setModalOpen(true); },
                    },
                    {
                      label: 'Провести',
                      hidden: o.status !== 'draft',
                      disabled: confirmMutation.isPending,
                      onClick: () => handleConfirm(o),
                    },
                    {
                      label: 'Оплатить',
                      hidden: !(
                        (o.status === 'confirmed' || o.status === 'paid') &&
                        parseFloat(o.paid_amount_uzs || '0') < parseFloat(o.amount_uzs || '0')
                      ),
                      onClick: () => setPayingOrder(o),
                    },
                    {
                      label: 'Файлы',
                      onClick: () => setFilesFor(o),
                    },
                    {
                      label: 'Сторно',
                      danger: true,
                      hidden: !(o.status === 'confirmed' && parseFloat(o.paid_amount_uzs || '0') === 0),
                      disabled: reverseMutation.isPending,
                      onClick: () => handleReverse(o),
                    },
                  ]}
                />
              ) : null,
            },
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
        <PurchaseOrderModal
          initial={editing}
          onClose={() => { setModalOpen(false); setEditing(null); }}
        />
      )}
      {payingOrder && (
        <PayPurchaseModal
          order={payingOrder}
          onClose={() => setPayingOrder(null)}
        />
      )}
      {filesFor && (
        <PurchaseAttachmentsModal
          purchase={filesFor}
          onClose={() => setFilesFor(null)}
        />
      )}
    </>
  );
}
