import {
  type ChangeEvent as ReactChangeEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import type { CrudRecord } from '@/shared/api/backend-crud';
import { ApiError } from '@/shared/api/error-handler';
import {
  generateMedicineBatchQr,
  getMedicineBatchQr,
  uploadMedicineBatchAttachment,
  type MedicineBatchQr,
} from '@/shared/api/medicine';

import { getRecordId } from '../module-crud-page.helpers';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

export interface UseMedicineBatchQrOptions {
  t: TranslateFn;
  emptyLabel: string;
  idColumn: string;
  isMedicineBatchesResource: boolean;
  canManageMedicineBatchOps: boolean;
  paginatedRecords: CrudRecord[];
  invalidateResource: () => Promise<void> | void;
  setSystemFormError: (message: string) => void;
  setOperationMessage: (message: string) => void;
}

export function useMedicineBatchQr(options: UseMedicineBatchQrOptions) {
  const {
    t,
    emptyLabel,
    idColumn,
    isMedicineBatchesResource,
    canManageMedicineBatchOps,
    paginatedRecords,
    invalidateResource,
    setSystemFormError,
    setOperationMessage,
  } = options;

  const [medicineBatchQrCache, setMedicineBatchQrCache] = useState<Record<string, MedicineBatchQr>>(
    {},
  );
  const [medicineBatchBusyKey, setMedicineBatchBusyKey] = useState('');
  const [medicineBatchQrSheetBatch, setMedicineBatchQrSheetBatch] = useState<{
    id: string;
    code: string;
  } | null>(null);
  const [attachmentTargetBatchId, setAttachmentTargetBatchId] = useState('');
  const medicineBatchAttachmentInputRef = useRef<HTMLInputElement | null>(null);

  const activeMedicineBatchQrSheetPayload = medicineBatchQrSheetBatch?.id
    ? medicineBatchQrCache[medicineBatchQrSheetBatch.id]
    : undefined;
  const isMedicineBatchQrSheetBusy =
    medicineBatchQrSheetBatch?.id &&
    medicineBatchBusyKey.startsWith(`${medicineBatchQrSheetBatch.id}:`)
      ? true
      : false;
  const isMedicineBatchPending = medicineBatchBusyKey.length > 0;

  useEffect(() => {
    if (!isMedicineBatchesResource && medicineBatchQrSheetBatch) {
      setMedicineBatchQrSheetBatch(null);
    }
  }, [isMedicineBatchesResource, medicineBatchQrSheetBatch]);

  const resetState = useCallback(() => {
    setMedicineBatchQrCache({});
    setMedicineBatchBusyKey('');
    setAttachmentTargetBatchId('');
  }, []);

  const isMedicineBatchActionBusy = useCallback(
    (batchId: string, action?: string): boolean => {
      if (!medicineBatchBusyKey) {
        return false;
      }
      if (action) {
        return medicineBatchBusyKey === `${batchId}:${action}`;
      }
      return medicineBatchBusyKey.startsWith(`${batchId}:`);
    },
    [medicineBatchBusyKey],
  );

  const getMedicineBatchCode = useCallback(
    (record: CrudRecord): string => {
      const recordBatchCode =
        typeof record.batch_code === 'string' && record.batch_code.trim().length > 0
          ? record.batch_code.trim()
          : '';
      return recordBatchCode || getRecordId(record, idColumn) || emptyLabel;
    },
    [emptyLabel, idColumn],
  );

  const resolveQr = useCallback(
    async (
      batchId: string,
      opts: { forceGenerate?: boolean; allowGenerateOnMissing?: boolean } = {},
    ): Promise<MedicineBatchQr> => {
      const { forceGenerate = false, allowGenerateOnMissing = true } = opts;
      if (!forceGenerate) {
        if (Object.prototype.hasOwnProperty.call(medicineBatchQrCache, batchId)) {
          return medicineBatchQrCache[batchId];
        }
      }

      try {
        const payload = forceGenerate
          ? await generateMedicineBatchQr(batchId)
          : await getMedicineBatchQr(batchId);
        setMedicineBatchQrCache((current) => ({ ...current, [batchId]: payload }));
        return payload;
      } catch (error) {
        if (
          !forceGenerate &&
          allowGenerateOnMissing &&
          error instanceof ApiError &&
          error.status === 404
        ) {
          const generated = await generateMedicineBatchQr(batchId);
          setMedicineBatchQrCache((current) => ({ ...current, [batchId]: generated }));
          return generated;
        }
        throw error;
      }
    },
    [medicineBatchQrCache],
  );

  const handleOpenCenter = useCallback(
    async (record: CrudRecord) => {
      if (!isMedicineBatchesResource) {
        return;
      }
      const batchId = getRecordId(record, idColumn);
      if (!batchId) {
        return;
      }
      setMedicineBatchBusyKey(`${batchId}:center`);
      setSystemFormError('');
      try {
        await resolveQr(batchId, { allowGenerateOnMissing: canManageMedicineBatchOps });
        setMedicineBatchQrSheetBatch({
          id: batchId,
          code: getMedicineBatchCode(record),
        });
      } catch (error) {
        setSystemFormError(error instanceof Error ? error.message : t('crud.saveError'));
      } finally {
        setMedicineBatchBusyKey('');
      }
    },
    [
      canManageMedicineBatchOps,
      getMedicineBatchCode,
      idColumn,
      isMedicineBatchesResource,
      resolveQr,
      setSystemFormError,
      t,
    ],
  );

  const handlePrint = useCallback(async () => {
    if (!medicineBatchQrSheetBatch) {
      return;
    }
    const batchId = medicineBatchQrSheetBatch.id;
    const batchCode = medicineBatchQrSheetBatch.code;
    setMedicineBatchBusyKey(`${batchId}:print`);
    setSystemFormError('');
    try {
      const qrPayload = activeMedicineBatchQrSheetPayload ?? (await resolveQr(batchId));
      printMedicineBatchQrImage(qrPayload.image_data_url, batchCode, t('crud.saveError'));
    } catch (error) {
      setSystemFormError(error instanceof Error ? error.message : t('crud.saveError'));
    } finally {
      setMedicineBatchBusyKey('');
    }
  }, [
    activeMedicineBatchQrSheetPayload,
    medicineBatchQrSheetBatch,
    resolveQr,
    setSystemFormError,
    t,
  ]);

  const handleDownload = useCallback(async () => {
    if (!medicineBatchQrSheetBatch) {
      return;
    }
    const batchId = medicineBatchQrSheetBatch.id;
    const batchCode = medicineBatchQrSheetBatch.code;
    setMedicineBatchBusyKey(`${batchId}:download`);
    setSystemFormError('');
    try {
      const qrPayload = activeMedicineBatchQrSheetPayload ?? (await resolveQr(batchId));
      downloadMedicineBatchQrImage(qrPayload.image_data_url, batchCode);
    } catch (error) {
      setSystemFormError(error instanceof Error ? error.message : t('crud.saveError'));
    } finally {
      setMedicineBatchBusyKey('');
    }
  }, [
    activeMedicineBatchQrSheetPayload,
    medicineBatchQrSheetBatch,
    resolveQr,
    setSystemFormError,
    t,
  ]);

  const handleOpenPublicPage = useCallback(async () => {
    if (!medicineBatchQrSheetBatch) {
      return;
    }
    const batchId = medicineBatchQrSheetBatch.id;
    setMedicineBatchBusyKey(`${batchId}:public`);
    setSystemFormError('');
    try {
      const qrPayload = activeMedicineBatchQrSheetPayload ?? (await resolveQr(batchId));
      const openedWindow = window.open(qrPayload.public_url, '_blank', 'noopener,noreferrer');
      if (!openedWindow) {
        throw new Error(
          t(
            'crud.popupBlocked',
            undefined,
            'Браузер заблокировал новое окно. Разрешите pop-up для этого сайта.',
          ),
        );
      }
    } catch (error) {
      setSystemFormError(error instanceof Error ? error.message : t('crud.saveError'));
    } finally {
      setMedicineBatchBusyKey('');
    }
  }, [
    activeMedicineBatchQrSheetPayload,
    medicineBatchQrSheetBatch,
    resolveQr,
    setSystemFormError,
    t,
  ]);

  const handleCopyPublicLink = useCallback(async () => {
    if (!medicineBatchQrSheetBatch) {
      return;
    }
    const batchId = medicineBatchQrSheetBatch.id;
    const batchCode = medicineBatchQrSheetBatch.code;
    setMedicineBatchBusyKey(`${batchId}:copy`);
    setSystemFormError('');
    try {
      const qrPayload = activeMedicineBatchQrSheetPayload ?? (await resolveQr(batchId));
      await copyTextToClipboard(qrPayload.public_url, t('crud.saveError'));
      setOperationMessage(
        t(
          'crud.medicineBatchPublicLinkCopied',
          { code: batchCode },
          `Публичная ссылка для партии ${batchCode} скопирована.`,
        ),
      );
    } catch (error) {
      setSystemFormError(error instanceof Error ? error.message : t('crud.saveError'));
    } finally {
      setMedicineBatchBusyKey('');
    }
  }, [
    activeMedicineBatchQrSheetPayload,
    medicineBatchQrSheetBatch,
    resolveQr,
    setOperationMessage,
    setSystemFormError,
    t,
  ]);

  const handleOpenAttachmentPicker = useCallback(
    (record: CrudRecord) => {
      const batchId = getRecordId(record, idColumn);
      if (!batchId || !canManageMedicineBatchOps) {
        return;
      }
      setAttachmentTargetBatchId(batchId);
      medicineBatchAttachmentInputRef.current?.click();
    },
    [canManageMedicineBatchOps, idColumn],
  );

  const handleAttachmentInputChange = useCallback(
    async (event: ReactChangeEvent<HTMLInputElement>) => {
      if (!canManageMedicineBatchOps) {
        event.target.value = '';
        setAttachmentTargetBatchId('');
        return;
      }

      const selectedFile = event.target.files?.[0] ?? null;
      event.target.value = '';

      if (!selectedFile || !attachmentTargetBatchId) {
        if (!selectedFile) {
          setAttachmentTargetBatchId('');
        }
        return;
      }

      setMedicineBatchBusyKey(`${attachmentTargetBatchId}:attach`);
      setSystemFormError('');
      try {
        await uploadMedicineBatchAttachment(attachmentTargetBatchId, selectedFile);
        const targetRecord = paginatedRecords.find(
          (record) => getRecordId(record, idColumn) === attachmentTargetBatchId,
        );
        const batchCode = targetRecord
          ? getMedicineBatchCode(targetRecord)
          : attachmentTargetBatchId;
        setOperationMessage(
          t(
            'crud.medicineBatchAttachmentUploaded',
            { code: batchCode },
            `Файл прикреплён к партии ${batchCode}.`,
          ),
        );
        await invalidateResource();
      } catch (error) {
        setSystemFormError(error instanceof Error ? error.message : t('crud.saveError'));
      } finally {
        setAttachmentTargetBatchId('');
        setMedicineBatchBusyKey('');
      }
    },
    [
      attachmentTargetBatchId,
      canManageMedicineBatchOps,
      getMedicineBatchCode,
      idColumn,
      invalidateResource,
      paginatedRecords,
      setOperationMessage,
      setSystemFormError,
      t,
    ],
  );

  return {
    medicineBatchAttachmentInputRef,
    medicineBatchQrSheetBatch,
    setMedicineBatchQrSheetBatch,
    activeMedicineBatchQrSheetPayload,
    isMedicineBatchQrSheetBusy,
    isMedicineBatchPending,
    isMedicineBatchActionBusy,
    getMedicineBatchCode,
    resetState,
    handleOpenCenter,
    handlePrint,
    handleDownload,
    handleOpenPublicPage,
    handleCopyPublicLink,
    handleOpenAttachmentPicker,
    handleAttachmentInputChange,
  };
}

function printMedicineBatchQrImage(imageDataUrl: string, batchLabel: string, errorMessage: string) {
  const safeBatchLabel = batchLabel.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const printDocument = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>QR ${safeBatchLabel}</title>
    <style>
      @page { margin: 12mm; }
      body { margin: 0; display: grid; place-items: center; min-height: 100vh; font-family: sans-serif; }
      .wrapper { text-align: center; }
      img { width: 320px; height: 320px; object-fit: contain; border: 1px solid #d1d5db; border-radius: 16px; padding: 16px; }
      .label { margin-top: 12px; color: #374151; font-size: 14px; font-weight: 600; }
    </style>
  </head>
  <body>
    <div class="wrapper">
      <img src="${imageDataUrl}" alt="QR code" />
      <div class="label">${safeBatchLabel}</div>
    </div>
  </body>
</html>`;

  const iframe = document.createElement('iframe');
  iframe.setAttribute('aria-hidden', 'true');
  iframe.setAttribute('title', `QR ${safeBatchLabel}`);
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  iframe.style.opacity = '0';
  document.body.append(iframe);

  const cleanup = () => {
    if (iframe.parentNode) {
      iframe.parentNode.removeChild(iframe);
    }
  };

  const triggerPrint = () => {
    const printWindow = iframe.contentWindow;
    if (!printWindow) {
      cleanup();
      return;
    }
    const finishOnce = (() => {
      let done = false;
      return () => {
        if (done) {
          return;
        }
        done = true;
        window.setTimeout(cleanup, 500);
      };
    })();
    printWindow.addEventListener('afterprint', finishOnce);
    try {
      printWindow.focus();
      printWindow.print();
    } catch {
      cleanup();
      return;
    }
    window.setTimeout(finishOnce, 60_000);
  };

  iframe.addEventListener('load', () => {
    const doc = iframe.contentDocument;
    const img = doc?.querySelector('img');
    if (img && !img.complete) {
      img.addEventListener('load', triggerPrint, { once: true });
      img.addEventListener('error', triggerPrint, { once: true });
      return;
    }
    triggerPrint();
  });

  const doc = iframe.contentDocument;
  if (!doc) {
    cleanup();
    throw new Error(errorMessage);
  }
  doc.open();
  doc.write(printDocument);
  doc.close();
}

function downloadMedicineBatchQrImage(imageDataUrl: string, batchLabel: string) {
  const safeLabel = batchLabel
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-+|-+$/g, '');
  const fileName = `qr-${safeLabel || 'medicine-batch'}.png`;
  const anchor = document.createElement('a');
  anchor.href = imageDataUrl;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
}

async function copyTextToClipboard(value: string, errorMessage: string): Promise<void> {
  const clipboard =
    'clipboard' in navigator && typeof navigator.clipboard.writeText === 'function'
      ? navigator.clipboard
      : null;

  if (clipboard) {
    await clipboard.writeText(value);
    return;
  }

  const fallbackInput = document.createElement('textarea');
  fallbackInput.value = value;
  fallbackInput.setAttribute('readonly', 'true');
  fallbackInput.style.position = 'fixed';
  fallbackInput.style.opacity = '0';
  document.body.append(fallbackInput);
  fallbackInput.select();
  const copied = document.execCommand('copy');
  fallbackInput.remove();

  if (!copied) {
    throw new Error(errorMessage);
  }
}
