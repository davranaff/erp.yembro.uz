'use client';

export interface TablePaginationProps {
  page: number;
  pageSize: number;
  count: number;
  onPageChange: (next: number) => void;
  onPageSizeChange?: (next: number) => void;
  pageSizeOptions?: number[];
  hasPrev?: boolean;
  hasNext?: boolean;
}

const DEFAULT_OPTIONS = [25, 50, 100, 200];

export default function TablePagination({
  page,
  pageSize,
  count,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_OPTIONS,
  hasPrev,
  hasNext,
}: TablePaginationProps) {
  if (count <= Math.min(...pageSizeOptions)) return null;

  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const prevDisabled = hasPrev !== undefined ? !hasPrev : page <= 1;
  const nextDisabled = hasNext !== undefined ? !hasNext : page >= totalPages;

  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(count, page * pageSize);

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      alignItems: 'center', padding: '10px 14px',
      borderTop: '1px solid var(--border)',
      fontSize: 12, color: 'var(--fg-3)',
      flexWrap: 'wrap', gap: 12,
    }}>
      <span style={{ whiteSpace: 'nowrap' }}>
        <b style={{ color: 'var(--fg-1)' }}>{from}–{to}</b> из {count}
        <span style={{ margin: '0 8px', opacity: 0.4 }}>·</span>
        стр. <b style={{ color: 'var(--fg-1)' }}>{page}</b> / {totalPages}
      </span>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'nowrap' }}>
        {onPageSizeChange && (
          <label style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            whiteSpace: 'nowrap', fontSize: 12, color: 'var(--fg-3)',
          }}>
            На странице
            <select
              className="input"
              style={{
                height: 28, padding: '0 22px 0 8px', fontSize: 12,
                width: 'auto', minWidth: 64,
              }}
              value={pageSize}
              onChange={(e) => {
                const next = Number(e.target.value);
                onPageChange(1);
                onPageSizeChange(next);
              }}
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
        )}
        <button
          className="btn btn-ghost btn-sm"
          style={{ whiteSpace: 'nowrap' }}
          disabled={prevDisabled}
          onClick={() => onPageChange(Math.max(1, page - 1))}
        >
          ← Назад
        </button>
        <button
          className="btn btn-ghost btn-sm"
          style={{ whiteSpace: 'nowrap' }}
          disabled={nextDisabled}
          onClick={() => onPageChange(page + 1)}
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}
