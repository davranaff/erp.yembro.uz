'use client';

import { useMemo } from 'react';

import type { BatchChainStep } from '@/types/auth';

import { moduleLabel } from './labels';

interface Props {
  steps: BatchChainStep[];
  height?: number;
}

/**
 * Visual «где набегала себестоимость» — линейный график накопленной
 * себестоимости по шагам цепочки + дельта между шагами как столбики.
 *
 * Берёт `step.accumulated_cost_at_exit` для уже завершённых шагов; для
 * текущего (без `exited_at`) — на тот же уровень что предыдущий, чтобы
 * пользователь видел «здесь ещё накапливается».
 */
export default function CostTrendChart({ steps, height = 160 }: Props) {
  const points = useMemo(() => {
    const data: { label: string; cost: number; isCurrent: boolean; delta: number }[] = [];
    let prev = 0;
    for (const s of steps) {
      const cost = parseFloat(s.accumulated_cost_at_exit ?? '0') || 0;
      const value = cost > 0 ? cost : prev;
      data.push({
        label:
          moduleLabel(s.module_code) +
          (s.block_code ? ` · ${s.block_code}` : ''),
        cost: value,
        isCurrent: s.exited_at === null,
        delta: Math.max(0, value - prev),
      });
      prev = value;
    }
    return data;
  }, [steps]);

  if (points.length === 0) {
    return (
      <div
        style={{
          height,
          display: 'grid',
          placeItems: 'center',
          color: 'var(--fg-3)',
          fontSize: 12,
        }}
      >
        Нет шагов для построения графика.
      </div>
    );
  }

  const W = 880;
  const H = height;
  const PAD_L = 60;
  const PAD_R = 16;
  const PAD_T = 14;
  const PAD_B = 38;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  const maxCost = Math.max(...points.map((p) => p.cost), 1);
  const stepX = innerW / Math.max(1, points.length - 1);

  function fmtShort(v: number): string {
    if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(0) + 'K';
    return v.toFixed(0);
  }

  // Накопительная линия
  const linePts = points.map((p, i) => {
    const x = PAD_L + (points.length === 1 ? innerW / 2 : i * stepX);
    const y = PAD_T + innerH - (p.cost / maxCost) * innerH;
    return { x, y, ...p };
  });
  const linePath = linePts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');
  const areaPath =
    linePath +
    ` L${linePts[linePts.length - 1].x.toFixed(1)},${PAD_T + innerH} ` +
    `L${linePts[0].x.toFixed(1)},${PAD_T + innerH} Z`;

  // Дельта-столбики (что прибавилось в каждом шаге)
  const barW = Math.max(8, Math.min(28, stepX * 0.4));
  const maxDelta = Math.max(...points.map((p) => p.delta), 1);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height, display: 'block' }}>
      {/* horizontal grid */}
      {[0.25, 0.5, 0.75, 1].map((t) => {
        const y = PAD_T + innerH - t * innerH;
        return (
          <g key={t}>
            <line
              x1={PAD_L}
              x2={W - PAD_R}
              y1={y}
              y2={y}
              stroke="var(--border-subtle)"
              strokeDasharray="2 3"
            />
            <text
              x={PAD_L - 6}
              y={y + 3}
              fontSize="10"
              fill="var(--fg-3)"
              fontFamily="var(--font-mono)"
              textAnchor="end"
            >
              {fmtShort(maxCost * t)}
            </text>
          </g>
        );
      })}

      {/* delta bars (за каждый шаг сколько добавилось) */}
      {linePts.map((p, i) => {
        if (p.delta <= 0) return null;
        const h = (p.delta / maxDelta) * (innerH * 0.6);
        return (
          <rect
            key={'b' + i}
            x={p.x - barW / 2}
            y={PAD_T + innerH - h}
            width={barW}
            height={h}
            fill="var(--brand-orange)"
            opacity="0.18"
          >
            <title>{`+${fmtShort(p.delta)} UZS на шаге «${p.label}»`}</title>
          </rect>
        );
      })}

      {/* area + line */}
      <path d={areaPath} fill="var(--brand-orange-soft, rgba(232,117,26,0.10))" />
      <path
        d={linePath}
        fill="none"
        stroke="var(--brand-orange)"
        strokeWidth="2"
        strokeLinejoin="round"
      />

      {/* dots */}
      {linePts.map((p, i) => (
        <g key={'d' + i}>
          <circle
            cx={p.x}
            cy={p.y}
            r={p.isCurrent ? 5 : 3.5}
            fill={p.isCurrent ? 'var(--brand-orange)' : 'var(--bg-card, #fff)'}
            stroke="var(--brand-orange)"
            strokeWidth="2"
          />
          <title>
            {`${p.label} · накопл. ${fmtShort(p.cost)} UZS`}
          </title>
        </g>
      ))}

      {/* x-axis labels */}
      {linePts.map((p, i) => {
        // На узких графиках показываем каждый второй
        if (linePts.length > 6 && i % 2 !== 0 && i !== linePts.length - 1) return null;
        return (
          <text
            key={'l' + i}
            x={p.x}
            y={H - PAD_B + 14}
            fontSize="10"
            fill="var(--fg-2)"
            textAnchor="middle"
          >
            {p.label.length > 18 ? p.label.slice(0, 16) + '…' : p.label}
          </text>
        );
      })}
      {/* helper caption */}
      <text
        x={PAD_L}
        y={H - 6}
        fontSize="10"
        fill="var(--fg-3)"
      >
        накопл. себ-ть, UZS · столбики = прирост шага
      </text>
    </svg>
  );
}
