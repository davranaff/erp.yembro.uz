'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import {
  transfersCrud,
  useAcceptTransfer,
  useCancelTransfer,
  useReviewTransfer,
  useSubmitTransfer,
} from '@/hooks/useTransfers';
import type { InterModuleTransfer, TransferState } from '@/types/auth';

const STATE_LABEL: Record<TransferState, string> = {
  draft: 'Черновик',
  awaiting_acceptance: 'Ожидает приёма',
  under_review: 'На проверке',
  posted: 'Проведён',
  cancelled: 'Отменён',
};

const STATE_TONE: Record<TransferState, 'neutral' | 'warn' | 'info' | 'success' | 'danger'> = {
  draft: 'neutral',
  awaiting_acceptance: 'warn',
  under_review: 'info',
  posted: 'success',
  cancelled: 'danger',
};

/** Локализация и иконки модулей. Если модуль не в карте — показываем как есть. */
const MODULE_META: Record<string, { label: string; icon: string; color: string }> = {
  matochnik:  { label: 'Маточник',     icon: '🐔', color: 'var(--info, #3B82F6)' },
  incubation: { label: 'Инкубация',    icon: '🥚', color: 'var(--warning, #F59E0B)' },
  feedlot:    { label: 'Откорм',       icon: '🐤', color: 'var(--success, #10B981)' },
  slaughter:  { label: 'Убойня',       icon: '🔪', color: 'var(--danger, #EF4444)' },
  feed:       { label: 'Корма',        icon: '🌾', color: 'var(--brand-orange, #E8751A)' },
  vet:        { label: 'Вет. аптека',  icon: '💊', color: '#8B5CF6' },
};

function moduleMeta(code: string | null | undefined) {
  if (!code) return { label: '—', icon: '', color: 'var(--fg-3)' };
  return MODULE_META[code] ?? { label: code, icon: '', color: 'var(--fg-3)' };
}

/** Чип модуля (эмодзи + локализованное имя + цветная плашка) */
function ModuleChip({
  code,
  block,
  size = 'sm',
}: {
  code: string | null | undefined;
  block?: string | null;
  size?: 'sm' | 'md';
}) {
  const m = moduleMeta(code);
  const fontSize = size === 'md' ? 14 : 12;
  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', minWidth: 0 }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        fontWeight: 600, fontSize,
        color: 'var(--fg-1)',
      }}>
        <span style={{ fontSize: fontSize + 2 }}>{m.icon}</span>
        {m.label}
      </div>
      {block && (
        <div className="mono" style={{
          fontSize: 11, color: 'var(--fg-3)', marginTop: 2,
        }}>
          {block}
        </div>
      )}
    </div>
  );
}

/** Карта производственного цикла — наглядная схема путей */
const FLOW_LANES: Array<{ from: string; to: string; description: string }> = [
  { from: 'matochnik',  to: 'incubation', description: 'Яйцо → инкубация' },
  { from: 'incubation', to: 'feedlot',    description: 'Цыплёнок → откорм' },
  { from: 'feedlot',    to: 'slaughter',  description: 'Птица → убой' },
  { from: 'feed',       to: 'feedlot',    description: 'Корм → откорм' },
  { from: 'feed',       to: 'matochnik',  description: 'Корм → маточник' },
];

function FlowCard({
  from, to, description, count,
}: {
  from: string; to: string; description: string; count: number;
}) {
  const f = moduleMeta(from);
  const t = moduleMeta(to);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 12px',
      borderRadius: 6,
      background: count > 0 ? 'var(--bg-card, #fff)' : 'var(--bg-soft)',
      border: '1px solid ' + (count > 0 ? 'var(--brand-orange)' : 'var(--border)'),
      borderLeft: '3px solid ' + (count > 0 ? 'var(--brand-orange)' : 'var(--border)'),
      fontSize: 12,
      flex: '1 1 220px',
      minWidth: 220,
    }}>
      <span style={{ fontSize: 18 }}>{f.icon}</span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
          <span>{f.label}</span>
          <span style={{ color: 'var(--fg-3)' }}>→</span>
          <span style={{ fontSize: 16 }}>{t.icon}</span>
          <span>{t.label}</span>
        </div>
        <div style={{ color: 'var(--fg-3)', fontSize: 11, marginTop: 2 }}>
          {description}
        </div>
      </div>
      <div style={{
        minWidth: 36, textAlign: 'right', fontWeight: 700,
        color: count > 0 ? 'var(--brand-orange)' : 'var(--fg-3)',
        fontSize: 16,
      }} className="mono">
        {count}
      </div>
    </div>
  );
}

export default function TransfersPage() {
  const [state, setState] = useState('');
  const [route, setRoute] = useState<string>(''); // "from→to" фильтр маршрута
  const [sel, setSel] = useState<InterModuleTransfer | null>(null);

  const { data, isLoading, error, refetch, isFetching } = transfersCrud.useList(
    state ? { state } : {},
  );

  const submit = useSubmitTransfer();
  const review = useReviewTransfer();
  const accept = useAcceptTransfer();
  const cancel = useCancelTransfer();

  const pending = submit.isPending || review.isPending || accept.isPending || cancel.isPending;

  const totals = useMemo(() => {
    if (!data) return { draft: 0, awaiting: 0, posted: 0 };
    return {
      draft: data.filter((t) => t.state === 'draft').length,
      awaiting: data.filter((t) => t.state === 'awaiting_acceptance').length,
      posted: data.filter((t) => t.state === 'posted').length,
    };
  }, [data]);

  // Счётчики маршрутов (только активные транзферы — не отменённые)
  const routeCounts = useMemo(() => {
    const map = new Map<string, number>();
    if (!data) return map;
    for (const t of data) {
      if (t.state === 'cancelled') continue;
      const key = `${t.from_module_code}→${t.to_module_code}`;
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return map;
  }, [data]);

  // Применяем фильтр маршрута к таблице
  const filteredRows = useMemo(() => {
    if (!data) return data;
    if (!route) return data;
    return data.filter((t) => `${t.from_module_code}→${t.to_module_code}` === route);
  }, [data, route]);

  const handleSubmit = async (t: InterModuleTransfer) => {
    try { await submit.mutateAsync({ id: t.id }); setSel(null); }
    catch (err) { alert(`Submit: ${err instanceof Error ? err.message : 'ошибка'}`); }
  };
  const handleAccept = async (t: InterModuleTransfer) => {
    try { await accept.mutateAsync({ id: t.id }); setSel(null); }
    catch (err) { alert(`Accept: ${err instanceof Error ? err.message : 'ошибка'}`); }
  };

  const handleReview = async (t: InterModuleTransfer) => {
    const reason = prompt(`Причина проверки ${t.doc_number}?`);
    if (reason === null) return;
    try {
      await review.mutateAsync({ id: t.id, body: { reason } });
    } catch (err) {
      alert(err instanceof Error ? err.message : 'ошибка');
    }
  };

  const handleCancel = async (t: InterModuleTransfer) => {
    const reason = prompt(`Причина отмены ${t.doc_number}?`);
    if (reason === null) return;
    try {
      await cancel.mutateAsync({ id: t.id, body: { reason } });
      setSel(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'ошибка');
    }
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Межмодульные передачи</h1>
          <div className="sub">
            Перемещение партий между этапами производства · FSM: черновик → ожидает приёма → проведён
          </div>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()} disabled={isFetching}>
            <Icon name="chart" size={14} /> {isFetching ? '…' : 'Обновить'}
          </button>
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard tone="orange" iconName="chart" label="Всего ММ" sub="в фильтре" value={String(data?.length ?? 0)} />
        <KpiCard tone="blue" iconName="box" label="Черновики" sub="готовятся" value={String(totals.draft)} />
        <KpiCard tone="red" iconName="close" label="Ждут приёма" sub="нужно действие" value={String(totals.awaiting)} />
        <KpiCard tone="green" iconName="check" label="Проведены" sub="завершены" value={String(totals.posted)} />
      </div>

      {/* Карта производственного цикла */}
      <div style={{ marginBottom: 14 }}>
        <div style={{
          fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
          textTransform: 'uppercase', letterSpacing: '.04em',
          marginBottom: 6, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>Маршруты передач</span>
          {route && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setRoute('')}
              style={{ fontSize: 11 }}
            >
              ✕ Сбросить фильтр
            </button>
          )}
        </div>
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 8,
        }}>
          {FLOW_LANES.map((lane) => {
            const key = `${lane.from}→${lane.to}`;
            const count = routeCounts.get(key) ?? 0;
            const isActive = route === key;
            return (
              <button
                key={key}
                onClick={() => setRoute(isActive ? '' : key)}
                style={{
                  flex: '1 1 220px', minWidth: 220, padding: 0,
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  textAlign: 'left',
                  outline: isActive ? '2px solid var(--brand-orange)' : 'none',
                  borderRadius: 6,
                }}
              >
                <FlowCard
                  from={lane.from}
                  to={lane.to}
                  description={lane.description}
                  count={count}
                />
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: '', label: 'Все' },
            { value: 'draft', label: 'Черновики' },
            { value: 'awaiting_acceptance', label: 'Ожидают' },
            { value: 'under_review', label: 'Проверка' },
            { value: 'posted', label: 'Проведены' },
            { value: 'cancelled', label: 'Отменены' },
          ]}
          value={state}
          onChange={setState}
        />
      </div>

      <Panel flush>
        <DataTable<InterModuleTransfer>
          isLoading={isLoading}
          rows={filteredRows}
          rowKey={(t) => t.id}
          error={error}
          emptyMessage={
            route
              ? 'Нет передач по этому маршруту. Попробуйте другой или сбросьте фильтр.'
              : 'Нет передач.'
          }
          onRowClick={(t) => setSel(t)}
          rowProps={(t) => ({ active: sel?.id === t.id })}
          columns={[
            { key: 'doc', label: 'ММ',
              render: (t) => <span className="badge id">{t.doc_number || '—'}</span> },
            { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
              render: (t) => new Date(t.transfer_date).toLocaleDateString('ru') },
            { key: 'route', label: 'Маршрут',
              render: (t) => (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  minWidth: 0,
                }}>
                  <ModuleChip code={t.from_module_code} block={t.from_block_code} />
                  <Icon name="arrow-right" size={14} />
                  <ModuleChip code={t.to_module_code} block={t.to_block_code} />
                </div>
              ) },
            { key: 'nom', label: 'Номенклатура', cellStyle: { fontSize: 12 },
              render: (t) => (
                <>
                  <div>{t.nomenclature_name ?? '—'}</div>
                  <div style={{ color: 'var(--fg-3)', fontSize: 11 }}>{t.nomenclature_sku ?? ''}</div>
                </>
              ) },
            { key: 'qty', label: 'Кол-во', align: 'right', mono: true,
              render: (t) => (
                <>
                  {parseFloat(t.quantity || '0').toLocaleString('ru-RU')}
                  {t.unit_code && <span style={{ color: 'var(--fg-3)', marginLeft: 4 }}>{t.unit_code}</span>}
                </>
              ) },
            { key: 'cost', label: 'Себест. UZS', align: 'right', mono: true,
              render: (t) => parseFloat(t.cost_uzs || '0').toLocaleString('ru-RU') },
            { key: 'status', label: 'Статус',
              render: (t) => <Badge tone={STATE_TONE[t.state]} dot>{STATE_LABEL[t.state]}</Badge> },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (t) => (
                <RowActions
                  actions={[
                    {
                      label: 'Отправить на приём',
                      hidden: t.state !== 'draft',
                      disabled: pending,
                      onClick: () => handleSubmit(t),
                    },
                    {
                      label: 'Проверить',
                      hidden: t.state !== 'awaiting_acceptance',
                      disabled: pending,
                      onClick: () => handleReview(t),
                    },
                    {
                      label: 'Принять',
                      hidden: !(t.state === 'awaiting_acceptance' || t.state === 'under_review'),
                      disabled: pending,
                      onClick: () => handleAccept(t),
                    },
                    {
                      label: 'Отменить',
                      danger: true,
                      hidden: t.state === 'posted' || t.state === 'cancelled',
                      disabled: pending,
                      onClick: () => handleCancel(t),
                    },
                  ]}
                />
              ) },
          ]}
        />
      </Panel>

      {sel && (
        <DetailDrawer
          title={`ММ · ${sel.doc_number || '(черновик)'}`}
          subtitle={`${moduleMeta(sel.from_module_code).label} → ${moduleMeta(sel.to_module_code).label} · ${STATE_LABEL[sel.state]}`}
          onClose={() => setSel(null)}
        >
          {/* Визуальный маршрут наверху drawer */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: 12, marginBottom: 14,
            background: 'var(--bg-soft)', borderRadius: 6,
            border: '1px solid var(--border)',
          }}>
            <ModuleChip code={sel.from_module_code} block={sel.from_block_code} size="md" />
            <Icon name="arrow-right" size={20} />
            <ModuleChip code={sel.to_module_code} block={sel.to_block_code} size="md" />
            <div style={{ flex: 1 }} />
            <Badge tone={STATE_TONE[sel.state]} dot>{STATE_LABEL[sel.state]}</Badge>
          </div>

          <KV
            items={[
              { k: 'Документ', v: sel.doc_number || '—', mono: true },
              { k: 'Дата', v: new Date(sel.transfer_date).toLocaleString('ru'), mono: true },
              { k: 'Из модуля', v: moduleMeta(sel.from_module_code).label },
              { k: 'В модуль', v: moduleMeta(sel.to_module_code).label },
              { k: 'Из блока', v: sel.from_block_code ?? '—' },
              { k: 'В блок', v: sel.to_block_code ?? '—' },
              { k: 'Со склада', v: sel.from_warehouse_code ?? '—' },
              { k: 'На склад', v: sel.to_warehouse_code ?? '—' },
              { k: 'Номенклатура', v: `${sel.nomenclature_sku ?? '—'} · ${sel.nomenclature_name ?? ''}` },
              { k: 'Количество', v: `${sel.quantity} ${sel.unit_code ?? ''}`, mono: true },
              { k: 'Себестоимость', v: `${parseFloat(sel.cost_uzs).toLocaleString('ru-RU')} UZS`, mono: true },
              { k: 'Партия', v: sel.batch_doc_number ?? '—', mono: true },
              ...(sel.review_reason ? [{ k: 'Причина проверки', v: sel.review_reason }] : []),
              ...(sel.posted_at ? [{ k: 'Проведён', v: new Date(sel.posted_at).toLocaleString('ru'), mono: true }] : []),
            ]}
          />
        </DetailDrawer>
      )}
    </>
  );
}
