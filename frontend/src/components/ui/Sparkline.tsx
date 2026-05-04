'use client';

import { useMemo } from 'react';

interface Props {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  /** Если задан — подсвечивается последняя точка маркером. */
  showLastDot?: boolean;
  /** Вспомогательный ARIA-label. */
  label?: string;
}

/**
 * Минималистичный SVG-sparkline. Без зависимостей.
 * Если values все одинаковые / пустые — рисуется плоская линия по центру.
 */
export default function Sparkline({
  values,
  width = 160,
  height = 40,
  stroke = 'var(--brand-orange)',
  fill = 'rgba(232, 117, 26, 0.12)',
  showLastDot = true,
  label,
}: Props) {
  const { path, areaPath, lastX, lastY } = useMemo(() => {
    if (values.length === 0) {
      return { path: '', areaPath: '', lastX: 0, lastY: 0 };
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const stepX = values.length > 1 ? width / (values.length - 1) : 0;
    const pts = values.map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return { x, y };
    });
    const pathStr = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(' ');
    const areaStr = pathStr + ` L${width},${height} L0,${height} Z`;
    const last = pts[pts.length - 1];
    return { path: pathStr, areaPath: areaStr, lastX: last.x, lastY: last.y };
  }, [values, width, height]);

  if (values.length === 0) {
    return (
      <svg width={width} height={height} aria-label={label}>
        <line
          x1="0" y1={height / 2} x2={width} y2={height / 2}
          stroke="var(--border)" strokeDasharray="3 3"
        />
      </svg>
    );
  }

  return (
    <svg width={width} height={height} aria-label={label}>
      <path d={areaPath} fill={fill} />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" />
      {showLastDot && (
        <circle cx={lastX} cy={lastY} r="2.5" fill={stroke} />
      )}
    </svg>
  );
}
