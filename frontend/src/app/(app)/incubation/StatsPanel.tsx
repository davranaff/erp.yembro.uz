'use client';

import KpiCard from '@/components/ui/KpiCard';
import { useIncubationStats } from '@/hooks/useIncubation';
import type { IncubationRun } from '@/types/auth';

interface Props {
  run: IncubationRun;
}

function fmtPct(v: string | null): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toFixed(1) + '%';
}

export default function StatsPanel({ run }: Props) {
  const { data: stats } = useIncubationStats(run.id);

  const dayValue = stats
    ? `${stats.current_day}/${run.days_total}`
    : `${run.current_day ?? 0}/${run.days_total}`;
  const daysLeft = stats?.days_remaining ?? Math.max(0, run.days_total - (run.current_day ?? 0));

  return (
    <div
      className="kpi-row"
      style={{ marginBottom: 12, gridTemplateColumns: 'repeat(4, 1fr)' }}
    >
      <KpiCard
        tone="orange"
        iconName="incubator"
        label="День инкубации"
        sub={`осталось ${daysLeft}`}
        value={dayValue}
      />
      <KpiCard
        tone="green"
        iconName="check"
        label="Выводимость"
        sub={
          stats?.hatched_count != null
            ? `выведено ${stats.hatched_count.toLocaleString('ru-RU')}`
            : 'после вывода'
        }
        value={fmtPct(stats?.hatchability_pct ?? null)}
      />
      <KpiCard
        tone="red"
        iconName="egg"
        label="Отход"
        sub={
          stats?.discarded_count != null
            ? `отбраковано ${stats.discarded_count.toLocaleString('ru-RU')}`
            : 'неоплод+смертность'
        }
        value={fmtPct(stats?.mortality_pct ?? null)}
      />
      <KpiCard
        tone="blue"
        iconName="chart"
        label="В шкафу сейчас"
        sub={
          stats?.last_regime_temp_c
            ? `последний замер · ${stats.regime_days_count} зам.`
            : 'нет замеров'
        }
        value={
          stats?.last_regime_temp_c
            ? `${stats.last_regime_temp_c}° / ${stats.last_regime_humidity_pct ?? '—'}%`
            : '—'
        }
      />
    </div>
  );
}
