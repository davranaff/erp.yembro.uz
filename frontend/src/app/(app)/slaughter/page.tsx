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
import { useHasLevel } from '@/hooks/usePermissions';
import {
  qualityChecksCrud,
  shiftsCrud,
  useReverseShift,
  useSlaughterStats,
} from '@/hooks/useSlaughter';
import type {
  SlaughterShift,
  SlaughterStatus,
} from '@/types/auth';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';

import IncomingTransfersPanel from './IncomingTransfersPanel';
import LabTestsPanel from './LabTestsPanel';
import PostShiftModal from './PostShiftModal';
import QualityCheckModal from './QualityCheckModal';
import ShiftEditModal from './ShiftEditModal';
import ShiftModal from './ShiftModal';
import SlaughterTimelineModal from './SlaughterTimelineModal';
import YieldsPanel from './YieldsPanel';

const STATUS_LABEL: Record<SlaughterStatus, string> = {
  active: 'Активна',
  closed: 'Закрыта',
  posted: 'Проведена',
  cancelled: 'Отменена',
};

const STATUS_TONE: Record<SlaughterStatus, 'info' | 'warn' | 'success' | 'neutral'> = {
  active: 'info',
  closed: 'warn',
  posted: 'success',
  cancelled: 'neutral',
};

const TABS = [
  { key: 'overview', label: 'Обзор' },
  { key: 'yields', label: 'Выходы' },
  { key: 'quality', label: 'Качество' },
  { key: 'lab', label: 'Лаборатория' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

function fmtNum(v: string | number | null | undefined, digits = 0): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function fmtPct(v: string | null | undefined): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toFixed(1) + '%';
}

export default function SlaughterPage() {
  const [status, setStatus] = useState('');
  const [sel, setSel] = useState<SlaughterShift | null>(null);
  const [tab, setTab] = useState<TabKey>('overview');
  const [postFor, setPostFor] = useState<SlaughterShift | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [qcOpen, setQcOpen] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [editFor, setEditFor] = useState<SlaughterShift | null>(null);
  const [confirmDel, setConfirmDel] = useState<SlaughterShift | null>(null);
  const del = shiftsCrud.useDelete();

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('slaughter', 'rw');

  const { data: shifts, isLoading, error, refetch, isFetching } = shiftsCrud.useList(
    status ? { status } : {},
  );
  const { data: stats } = useSlaughterStats(sel?.id ?? null);
  const { data: qcList } = qualityChecksCrud.useList(
    sel ? { shift: sel.id } : {},
  );
  const qc = qcList && qcList.length > 0 ? qcList[0] : null;

  const update = shiftsCrud.useUpdate();
  const reverse = useReverseShift();

  // Auto-refresh sel из свежего списка shifts.
  // Иначе drawer показывает stale snapshot после CRUD (yields, qc, lab tests
  // меняют KPI на shift, но sel хранит старые значения).
  useEffect(() => {
    if (!sel || !shifts) return;
    const fresh = shifts.find((s) => s.id === sel.id);
    if (fresh && fresh !== sel) setSel(fresh);
  }, [shifts, sel]);

  const totals = useMemo(() => {
    if (!shifts) return { count: 0, heads: 0, kg: 0, posted: 0 };
    const heads = shifts.reduce((a, s) => a + s.live_heads_received, 0);
    const kg = shifts.reduce(
      (a, s) => a + parseFloat(s.live_weight_kg_total || '0'),
      0,
    );
    const posted = shifts.filter((s) => s.status === 'posted').length;
    return { count: shifts.length, heads, kg, posted };
  }, [shifts]);

  const avgYieldPct = useMemo(() => {
    if (!shifts || shifts.length === 0) return null;
    const valid = shifts
      .map((s) => parseFloat(s.carcass_yield_pct ?? ''))
      .filter((n) => !Number.isNaN(n) && n > 0);
    if (valid.length === 0) return null;
    return valid.reduce((a, b) => a + b, 0) / valid.length;
  }, [shifts]);

  const handleClose = (s: SlaughterShift) => {
    if (!window.confirm(`Закрыть смену ${s.doc_number} (ACTIVE → CLOSED)?`)) return;
    update.mutate(
      { id: s.id, patch: { status: 'closed' } as Partial<SlaughterShift> },
      { onError: (err) => alert(`Не удалось: ${err.message}`) },
    );
  };

  const handleReverse = (s: SlaughterShift) => {
    const reason = prompt(`Причина реверса смены ${s.doc_number}?`);
    if (reason === null) return;
    reverse.mutate(
      { id: s.id, body: { reason } },
      { onError: (err) => alert(`Не удалось: ${err.message}`) },
    );
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Убойня</h1>
          <div className="sub">
            Смены разделки · выход по номенклатуре · качество · FCR{' '}
            <HelpHint text="Норма выхода тушки бройлера: 70-75% от живого веса. Дефекты: до 1.5%." />
          </div>
        </div>
        <div className="actions">
          <button className="btn btn-secondary btn-sm" onClick={() => refetch()} disabled={isFetching}>
            <Icon name="chart" size={14} /> {isFetching ? '…' : 'Обновить'}
          </button>
          {canEdit && (
            <>
              <OpexButton moduleCode="slaughter" suggestedContraCode="20.04" />
              <OpenSaleFromModule moduleCode="slaughter" />
              <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
                <Icon name="plus" size={14} /> Новая смена
              </button>
            </>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard
          tone="orange"
          iconName="building"
          label="Смен"
          sub={`проведено ${totals.posted}`}
          value={String(totals.count)}
        />
        <KpiCard
          tone="blue"
          iconName="users"
          label="Голов (всего)"
          sub="по фильтру"
          value={totals.heads.toLocaleString('ru-RU')}
        />
        <KpiCard
          tone="green"
          iconName="chart"
          label="Живой вес, кг"
          sub="по фильтру"
          value={totals.kg.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}
        />
        <KpiCard
          tone="orange"
          iconName="chart"
          label="Средний выход"
          sub="тушка / живой вес"
          value={avgYieldPct != null ? avgYieldPct.toFixed(1) + '%' : '—'}
        />
      </div>

      <IncomingTransfersPanel />

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: '', label: 'Все' },
            { value: 'active', label: 'Активные' },
            { value: 'closed', label: 'Закрыты' },
            { value: 'posted', label: 'Проведены' },
            { value: 'cancelled', label: 'Отменены' },
          ]}
          value={status}
          onChange={setStatus}
        />
      </div>

      <Panel flush>
        <DataTable<SlaughterShift>
          isLoading={isLoading}
          rows={shifts}
          rowKey={(s) => s.id}
          error={error}
          emptyMessage={
            <EmptyState
              icon="box"
              title="Смен убоя пока нет"
              description="Убойня — это модуль учёта переработки птицы. Каждая смена фиксирует забой партии с выходами продуктов, контролем качества и лабораторией."
              steps={[
                { label: 'Убедитесь, что в «Фабрике откорма» есть партия со статусом «К съёму»' },
                { label: 'Нажмите «+ Новая смена» — выберите линию, дату и откормочную партию' },
                { label: 'Заполните выходы продукции (тушки, субпродукты, отходы) во вкладке «Выходы»' },
                { label: 'Проведите смену — она зафиксирует себестоимость и остатки на складе' },
              ]}
              action={{
                label: 'Новая смена',
                onClick: () => setCreateOpen(true),
              }}
              hint="Только проведённые смены влияют на складские остатки и себестоимость продукции."
            />
          }
          onRowClick={(s) => { setSel(s); setTab('overview'); }}
          rowProps={(s) => ({ active: sel?.id === s.id })}
          columns={[
            { key: 'doc', label: 'Смена',
              render: (s) => <span className="badge id">{s.doc_number}</span> },
            { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
              render: (s) => s.shift_date },
            { key: 'line', label: 'Линия', mono: true, cellStyle: { fontSize: 12 },
              render: (s) => s.line_code ?? '—' },
            { key: 'batch', label: 'Партия', mono: true, cellStyle: { fontSize: 12 },
              render: (s) => s.batch_doc ?? '—' },
            { key: 'heads', label: 'Голов', align: 'right', mono: true,
              render: (s) => s.live_heads_received.toLocaleString('ru-RU') },
            { key: 'live', label: 'Живой, кг', align: 'right', mono: true,
              render: (s) => fmtNum(s.live_weight_kg_total, 0) },
            { key: 'out', label: 'Выход, кг', align: 'right', mono: true,
              render: (s) => fmtNum(s.total_output_kg, 0) },
            { key: 'yield', label: 'Выход %', align: 'right', mono: true,
              cellStyle: { fontWeight: 600 },
              render: (s) => fmtPct(s.carcass_yield_pct) },
            { key: 'status', label: 'Статус',
              render: (s) => (
                <Badge tone={STATUS_TONE[s.status]} dot>{STATUS_LABEL[s.status]}</Badge>
              ) },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (s) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'Редактировать',
                      hidden: s.status === 'posted' || s.status === 'cancelled',
                      onClick: () => setEditFor(s),
                    },
                    {
                      label: 'Закрыть смену',
                      hidden: s.status !== 'active',
                      disabled: update.isPending,
                      onClick: () => handleClose(s),
                    },
                    {
                      label: 'Провести смену',
                      hidden: !(s.status === 'active' || s.status === 'closed'),
                      onClick: () => setPostFor(s),
                    },
                    {
                      label: 'Удалить',
                      danger: true,
                      hidden: s.status === 'posted' || s.status === 'cancelled',
                      disabled: del.isPending,
                      onClick: () => setConfirmDel(s),
                    },
                    {
                      label: 'Реверс',
                      danger: true,
                      hidden: s.status !== 'posted',
                      disabled: reverse.isPending,
                      onClick: () => handleReverse(s),
                    },
                  ]}
                />
              ) : null },
          ]}
        />
      </Panel>

      {sel && (
        <DetailDrawer
          title={`Смена · ${sel.doc_number}`}
          subtitle={`${sel.shift_date} · ${STATUS_LABEL[sel.status]}`}
          onClose={() => setSel(null)}
          tabs={TABS.map((t) => ({
            ...t,
            count:
              t.key === 'yields' ? sel.yields_count :
              t.key === 'lab' ? (sel.lab_pending_count + sel.lab_passed_count + sel.lab_failed_count) :
              undefined,
          }))}
          activeTab={tab}
          onTab={(k) => setTab(k as TabKey)}
          actions={
            <>
              <button className="btn btn-ghost btn-sm" onClick={() => setTimelineOpen(true)}>
                <Icon name="chart" size={12} /> История
              </button>
              {canEdit && sel.status === 'active' && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleClose(sel)}
                  disabled={update.isPending}
                >
                  Закрыть смену
                </button>
              )}
              {canEdit && (sel.status === 'active' || sel.status === 'closed') && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setPostFor(sel)}
                >
                  Провести
                </button>
              )}
              {sel.status === 'posted' && (
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => handleReverse(sel)}
                  disabled={reverse.isPending}
                >
                  Реверс
                </button>
              )}
            </>
          }
        >
          {tab === 'overview' && (
            <>
              <div className="kpi-row" style={{ marginBottom: 12 }}>
                <KpiCard
                  tone="blue"
                  iconName="users"
                  label="Голов"
                  sub="принято на смену"
                  value={sel.live_heads_received.toLocaleString('ru-RU')}
                />
                <KpiCard
                  tone="green"
                  iconName="chart"
                  label="Живой вес"
                  sub="кг"
                  value={fmtNum(sel.live_weight_kg_total, 1)}
                />
                <KpiCard
                  tone="orange"
                  iconName="bag"
                  label="Выход всего"
                  sub={
                    sel.total_output_pct
                      ? `${fmtPct(sel.total_output_pct)} от живого`
                      : 'кг готовой продукции'
                  }
                  value={fmtNum(sel.total_output_kg, 1) + ' кг'}
                />
                <KpiCard
                  tone="red"
                  iconName="close"
                  label="Отходы"
                  sub={
                    sel.waste_kg
                      ? `${fmtNum(sel.waste_kg, 1)} кг`
                      : 'не считано'
                  }
                  value={fmtPct(sel.waste_pct)}
                />
                <KpiCard
                  tone="green"
                  iconName="check"
                  label="На голову"
                  sub="кг готового / голову"
                  value={
                    sel.yield_per_head_kg
                      ? fmtNum(sel.yield_per_head_kg, 3) + ' кг'
                      : '—'
                  }
                />
              </div>

              {stats && stats.breakdown.length > 0 && (
                <div style={{
                  background: 'var(--bg-card, #fff)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: 12,
                  marginBottom: 12,
                }}>
                  <div style={{
                    fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
                    textTransform: 'uppercase', letterSpacing: '.04em',
                    marginBottom: 8,
                  }}>
                    Разбивка по SKU · факт vs норма (бройлер)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {stats.breakdown.map((row) => {
                      const yp = row.yield_pct ? parseFloat(row.yield_pct) : 0;
                      const norm = row.norm_pct ? parseFloat(row.norm_pct) : null;
                      const dev = row.deviation_pct ? parseFloat(row.deviation_pct) : null;
                      const barPct = Math.min(100, Math.max(0, yp));
                      const barColor = !row.is_within_tolerance
                        ? 'var(--danger)'
                        : 'var(--brand-orange, #E8751A)';
                      return (
                        <div key={row.sku} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                          <div style={{ minWidth: 130, fontWeight: 500 }}>
                            <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                              {row.sku}
                            </span>{' '}
                            {row.name}
                          </div>
                          <div style={{
                            flex: 1, height: 12, background: 'var(--bg-soft)',
                            borderRadius: 3, overflow: 'hidden', position: 'relative',
                          }}>
                            <div style={{
                              width: `${barPct}%`, height: '100%',
                              background: barColor, transition: 'width .2s',
                            }} />
                            {norm !== null && (
                              <div style={{
                                position: 'absolute', top: 0, bottom: 0,
                                left: `${norm}%`, width: 1,
                                background: 'var(--fg-3)', opacity: 0.7,
                              }} title={`Норма ${norm}%`} />
                            )}
                          </div>
                          <div className="mono" style={{ minWidth: 60, textAlign: 'right', fontWeight: 600 }}>
                            {yp.toFixed(2)}%
                          </div>
                          <div className="mono" style={{
                            minWidth: 70, textAlign: 'right',
                            color: dev === null ? 'var(--fg-3)'
                              : !row.is_within_tolerance ? 'var(--danger)'
                              : 'var(--fg-3)',
                            fontSize: 11,
                          }}>
                            {dev !== null
                              ? `${dev > 0 ? '+' : ''}${dev.toFixed(2)}%`
                              : '— нет нормы'}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div style={{
                    marginTop: 10, paddingTop: 8,
                    borderTop: '1px solid var(--border)',
                    display: 'flex', justifyContent: 'space-between',
                    fontSize: 12, fontWeight: 600,
                  }}>
                    <span>Σ выходов / Отходы</span>
                    <span className="mono">
                      {fmtPct(stats.total_output_pct)} / {' '}
                      <span style={{ color: 'var(--danger)' }}>
                        {fmtPct(stats.waste_pct)}
                      </span>
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
                    Серая чёрточка на полосе — норма по бройлеру (ROSS-308 / COBB-500). Допуск ±2%.
                  </div>
                </div>
              )}
              <KV
                items={[
                  { k: 'Документ', v: sel.doc_number, mono: true },
                  { k: 'Дата', v: sel.shift_date, mono: true },
                  { k: 'Линия', v: sel.line_code ?? '—', mono: true },
                  { k: 'Партия источник', v: sel.batch_doc ?? '—', mono: true },
                  { k: 'Начало', v: sel.start_time?.slice(0, 16).replace('T', ' ') ?? '—', mono: true },
                  { k: 'Конец', v: sel.end_time?.slice(0, 16).replace('T', ' ') ?? '—', mono: true },
                  { k: 'Голов принято', v: sel.live_heads_received.toLocaleString('ru-RU'), mono: true },
                  { k: 'Живой вес, кг', v: fmtNum(sel.live_weight_kg_total, 3), mono: true },
                  {
                    k: 'Вет. инспекция',
                    v: sel.quality_checked
                      ? <Badge tone="success" dot>Пройдена</Badge>
                      : <Badge tone="warn" dot>Требуется</Badge>,
                  },
                  {
                    k: 'Лаб. тесты',
                    v: `✓ ${sel.lab_passed_count} · ⌛ ${sel.lab_pending_count} · ✗ ${sel.lab_failed_count}`,
                  },
                  { k: 'Статус', v: <Badge tone={STATUS_TONE[sel.status]}>{STATUS_LABEL[sel.status]}</Badge> },
                  { k: 'Заметка', v: sel.notes || '—' },
                ]}
              />
            </>
          )}

          {tab === 'yields' && <YieldsPanel shift={sel} />}

          {tab === 'quality' && (
            <Panel
              title="Контроль качества"
              tools={
                canEdit && (sel.status === 'active' || sel.status === 'closed') ? (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setQcOpen(true)}
                  >
                    <Icon name="plus" size={12} />{' '}
                    {qc ? 'Изменить' : 'Заполнить'}
                  </button>
                ) : null
              }
              flush
            >
              {qc ? (
                <KV
                  items={[
                    {
                      k: 'Вет. инспекция',
                      v: qc.vet_inspection_passed
                        ? <Badge tone="success" dot>Пройдена</Badge>
                        : <Badge tone="danger" dot>Не пройдена</Badge>,
                    },
                    { k: 'Дефект тушки, %', v: qc.carcass_defect_percent ?? '—', mono: true },
                    { k: 'Травмы, %', v: qc.trauma_percent ?? '—', mono: true },
                    { k: 'Темп. охлажд., °C', v: qc.cooling_temperature_c ?? '—', mono: true },
                    { k: 'Инспектор', v: qc.inspector_name ?? '—' },
                    { k: 'Когда', v: qc.inspected_at.slice(0, 16).replace('T', ' '), mono: true },
                    { k: 'Заметка', v: qc.notes || '—' },
                  ]}
                />
              ) : (
                <EmptyState
                  icon="check"
                  title="Контроль качества не заполнен"
                  description="Контроль качества фиксирует прохождение ветеринарной инспекции, дефекты тушек и температуру охлаждения. Без этой отметки провести смену невозможно."
                  steps={[
                    { label: 'Нажмите «Заполнить» в верхней части панели' },
                    { label: 'Укажите результат вет. инспекции и параметры качества' },
                    { label: 'После заполнения смену можно будет провести' },
                  ]}
                  action={canEdit && (sel.status === 'active' || sel.status === 'closed') ? {
                    label: 'Заполнить контроль',
                    onClick: () => setQcOpen(true),
                  } : undefined}
                  hint="Без отметки ветеринара провести смену невозможно."
                />
              )}
            </Panel>
          )}

          {tab === 'lab' && <LabTestsPanel shift={sel} />}
        </DetailDrawer>
      )}

      {postFor && <PostShiftModal shift={postFor} onClose={() => setPostFor(null)} />}
      {createOpen && <ShiftModal onClose={() => setCreateOpen(false)} />}
      {editFor && (
        <ShiftEditModal shift={editFor} onClose={() => setEditFor(null)} />
      )}
      {confirmDel && (
        <ConfirmDeleteWithReason
          title="Удалить смену?"
          subject={`${confirmDel.doc_number} · ${confirmDel.shift_date}`}
          isPending={del.isPending}
          onConfirm={async (reason) => {
            await del.mutateAsync({ id: confirmDel.id, reason });
            setConfirmDel(null);
            if (sel?.id === confirmDel.id) setSel(null);
          }}
          onClose={() => setConfirmDel(null)}
        />
      )}
      {qcOpen && sel && (
        <QualityCheckModal
          shift={sel}
          qc={qc}
          onClose={() => setQcOpen(false)}
        />
      )}
      {timelineOpen && sel && (
        <SlaughterTimelineModal
          shift={sel}
          onClose={() => setTimelineOpen(false)}
        />
      )}
    </>
  );
}
