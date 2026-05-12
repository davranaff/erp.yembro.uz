'use client';

import { useEffect, useRef, useState } from 'react';

import AmountInput from '@/components/ui/AmountInput';
import { useCreateAdjustment } from '@/hooks/usePayroll';

interface Props {
  employeeId: string;
  employeeName: string;
  kind: 'bonus' | 'deduction';
  /** Координаты якоря (right/top строки таблицы) для позиционирования. */
  anchor: { top: number; left: number };
  onClose: () => void;
}

const PLUS_REASONS = [
  'Премия',
  'Доплата за переработку',
  'Доплата за выполнение',
  'Доплата (прочее)',
];
const MINUS_REASONS = [
  'Опоздание',
  'Штраф',
  'Невыход',
  'Удержание (прочее)',
];

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/**
 * Быстрая корректировка ЗП за текущий день. HR жмёт ± у строки сотрудника
 * — попап появляется рядом, заполнил сумму + причину → save → POST на
 * /api/payroll/adjustments/ с effective_date=today.
 */
export default function QuickAdjustmentPopover({
  employeeId, employeeName, kind, anchor, onClose,
}: Props) {
  const reasons = kind === 'bonus' ? PLUS_REASONS : MINUS_REASONS;
  const [amount, setAmount] = useState('');
  const [reasonPreset, setReasonPreset] = useState(reasons[0]);
  const [customReason, setCustomReason] = useState('');
  const isCustom = reasonPreset === 'Прочее' || reasonPreset.endsWith('(прочее)');
  const ref = useRef<HTMLDivElement>(null);
  const create = useCreateAdjustment();

  // Закрытие по клику вне попапа и Escape.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  const canSave = Boolean(amount) && parseFloat(amount.replace(/\s/g, '')) > 0
    && !create.isPending;

  const handleSave = async () => {
    const amt = amount.replace(/\s/g, '');
    const reason = isCustom ? customReason.trim() : reasonPreset;
    try {
      await create.mutateAsync({
        employee: employeeId,
        kind,
        effective_date: todayISO(),
        amount_uzs: amt,
        reason,
      });
      onClose();
    } catch {
      /* mutation хранит ошибку, покажем ниже */
    }
  };

  const accent = kind === 'bonus' ? '#16a34a' : '#dc2626';
  const title = kind === 'bonus' ? '+ Добавить премию' : '− Удержать';

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top: anchor.top, left: anchor.left,
        zIndex: 1000,
        width: 280,
        background: 'var(--bg-raised, #fff)',
        border: '1px solid var(--border)',
        borderTop: `3px solid ${accent}`,
        borderRadius: 8,
        boxShadow: '0 12px 32px rgba(0,0,0,.15)',
        padding: 12,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: accent, marginBottom: 2 }}>
        {title}
      </div>
      <div style={{
        fontSize: 11, color: 'var(--fg-3)', marginBottom: 10,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {employeeName} · {todayISO()}
      </div>

      <div className="field" style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 11 }}>Сумма, UZS</label>
        <AmountInput
          className="input"
          autoFocus
          value={amount}
          onChange={setAmount}
          placeholder="100 000"
          style={{ fontSize: 14, fontWeight: 600 }}
        />
      </div>

      <div className="field" style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 11 }}>Причина</label>
        <select
          className="input"
          value={reasonPreset}
          onChange={(e) => setReasonPreset(e.target.value)}
        >
          {reasons.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      {isCustom && (
        <div className="field" style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 11 }}>Уточните</label>
          <input
            className="input"
            value={customReason}
            onChange={(e) => setCustomReason(e.target.value)}
            placeholder="Текст причины"
          />
        </div>
      )}

      {create.error && (
        <div style={{
          fontSize: 11, color: 'var(--danger)', marginBottom: 8,
          padding: 6, background: '#fef2f2', borderRadius: 4,
        }}>
          {create.error.message}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={create.isPending}>
          Отмена
        </button>
        <button
          className="btn btn-sm"
          disabled={!canSave}
          onClick={handleSave}
          style={{
            background: accent, color: '#fff', borderColor: accent,
          }}
        >
          {create.isPending ? 'Сохранение…' : 'Применить'}
        </button>
      </div>
    </div>
  );
}
