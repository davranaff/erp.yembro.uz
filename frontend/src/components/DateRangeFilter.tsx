'use client';

interface Props {
  dateFrom: string;
  dateTo: string;
  onChange: (dateFrom: string, dateTo: string) => void;
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoMonthsAgo(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}

function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}

function startOfYear(): string {
  const d = new Date();
  return `${d.getFullYear()}-01-01`;
}

function startOfQuarter(): string {
  const d = new Date();
  const m = Math.floor(d.getMonth() / 3) * 3;
  return new Date(d.getFullYear(), m, 1).toISOString().slice(0, 10);
}

/**
 * Универсальный фильтр периода с пресетами.
 * Используется в /reports и в любом месте где нужен «date_from / date_to».
 */
export default function DateRangeFilter({ dateFrom, dateTo, onChange }: Props) {
  const today = isoToday();

  const presets = [
    { label: 'Месяц', from: startOfMonth(), to: today },
    { label: 'Квартал', from: startOfQuarter(), to: today },
    { label: 'YTD', from: startOfYear(), to: today },
    { label: 'Год', from: isoMonthsAgo(12), to: today },
  ];

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
      <div className="field" style={{ marginBottom: 0 }}>
        <label style={{ fontSize: 11 }}>С</label>
        <input
          className="input"
          type="date"
          value={dateFrom}
          onChange={(e) => onChange(e.target.value, dateTo)}
          style={{ width: 140 }}
        />
      </div>
      <div className="field" style={{ marginBottom: 0 }}>
        <label style={{ fontSize: 11 }}>По</label>
        <input
          className="input"
          type="date"
          value={dateTo}
          onChange={(e) => onChange(dateFrom, e.target.value)}
          style={{ width: 140 }}
        />
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        {presets.map((p) => (
          <button
            key={p.label}
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onChange(p.from, p.to)}
            style={{ fontSize: 11 }}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}
