import { Copy, Download, ExternalLink, Printer } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import type { MedicineBatchQr } from '@/shared/api/medicine';

import { frostedPanelClassName, inputBaseClassName } from '../module-crud-page.helpers';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

export interface MedicineBatchQrSheetProps {
  batch: { id: string; code: string } | null;
  payload: MedicineBatchQr | null | undefined;
  emptyLabel: string;
  t: TranslateFn;
  formatDateTime: (value: unknown) => string;
  pendingAction: boolean;
  isBusy: boolean;
  onClose: () => void;
  onCopyLink: () => void;
  onDownload: () => void;
  onPrint: () => void;
  onOpenPublic: () => void;
}

export function MedicineBatchQrSheet({
  batch,
  payload,
  emptyLabel,
  t,
  formatDateTime,
  pendingAction,
  isBusy,
  onClose,
  onCopyLink,
  onDownload,
  onPrint,
  onOpenPublic,
}: MedicineBatchQrSheetProps) {
  return (
    <Sheet
      open={Boolean(batch)}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <SheetContent
        side="right"
        className="data-[side=right]:w-[92vw] data-[side=right]:sm:max-w-md"
      >
        <SheetHeader>
          <SheetTitle>
            {t(
              'crud.medicineBatchQrCenterTitle',
              { code: batch?.code ?? emptyLabel },
              `QR-код партии ${batch?.code ?? emptyLabel}`,
            )}
          </SheetTitle>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-4">
          {payload ? (
            <>
              <div className="rounded-2xl border border-border/75 bg-card px-4 py-4 text-center shadow-[0_18px_46px_-34px_rgba(15,23,42,0.16)]">
                <img
                  src={payload.image_data_url}
                  alt="QR code"
                  className="mx-auto h-[min(16rem,70vw)] w-[min(16rem,70vw)] rounded-2xl border border-border/70 bg-white object-contain p-3"
                />
              </div>

              <div className={`${frostedPanelClassName} space-y-3 px-4 py-4`}>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {t('crud.openPublicCard', undefined, 'Public')}
                </p>
                <Input value={payload.public_url} readOnly className={inputBaseClassName} />
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <Button
                  type="button"
                  variant="outline"
                  className="border-border/75 bg-card"
                  onClick={onCopyLink}
                  disabled={pendingAction || isBusy}
                >
                  <Copy className="h-3.5 w-3.5" />
                  {t('crud.copyPublicLink', undefined, 'Копировать ссылку')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="border-border/75 bg-card"
                  onClick={onDownload}
                  disabled={pendingAction || isBusy}
                >
                  <Download className="h-3.5 w-3.5" />
                  {t('crud.downloadQr', undefined, 'Скачать PNG')}
                </Button>
              </div>

              <div className={`${frostedPanelClassName} space-y-2 px-4 py-4 text-xs`}>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-muted-foreground">
                    {t('crud.qrGeneratedAt', undefined, 'Сгенерирован')}
                  </span>
                  <span className="text-right text-foreground">
                    {formatDateTime(payload.generated_at)}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-muted-foreground">
                    {t('crud.qrExpiresAt', undefined, 'Действует до')}
                  </span>
                  <span className="text-right text-foreground">
                    {formatDateTime(payload.token_expires_at)}
                  </span>
                </div>
              </div>
            </>
          ) : (
            <div className={`${frostedPanelClassName} px-4 py-8 text-sm text-muted-foreground`}>
              {t('common.loadingLabel')}
            </div>
          )}
        </div>

        <SheetFooter>
          <Button
            type="button"
            variant="outline"
            className="border-border/75 bg-card"
            onClick={onPrint}
            disabled={pendingAction || isBusy}
          >
            <Printer className="h-3.5 w-3.5" />
            {t('crud.printQr', undefined, 'Печать')}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-border/75 bg-card"
            onClick={onOpenPublic}
            disabled={pendingAction || isBusy}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {t('crud.openPublicCard', undefined, 'Public')}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
