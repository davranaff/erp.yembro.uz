'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import { useDashboardCashflow, useDashboardSummary } from '@/hooks/useDashboard';
import type { DashboardArSummary, DashboardCashChannel, DashboardModuleKassa } from '@/types/auth';

import PurchaseOrderModal from '../purchases/PurchaseOrderModal';
import CashflowChart from './CashflowChart';

function fmt(v: string | number | null | undefined, opts: { short?: boolean } = {}): string {
  if (v == null) return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  if (opts.short) {
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(0) + 'K';
  }
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function formatPeriod(from: string, to: string): string {
  const f = new Date(from);
  const t = new Date(to);
  const sameMonth = f.getMonth() === t.getMonth() && f.getFullYear() === t.getFullYear();
  if (sameMonth) {
    return `${f.getDate()}–${t.getDate()} ${t.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' })}`;
  }
  return `${f.toLocaleDateString('ru-RU')} – ${t.toLocaleDateString('ru-RU')}`;
}

const CHANNEL_LABEL: Record<string, string> = {
  cash: 'Наличные',
  transfer: 'Перечисление',
  click: 'Click',
  other: 'Прочее',
};

const CHANNEL_ICON: Record<string, string> = {
  cash: 'bag',
  transfer: 'book',
  click: 'check',
  other: 'box',
};

export default function DashboardPage() {
  const router = useRouter();
  const [days, setDays] = useState<7 | 30 | 90>(30);
  // Открытие модалки прямо на дашборде вместо редиректа на /purchases —
  // редирект на холодный роут стоит ~1с компиляции в dev. Модалка
  // открывается мгновенно, после save react-query инвалидирует
  // ['purchases','orders'] — данные подхватятся когда юзер всё-таки
  // зайдёт в раздел.
  const [purchaseModalOpen, setPurchaseModalOpen] = useState(false);

  const { data: summary, isLoading, error, refetch, isFetching } = useDashboardSummary();
  const { data: cashflow } = useDashboardCashflow(days);

  // Префетч на hover — Next.js dev-сервер компилирует роут заранее,
  // и переход становится мгновенным.
  const prefetch = (path: string) => () => router.prefetch(path);

  if (isLoading) {
    return (
      <>
        <div className="page-hdr">
          <div>
            <h1>Сводка</h1>
            <div className="sub">Загрузка показателей…</div>
          </div>
        </div>
      </>
    );
  }

  if (error || !summary) {
    return (
      <>
        <div className="page-hdr">
          <div>
            <h1>Сводка</h1>
          </div>
        </div>
        <div style={{ padding: 24, color: 'var(--danger)', fontSize: 13 }}>
          Ошибка загрузки: {error?.message ?? 'нет данных'}
        </div>
      </>
    );
  }

  const k = summary.kpis;
  const prod = summary.production;
  const cash = summary.cash;
  // Backend ставит флаг false если у юзера нет ledger.r — финансовые
  // KPI приходят как null, а cash может быть полностью null.
  const financesVisible = (summary as { _finances_visible?: boolean })._finances_visible !== false;

  const forecast = financesVisible && k.sales_forecast_uzs ? parseFloat(k.sales_forecast_uzs) : 0;
  const netCash = financesVisible && k.payments_in_uzs && k.payments_out_uzs
    ? parseFloat(k.payments_in_uzs) - parseFloat(k.payments_out_uzs)
    : 0;

  const totalDrafts = (k.purchases_drafts ?? 0) + (k.sales_drafts ?? 0) + (k.payments_drafts ?? 0);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Сводка</h1>
          <div className="sub">
            Финансы и производство · период {formatPeriod(k.period.from, k.period.to)}
          </div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} />
            {isFetching ? '…' : 'Обновить'}
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setPurchaseModalOpen(true)}
            onMouseEnter={prefetch('/purchases')}
          >
            <Icon name="plus" size={14} /> Новый закуп
          </button>
        </div>
      </div>

      {/* ───── 4 главных аналитики — только при ledger.r ───── */}
      {financesVisible && cash && (
        <div className="kpi-row" style={{ marginBottom: 12 }}>
          <KpiCard
            tone="green"
            iconName="download"
            label="Поступления"
            sub={`за период · ${formatPeriod(k.period.from, k.period.to)}`}
            value={fmt(k.payments_in_uzs)}
            valueSuffix="UZS"
          />
          <KpiCard
            tone="blue"
            iconName="users"
            label="Дебиторка"
            sub="должны нам (всё время)"
            value={fmt(k.debtor_balance_uzs)}
            valueSuffix="UZS"
            meta={forecast > 0 ? `прогноз: +${fmt(k.sales_forecast_uzs)}` : undefined}
          />
          <KpiCard
            tone="red"
            iconName="arrow-right"
            label="Расходы"
            sub={`за период · ${formatPeriod(k.period.from, k.period.to)}`}
            value={fmt(k.payments_out_uzs)}
            valueSuffix="UZS"
          />
          <KpiCard
            tone="orange"
            iconName="bag"
            label="Касса всего"
            sub="текущий остаток"
            value={fmt(typeof cash._total_uzs === 'string' ? cash._total_uzs : '0')}
            valueSuffix="UZS"
            meta={netCash !== 0 ? `поток: ${netCash >= 0 ? '+' : '−'}${fmt(Math.abs(netCash))}` : undefined}
          />
        </div>
      )}

      {/* ───── AR snapshot — дебиторка с aging + DSO + топ должников ───── */}
      {financesVisible && summary.ar && (
        <ArSnapshotPanel ar={summary.ar} />
      )}

      {/* ───── Кассы по подразделениям — видны по правам модуля ───── */}
      {summary.module_kassas && summary.module_kassas.length > 0 && (
        <ModuleKassasSection kassas={summary.module_kassas} period={formatPeriod(k.period.from, k.period.to)} />
      )}

      {/* ───── Cashflow chart + side panels — только при ledger.r ───── */}
      {financesVisible && cash && (
      <div className="grid-main-side" style={{ marginBottom: 12 }}>
        <Panel
          title="Денежные потоки по дням"
          tools={
            <Seg
              options={[
                { value: '7',  label: '7 дн' },
                { value: '30', label: '30 дн' },
                { value: '90', label: '90 дн' },
              ]}
              value={String(days)}
              onChange={(v) => setDays(Number(v) as 7 | 30 | 90)}
            />
          }
        >
          <CashflowChart points={cashflow?.points ?? []} />
        </Panel>

        <Panel title="Касса и счета" flush>
          {(Object.entries(cash).filter(
            ([key, info]) => !key.startsWith('_') && typeof info !== 'string',
          ) as [string, DashboardCashChannel][])
            .map(([key, info]) => {
              const balance = parseFloat(info.balance_uzs);
              const isZero = balance === 0;
              const isNeg = balance < 0;
              return (
                <div
                  key={key}
                  style={{
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 4,
                      background: isZero ? 'var(--bg-subtle)' : 'var(--bg-soft)',
                      color: isNeg ? 'var(--danger)' : isZero ? 'var(--fg-3)' : 'var(--fg-2)',
                      display: 'grid',
                      placeItems: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <Icon name={CHANNEL_ICON[key] ?? 'box'} size={16} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>
                      {CHANNEL_LABEL[key] ?? info.label}
                    </div>
                    <div
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 13,
                        color: isNeg ? 'var(--danger)' : isZero ? 'var(--fg-3)' : 'var(--fg-1)',
                        fontWeight: isZero ? 400 : 600,
                        marginTop: 2,
                      }}
                    >
                      {isZero ? '—' : fmt(info.balance_uzs) + ' UZS'}
                    </div>
                  </div>
                </div>
              );
            })}
          <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between' }}>
            <a
              href="/finance/cashbox"
              style={{ fontSize: 12, color: 'var(--brand-orange)' }}
            >
              Все движения →
            </a>
          </div>
        </Panel>
      </div>
      )}

      {/* ───── Производство «здесь и сейчас» ───── */}
      <Panel title="Производство · текущее состояние" style={{ marginBottom: 12 }}>
        <div
          className="grid-auto-180"
          style={{ padding: 12 }}
        >
          {prod.matochnik_heads != null && (
            <ProductionTile
              label="Маточник"
              value={prod.matochnik_heads}
              unit="голов"
              tone="neutral"
              href="/matochnik"
            />
          )}
          {prod.incubation_runs != null && (
            <ProductionTile
              label="Инкубация"
              value={prod.incubation_runs}
              unit={`закладок (${fmt(prod.incubation_eggs_loaded ?? 0)} яиц)`}
              tone="warn"
              href="/incubation"
            />
          )}
          {prod.feedlot_heads != null && (
            <ProductionTile
              label="Откорм"
              value={prod.feedlot_heads}
              unit="голов"
              tone="info"
              href="/feedlot"
            />
          )}
          <ProductionTile
            label="Активных партий"
            value={k.active_batches}
            unit="всего"
            tone="success"
            href="/traceability"
          />
        </div>
      </Panel>

      {/* ───── Требует действия ───── */}
      <Panel
        title={`Требует действия · ${totalDrafts + k.transfers_pending}`}
        style={{ marginBottom: 12 }}
      >
        <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {k.purchases_drafts != null && (
            <ActionRow
              label="Закупки в черновиках"
              count={k.purchases_drafts}
              href="/purchases"
              help="Не проведены — товар не оприходован"
              tone="warn"
            />
          )}
          {k.sales_drafts != null && (
            <ActionRow
              label="Продажи в черновиках"
              count={k.sales_drafts}
              href="/sales"
              help="Резервируют партии, но не отгружены"
              tone="warn"
            />
          )}
          {k.payments_drafts != null && (
            <ActionRow
              label="Платежи в черновиках"
              count={k.payments_drafts}
              href="/finance/cashbox"
              help="Не проведены в ГК"
              tone="warn"
            />
          )}
          <ActionRow
            label="Межмодульные передачи на приёмке"
            count={k.transfers_pending}
            href="/transfers"
            help="Принимающий модуль ещё не подтвердил"
            tone="info"
          />
          {totalDrafts === 0 && k.transfers_pending === 0 && (
            <div style={{ fontSize: 13, color: 'var(--fg-3)', textAlign: 'center', padding: 16 }}>
              <Icon name="check" size={16} /> Всё в порядке — нет документов, ждущих действия.
            </div>
          )}
        </div>
      </Panel>

      {/* ───── Quick actions ───── */}
      <Panel title="Быстрые действия">
        <div style={{ padding: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setPurchaseModalOpen(true)}
            onMouseEnter={prefetch('/purchases')}
          >
            <Icon name="plus" size={12} /> Новый закуп
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => router.push('/sales')}
            onMouseEnter={prefetch('/sales')}
          >
            <Icon name="plus" size={12} /> Новая продажа
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => router.push('/finance/cashbox')}
            onMouseEnter={prefetch('/finance/cashbox')}
          >
            <Icon name="plus" size={12} /> Новый платёж
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => router.push('/stock')}
            onMouseEnter={prefetch('/stock')}
          >
            <Icon name="plus" size={12} /> Движение склада
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => router.push('/reports')}
            onMouseEnter={prefetch('/reports')}
          >
            <Icon name="book" size={12} /> Отчёты
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => router.push('/audit-log')}
            onMouseEnter={prefetch('/audit-log')}
          >
            <Icon name="book" size={12} /> Журнал аудита
          </button>
        </div>
      </Panel>

      {purchaseModalOpen && (
        <PurchaseOrderModal onClose={() => setPurchaseModalOpen(false)} />
      )}
    </>
  );
}

interface ProductionTileProps {
  label: string;
  value: number;
  unit: string;
  tone: 'neutral' | 'warn' | 'info' | 'success';
  href: string;
}

function ProductionTile({ label, value, unit, tone, href }: ProductionTileProps) {
  const tones: Record<string, string> = {
    neutral: 'var(--fg-2)',
    warn: 'var(--warning)',
    info: 'var(--info)',
    success: 'var(--success)',
  };
  return (
    <a
      href={href}
      style={{
        padding: 14,
        border: '1px solid var(--border)',
        borderRadius: 6,
        display: 'block',
        textDecoration: 'none',
        color: 'inherit',
        background: 'var(--bg-card)',
        borderLeft: `3px solid ${tones[tone]}`,
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 4 }}>{label}</div>
      <div
        className="mono"
        style={{ fontSize: 22, fontWeight: 700, color: 'var(--fg-1)' }}
      >
        {value.toLocaleString('ru-RU')}
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{unit}</div>
    </a>
  );
}

function ArSnapshotPanel({ ar }: { ar: DashboardArSummary }) {
  const totalAr = parseFloat(ar.total_ar_uzs);
  const totalOverdue = parseFloat(ar.total_overdue_uzs);
  const overduePct = totalAr > 0 ? Math.round(totalOverdue / totalAr * 100) : 0;

  return (
    <div style={{ marginBottom: 12 }}>
      <Panel
        title="Дебиторка — снимок"
        tools={
          <a
            href="/reports/aging"
            style={{
              fontSize: 12, color: 'var(--brand-orange)',
              textDecoration: 'none',
            }}
          >
            Полный отчёт →
          </a>
        }
      >
        <div style={{
          padding: 12, display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr', gap: 12,
        }}>
          {/* Левая колонка: KPI */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 2 }}>Всего долгов</div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 600 }}>
              {fmt(ar.total_ar_uzs)}{' '}
              <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>UZS</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
              {ar.customers_count} клиент(ов), из них{' '}
              <strong style={{ color: 'var(--brand-orange)' }}>
                {ar.overdue_customers_count}
              </strong>{' '}
              с просрочкой
            </div>
          </div>

          {/* Средняя: aging buckets как mini-bars */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 4 }}>
              Просрочено: <strong style={{ color: overduePct > 30 ? 'var(--danger)' : 'var(--fg-2)' }}>
                {fmt(ar.total_overdue_uzs)} UZS
              </strong> ({overduePct}%)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <ArMiniBar label="Текущие" total={totalAr} value={ar.buckets.current} color="var(--success, #10b981)" />
              <ArMiniBar label="0-30" total={totalAr} value={ar.buckets.b_0_30} color="var(--brand-orange)" />
              <ArMiniBar label="31-60" total={totalAr} value={ar.buckets.b_31_60} color="var(--brand-orange)" />
              <ArMiniBar label="61-90" total={totalAr} value={ar.buckets.b_61_90} color="var(--danger)" />
              <ArMiniBar label="90+" total={totalAr} value={ar.buckets.b_90_plus} color="var(--danger)" />
            </div>
          </div>

          {/* Правая: DSO + топ-3 */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 2 }}>
              DSO ({ar.dso_window_days} дн)
            </div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>
              {ar.dso_days != null ? `${ar.dso_days} дн` : '—'}
              <div style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 400 }}>
                Days Sales Outstanding
              </div>
            </div>

            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 4 }}>Топ-3 должников</div>
            {ar.top_debtors.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Долгов нет</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {ar.top_debtors.map((d) => (
                  <a
                    key={d.counterparty_id}
                    href={`/counterparties/${d.counterparty_id}`}
                    style={{
                      fontSize: 12, padding: '4px 6px',
                      background: 'var(--bg-soft)', borderRadius: 4,
                      textDecoration: 'none', color: 'inherit',
                      display: 'flex', justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <span style={{
                      overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', flex: 1,
                    }}>
                      {d.name}
                    </span>
                    <span className="mono" style={{
                      fontWeight: 600,
                      color: d.oldest_overdue_days > 30 ? 'var(--danger)' : 'var(--fg-1)',
                    }}>
                      {fmt(d.total, { short: true })}
                    </span>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </Panel>
    </div>
  );
}

const MODULE_ICON: Record<string, string> = {
  feedlot:    'box',
  feed:       'box',
  matochnik:  'users',
  incubation: 'box',
  sales:      'chart',
  purchases:  'download',
  ledger:     'book',
  slaughter:  'box',
  vet:        'check',
  hr:         'users',
};

function ModuleKassasSection({
  kassas,
  period,
}: { kassas: DashboardModuleKassa[]; period: string }) {
  return (
    <Panel
      title="Кассы по подразделениям"
      tools={
        <a href="/finance/cashbox" style={{ fontSize: 12, color: 'var(--brand-orange)', textDecoration: 'none' }}>
          Все движения →
        </a>
      }
      style={{ marginBottom: 12 }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          gap: 1,
          background: 'var(--border)',
        }}
      >
        {kassas.map((k) => {
          const balance = parseFloat(k.balance_uzs);
          const pIn = parseFloat(k.period_in_uzs);
          const pOut = parseFloat(k.period_out_uzs);
          const isNeg = balance < 0;
          const isZero = balance === 0;

          return (
            <div
              key={k.module_code}
              style={{
                background: 'var(--bg-card)',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 4,
                  background: 'var(--bg-soft)',
                  display: 'grid', placeItems: 'center', flexShrink: 0,
                }}>
                  <Icon name={MODULE_ICON[k.module_code] ?? 'box'} size={14} />
                </div>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{k.module_name}</span>
              </div>

              <div
                className="mono"
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: isNeg ? 'var(--danger)' : isZero ? 'var(--fg-3)' : 'var(--fg-1)',
                }}
              >
                {isZero ? '—' : `${isNeg ? '−' : ''}${fmt(Math.abs(balance))}`}
                {!isZero && (
                  <span style={{ fontSize: 11, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 4 }}>
                    UZS
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--fg-3)' }}>
                <span style={{ color: pIn > 0 ? 'var(--success)' : 'var(--fg-3)' }}>
                  ↑ {pIn > 0 ? fmt(pIn, { short: true }) : '—'}
                </span>
                <span style={{ color: pOut > 0 ? 'var(--danger)' : 'var(--fg-3)' }}>
                  ↓ {pOut > 0 ? fmt(pOut, { short: true }) : '—'}
                </span>
                <span style={{ color: 'var(--fg-3)' }}>{period}</span>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ArMiniBar({
  label, total, value, color,
}: { label: string; total: number; value: string; color: string }) {
  const v = parseFloat(value);
  const pct = total > 0 ? (v / total) * 100 : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
      <span style={{ width: 50, color: 'var(--fg-3)' }}>{label}</span>
      <div style={{ flex: 1, height: 8, background: 'var(--bg-soft)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color }} />
      </div>
      <span className="mono" style={{ width: 70, textAlign: 'right' }}>
        {v === 0 ? '—' : fmt(value, { short: true })}
      </span>
    </div>
  );
}

interface ActionRowProps {
  label: string;
  count: number;
  href: string;
  help: string;
  tone: 'warn' | 'info';
}

function ActionRow({ label, count, href, help, tone }: ActionRowProps) {
  if (count === 0) return null;
  return (
    <a
      href={href}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        border: '1px solid var(--border)',
        borderRadius: 6,
        textDecoration: 'none',
        color: 'inherit',
        background: 'var(--bg-card)',
      }}
    >
      <Badge tone={tone}>{count}</Badge>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{help}</div>
      </div>
      <Icon name="arrow-right" size={14} />
    </a>
  );
}
