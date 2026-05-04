'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useBatches, useBatchCostEntries, useBatchTrace } from '@/hooks/useBatches';
import type {
  Batch,
  BatchChainStep,
  BatchCostBreakdownItem,
  BatchCostEntry,
} from '@/types/auth';

import CostTrendChart from './CostTrendChart';
import {
  BATCH_COST_CATEGORY_LABEL,
  BATCH_COST_CATEGORY_TONE,
  BATCH_STATE_LABEL,
  BATCH_STATE_TONE,
  moduleLabel,
} from './labels';

function fmtUzs(v: string | null | undefined, short = false): string {
  if (v == null) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  if (short && Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'М';
  if (short && Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'К';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function fmtQty(v: string | null | undefined, unit?: string | null): string {
  if (v == null) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU') + (unit ? ` ${unit}` : '');
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  });
}

function daysBetween(from: string | null | undefined, to: string | null): number | null {
  if (!from) return null;
  const a = new Date(from).getTime();
  const b = to ? new Date(to).getTime() : Date.now();
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.floor((b - a) / 86400000);
}

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows
    .map((r) =>
      r
        .map((cell) => {
          const s = cell ?? '';
          // Эскейп по правилам RFC 4180: оборачиваем в кавычки если есть , " \n
          if (/[,"\n]/.test(s)) {
            return '"' + s.replace(/"/g, '""') + '"';
          }
          return s;
        })
        .join(','),
    )
    .join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

export default function TraceabilityPage() {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Batch | null>(null);

  const { data: batches, isLoading: batchesLoading } = useBatches(
    search ? { search } : {},
  );

  const { data: trace, isLoading: traceLoading } = useBatchTrace(selected?.id);
  const { data: costEntries } = useBatchCostEntries(selected?.id);

  const list = batches ?? [];
  const effectiveSelected = selected ?? (list.length > 0 ? list[0] : null);

  // KPI блок
  const kpi = useMemo(() => {
    if (!trace) return null;
    const steps = trace.chain_steps;
    const first = steps[0];
    const last = steps[steps.length - 1];
    const startDate = first?.entered_at ?? trace.batch.started_at;
    const endDate = last?.exited_at ?? trace.batch.completed_at ?? null;
    const days = daysBetween(startDate, endDate);
    const transferCount = steps.filter((s) => s.transfer_in_doc).length;

    // Yield = current / initial — для активных партий показывает «осталось»,
    // для completed — финальный выход.
    const initial = parseFloat(trace.batch.initial_quantity || '0') || 0;
    const current = parseFloat(trace.batch.current_quantity || '0') || 0;
    const yieldPct = initial > 0 ? (current / initial) * 100 : null;
    const lossPct = initial > 0 ? Math.max(0, 100 - (current / initial) * 100) : null;

    return {
      stepsCount: steps.length,
      days,
      transfers: transferCount,
      cost: trace.totals.accumulated_cost_uzs,
      unitCost: trace.totals.unit_cost_uzs,
      yieldPct,
      lossPct,
      initial,
      current,
    };
  }, [trace]);

  const handleExportJournal = () => {
    if (!trace || !costEntries || costEntries.length === 0) return;
    const rows: string[][] = [
      ['Дата', 'Категория', 'Сумма UZS', 'Описание', 'Модуль'],
    ];
    for (const ce of costEntries) {
      rows.push([
        fmtDate(ce.occurred_at),
        BATCH_COST_CATEGORY_LABEL[ce.category] ?? ce.category,
        ce.amount_uzs,
        ce.description ?? '',
        moduleLabel(ce.module_code),
      ]);
    }
    const fname = `journal-${trace.batch.doc_number}.csv`;
    downloadCsv(fname, rows);
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Сквозная трассировка партии</h1>
          <div className="sub">
            Путь партии по модулям · затраты · родительские и дочерние партии
          </div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            disabled={!trace || !costEntries || costEntries.length === 0}
            onClick={handleExportJournal}
          >
            <Icon name="download" size={14} /> Экспорт журнала
          </button>
        </div>
      </div>

      {/* Sidebar (батчи) + правая колонка (детали) */}
      <div className="trace-grid">
        <Panel flush>
          <div style={{ padding: 10, borderBottom: '1px solid var(--border)' }}>
            <input
              className="input"
              placeholder="Поиск: № партии, SKU, название…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div style={{ maxHeight: 480, overflowY: 'auto' }}>
            {batchesLoading && (
              <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 12 }}>
                Загрузка…
              </div>
            )}
            {!batchesLoading && list.length === 0 && (
              <div
                style={{
                  padding: 12,
                  color: 'var(--fg-3)',
                  fontSize: 12,
                  textAlign: 'center',
                }}
              >
                Партий не найдено.
              </div>
            )}
            {list.slice(0, 100).map((b) => {
              const isSel = effectiveSelected?.id === b.id;
              return (
                <button
                  key={b.id}
                  onClick={() => setSelected(b)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 10px',
                    border: 'none',
                    borderBottom: '1px solid var(--border)',
                    background: isSel ? 'var(--bg-soft)' : 'transparent',
                    borderLeft: isSel
                      ? '3px solid var(--brand-orange)'
                      : '3px solid transparent',
                    cursor: 'pointer',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>
                      {b.doc_number}
                    </span>
                    <Badge tone={BATCH_STATE_TONE[b.state] ?? 'neutral'}>
                      {BATCH_STATE_LABEL[b.state] ?? b.state}
                    </Badge>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>
                    {b.nomenclature_sku ?? ''} · {b.nomenclature_name ?? ''}
                  </div>
                  <div
                    className="mono"
                    style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}
                  >
                    Остаток {fmtQty(b.current_quantity, b.unit_code)}
                    {b.current_module_code &&
                      ` · в ${moduleLabel(b.current_module_code)}`}
                  </div>
                </button>
              );
            })}
          </div>
        </Panel>

        <div>
          {!effectiveSelected && (
            <Panel>
              <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
                Выберите партию слева, чтобы увидеть её путь.
              </div>
            </Panel>
          )}

          {effectiveSelected && traceLoading && (
            <Panel>
              <div style={{ padding: 24, color: 'var(--fg-3)' }}>
                Загрузка трассировки…
              </div>
            </Panel>
          )}

          {effectiveSelected && trace && (
            <>
              {/* Заголовок выбранной партии */}
              <div style={{ marginBottom: 10 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    marginBottom: 4,
                    flexWrap: 'wrap',
                  }}
                >
                  <span className="mono" style={{ fontSize: 15, fontWeight: 700 }}>
                    {trace.batch.doc_number}
                  </span>
                  <Badge tone={BATCH_STATE_TONE[trace.batch.state] ?? 'neutral'}>
                    {BATCH_STATE_LABEL[trace.batch.state] ?? trace.batch.state}
                  </Badge>
                  {trace.batch.origin_module_code && (
                    <span
                      style={{ fontSize: 11, color: 'var(--fg-3)' }}
                      className="mono"
                    >
                      origin: {moduleLabel(trace.batch.origin_module_code)}
                    </span>
                  )}
                  {trace.batch.current_module_code && (
                    <span
                      style={{ fontSize: 11, color: 'var(--fg-3)' }}
                      className="mono"
                    >
                      сейчас: {moduleLabel(trace.batch.current_module_code)}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>
                  {trace.batch.nomenclature_sku ?? ''} ·{' '}
                  {trace.batch.nomenclature_name ?? ''}
                </div>
              </div>

              {/* KPI: финансовые показываются только если у юзера есть доступ
                  к финансам модуля партии (или к ledger).
                  Backend ставит trace._finances_visible=false и обнуляет cost-поля. */}
              {kpi && (
                <>
                  <div className="kpi-row" style={{ marginBottom: 12 }}>
                    {(trace as { _finances_visible?: boolean })._finances_visible !== false && (
                      <>
                        <KpiCard
                          tone="red"
                          iconName="bag"
                          label="Накопл. себ-ть"
                          sub="UZS"
                          value={fmtUzs(kpi.cost, true)}
                        />
                        <KpiCard
                          tone="orange"
                          iconName="chart"
                          label="Себ-ть единицы"
                          sub={
                            trace.batch.unit_code
                              ? `за 1 ${trace.batch.unit_code}`
                              : 'UZS / ед.'
                          }
                          value={fmtUzs(kpi.unitCost, true)}
                        />
                      </>
                    )}
                    <KpiCard
                      tone={kpi.yieldPct !== null && kpi.yieldPct >= 90 ? 'green' : 'orange'}
                      iconName="check"
                      label={
                        trace.batch.state === 'completed' ? 'Финальный выход' : 'Выход (текущий)'
                      }
                      sub={
                        kpi.yieldPct !== null
                          ? `${kpi.current.toLocaleString('ru-RU')} / ${kpi.initial.toLocaleString('ru-RU')}`
                          : '—'
                      }
                      value={kpi.yieldPct !== null ? `${kpi.yieldPct.toFixed(1)}%` : '—'}
                    />
                    <KpiCard
                      tone="red"
                      iconName="close"
                      label="Потери"
                      sub="отход / падёж"
                      value={kpi.lossPct !== null ? `${kpi.lossPct.toFixed(1)}%` : '—'}
                    />
                  </div>

                  <div className="kpi-row" style={{ marginBottom: 12 }}>
                    <KpiCard
                      tone="blue"
                      iconName="book"
                      label="Дней в цепочке"
                      sub={
                        kpi.days !== null ? 'от старта до текущего момента' : '—'
                      }
                      value={kpi.days !== null ? String(kpi.days) : '—'}
                    />
                    <KpiCard
                      tone="orange"
                      iconName="chart"
                      label="Этапов пройдено"
                      sub="в производственных модулях"
                      value={String(kpi.stepsCount)}
                    />
                    <KpiCard
                      tone="green"
                      iconName="chart"
                      label="Передач"
                      sub="между модулями"
                      value={String(kpi.transfers)}
                    />
                    <KpiCard
                      tone="blue"
                      iconName="users"
                      label="Записей в журнале"
                      sub="отдельных операций"
                      value={String(costEntries?.length ?? 0)}
                    />
                  </div>
                </>
              )}

              {/* Происхождение / связанные */}
              <Panel title="Происхождение и связи" style={{ marginBottom: 12 }}>
                <div className="trace-relatives-grid">
                  <div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--fg-3)',
                        textTransform: 'uppercase',
                        letterSpacing: '.06em',
                        fontWeight: 700,
                        marginBottom: 6,
                      }}
                    >
                      Откуда (родитель / закуп)
                    </div>
                    {trace.parent ? (
                      <button
                        onClick={() => {
                          const full = list.find((b) => b.id === trace.parent!.id);
                          if (full) setSelected(full);
                        }}
                        style={{
                          display: 'block',
                          width: '100%',
                          textAlign: 'left',
                          padding: 8,
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          background: 'var(--bg-card)',
                          cursor: 'pointer',
                        }}
                      >
                        <div className="mono" style={{ fontWeight: 600 }}>
                          {trace.parent.doc_number}
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--fg-2)',
                            marginTop: 2,
                          }}
                        >
                          {trace.parent.nomenclature_sku ?? '—'}
                        </div>
                        <div
                          className="mono"
                          style={{
                            fontSize: 11,
                            color: 'var(--fg-3)',
                            marginTop: 4,
                          }}
                        >
                          Остаток: {fmtQty(trace.parent.current_quantity)} ·{' '}
                          {fmtUzs(trace.parent.accumulated_cost_uzs)} UZS
                        </div>
                      </button>
                    ) : trace.batch.origin_purchase ? (
                      <a
                        href={`/purchases?id=${trace.batch.origin_purchase}`}
                        style={{
                          display: 'block',
                          padding: 8,
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          background: 'var(--bg-card)',
                          textDecoration: 'none',
                          color: 'inherit',
                        }}
                      >
                        <div style={{ fontSize: 12, fontWeight: 600 }}>
                          Закуп у поставщика
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            color: 'var(--brand-orange)',
                            marginTop: 4,
                          }}
                        >
                          Открыть закуп →
                        </div>
                      </a>
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                        Первичная партия (не имеет родителя)
                      </div>
                    )}
                  </div>

                  <div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--fg-3)',
                        textTransform: 'uppercase',
                        letterSpacing: '.06em',
                        fontWeight: 700,
                        marginBottom: 6,
                      }}
                    >
                      Куда (дочерние партии · {trace.children.length})
                    </div>
                    {trace.children.length === 0 ? (
                      <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                        Партия ещё не распалась на дочерние.
                      </div>
                    ) : (
                      <div
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 6,
                        }}
                      >
                        {trace.children.map((c) => (
                          <button
                            key={c.id}
                            onClick={() => {
                              const full = list.find((b) => b.id === c.id);
                              if (full) setSelected(full);
                            }}
                            style={{
                              textAlign: 'left',
                              padding: 8,
                              border: '1px solid var(--border)',
                              borderRadius: 6,
                              background: 'var(--bg-card)',
                              cursor: 'pointer',
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                gap: 8,
                              }}
                            >
                              <span className="mono" style={{ fontWeight: 600 }}>
                                {c.doc_number}
                              </span>
                              {c.current_module && (
                                <span
                                  style={{ fontSize: 11, color: 'var(--fg-3)' }}
                                  className="mono"
                                >
                                  в {moduleLabel(c.current_module)}
                                </span>
                              )}
                            </div>
                            <div
                              style={{
                                fontSize: 12,
                                color: 'var(--fg-2)',
                                marginTop: 2,
                              }}
                            >
                              {c.nomenclature_sku ?? '—'} ·{' '}
                              {fmtQty(c.current_quantity)} ·{' '}
                              {fmtUzs(c.accumulated_cost_uzs)} UZS
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </Panel>

              {/* Cost trend */}
              {trace.chain_steps.length > 0 && (
                <Panel
                  title="Себестоимость по цепочке"
                  style={{ marginBottom: 12 }}
                >
                  <CostTrendChart steps={trace.chain_steps} />
                </Panel>
              )}

              {/* Chain visualization */}
              <Panel title="Путь по модулям" style={{ marginBottom: 12 }}>
                {trace.chain_steps.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                    У партии пока нет шагов — она ещё не перемещалась между модулями.
                  </div>
                ) : (
                  <div className="trace-chain">
                    {trace.chain_steps.map((step, i) => (
                      <ChainStepCard
                        key={step.id}
                        step={step}
                        isFirst={i === 0}
                        isLast={i === trace.chain_steps.length - 1}
                        isCurrent={step.exited_at === null}
                      />
                    ))}
                  </div>
                )}
              </Panel>

              {/* Cost breakdown + journal */}
              <div className="trace-cost-grid">
                <Panel title="Накопленная себестоимость" flush>
                  <DataTable<BatchCostBreakdownItem>
                    rows={trace.cost_breakdown}
                    rowKey={(c) => c.category}
                    emptyMessage="Ещё нет учтённых затрат по этой партии."
                    columns={[
                      {
                        key: 'cat',
                        label: 'Статья затрат',
                        render: (c) => (
                          <>
                            <span
                              style={{
                                display: 'inline-block',
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                background:
                                  BATCH_COST_CATEGORY_TONE[c.category] ??
                                  'var(--fg-3)',
                                marginRight: 8,
                                verticalAlign: 'middle',
                              }}
                            />
                            {c.category_label ||
                              BATCH_COST_CATEGORY_LABEL[c.category] ||
                              c.category}
                          </>
                        ),
                      },
                      {
                        key: 'amount',
                        label: 'Сумма, UZS',
                        align: 'right',
                        mono: true,
                        render: (c) => fmtUzs(c.amount_uzs),
                      },
                      {
                        key: 'share',
                        label: 'Доля',
                        align: 'right',
                        mono: true,
                        render: (c) => `${parseFloat(c.share_percent).toFixed(1)}%`,
                      },
                    ]}
                  />
                  {trace.cost_breakdown.length > 0 && (
                    <div
                      style={{
                        padding: '10px 12px',
                        borderTop: '1px solid var(--border)',
                        background: 'var(--bg-soft)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: 13,
                        fontWeight: 600,
                      }}
                    >
                      <span>Итого накоплено</span>
                      <span className="mono">
                        {fmtUzs(trace.totals.accumulated_cost_uzs)} UZS
                      </span>
                    </div>
                  )}
                  <div
                    style={{
                      padding: 8,
                      fontSize: 11,
                      color: 'var(--fg-3)',
                      borderTop: '1px solid var(--border)',
                    }}
                  >
                    Себестоимость 1 единицы:{' '}
                    <span
                      className="mono"
                      style={{ color: 'var(--fg-1)', fontWeight: 600 }}
                    >
                      {fmtUzs(trace.totals.unit_cost_uzs)} UZS
                    </span>
                    {trace.batch.unit_code && ` / ${trace.batch.unit_code}`}
                  </div>
                </Panel>

                <Panel
                  title={`Журнал затрат · ${costEntries?.length ?? 0}`}
                  flush
                >
                  <div style={{ maxHeight: 360, overflowY: 'auto' }}>
                    <DataTable<BatchCostEntry>
                      rows={costEntries}
                      rowKey={(ce) => ce.id}
                      emptyMessage="Операции не зарегистрированы."
                      columns={[
                        {
                          key: 'date',
                          label: 'Дата',
                          mono: true,
                          cellStyle: { fontSize: 11 },
                          render: (ce) => fmtDate(ce.occurred_at),
                        },
                        {
                          key: 'cat',
                          label: 'Категория',
                          render: (ce) => (
                            <>
                              <span
                                style={{
                                  display: 'inline-block',
                                  width: 6,
                                  height: 6,
                                  borderRadius: '50%',
                                  background:
                                    BATCH_COST_CATEGORY_TONE[ce.category] ??
                                    'var(--fg-3)',
                                  marginRight: 6,
                                  verticalAlign: 'middle',
                                }}
                              />
                              {BATCH_COST_CATEGORY_LABEL[ce.category] ?? ce.category}
                            </>
                          ),
                        },
                        {
                          key: 'amount',
                          label: 'Сумма',
                          align: 'right',
                          mono: true,
                          cellStyle: { fontSize: 12 },
                          render: (ce) => fmtUzs(ce.amount_uzs),
                        },
                        {
                          key: 'desc',
                          label: 'Описание',
                          cellStyle: { fontSize: 12 },
                          render: (ce) => (
                            <>
                              {ce.description}
                              {ce.module_code && (
                                <span
                                  style={{
                                    fontSize: 10,
                                    color: 'var(--fg-3)',
                                    marginLeft: 6,
                                  }}
                                  className="mono"
                                >
                                  [{moduleLabel(ce.module_code)}]
                                </span>
                              )}
                            </>
                          ),
                        },
                      ]}
                    />
                  </div>
                </Panel>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ─── Chain step card ──────────────────────────────────────────────────

function ChainStepCard({
  step,
  isFirst,
  isLast,
  isCurrent,
}: {
  step: BatchChainStep;
  isFirst: boolean;
  isLast: boolean;
  isCurrent: boolean;
}) {
  const moduleStr = moduleLabel(step.module_code);
  const blockLabel = step.block_code ?? '';
  const daysIn = daysBetween(step.entered_at, step.exited_at);

  const bg = isCurrent
    ? 'var(--brand-orange-soft, #FFF0E6)'
    : step.exited_at
    ? 'var(--success-soft, #ECFDF5)'
    : 'var(--bg-subtle, var(--bg-soft))';
  const border = isCurrent
    ? 'var(--brand-orange)'
    : step.exited_at
    ? 'var(--success, #10B981)'
    : 'var(--border)';
  const titleColor = isCurrent
    ? 'var(--brand-orange-dark, #C85D13)'
    : step.exited_at
    ? 'var(--success, #0F766E)'
    : 'var(--fg-3)';

  return (
    <div className="trace-chain-step">
      <div
        style={{
          flex: 1,
          padding: '12px',
          borderRadius: isFirst ? '6px 0 0 6px' : isLast ? '0 6px 6px 0' : 0,
          background: bg,
          border: '1px solid ' + border,
          borderRight: !isLast ? 'none' : undefined,
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: titleColor,
            textTransform: 'uppercase',
            letterSpacing: '.06em',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          шаг {step.sequence} · {moduleStr}
          {isCurrent && (
            <span
              aria-label="сейчас здесь"
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--brand-orange)',
                animation: 'pulse 1.4s ease-in-out infinite',
              }}
            />
          )}
        </div>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--fg-1)',
            marginTop: 4,
          }}
        >
          {blockLabel || '—'}
        </div>
        <div
          className="mono"
          style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 4 }}
        >
          Вошло: {fmtQty(step.quantity_in)}
          {step.quantity_out && (
            <>
              <br />
              Вышло: {fmtQty(step.quantity_out)}
            </>
          )}
        </div>
        <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 6 }}>
          {fmtDate(step.entered_at)}
          {step.exited_at && ` → ${fmtDate(step.exited_at)}`}
          {daysIn !== null && ` · ${daysIn} дн`}
        </div>
        {step.accumulated_cost_at_exit && (
          <div
            className="mono"
            style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 4 }}
          >
            Себ-ть на выходе:{' '}
            <b>{fmtUzs(step.accumulated_cost_at_exit, true)}</b>
          </div>
        )}
        {(step.transfer_in_doc || step.transfer_out_doc) && (
          <div style={{ fontSize: 10, marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {step.transfer_in_doc && (
              <a
                href={`/transfers?id=${step.transfer_in ?? ''}`}
                className="mono"
                style={{
                  color: 'var(--brand-orange)',
                  textDecoration: 'none',
                  background: 'var(--bg-card, #fff)',
                  padding: '1px 5px',
                  border: '1px solid var(--border)',
                  borderRadius: 3,
                }}
                title="Открыть передачу"
              >
                ← {step.transfer_in_doc}
              </a>
            )}
            {step.transfer_out_doc && (
              <a
                href={`/transfers?id=${step.transfer_out ?? ''}`}
                className="mono"
                style={{
                  color: 'var(--brand-orange)',
                  textDecoration: 'none',
                  background: 'var(--bg-card, #fff)',
                  padding: '1px 5px',
                  border: '1px solid var(--border)',
                  borderRadius: 3,
                }}
                title="Открыть передачу"
              >
                {step.transfer_out_doc} →
              </a>
            )}
          </div>
        )}
      </div>
      {!isLast && (
        <div
          className="trace-chain-arrow"
          style={{ display: 'flex', alignItems: 'center', padding: '0 4px' }}
        >
          <Icon name="chevron-right" size={16} style={{ color: 'var(--fg-3)' }} />
        </div>
      )}
    </div>
  );
}
