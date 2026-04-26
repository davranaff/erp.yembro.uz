'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { useCurrenciesSorted, useLatestRates, useSyncCbuRates } from '@/hooks/useCurrencyRates';
import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { ExchangeRate, Paginated } from '@/types/auth';

/** Архив курсов для валюты (с фильтром по периоду). */
function useRatesHistory(currencyCode: string, dateFrom: string, dateTo: string) {
  const enabled = Boolean(currencyCode);
  return useQuery<ExchangeRate[], ApiError>({
    queryKey: ['currency', 'rates', 'history', currencyCode, dateFrom, dateTo],
    enabled,
    queryFn: async () => {
      const qs = new URLSearchParams({
        currency: currencyCode,
        ordering: '-date',
        page_size: '1000',
      });
      if (dateFrom) qs.set('date_after', dateFrom);
      if (dateTo) qs.set('date_before', dateTo);
      const data = await apiFetch<Paginated<ExchangeRate> | ExchangeRate[]>(
        `/api/currency/rates/?${qs.toString()}`,
        { skipOrg: true },
      );
      return asList(data);
    },
    staleTime: 60_000,
  });
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function fmtRate(r: string): string {
  return parseFloat(r).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

export default function RatesHistoryPage() {
  const [code, setCode] = useState('USD');
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(30));
  const [dateTo, setDateTo] = useState(todayISO());

  const { data: currencies } = useCurrenciesSorted();
  const { data: latest } = useLatestRates();
  const { data: history, isLoading: historyLoading } = useRatesHistory(code, dateFrom, dateTo);
  const sync = useSyncCbuRates();

  // Вычисления: изменения курса за период
  const stats = useMemo(() => {
    if (!history || history.length === 0) return null;
    const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date));
    const first = parseFloat(sorted[0].rate);
    const last = parseFloat(sorted[sorted.length - 1].rate);
    const delta = last - first;
    const deltaPct = first > 0 ? (delta / first) * 100 : 0;
    const rates = sorted.map((r) => parseFloat(r.rate));
    const max = Math.max(...rates);
    const min = Math.min(...rates);
    return { first, last, delta, deltaPct, max, min, count: sorted.length };
  }, [history]);

  const currentLatest = latest?.find((r) => r.currency_code === code);

  const handleSync = () => {
    sync.mutate(undefined, {
      onError: (e) => alert('Не удалось синхронизировать: ' + e.message),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Архив курсов валют</h1>
          <div className="sub">
            История курсов ЦБ Узбекистана ·{' '}
            <a href="https://cbu.uz/ru/arkhiv-kursov-valyut/" target="_blank" rel="noreferrer"
               style={{ color: 'var(--brand-orange)' }}>
              cbu.uz
            </a>
          </div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleSync}
            disabled={sync.isPending}
          >
            <Icon name="chart" size={14} />
            {sync.isPending ? 'Синхронизация…' : 'Синхронизировать с ЦБ'}
          </button>
        </div>
      </div>

      {/* KPI для выбранной валюты */}
      {stats && currentLatest && (
        <div className="kpi-row" style={{ marginBottom: 12 }}>
          <KpiCard
            tone="orange"
            iconName="chart"
            label={`${code} сейчас`}
            sub={'на ' + currentLatest.date}
            value={fmtRate(currentLatest.rate) + ' сум'}
          />
          <KpiCard
            tone={stats.delta >= 0 ? 'red' : 'green'}
            iconName={stats.delta >= 0 ? 'arrow-right' : 'check'}
            label="Изменение за период"
            sub={`${stats.deltaPct >= 0 ? '+' : ''}${stats.deltaPct.toFixed(2)}%`}
            value={(stats.delta >= 0 ? '+' : '') + fmtRate(String(stats.delta)) + ' сум'}
          />
          <KpiCard
            tone="blue"
            iconName="chart"
            label="Max / Min"
            sub={`за период`}
            value={`${fmtRate(String(stats.max))} / ${fmtRate(String(stats.min))}`}
          />
          <KpiCard
            tone="green"
            iconName="book"
            label="Записей в архиве"
            sub="для этой валюты"
            value={String(stats.count)}
          />
        </div>
      )}

      {/* Фильтры */}
      <div className="filter-bar">
        <div className="filter-cell" style={{ minWidth: 160 }}>
          <label>Валюта</label>
          <select className="input" value={code} onChange={(e) => setCode(e.target.value)}>
            {currencies?.map((c) => (
              <option key={c.id} value={c.code}>{c.code} · {c.name_ru}</option>
            ))}
          </select>
        </div>
        <div className="filter-cell">
          <label>С</label>
          <input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="filter-cell">
          <label>По</label>
          <input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="filter-cell">
          <label>Пресет</label>
          <div className="filter-presets">
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(7)); setDateTo(todayISO()); }}>
              7 дн
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(30)); setDateTo(todayISO()); }}>
              30 дн
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(90)); setDateTo(todayISO()); }}>
              90 дн
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDateFrom(isoDaysAgo(365)); setDateTo(todayISO()); }}>
              Год
            </button>
          </div>
        </div>
      </div>

      {/* Таблица истории */}
      <Panel flush>
        <DataTable<ExchangeRate>
          isLoading={historyLoading}
          rows={history}
          rowKey={(r) => r.id}
          emptyMessage="Нет данных за выбранный период. Попробуйте расширить диапазон или запустите синхронизацию ЦБ."
          columns={[
            { key: 'date', label: 'Дата', mono: true, render: (r) => r.date },
            { key: 'rate', label: 'Курс (за номинал)', align: 'right', mono: true,
              render: (r) => fmtRate(r.rate) },
            { key: 'nominal', label: 'Номинал', align: 'right', mono: true, muted: true,
              render: (r) => r.nominal },
            { key: 'perUnit', label: 'Курс за 1 ед.', align: 'right', mono: true,
              cellStyle: { fontWeight: 600 },
              render: (r) => fmtRate(String(parseFloat(r.rate) / (r.nominal || 1))) },
            { key: 'delta', label: 'Δ к пред. дню', align: 'right', mono: true,
              render: (r, idx) => {
                const all = history ?? [];
                const perUnit = parseFloat(r.rate) / (r.nominal || 1);
                const prev = all[idx + 1];
                const prevUnit = prev ? parseFloat(prev.rate) / (prev.nominal || 1) : null;
                const delta = prevUnit !== null ? perUnit - prevUnit : null;
                const deltaPct = delta !== null && prevUnit ? (delta / prevUnit) * 100 : null;
                const color = delta === null ? 'var(--fg-3)' : delta > 0 ? 'var(--danger)' : delta < 0 ? 'var(--success)' : 'var(--fg-3)';
                return (
                  <span style={{ color }}>
                    {delta === null ? '—' : (
                      <>
                        {delta > 0 ? '+' : ''}{fmtRate(String(delta))}
                        {deltaPct !== null && (
                          <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 4 }}>
                            ({deltaPct > 0 ? '+' : ''}{deltaPct.toFixed(2)}%)
                          </span>
                        )}
                      </>
                    )}
                  </span>
                );
              } },
            { key: 'source', label: 'Источник', mono: true, muted: true,
              render: (r) => r.source },
            { key: 'fetched_at', label: 'Получено', mono: true, muted: true,
              render: (r) => r.fetched_at ? new Date(r.fetched_at).toLocaleString('ru-RU') : '—' },
          ]}
        />
      </Panel>

      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--fg-3)' }}>
        Курсы синхронизируются автоматически ежедневно в 10:00 (Ташкент). Источник: ЦБ Узбекистана.
        При проведении закупки или продажи в иностранной валюте текущий курс фиксируется в документе
        и больше не меняется.
      </div>
    </>
  );
}
