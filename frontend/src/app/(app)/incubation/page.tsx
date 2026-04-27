'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import OpexButton from '@/components/OpexButton';
import { OpenSaleFromModule } from '@/components/SellBatchButton';
import DataTable from '@/components/ui/DataTable';
import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import EmptyState from '@/components/ui/EmptyState';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useProductionBlocks } from '@/hooks/useBlocks';
import {
  runsCrud,
  useCancelRun,
  useChickBatchForRun,
  useSendChicksToFeedlot,
  useTransferToHatcher,
} from '@/hooks/useIncubation';
import { useHasLevel } from '@/hooks/usePermissions';
import type { IncubationRun, IncubationStatus } from '@/types/auth';

import HatchModal from './HatchModal';
import IncubationTimelineModal from './IncubationTimelineModal';
import MiragePanel from './MiragePanel';
import RegimePanel from './RegimePanel';
import RunModal from './RunModal';
import StatsPanel from './StatsPanel';

const STATUS_LABEL: Record<IncubationStatus, string> = {
  incubating: 'Инкубация',
  hatching: 'Вывод',
  transferred: 'Передано',
  cancelled: 'Отменено',
};

const STATUS_TONE: Record<IncubationStatus, 'warn' | 'info' | 'success' | 'neutral'> = {
  incubating: 'warn',
  hatching: 'info',
  transferred: 'success',
  cancelled: 'neutral',
};

const TABS = [
  { key: 'overview', label: 'Обзор' },
  { key: 'regime', label: 'Режим' },
  { key: 'mirage', label: 'Овоскопия' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

function daysBetween(from: string, to: string): number {
  const a = new Date(from).getTime();
  const b = new Date(to).getTime();
  return Math.max(0, Math.floor((b - a) / 86400000));
}

export default function IncubationPage() {
  const [status, setStatus] = useState('');
  const [sel, setSel] = useState<IncubationRun | null>(null);
  const [tab, setTab] = useState<TabKey>('overview');
  const [createOpen, setCreateOpen] = useState(false);
  const [hatchFor, setHatchFor] = useState<IncubationRun | null>(null);
  const [hatcherPick, setHatcherPick] = useState<IncubationRun | null>(null);
  const [timelineFor, setTimelineFor] = useState<IncubationRun | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('incubation', 'rw');

  const { data: runs, isLoading, error, refetch, isFetching } = runsCrud.useList({
    status: status || undefined,
  });
  const { data: hatchers } = useProductionBlocks({ kind: 'hatcher' });
  const del = runsCrud.useDelete();
  const transfer = useTransferToHatcher();
  const cancelRun = useCancelRun();
  const sendToFeedlot = useSendChicksToFeedlot();
  const { data: chickBatch } = useChickBatchForRun(sel);

  const totals = useMemo(() => {
    if (!runs) return { loaded: 0, onHatching: 0, done: 0 };
    let loaded = 0, onHatching = 0, done = 0;
    for (const r of runs) {
      if (r.status === 'incubating') loaded += r.eggs_loaded;
      if (r.status === 'hatching') onHatching += r.eggs_loaded;
      if (r.status === 'transferred') done += r.hatched_count ?? 0;
    }
    return { loaded, onHatching, done };
  }, [runs]);

  const handleDelete = (r: IncubationRun) => {
    if (!confirm(`Удалить партию ${r.doc_number}?`)) return;
    del.mutate(r.id, {
      onSuccess: () => { if (sel?.id === r.id) setSel(null); },
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  const handleTransfer = async (r: IncubationRun, hatcherBlockId: string) => {
    try {
      await transfer.mutateAsync({ id: r.id, body: { hatcher_block: hatcherBlockId } });
      setHatcherPick(null);
    } catch (err) {
      alert(`Не удалось: ${err instanceof Error ? err.message : 'ошибка'}`);
    }
  };

  const handleCancel = (r: IncubationRun) => {
    const reason = prompt(`Причина отмены партии ${r.doc_number}?`);
    if (reason === null) return;
    cancelRun.mutate({ id: r.id, body: { reason } });
  };

  const handleSendToFeedlot = () => {
    if (!chickBatch) return;
    if (!window.confirm(
      `Отправить цыплят (партия ${chickBatch.doc_number}) в откорм?\n` +
      `Будет создан межмодульный трансфер incubation→feedlot.`,
    )) return;
    sendToFeedlot.mutate({ batchId: chickBatch.id }, {
      onError: (err) => alert('Не удалось: ' + err.message),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Инкубация</h1>
          <div className="sub">Партии яиц в шкафах · режим · овоскопия · вывод цыплят</div>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()} disabled={isFetching}>
            <Icon name="chart" size={14} /> {isFetching ? '…' : 'Обновить'}
          </button>
          {canEdit && (
            <>
              <OpexButton moduleCode="incubation" suggestedContraCode="20.03" />
              <OpenSaleFromModule moduleCode="incubation" />
              <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
                <Icon name="plus" size={14} /> Загрузить партию
              </button>
            </>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard tone="orange" iconName="incubator" label="Партий" sub="всего" value={String(runs?.length ?? 0)} />
        <KpiCard tone="blue" iconName="egg" label="В инкубации" sub="яиц" value={totals.loaded.toLocaleString('ru-RU')} />
        <KpiCard tone="red" iconName="egg" label="На выводе" sub="яиц" value={totals.onHatching.toLocaleString('ru-RU')} />
        <KpiCard tone="green" iconName="check" label="Выведено" sub="цыплят (итого)" value={totals.done.toLocaleString('ru-RU')} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: '', label: 'Все' },
            { value: 'incubating', label: 'Инкубация' },
            { value: 'hatching', label: 'Вывод' },
            { value: 'transferred', label: 'Передано' },
            { value: 'cancelled', label: 'Отменено' },
          ]}
          value={status}
          onChange={setStatus}
        />
      </div>

      <Panel flush>
        <DataTable<IncubationRun>
          isLoading={isLoading}
          rows={runs}
          rowKey={(r) => r.id}
          error={error}
          emptyMessage={
            <EmptyState
              icon="incubator"
              title="Партий инкубации пока нет"
              description="Инкубация — это процесс вывода цыплят из яиц маточника. Каждая партия проходит стадии: инкубатор → выводной шкаф → вывод цыплят."
              steps={[
                { label: 'Убедитесь, что в маточнике есть сформированная яичная партия' },
                { label: 'Нажмите «Загрузить партию» — выберите инкубатор и количество яиц' },
                { label: 'Отслеживайте режим температуры и влажности во вкладке «Режим»' },
                { label: 'На 18-й день переведите на вывод, на 21-й — проведите вывод цыплят' },
              ]}
              action={{
                label: 'Загрузить партию',
                onClick: () => setCreateOpen(true),
              }}
              hint="После вывода цыплята автоматически передаются в Фабрику откорма через межмодульный трансфер."
            />
          }
          onRowClick={(r) => { setSel(r); setTab('overview'); }}
          rowProps={(r) => ({ active: sel?.id === r.id })}
          columns={[
            { key: 'doc', label: 'Партия',
              render: (r) => <span className="badge id">{r.doc_number}</span> },
            { key: 'cabinet', label: 'Шкаф', mono: true, cellStyle: { fontSize: 12 },
              render: (r) => r.hatcher_block_code ?? r.incubator_block_code ?? '—' },
            { key: 'status', label: 'Статус',
              render: (r) => <Badge tone={STATUS_TONE[r.status]} dot>{STATUS_LABEL[r.status]}</Badge> },
            { key: 'loaded', label: 'Загружена', mono: true, cellStyle: { fontSize: 12 },
              render: (r) => r.loaded_date },
            { key: 'hatch', label: 'Вывод (план)', mono: true, cellStyle: { fontSize: 12 },
              render: (r) => r.actual_hatch_date ?? r.expected_hatch_date },
            { key: 'eggs', label: 'Яиц', align: 'right', mono: true,
              render: (r) => r.eggs_loaded.toLocaleString('ru-RU') },
            { key: 'hatched', label: 'Выведено', align: 'right', mono: true,
              render: (r) => (
                <span style={{ color: 'var(--success)' }}>
                  {r.hatched_count?.toLocaleString('ru-RU') ?? '—'}
                </span>
              ) },
            { key: 'hatchPct', label: 'Выводимость', align: 'right', mono: true,
              cellStyle: { fontSize: 12 },
              render: (r) => r.hatchability_pct ? `${parseFloat(r.hatchability_pct).toFixed(1)}%` : '—' },
            { key: 'day', label: 'День', align: 'right', mono: true,
              render: (r) => {
                const today = new Date().toISOString().slice(0, 10);
                const current = r.current_day ?? daysBetween(r.loaded_date, today);
                return `${current}/${r.days_total}`;
              } },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (r) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'На вывод',
                      hidden: r.status !== 'incubating',
                      onClick: () => setHatcherPick(r),
                    },
                    {
                      label: 'Провести вывод',
                      hidden: !(r.status === 'incubating' || r.status === 'hatching'),
                      onClick: () => setHatchFor(r),
                    },
                    {
                      label: 'Отменить партию',
                      danger: true,
                      hidden: !(r.status === 'incubating' || r.status === 'hatching'),
                      onClick: () => handleCancel(r),
                    },
                    {
                      label: 'Удалить',
                      danger: true,
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
          title={`Партия · ${sel.doc_number}`}
          subtitle={`${STATUS_LABEL[sel.status]} · ${sel.eggs_loaded.toLocaleString('ru-RU')} яиц`}
          onClose={() => setSel(null)}
          tabs={TABS.map((t) => ({ key: t.key, label: t.label }))}
          activeTab={tab}
          onTab={(k) => setTab(k as TabKey)}
          actions={
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setTimelineFor(sel)}
                title="История"
              >
                <Icon name="book" size={12} /> История
              </button>
              {canEdit && sel.status === 'incubating' && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setHatcherPick(sel)}
                >↗ На вывод</button>
              )}
              {canEdit && (sel.status === 'incubating' || sel.status === 'hatching') && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setHatchFor(sel)}
                >✓ Вывод</button>
              )}
              {canEdit && sel.status === 'transferred' && chickBatch && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleSendToFeedlot}
                  disabled={sendToFeedlot.isPending}
                  title={`Отправить ${chickBatch.doc_number} в откорм`}
                >
                  → В откорм
                </button>
              )}
            </>
          }
        >
          {tab === 'overview' && (
            <>
              <StatsPanel run={sel} />

              <Panel title="Параметры партии">
                <KV
                  items={[
                    { k: 'Документ', v: sel.doc_number, mono: true },
                    { k: 'Инкубатор', v: sel.incubator_block_code ?? '—', mono: true },
                    { k: 'Выводной шкаф', v: sel.hatcher_block_code ?? '—', mono: true },
                    { k: 'Партия яиц', v: sel.batch_doc ?? '—', mono: true },
                    { k: 'Загружена', v: sel.loaded_date, mono: true },
                    { k: 'Ожидаемый вывод', v: sel.expected_hatch_date, mono: true },
                    { k: 'Фактический вывод', v: sel.actual_hatch_date ?? '—', mono: true },
                    { k: 'Яиц загружено', v: sel.eggs_loaded.toLocaleString('ru-RU'), mono: true },
                    { k: 'Оплодотворено', v: sel.fertile_eggs?.toLocaleString('ru-RU') ?? '—', mono: true },
                    { k: 'Выведено', v: sel.hatched_count?.toLocaleString('ru-RU') ?? '—', mono: true },
                    { k: 'Отбраковано', v: sel.discarded_count?.toLocaleString('ru-RU') ?? '—', mono: true },
                    { k: 'Дней', v: `${sel.days_total}`, mono: true },
                    { k: 'Статус', v: <Badge tone={STATUS_TONE[sel.status]}>{STATUS_LABEL[sel.status]}</Badge> },
                  ]}
                />
              </Panel>

              {sel.status === 'transferred' && chickBatch && (
                <Panel title="Цыплята">
                  <div style={{ padding: 10, fontSize: 13 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span>Партия цыплят:</span>
                      <span className="mono" style={{ fontWeight: 600 }}>{chickBatch.doc_number}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span>Текущее количество:</span>
                      <span className="mono">
                        {parseFloat(chickBatch.current_quantity).toLocaleString('ru-RU')}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span>Текущий модуль:</span>
                      <span className="mono">
                        {chickBatch.current_module_code ?? chickBatch.origin_module_code ?? '—'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Накопл. себестоимость:</span>
                      <span className="mono">
                        {parseFloat(chickBatch.accumulated_cost_uzs ?? '0').toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум
                      </span>
                    </div>
                  </div>
                </Panel>
              )}
            </>
          )}

          {tab === 'regime' && <RegimePanel run={sel} />}
          {tab === 'mirage' && <MiragePanel run={sel} />}
        </DetailDrawer>
      )}

      {createOpen && <RunModal onClose={() => setCreateOpen(false)} />}
      {hatchFor && <HatchModal run={hatchFor} onClose={() => setHatchFor(null)} />}
      {timelineFor && (
        <IncubationTimelineModal
          run={timelineFor}
          onClose={() => setTimelineFor(null)}
        />
      )}
      {hatcherPick && (
        <HatcherPickModal
          run={hatcherPick}
          hatchers={hatchers ?? []}
          onClose={() => setHatcherPick(null)}
          onPick={(id) => handleTransfer(hatcherPick, id)}
        />
      )}
    </>
  );
}

function HatcherPickModal({
  run,
  hatchers,
  onClose,
  onPick,
}: {
  run: IncubationRun;
  hatchers: { id: string; code: string; name: string }[];
  onClose: () => void;
  onPick: (id: string) => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-hdr">
          <h3>Перевести {run.doc_number} на вывод</h3>
          <button className="close-btn" onClick={onClose}><Icon name="close" size={16} /></button>
        </div>
        <div className="modal-body">
          <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
            Выберите выводной шкаф:
          </div>
          {hatchers.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>
              Нет доступных выводных шкафов. Создайте блок с kind=hatcher.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {hatchers.map((h) => (
                <button
                  key={h.id}
                  className="btn btn-ghost"
                  style={{ justifyContent: 'flex-start' }}
                  onClick={() => onPick(h.id)}
                >
                  <span className="mono">{h.code}</span> · {h.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
