'use client';

import { useEffect, useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import OpexButton from '@/components/OpexButton';
import { OpenSaleFromModule } from '@/components/SellBatchButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import HelpHint from '@/components/ui/HelpHint';
import Icon from '@/components/ui/Icon';
import EmptyState from '@/components/ui/EmptyState';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import {
  feedlotCrud,
  feedlotMortalityCrud,
  useFeedlotStats,
} from '@/hooks/useFeedlot';
import { useHasLevel } from '@/hooks/usePermissions';
import type { FeedlotBatch, FeedlotMortality, FeedlotStatus } from '@/types/auth';
import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';

import FeedConsumptionPanel from './FeedConsumptionPanel';
import FeedlotActionsModal from './FeedlotActionsModal';
import FeedlotTimelineModal from './FeedlotTimelineModal';
import PlaceModal from './PlaceModal';
import WeighingsPanel from './WeighingsPanel';

const STATUS_LABEL: Record<FeedlotStatus, string> = {
  placed: 'Посажено',
  growing: 'Откорм',
  ready_slaughter: 'К съёму',
  shipped: 'Передано',
};

const STATUS_TONE: Record<FeedlotStatus, 'info' | 'success' | 'warn' | 'neutral'> = {
  placed: 'info',
  growing: 'success',
  ready_slaughter: 'warn',
  shipped: 'neutral',
};

const TABS = [
  { key: 'overview', label: 'Обзор' },
  { key: 'weighings', label: 'Взвешивания' },
  { key: 'feed', label: 'Кормление' },
  { key: 'mortality', label: 'Падёж' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

function daysBetween(fromISO: string): number {
  const start = new Date(fromISO).getTime();
  return Math.max(0, Math.floor((Date.now() - start) / 86400000));
}

function fmtNum(v: string | number | null | undefined, digits = 0): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function fmtFcr(v: string | null | undefined): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toFixed(2);
}

export default function FeedlotPage() {
  const [status, setStatus] = useState('');
  const [sel, setSel] = useState<FeedlotBatch | null>(null);
  const [tab, setTab] = useState<TabKey>('overview');
  const [mode, setMode] = useState<'ship' | 'mortality' | null>(null);
  const delMortality = feedlotMortalityCrud.useDelete();
  const [confirmDelMortality, setConfirmDelMortality] = useState<FeedlotMortality | null>(null);
  const [placeOpen, setPlaceOpen] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(false);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('feedlot', 'rw');

  const { data: batches, isLoading, error, refetch, isFetching } = feedlotCrud.useList(
    status ? { status } : {},
  );
  const { data: mortality } = feedlotMortalityCrud.useList(
    sel ? { feedlot_batch: sel.id } : {},
  );
  const { data: stats } = useFeedlotStats(sel?.id);

  // Auto-refresh sel из свежего списка batches.
  // Иначе drawer показывает stale snapshot после CRUD (взвешивания, кормление,
  // падёж меняют KPI на batch, но sel хранит старые значения).
  useEffect(() => {
    if (!sel || !batches) return;
    const fresh = batches.find((b) => b.id === sel.id);
    if (fresh && fresh !== sel) setSel(fresh);
  }, [batches, sel]);

  const totals = useMemo(() => {
    if (!batches) return { count: 0, heads: 0, growing: 0, ready: 0 };
    let heads = 0, growing = 0, ready = 0;
    for (const b of batches) {
      heads += b.current_heads;
      if (b.status === 'growing') growing += 1;
      if (b.status === 'ready_slaughter') ready += 1;
    }
    return { count: batches.length, heads, growing, ready };
  }, [batches]);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Фабрика откорма</h1>
          <div className="sub">
            Партии бройлера · взвешивания · кормление · FCR · падёж · отгрузки
          </div>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()} disabled={isFetching}>
            <Icon name="chart" size={14} /> {isFetching ? '…' : 'Обновить'}
          </button>
          {canEdit && (
            <>
              <OpexButton moduleCode="feedlot" suggestedContraCode="20.02" />
              <OpenSaleFromModule moduleCode="feedlot" />
              <button className="btn btn-primary btn-sm" onClick={() => setPlaceOpen(true)}>
                <Icon name="plus" size={14} /> Разместить партию
              </button>
            </>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard
          tone="orange"
          iconName="factory"
          label="Партий"
          sub={`в работе ${totals.growing}`}
          value={String(totals.count)}
        />
        <KpiCard
          tone="blue"
          iconName="users"
          label="Поголовье"
          sub="всего на откорме"
          value={totals.heads.toLocaleString('ru-RU')}
        />
        <KpiCard
          tone="orange"
          iconName="check"
          label="К съёму"
          sub="готовы к отгрузке"
          value={String(totals.ready)}
        />
        <KpiCard
          tone="green"
          iconName="bag"
          label="Падежей"
          sub={sel ? sel.doc_number : 'выберите партию'}
          value={String(mortality?.length ?? 0)}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: '', label: 'Все' },
            { value: 'placed', label: 'Посажено' },
            { value: 'growing', label: 'Откорм' },
            { value: 'ready_slaughter', label: 'К съёму' },
            { value: 'shipped', label: 'Переданы' },
          ]}
          value={status}
          onChange={setStatus}
        />
      </div>

      <Panel flush>
        <DataTable<FeedlotBatch>
          isLoading={isLoading}
          rows={batches}
          rowKey={(b) => b.id}
          error={error}
          emptyMessage={
            <EmptyState
              icon="factory"
              title="Партий на откорме пока нет"
              description="Фабрика откорма — это финальная стадия выращивания бройлеров. Цыплята поступают из инкубации и растут до убойного веса."
              steps={[
                { label: 'В модуле «Инкубация» проведите вывод цыплят' },
                { label: 'Нажмите «→ В откорм» на карточке выведенной партии' },
                { label: 'Откормочная партия появится здесь — ведите взвешивания и кормление' },
                { label: 'Когда птица готова — нажмите «Отправить на убой»' },
              ]}
              hint="Партия создаётся автоматически из инкубации через межмодульный трансфер — вручную не создаётся."
            />
          }
          onRowClick={(b) => { setSel(b); setTab('overview'); }}
          rowProps={(b) => ({ active: sel?.id === b.id })}
          columns={[
            { key: 'doc', label: 'Партия',
              render: (b) => <span className="badge id">{b.doc_number}</span> },
            { key: 'house', label: 'Птичник', mono: true, cellStyle: { fontSize: 12 },
              render: (b) => b.house_code ?? '—' },
            { key: 'day', label: 'День', align: 'right', mono: true,
              render: (b) => b.days_on_feedlot ?? daysBetween(b.placed_date) },
            { key: 'heads', label: 'Голов', align: 'right', mono: true,
              render: (b) => (
                <>
                  {b.current_heads.toLocaleString('ru-RU')}
                  <span style={{ fontSize: 10, color: 'var(--fg-3)', marginLeft: 4 }}>
                    /{b.initial_heads.toLocaleString('ru-RU')}
                  </span>
                </>
              ) },
            { key: 'survival', label: 'Выжив.', align: 'right', mono: true,
              cellStyle: { fontSize: 12 },
              render: (b) => b.survival_pct ? parseFloat(b.survival_pct).toFixed(1) + '%' : '—' },
            { key: 'avg_weight', label: 'Ср. вес', align: 'right', mono: true,
              cellStyle: { fontSize: 12 },
              render: (b) => b.current_avg_weight_kg
                ? parseFloat(b.current_avg_weight_kg).toFixed(2) + ' кг'
                : '—' },
            { key: 'fcr', label: 'FCR', align: 'right', mono: true,
              cellStyle: { fontWeight: 600, color: 'var(--brand-orange)' },
              render: (b) => fmtFcr(b.total_fcr) },
            { key: 'status', label: 'Статус',
              render: (b) => <Badge tone={STATUS_TONE[b.status]} dot>{STATUS_LABEL[b.status]}</Badge> },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (b) => {
                if (!canEdit) return null;
                const canAct = b.status === 'growing' || b.status === 'placed' || b.status === 'ready_slaughter';
                return (
                  <RowActions
                    actions={[
                      {
                        label: 'Отгрузка на убой',
                        hidden: !canAct,
                        onClick: () => { setSel(b); setMode('ship'); },
                      },
                      {
                        label: 'Падёж',
                        danger: true,
                        hidden: !canAct,
                        onClick: () => { setSel(b); setMode('mortality'); },
                      },
                    ]}
                  />
                );
              } },
          ]}
        />
      </Panel>

      {sel && (
        <DetailDrawer
          title={`Партия · ${sel.doc_number}`}
          subtitle={`${STATUS_LABEL[sel.status]} · день ${stats?.days_on_feedlot ?? daysBetween(sel.placed_date)}`}
          onClose={() => { setSel(null); setTab('overview'); }}
          tabs={TABS.map((t) => ({ key: t.key, label: t.label }))}
          activeTab={tab}
          onTab={(k) => setTab(k as TabKey)}
          actions={
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setTimelineOpen(true)}
                title="История"
              >
                <Icon name="book" size={12} /> История
              </button>
              {canEdit && (sel.status === 'placed' || sel.status === 'growing'
                || sel.status === 'ready_slaughter') && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setMode('mortality')}
                >
                  <Icon name="close" size={12} /> Падёж
                </button>
              )}
              {canEdit && (sel.status === 'placed' || sel.status === 'growing'
                || sel.status === 'ready_slaughter') && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setMode('ship')}
                >
                  Отгрузка
                </button>
              )}
            </>
          }
        >
          {tab === 'overview' && (
            <>
              {/* KPI Grid 5 — день, поголовье, ср. вес, FCR, корм */}
              <div
                className="grid-5"
                style={{ marginBottom: 12 }}
              >
                <KpiCard
                  tone="orange"
                  iconName="incubator"
                  label="День откорма"
                  sub={
                    sel.target_slaughter_date
                      ? `цель ${sel.target_slaughter_date}`
                      : '—'
                  }
                  value={String(stats?.days_on_feedlot ?? daysBetween(sel.placed_date))}
                />
                <KpiCard
                  tone="blue"
                  iconName="users"
                  label="Поголовье"
                  sub={
                    stats?.survival_pct
                      ? `выжило ${parseFloat(stats.survival_pct).toFixed(1)}%`
                      : 'выжив. —'
                  }
                  value={`${sel.current_heads}/${sel.initial_heads}`}
                />
                <KpiCard
                  tone="green"
                  iconName="chart"
                  label="Средний вес"
                  sub={`цель ${sel.target_weight_kg} кг`}
                  value={
                    stats?.current_avg_weight_kg
                      ? `${parseFloat(stats.current_avg_weight_kg).toFixed(2)} кг`
                      : '—'
                  }
                />
                <KpiCard
                  tone="orange"
                  iconName="chart"
                  label="FCR"
                  sub="корм/прирост"
                  value={fmtFcr(stats?.total_fcr ?? null)}
                />
                <KpiCard
                  tone="green"
                  iconName="bag"
                  label="Корма"
                  sub="всего скормлено"
                  value={
                    stats?.total_feed_kg
                      ? fmtNum(stats.total_feed_kg, 0) + ' кг'
                      : '—'
                  }
                />
              </div>

              <Panel
                title={
                  <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                    Параметры партии
                    <HelpHint
                      text="Ключевые показатели и состояние."
                      details={
                        'FCR (food conversion ratio) — главный KPI откорма. '
                        + '1.6–1.8 = отличный показатель для бройлера, >2.0 = надо разбираться.\n\n'
                        + 'Выживаемость: норма 95%+ для бройлера.\n\n'
                        + 'Целевой вес 2.5 кг достигается за ~42 дня.'
                      }
                    />
                  </span> as unknown as string
                }
              >
                <KV
                  items={[
                    { k: 'Документ', v: sel.doc_number, mono: true },
                    { k: 'Птичник', v: sel.house_code ?? '—', mono: true },
                    { k: 'Посажено', v: sel.placed_date, mono: true },
                    {
                      k: 'Целевой съём',
                      v: stats?.projected_slaughter_date
                        ? `${sel.target_slaughter_date ?? '—'} (прогноз: ${stats.projected_slaughter_date})`
                        : (sel.target_slaughter_date ?? '—'),
                      mono: true,
                    },
                    { k: 'Целевой вес', v: `${sel.target_weight_kg} кг`, mono: true },
                    {
                      k: 'Поголовье',
                      v: `${sel.current_heads.toLocaleString('ru-RU')} из ${sel.initial_heads.toLocaleString('ru-RU')}`,
                      mono: true,
                    },
                    {
                      k: 'Падёж',
                      v: stats
                        ? `${stats.dead_count} гол (${parseFloat(stats.total_mortality_pct).toFixed(2)}%)`
                        : '—',
                      mono: true,
                    },
                    {
                      k: 'Прирост массы',
                      v: stats?.total_gain_kg
                        ? `${fmtNum(stats.total_gain_kg, 0)} кг`
                        : '—',
                      mono: true,
                    },
                    { k: 'Статус', v: <Badge tone={STATUS_TONE[sel.status]}>{STATUS_LABEL[sel.status]}</Badge> },
                    ...(sel.notes ? [{ k: 'Заметка', v: sel.notes }] : []),
                  ]}
                />
              </Panel>
            </>
          )}

          {tab === 'weighings' && <WeighingsPanel batch={sel} />}
          {tab === 'feed' && <FeedConsumptionPanel batch={sel} />}
          {tab === 'mortality' && (
            <Panel
              title={`Падёж (${mortality?.length ?? 0})`}
              tools={
                canEdit && (sel.status === 'placed' || sel.status === 'growing'
                  || sel.status === 'ready_slaughter') ? (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setMode('mortality')}
                  >
                    <Icon name="plus" size={12} /> Записать падёж
                  </button>
                ) : null
              }
              flush
            >
              <DataTable
                rows={mortality ?? []}
                rowKey={(m) => m.id}
                emptyMessage={
                  <EmptyState
                    icon="close"
                    title="Падежа не зафиксировано"
                    description="Записывайте каждый случай гибели птицы с указанием причины — это необходимо для ветеринарного контроля и точного расчёта живого веса партии."
                    steps={[
                      { label: 'Нажмите «+ Записать падёж» в верхней части панели' },
                      { label: 'Укажите дату, день откорма и количество павших голов' },
                      { label: 'По возможности укажите причину (болезнь, травма, прочее)' },
                    ]}
                    hint="Падёж автоматически уменьшает текущее поголовье партии и учитывается при расчёте FCR."
                  />
                }
                columns={[
                  { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
                    render: (m) => m.date },
                  { key: 'day', label: 'День', align: 'right', mono: true,
                    render: (m) => m.day_of_age },
                  { key: 'dead', label: 'Пало', align: 'right', mono: true,
                    cellStyle: { fontWeight: 600 },
                    render: (m) => <span style={{ color: 'var(--danger)' }}>−{m.dead_count}</span> },
                  { key: 'cause', label: 'Причина', cellStyle: { fontSize: 12 },
                    render: (m) => m.cause || '—' },
                  { key: 'notes', label: 'Заметка', cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                    render: (m) => m.notes || '—' },
                  { key: 'actions', label: '', width: 60, align: 'right',
                    render: (m) => canEdit ? (
                      <RowActions
                        actions={[
                          {
                            label: 'Удалить',
                            danger: true,
                            hidden: sel.status === 'shipped',
                            disabled: delMortality.isPending,
                            onClick: () => setConfirmDelMortality(m),
                          },
                        ]}
                      />
                    ) : null },
                ]}
              />
              <div style={{ padding: 8, fontSize: 11, color: 'var(--fg-3)' }}>
                Списание идёт автоматически: уменьшается поголовье, накопленная стоимость
                на партии, создаётся проводка Дт 91.02 / Кт 20.02 на убыток.
              </div>
            </Panel>
          )}
        </DetailDrawer>
      )}

      {sel && mode && (
        <FeedlotActionsModal batch={sel} mode={mode} onClose={() => setMode(null)} />
      )}
      {sel && timelineOpen && (
        <FeedlotTimelineModal batch={sel} onClose={() => setTimelineOpen(false)} />
      )}
      {placeOpen && <PlaceModal onClose={() => setPlaceOpen(false)} />}
      {confirmDelMortality && (
        <ConfirmDeleteWithReason
          title="Удалить запись падежа?"
          subject={`день ${confirmDelMortality.day_of_age} · −${confirmDelMortality.dead_count} гол`}
          isPending={delMortality.isPending}
          onConfirm={async (reason) => {
            await delMortality.mutateAsync({ id: confirmDelMortality.id, reason });
            setConfirmDelMortality(null);
          }}
          onClose={() => setConfirmDelMortality(null)}
        />
      )}
    </>
  );
}
