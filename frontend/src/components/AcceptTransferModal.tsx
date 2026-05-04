'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import Modal from '@/components/ui/Modal';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useWarehouses } from '@/hooks/useStockMovements';
import { ApiError, apiFetch } from '@/lib/api';
import type { InterModuleTransfer } from '@/types/auth';


interface Props {
  transfer: InterModuleTransfer;
  /** Список query keys для invalidation после успешного accept (помимо ['transfers'] и ['batches']). */
  invalidateKeys?: readonly (readonly unknown[])[];
  onClose: () => void;
}

/**
 * Модалка приёма межмодульной передачи.
 *
 * Оператор-приёмщик (incubation/feedlot/slaughter/...) видит входящую
 * партию и должен явно указать **на какой склад** её положить. Это
 * принципиально, иначе fallback на склад отправителя сделает учёт
 * неверным — партия числилась бы у sender-а после переезда.
 *
 * Backend (`/api/transfers/{id}/accept/`) принимает body
 * `{to_warehouse_id, to_block_id?}` и обновляет transfer перед
 * `accept_transfer()` (который проверит что `to_warehouse` задан и
 * упадёт с понятной ошибкой если оператор оставит пустым).
 */
export default function AcceptTransferModal({ transfer, invalidateKeys = [], onClose }: Props) {
  const qc = useQueryClient();
  const moduleCode = transfer.to_module_code ?? '';

  const { data: warehouses } = useWarehouses({
    module_code: moduleCode,
    is_active: 'true',
  });
  const { data: blocks } = useProductionBlocks({ module_code: moduleCode });

  // Если sender уже выбрал склад — preselect, оператор может оставить
  // или поменять. Поле приходит как warehouse_id (uuid) либо null.
  const [warehouseId, setWarehouseId] = useState<string>(
    transfer.to_warehouse ?? '',
  );
  const [blockId, setBlockId] = useState<string>(transfer.to_block ?? '');

  const accept = useMutation<unknown, ApiError, void>({
    mutationFn: () =>
      apiFetch(`/api/transfers/${transfer.id}/accept/`, {
        method: 'POST',
        body: {
          to_warehouse_id: warehouseId,
          ...(blockId ? { to_block_id: blockId } : {}),
        },
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['transfers'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['batches'], refetchType: 'all' }),
        ...invalidateKeys.map((key) =>
          qc.invalidateQueries({ queryKey: [...key], refetchType: 'all' }),
        ),
      ]);
      onClose();
    },
  });

  const canAccept = Boolean(warehouseId) && !accept.isPending;

  // FE-тексты ошибок поля (если backend вернул 400 с {to_warehouse_id: ...})
  const fieldErrors = accept.error instanceof ApiError && accept.error.status === 400
    ? ((accept.error.data as Record<string, unknown>) ?? {})
    : {};
  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title="Принять партию"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={accept.isPending}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={!canAccept}
            onClick={() => accept.mutate()}
          >
            {accept.isPending ? 'Приём…' : 'Принять'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 14 }}>
        После приёма произойдёт:<br />
        • Партия <strong>{transfer.batch_doc_number ?? transfer.doc_number}</strong> ({parseFloat(transfer.quantity).toLocaleString('ru-RU')} {transfer.unit_code ?? ''}) перейдёт в модуль <strong>{transfer.to_module_name ?? moduleCode}</strong><br />
        • Создастся пара бухпроводок через 79.01<br />
        • Появится запись StockMovement (приход) на выбранный склад<br />
        • Откроется новый шаг трассировки (BatchChainStep)
      </div>

      <div className="field">
        <label>Склад приёмки *</label>
        <select
          className="input"
          value={warehouseId}
          onChange={(e) => setWarehouseId(e.target.value)}
        >
          <option value="">— выберите склад —</option>
          {warehouses?.map((w) => (
            <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
          ))}
        </select>
        {getErr('to_warehouse_id') && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('to_warehouse_id')}</div>
        )}
        {!warehouses?.length && (
          <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
            В модуле «{transfer.to_module_name ?? moduleCode}» нет активных складов.
            Создайте склад в разделе «Склады» перед приёмом.
          </div>
        )}
      </div>

      <div className="field">
        <label>Блок (опционально)</label>
        <select
          className="input"
          value={blockId}
          onChange={(e) => setBlockId(e.target.value)}
        >
          <option value="">— не указан —</option>
          {blocks?.map((b) => (
            <option key={b.id} value={b.id}>{b.code} · {b.name}</option>
          ))}
        </select>
        {getErr('to_block_id') && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('to_block_id')}</div>
        )}
      </div>

      {accept.error && accept.error.status !== 400 && (
        <div style={{
          marginTop: 10, padding: 8,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 12,
        }}>
          {accept.error.message}
        </div>
      )}
    </Modal>
  );
}
