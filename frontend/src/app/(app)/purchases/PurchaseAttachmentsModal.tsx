'use client';

import { useRef, useState } from 'react';

import Modal from '@/components/ui/Modal';
import Icon from '@/components/ui/Icon';
import { ApiError } from '@/lib/api';
import {
  MAX_PURCHASE_ATTACHMENT_BYTES,
  useDeletePurchaseAttachment,
  usePurchaseAttachments,
  useUploadPurchaseAttachment,
} from '@/hooks/usePurchases';
import type { PurchaseOrder } from '@/types/auth';

interface Props {
  purchase: PurchaseOrder;
  onClose: () => void;
}

const ALLOWED_EXT = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv'];

/**
 * Модалка управления файл-приложениями к закупу.
 *
 * Загружает скан заявления, контракт, фото товара (PDF/изображения/Office/CSV).
 * Лимит 50МБ на файл, проверяется и на FE (быстрый отказ) и на backend
 * (защита от обхода).
 */
export default function PurchaseAttachmentsModal({ purchase, onClose }: Props) {
  const { data: files, isLoading } = usePurchaseAttachments(purchase.id);
  const upload = useUploadPurchaseAttachment();
  const remove = useDeletePurchaseAttachment();

  const inputRef = useRef<HTMLInputElement>(null);
  const [description, setDescription] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const onPickFile = () => inputRef.current?.click();

  const onFileChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // позволить выбрать тот же файл повторно
    if (!file) return;

    setLocalError(null);

    if (file.size > MAX_PURCHASE_ATTACHMENT_BYTES) {
      const mb = MAX_PURCHASE_ATTACHMENT_BYTES / (1024 * 1024);
      setLocalError(
        `Файл больше ${mb} МБ (выбран: ${(file.size / (1024 * 1024)).toFixed(1)} МБ).`,
      );
      return;
    }
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!ALLOWED_EXT.includes(ext)) {
      setLocalError(`Тип файла .${ext} не поддерживается. Разрешены: ${ALLOWED_EXT.join(', ')}.`);
      return;
    }

    try {
      await upload.mutateAsync({
        purchaseId: purchase.id,
        file,
        description: description.trim() || undefined,
      });
      setDescription('');
    } catch {
      /* err shown via mutation state */
    }
  };

  const uploadErr = upload.error instanceof ApiError && upload.error.status === 400
    ? (() => {
        const data = upload.error.data as Record<string, unknown> | undefined;
        const fileErr = data?.file;
        if (Array.isArray(fileErr)) return fileErr.join(' · ');
        if (typeof fileErr === 'string') return fileErr;
        return upload.error.message;
      })()
    : upload.error?.message ?? null;

  return (
    <Modal
      title={`Файлы к закупу · ${purchase.doc_number}`}
      onClose={onClose}
      footer={
        <button className="btn btn-ghost" onClick={onClose}>Закрыть</button>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 14 }}>
        Поставщик: <b>{purchase.counterparty_name ?? '—'}</b>{' '}
        · Сумма: <span className="mono">{parseFloat(purchase.amount_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум</span>
      </div>

      {/* ── Загрузка ─────────────────────────────────────── */}
      <div style={{
        padding: 12, marginBottom: 14, borderRadius: 6,
        border: '1px dashed var(--border)',
        background: 'var(--bg-soft)',
      }}>
        <div className="field" style={{ marginBottom: 8 }}>
          <label>Описание (опционально)</label>
          <input
            className="input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="скан заявления / договор / фото товара…"
          />
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            className="btn btn-primary btn-sm"
            disabled={upload.isPending}
            onClick={onPickFile}
          >
            <Icon name="plus" size={12} />
            {upload.isPending ? ' Загрузка…' : ' Выбрать файл'}
          </button>
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            Лимит 50 МБ. Поддерживается: {ALLOWED_EXT.join(', ')}.
          </span>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_EXT.map((e) => `.${e}`).join(',')}
          style={{ display: 'none' }}
          onChange={onFileChosen}
        />

        {(localError || uploadErr) && (
          <div style={{ marginTop: 8, padding: 6, fontSize: 11, color: 'var(--danger)', background: '#fef2f2', borderRadius: 4 }}>
            {localError || uploadErr}
          </div>
        )}
      </div>

      {/* ── Список файлов ────────────────────────────────── */}
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
        Файлы ({files?.length ?? 0})
      </div>

      {isLoading && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Загружаем…</div>
      )}

      {!isLoading && (files?.length ?? 0) === 0 && (
        <div style={{
          padding: 16, fontSize: 12, color: 'var(--fg-3)', textAlign: 'center',
          border: '1px dashed var(--border)', borderRadius: 6,
        }}>
          Файлов ещё нет. Загрузите первый ↑
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {(files ?? []).map((f) => (
          <div
            key={f.id}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: 8, borderRadius: 4,
              border: '1px solid var(--border)',
              background: 'var(--bg-card)',
            }}
          >
            <Icon name="bag" size={14} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <a
                href={f.file_url ?? '#'}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: 12, fontWeight: 500, color: 'var(--brand-orange)',
                  textDecoration: 'none', display: 'block',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}
              >
                {f.original_name}
              </a>
              <div style={{ fontSize: 11, color: 'var(--fg-3)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span className="mono">{f.size_human}</span>
                {f.description && <span>· {f.description}</span>}
                {f.uploaded_by_name && <span>· {f.uploaded_by_name}</span>}
                <span>· {new Date(f.created_at).toLocaleDateString('ru-RU')}</span>
              </div>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--danger)' }}
              disabled={remove.isPending}
              onClick={() => {
                if (confirm(`Удалить файл «${f.original_name}»?`)) {
                  remove.mutate({ id: f.id, purchaseId: purchase.id });
                }
              }}
            >
              Удалить
            </button>
          </div>
        ))}
      </div>
    </Modal>
  );
}
