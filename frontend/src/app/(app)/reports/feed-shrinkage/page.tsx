'use client';

import { useState } from 'react';

import DateRangeFilter from '@/components/DateRangeFilter';
import ExportCsvButton from '@/components/ExportCsvButton';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import { useShrinkageReport } from '@/hooks/useFeed';
import type { ShrinkageReportRow } from '@/types/auth';


function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function fmtKg(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 3 }) + ' кг';
}

function fmtMoney(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

export default function FeedShrinkageReportPage() {
  const [dateFrom, setDateFrom] = useState(startOfMonth());
  const [dateTo, setDateTo] = useState(isoToday());
  const [groupBy, setGroupBy] = useState<'ingredient' | 'warehouse'>('ingredient');

  const { data, isLoading, error } = useShrinkageReport({
    date_from: dateFrom,
    date_to: dateTo,
    group_by: groupBy,
  });

  const csvUrl = `/api/feed/shrinkage-report/?date_from=${dateFrom}&date_to=${dateTo}&group_by=${groupBy}`;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Потери от усушки</h1>
          <div className="sub">
            Списания через <strong>StockMovement(kind=shrinkage)</strong> за период
            <strong> {dateFrom}</strong> — <strong>{dateTo}</strong>
          </div>
        </div>
        <div className="actions">
          <ExportCsvButton
            url={csvUrl}
            filename={`feed-shrinkage-${groupBy}-${dateFrom}-${dateTo}.csv`}
          />
        </div>
      </div>

      <Panel title="Период и группировка" flush>
        <div style={{ padding: 12, display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <DateRangeFilter
            dateFrom={dateFrom}
            dateTo={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
          />
          <div>
            <label className="label" style={{ display: 'block', fontSize: 11, marginBottom: 6 }}>
              Группировать по
            </label>
            <Seg
              value={groupBy}
              onChange={(v) => setGroupBy(v as 'ingredient' | 'warehouse')}
              options={[
                { value: 'ingredient', label: 'Ингредиент' },
                { value: 'warehouse', label: 'Склад' },
              ]}
            />
          </div>
        </div>
      </Panel>

      <div className="kpi-row" style={{ marginTop: 12 }}>
        <KpiCard
          tone="orange"
          iconName="bag"
          label="Списано всего"
          sub={`${data?.rows.length ?? 0} строки`}
          value={data ? fmtKg(data.summary.total_loss_kg) : '…'}
        />
        <KpiCard
          tone="red"
          iconName="chart"
          label="Стоимость потерь"
          sub="по unit_price партии"
          value={data ? fmtMoney(data.summary.total_loss_uzs) : '…'}
        />
      </div>

      <div style={{ marginTop: 14 }}>
        <Panel title={groupBy === 'ingredient' ? 'По ингредиентам' : 'По складам'} flush>
          <DataTable<ShrinkageReportRow>
            isLoading={isLoading}
            error={error}
            rows={data?.rows ?? []}
            rowKey={(r) => r.key ?? r.label}
            emptyMessage="За выбранный период списаний усушки нет."
            columns={[
              { key: 'label', label: groupBy === 'ingredient' ? 'Ингредиент' : 'Склад', render: (r) => r.label },
              { key: 'kg', label: 'Списано', mono: true, align: 'right', render: (r) => fmtKg(r.total_loss_kg) },
              { key: 'uzs', label: 'Стоимость', mono: true, align: 'right', render: (r) => fmtMoney(r.total_loss_uzs) },
            ]}
            footer={data && data.rows.length > 0 ? (
              <tr style={{ fontWeight: 700, background: 'var(--bg-subtle)' }}>
                <td>Итого</td>
                <td className="num">{fmtKg(data.summary.total_loss_kg)}</td>
                <td className="num">{fmtMoney(data.summary.total_loss_uzs)}</td>
              </tr>
            ) : undefined}
          />
        </Panel>
      </div>
    </>
  );
}
