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
      alignItems: 'center', padding: '8px 12px',
      borderTop: '1px solid var(--border)',
      fontSize: 12, color: 'var(--fg-3)',
      flexWrap: 'wrap', gap: 8,
    }}>
      <span>
        {from}–{to} из {count} · стр. {page} / {totalPages}
      </span>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {onPageSizeChange && (
          <>
            <span>На странице:</span>
            <select
              className="input"
              style={{ height: 24, padding: '0 6px', fontSize: 12 }}
              value={pageSize}
              onChange={(e) => {
                onPageSizeChange(Number(e.target.value));
                onPageChange(1);
              }}
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </>
        )}
        <button
          className="btn btn-ghost btn-sm"
          disabled={prevDisabled}
          onClick={() => onPageChange(Math.max(1, page - 1))}
        >
          ← Назад
        </button>
        <button
          className="btn btn-ghost btn-sm"
          disabled={nextDisabled}
          onClick={() => onPageChange(page + 1)}
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}
