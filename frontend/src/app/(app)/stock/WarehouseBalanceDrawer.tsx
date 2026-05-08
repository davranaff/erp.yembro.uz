'use client';

import { Fragment } from 'react';

import DetailDrawer from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import {
  useWarehouseBalance,
  type WarehouseBalanceRow,
} from '@/hooks/useStockMovements';
import type { WarehouseRef } from '@/types/auth';

interface Props {
  warehouse: WarehouseRef;
  onClose: () => void;
  /** Клик по строке номенклатуры — открыть историю движений этого SKU. */
  onRowClick?: (row: WarehouseBalanceRow) => void;
}

function fmt(n: string, digits = 2): string {
  const v = parseFloat(n || '0');
  if (Number.isNaN(v)) return '—';
  return v.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

/**
 * Drawer с остатками склада: для каждой номенклатуры показывает Σ приход,
 * Σ расход, текущий баланс. Сортировка: с балансом сверху, исчерпанные снизу.
 */
export default function WarehouseBalanceDrawer({ warehouse, onClose, onRowClick }: Props) {
  const { data, isLoading, error } = useWarehouseBalance(warehouse.id);

  return (
    <DetailDrawer
      title={`${warehouse.code} · ${warehouse.name}`}
      subtitle={
        data
          ? `Остатков: ${data.summary.with_balance} / SKU всего: ${data.summary.sku_count}`
          : 'Загрузка…'
      }
      onClose={onClose}
    >
      {isLoading && (
        <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Загрузка…</div>
      )}
      {error && (
        <div style={{ padding: 12, color: 'var(--danger)', fontSize: 13 }}>
          Ошибка: {error.message}
        </div>
      )}
      {data && data.rows.length === 0 && (
        <div style={{
          padding: 24, color: 'var(--fg-3)', fontSize: 13, textAlign: 'center',
        }}>
          На этом складе нет движений.
        </div>
      )}
      {data && data.rows.length > 0 && (
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
              <th style={{ padding: '6px 10px' }}>SKU</th>
              <th style={{ padding: '6px 10px', textAlign: 'right' }}>Σ Приход</th>
              <th style={{ padding: '6px 10px', textAlign: 'right' }}>Σ Расход</th>
              <th style={{ padding: '6px 10px', textAlign: 'right' }}>Остаток</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => {
              const bal = parseFloat(r.balance_qty);
              const tone = bal > 0 ? 'success' : bal < 0 ? 'danger' : 'neutral';
              const hasLots = (r.lots?.length ?? 0) > 0;
              return (
                <Fragment key={r.nomenclature_id}>
                  <tr
                    onClick={onRowClick ? () => onRowClick(r) : undefined}
                    style={{
                      borderBottom: hasLots ? 'none' : '1px solid var(--border)',
                      cursor: onRowClick ? 'pointer' : 'default',
                    }}
                    title={onRowClick ? 'Открыть историю движений' : undefined}
                  >
                    <td style={{ padding: '6px 10px' }}>
                      <div className="mono" style={{ fontWeight: 500 }}>{r.sku}</div>
                      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{r.name}</div>
                    </td>
                    <td className="mono" style={{
                      padding: '6px 10px', textAlign: 'right',
                      color: 'var(--success)',
                    }}>
                      +{fmt(r.incoming_qty, 2)}
                    </td>
                    <td className="mono" style={{
                      padding: '6px 10px', textAlign: 'right',
                      color: 'var(--danger)',
                    }}>
                      −{fmt(r.outgoing_qty, 2)}
                    </td>
                    <td style={{ padding: '6px 10px', textAlign: 'right' }}>
                      <Badge tone={tone}>
                        <span className="mono" style={{ fontWeight: 600 }}>
                          {fmt(r.balance_qty, 2)} {r.unit}
                        </span>
                      </Badge>
                    </td>
                  </tr>
                  {hasLots && (
                    <tr style={{
                      borderBottom: '1px solid var(--border)',
                      background: 'var(--bg-soft)',
                    }}>
                      <td colSpan={4} style={{ padding: '4px 10px 8px 24px' }}>
                        <div style={{
                          fontSize: 10, fontWeight: 700, color: 'var(--fg-3)',
                          textTransform: 'uppercase', letterSpacing: '.04em',
                          marginBottom: 4,
                        }}>
                          Лоты ({r.lots!.length}):
                        </div>
                        {r.lots!.map((lot) => {
                          const exp = lot.expiration_date ? new Date(lot.expiration_date) : null;
                          const days = exp ? Math.floor((exp.getTime() - Date.now()) / 86400000) : null;
                          const expColor = days == null ? 'var(--fg-3)'
                            : days < 30 ? 'var(--danger)'
                            : days < 90 ? 'var(--brand-orange)' : 'var(--fg-2)';
                          return (
                            <div key={lot.id} style={{
                              display: 'flex', justifyContent: 'space-between',
                              gap: 10, padding: '2px 0', fontSize: 11,
                            }}>
                              <span className="mono" style={{ color: 'var(--fg-2)' }}>
                                {lot.lot_number} <span style={{ color: 'var(--fg-3)' }}>· {lot.doc_number}</span>
                              </span>
                              <span className="mono" style={{ color: expColor }}>
                                до {lot.expiration_date ?? '—'}
                                {days != null && (
                                  <span style={{ marginLeft: 4 }}>
                                    ({days < 0 ? `просрочен ${-days} дн` : `${days} дн`})
                                  </span>
                                )}
                              </span>
                              <span className="mono" style={{ fontWeight: 600 }}>
                                {fmt(lot.current_quantity, 2)} {r.unit}
                              </span>
                            </div>
                          );
                        })}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </DetailDrawer>
  );
}
