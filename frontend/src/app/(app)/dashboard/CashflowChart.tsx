'use client';

import { useMemo } from 'react';

import type { CashflowPoint } from '@/types/auth';

interface Props {
  points: CashflowPoint[];
  height?: number;
}

/**
 * SVG бар-чарт cashflow: на каждую дату — пара столбиков (in вверх, out вниз).
 * Справа — линия накопительного остатка (running balance).
 */
export default function CashflowChart({ points, height = 220 }: Props) {
  const data = useMemo(() => {
    return points.map((p) => ({
      date: p.date,
      inUzs: parseFloat(p.in_uzs) || 0,
      outUzs: parseFloat(p.out_uzs) || 0,
    }));
  }, [points]);

  const W = 880;
  const H = height;
  const PAD_L = 50;
  const PAD_R = 16;
  const PAD_T = 16;
  const PAD_B = 28;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  const maxAbs = useMemo(() => {
    if (data.length === 0) return 1;
    const vals = data.flatMap((d) => [d.inUzs, d.outUzs]);
    const m = Math.max(...vals);
    return m === 0 ? 1 : m;
  }, [data]);

  // Cumulative balance line — net = in − out, running sum starting at 0.
  const balance = useMemo(() => {
    const arr: number[] = [];
    let s = 0;
    for (const d of data) {
      s += d.inUzs - d.outUzs;
      arr.push(s);
    }
    return arr;
  }, [data]);

  const balMin = balance.length > 0 ? Math.min(...balance, 0) : 0;
  const balMax = balance.length > 0 ? Math.max(...balance, 0) : 1;
  const balRange = balMax - balMin || 1;

  if (data.length === 0) {
    return (
      <div style={{
        height,
        display: 'grid',
        placeItems: 'center',
        color: 'var(--fg-3)',
        fontSize: 13,
      }}>
        Нет данных за период.
      </div>
    );
  }

  const stepX = innerW / data.length;
  const barW = Math.max(2, stepX * 0.4);
  const midY = PAD_T + innerH / 2;

  // Y-axis ticks (4 horizontal grid lines)
  const grid = [0.25, 0.5, 0.75, 1].map((t) => midY - t * (innerH / 2));
  const gridBottom = [0.25, 0.5, 0.75, 1].map((t) => midY + t * (innerH / 2));

  // Date labels — every Nth tick
  const labelStep = Math.ceil(data.length / 8);
  const labels = data
    .map((d, i) => ({ d, i }))
    .filter((p) => p.i % labelStep === 0);

  // Balance line points
  const balancePts = balance.map((v, i) => {
    const x = PAD_L + i * stepX + stepX / 2;
    // Map balance into the upper-half coordinate space (we'll use full height, scaled)
    const y = PAD_T + innerH - ((v - balMin) / balRange) * innerH;
    return { x, y };
  });
  const balancePath = balancePts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');

  function fmtCompact(v: number): string {
    if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(0) + 'K';
    return v.toFixed(0);
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height, display: 'block' }}>
      {/* horizontal grid */}
      {grid.map((y, i) => (
        <line
          key={'gt' + i}
          x1={PAD_L}
          x2={W - PAD_R}
          y1={y}
          y2={y}
          stroke="var(--border-subtle)"
          strokeDasharray="2 3"
        />
      ))}
      {gridBottom.map((y, i) => (
        <line
          key={'gb' + i}
          x1={PAD_L}
          x2={W - PAD_R}
          y1={y}
          y2={y}
          stroke="var(--border-subtle)"
          strokeDasharray="2 3"
        />
      ))}
      {/* zero baseline */}
      <line
        x1={PAD_L}
        x2={W - PAD_R}
        y1={midY}
        y2={midY}
        stroke="var(--border)"
        strokeWidth="1"
      />

      {/* y-axis ticks (in/out scale) */}
      <text
        x={PAD_L - 6}
        y={PAD_T + 4}
        fontSize="10"
        fill="var(--fg-3)"
        fontFamily="var(--font-mono)"
        textAnchor="end"
      >
        +{fmtCompact(maxAbs)}
      </text>
      <text
        x={PAD_L - 6}
        y={midY + 4}
        fontSize="10"
        fill="var(--fg-3)"
        fontFamily="var(--font-mono)"
        textAnchor="end"
      >
        0
      </text>
      <text
        x={PAD_L - 6}
        y={H - PAD_B + 4}
        fontSize="10"
        fill="var(--fg-3)"
        fontFamily="var(--font-mono)"
        textAnchor="end"
      >
        −{fmtCompact(maxAbs)}
      </text>

      {/* bars */}
      {data.map((d, i) => {
        const cx = PAD_L + i * stepX + stepX / 2;
        const inH = (d.inUzs / maxAbs) * (innerH / 2);
        const outH = (d.outUzs / maxAbs) * (innerH / 2);
        return (
          <g key={d.date}>
            {/* IN bar (green, above baseline) */}
            {inH > 0 && (
              <rect
                x={cx - barW - 0.5}
                y={midY - inH}
                width={barW}
                height={inH}
                fill="var(--success)"
                opacity="0.85"
              >
                <title>{`${d.date} · приход +${d.inUzs.toLocaleString('ru-RU')} UZS`}</title>
              </rect>
            )}
            {/* OUT bar (red, below baseline) */}
            {outH > 0 && (
              <rect
                x={cx + 0.5}
                y={midY}
                width={barW}
                height={outH}
                fill="var(--danger)"
                opacity="0.85"
              >
                <title>{`${d.date} · расход −${d.outUzs.toLocaleString('ru-RU')} UZS`}</title>
              </rect>
            )}
          </g>
        );
      })}

      {/* balance line */}
      <path
        d={balancePath}
        fill="none"
        stroke="var(--brand-orange)"
        strokeWidth="2"
        strokeLinejoin="round"
        opacity="0.7"
      />

      {/* date labels */}
      {labels.map(({ d, i }) => {
        const x = PAD_L + i * stepX + stepX / 2;
        const dt = new Date(d.date);
        const lbl = `${dt.getDate()}.${(dt.getMonth() + 1).toString().padStart(2, '0')}`;
        return (
          <text
            key={d.date}
            x={x}
            y={H - 8}
            fontSize="9"
            fill="var(--fg-3)"
            fontFamily="var(--font-mono)"
            textAnchor="middle"
          >
            {lbl}
          </text>
        );
      })}

      {/* legend */}
      <g transform={`translate(${PAD_L + 8}, ${PAD_T + 8})`}>
        <rect width="10" height="10" fill="var(--success)" opacity="0.85" />
        <text x="14" y="9" fontSize="10" fill="var(--fg-2)">Приход</text>
        <rect x="74" width="10" height="10" fill="var(--danger)" opacity="0.85" />
        <text x="88" y="9" fontSize="10" fill="var(--fg-2)">Расход</text>
        <line x1="148" y1="5" x2="158" y2="5" stroke="var(--brand-orange)" strokeWidth="2" />
        <text x="162" y="9" fontSize="10" fill="var(--fg-2)">Накоп. остаток</text>
      </g>
    </svg>
  );
}
