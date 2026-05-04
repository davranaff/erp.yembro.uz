'use client';

import { useState } from 'react';

import Icon from '@/components/ui/Icon';
import OpexModal from '@/app/(app)/finance/cashbox/OpexModal';

interface Props {
  /** Код модуля-источника. Попадёт в Payment.module и в быстрые кнопки. */
  moduleCode: string;
  /** Стартовое направление (расход/приход). По умолчанию 'out'. */
  direction?: 'out' | 'in';
  /** Код контр-субсчёта (20.XX), который будет выбран по умолчанию. */
  suggestedContraCode?: string;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  label?: string;
}

/**
 * Кнопка «+ Операция» для page-header любого производственного модуля.
 * Открывает OpexModal с предвыбранным модулем → быстрая кнопка «НЗП модуля»
 * готова к нажатию.
 */
export default function OpexButton({
  moduleCode,
  direction = 'out',
  suggestedContraCode,
  variant = 'secondary',
  size = 'sm',
  label = 'Операция',
}: Props) {
  const [open, setOpen] = useState(false);

  const cls = [
    'btn',
    variant === 'primary' ? 'btn-primary' : variant === 'secondary' ? 'btn-secondary' : 'btn-ghost',
    size === 'sm' ? 'btn-sm' : '',
  ].filter(Boolean).join(' ');

  return (
    <>
      <button className={cls} onClick={() => setOpen(true)}>
        <Icon name="plus" size={size === 'sm' ? 12 : 14} /> {label}
      </button>
      {open && (
        <OpexModal
          preselect={{ moduleCode, direction, suggestedContraCode }}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
