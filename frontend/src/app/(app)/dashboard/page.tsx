'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import { useDashboardSummary } from '@/hooks/useDashboard';

import PurchaseOrderModal from '../purchases/PurchaseOrderModal';
import ModuleSection from './ModuleSection';

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

export default function DashboardPage() {
  const router = useRouter();
  const [purchaseModalOpen, setPurchaseModalOpen] = useState(false);

  const { data: summary, isLoading, error, refetch, isFetching } = useDashboardSummary();

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

      {/* ───── Per-module sections — видны по правам доступа к модулю ───── */}
      {summary.module_kassas?.map((mk) => (
        <ModuleSection
          key={mk.module_code}
          moduleCode={mk.module_code}
          moduleName={mk.module_name}
        />
      ))}

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
