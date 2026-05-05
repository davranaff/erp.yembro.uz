'use client';

import DetailDrawer from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import { useWarehouseBalance } from '@/hooks/useStockMovements';
import type { WarehouseRef } from '@/types/auth';

interface Props {
  warehouse: WarehouseRef;
  onClose: () => void;
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
export default function WarehouseBalanceDrawer({ warehouse, onClose }: Props) {
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
              return (
                <tr key={r.nomenclature_id} style={{ borderBottom: '1px solid var(--border)' }}>
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
              );
            })}
          </tbody>
        </table>
      )}
    </DetailDrawer>
  );
}
