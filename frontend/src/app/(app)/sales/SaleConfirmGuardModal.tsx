'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useConfirmSale, useCreditCheck } from '@/hooks/useSales';
import { useHasLevel } from '@/hooks/usePermissions';
import type { SaleOrder } from '@/types/auth';

interface Props {
  order: SaleOrder;
  onClose: () => void;
  onSuccess?: () => void;
}

function fmt(uzs: string | null): string {
  if (uzs == null || uzs === '') return '—';
  const n = parseFloat(uzs);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

/**
 * Гейт перед confirm продажи.
 *
 * Дёргает /credit_check/, показывает текущий долг клиента / лимит /
 * максимальную просрочку. Если ok — сразу confirm. Если нет — показывает
 * причины + (для sales:admin) чекбокс «Провести с overrides».
 */
export default function SaleConfirmGuardModal({ order, onClose, onSuccess }: Props) {
  const { data: check, isLoading } = useCreditCheck(order.id);
  const confirmMutation = useConfirmSale();
  const hasLevel = useHasLevel();
  const isAdmin = hasLevel('sales', 'admin');

  const [override, setOverride] = useState(false);

  const blocked = check && !check.ok;
  const canConfirm = check && (check.ok || (blocked && isAdmin && override));

  const error = confirmMutation.error;
  const errorMessage = error instanceof ApiError && error.status === 400
    ? (() => {
        const data = error.data as Record<string, unknown> | undefined;
        const customer = data?.customer;
        if (Array.isArray(customer)) return customer.join(' · ');
        if (typeof customer === 'string') return customer;
        return error.message;
      })()
    : error?.message ?? null;

  const submit = () => {
    confirmMutation.mutate(
      { id: order.id, body: { force_credit_override: blocked ? override : false } },
      {
        onSuccess: () => {
          onSuccess?.();
          onClose();
        },
      },
    );
  };

  return (
    <Modal
      title={`Провести продажу · ${order.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={confirmMutation.isPending}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={!canConfirm || confirmMutation.isPending}
            onClick={submit}
            style={blocked && override ? { background: 'var(--danger)' } : undefined}
          >
            {confirmMutation.isPending ? 'Проведение…' : (blocked && override ? 'Провести с override' : 'Провести')}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Клиент: <b>{order.customer_name ?? '—'}</b> · Сумма продажи:{' '}
        <span className="mono">{fmt(check?.new_sale_uzs ?? null)}</span>
      </div>

      {isLoading && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Проверяем кредит клиента…</div>
      )}

      {check && (
        <>
          <div style={{
            padding: 10, marginBottom: 12, borderRadius: 6,
            background: check.ok ? 'var(--bg-soft)' : '#fef2f2',
            border: `1px solid ${check.ok ? 'var(--border)' : 'var(--danger)'}`,
            fontSize: 12,
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ color: 'var(--fg-3)' }}>Текущий долг</div>
                <div className="mono" style={{ fontWeight: 600 }}>{fmt(check.current_debt_uzs)}</div>
              </div>
              <div>
                <div style={{ color: 'var(--fg-3)' }}>После продажи</div>
                <div className="mono" style={{ fontWeight: 600 }}>{fmt(check.projected_debt_uzs)}</div>
              </div>
              <div>
                <div style={{ color: 'var(--fg-3)' }}>Кредитный лимит</div>
                <div className="mono">
                  {check.limit_uzs ? fmt(check.limit_uzs) : 'не задан'}
                </div>
              </div>
              <div>
                <div style={{ color: 'var(--fg-3)' }}>Макс. просрочка</div>
                <div className="mono">
                  {check.max_overdue_days != null
                    ? `${check.max_overdue_days} дн (сейчас ${check.oldest_overdue_days})`
                    : 'не задана'}
                </div>
              </div>
            </div>
          </div>

          {blocked && (
            <div style={{
              padding: 10, marginBottom: 12, borderRadius: 6,
              background: '#fef2f2', border: '1px solid var(--danger)',
              fontSize: 12, color: 'var(--danger)',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                ⚠ Кредитная политика блокирует продажу:
              </div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {check.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}

          {blocked && isAdmin && (
            <label style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              padding: 10, background: 'var(--bg-soft)', borderRadius: 6,
              fontSize: 12, cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={override}
                onChange={(e) => setOverride(e.target.checked)}
                style={{ marginTop: 2 }}
              />
              <span>
                Провести с <b>force_credit_override</b> — игнорировать
                кредитную политику. Действие логируется в audit, ваше имя
                будет видно в истории клиента.
              </span>
            </label>
          )}

          {blocked && !isAdmin && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              Override доступен только sales:admin. Свяжитесь с владельцем
              если нужно провести продажу несмотря на превышение лимита.
            </div>
          )}
        </>
      )}

      {errorMessage && (
        <div style={{ marginTop: 10, padding: 8, fontSize: 12, color: 'var(--danger)', background: '#fef2f2', borderRadius: 4 }}>
          {errorMessage}
        </div>
      )}
    </Modal>
  );
}
