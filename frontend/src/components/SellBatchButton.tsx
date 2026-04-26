'use client';

import { useState } from 'react';

import Icon from '@/components/ui/Icon';
import SaleOrderModal, {
  type SalePreselect,
  type SaleSourceKind,
} from '@/app/(app)/sales/SaleOrderModal';

interface Props {
  /** Модуль-источник (совпадает с Module.code в БД). */
  moduleCode: string;
  /** Тип партии — зависит от модуля. */
  sourceKind: SaleSourceKind;
  /** UUID партии (Batch / VetStockBatch / FeedBatch). */
  batchId: string;
  /** Опционально: nomenclature чтобы не искать повторно. */
  nomenclatureId?: string;
  /** Опционально: склад-источник. */
  warehouseId?: string;
  /** Вариант кнопки: "primary" или "secondary". */
  variant?: 'primary' | 'secondary' | 'ghost';
  /** Размер кнопки. */
  size?: 'sm' | 'md';
  /** Произвольный лейбл; по умолчанию "Продать". */
  label?: string;
  /** Отключение кнопки (например если batch уже completed). */
  disabled?: boolean;
  /** Подсказка при disabled. */
  disabledReason?: string;
}

/**
 * Универсальная кнопка "Продать" для drawer-ов партий любого модуля.
 *
 * Открывает SaleOrderModal с preselect: модуль + тип партии + её UUID
 * уже проставлены, пользователю остаётся только указать клиента, склад,
 * количество и цену.
 */
export default function SellBatchButton({
  moduleCode,
  sourceKind,
  batchId,
  nomenclatureId,
  warehouseId,
  variant = 'primary',
  size = 'sm',
  label = 'Продать',
  disabled,
  disabledReason,
}: Props) {
  const [open, setOpen] = useState(false);

  const preselect: SalePreselect = {
    moduleCode,
    sourceKind,
    batchId,
    nomenclatureId,
    warehouseId,
  };

  const cls = [
    'btn',
    variant === 'primary' ? 'btn-primary' : variant === 'secondary' ? 'btn-secondary' : 'btn-ghost',
    size === 'sm' ? 'btn-sm' : '',
  ].filter(Boolean).join(' ');

  return (
    <>
      <button
        className={cls}
        onClick={() => setOpen(true)}
        disabled={disabled}
        title={disabled ? disabledReason : undefined}
      >
        <Icon name="bag" size={size === 'sm' ? 12 : 14} /> {label}
      </button>

      {open && (
        <SaleOrderModal preselect={preselect} onClose={() => setOpen(false)} />
      )}
    </>
  );
}


interface OpenSaleProps {
  moduleCode: string;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  label?: string;
}

/**
 * Кнопка «Продать» для page-header модуля (без конкретной партии).
 * Открывает SaleOrderModal с предзаданным модулем — пользователь сам
 * выберет партию внутри.
 */
export function OpenSaleFromModule({
  moduleCode,
  variant = 'secondary',
  size = 'sm',
  label = 'Продать',
}: OpenSaleProps) {
  const [open, setOpen] = useState(false);

  const cls = [
    'btn',
    variant === 'primary' ? 'btn-primary' : variant === 'secondary' ? 'btn-secondary' : 'btn-ghost',
    size === 'sm' ? 'btn-sm' : '',
  ].filter(Boolean).join(' ');

  // Для vet sourceKind='vet_stock_batch', для feed — 'feed_batch', для прочих — 'batch'
  let sourceKind: SaleSourceKind = 'batch';
  if (moduleCode === 'vet') sourceKind = 'vet_stock_batch';
  else if (moduleCode === 'feed') sourceKind = 'feed_batch';

  return (
    <>
      <button className={cls} onClick={() => setOpen(true)}>
        <Icon name="bag" size={size === 'sm' ? 12 : 14} /> {label}
      </button>
      {open && (
        <SaleOrderModal
          preselect={{ moduleCode, sourceKind, batchId: '' }}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
