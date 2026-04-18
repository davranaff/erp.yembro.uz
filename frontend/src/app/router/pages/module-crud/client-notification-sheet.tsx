import { Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import type {
  ClientNotificationBulkResult,
  ClientNotificationContext,
} from '@/shared/api/backend-crud';

import { compactPillClassName, frostedPanelClassName } from '../module-crud-page.helpers';

import type { ClientNotificationTemplateKey } from './constants';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

export interface ClientNotificationTemplateSummary {
  key: string;
  title: string;
}

export interface ClientNotificationSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isBulkMode: boolean;
  targetLabel: string;
  emptyLabel: string;
  visibleClientCount: number;
  t: TranslateFn;
  notificationError: unknown;
  feedback: string;
  context: {
    isLoading: boolean;
    error: unknown;
    data: ClientNotificationContext | null | undefined;
  };
  templates: ClientNotificationTemplateSummary[];
  templateKey: ClientNotificationTemplateKey;
  onTemplateKeyChange: (key: ClientNotificationTemplateKey) => void;
  message: string;
  onMessageChange: (message: string) => void;
  onMessageTouched: () => void;
  bulkResult: ClientNotificationBulkResult | null;
  pendingAction: boolean;
  sendDisabled: boolean;
  onClose: () => void;
  onSend: () => void;
}

export function ClientNotificationSheet({
  open,
  onOpenChange,
  isBulkMode,
  targetLabel,
  emptyLabel,
  visibleClientCount,
  t,
  notificationError,
  feedback,
  context,
  templates,
  templateKey,
  onTemplateKeyChange,
  message,
  onMessageChange,
  onMessageTouched,
  bulkResult,
  pendingAction,
  sendDisabled,
  onClose,
  onSend,
}: ClientNotificationSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="data-[side=right]:w-[96vw] data-[side=right]:sm:max-w-xl"
        data-tour="client-notification-drawer"
      >
        <SheetHeader>
          <SheetTitle>
            {isBulkMode
              ? t('crud.bulkClientNotification', undefined, 'Массовое уведомление')
              : t(
                  'crud.clientNotificationTitle',
                  { client: targetLabel || emptyLabel },
                  `Уведомление: ${targetLabel || emptyLabel}`,
                )}
          </SheetTitle>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-4">
          {notificationError ? <ErrorNotice error={notificationError} /> : null}
          {feedback ? (
            <div className={`${frostedPanelClassName} px-4 py-3 text-sm text-foreground`}>
              {feedback}
            </div>
          ) : null}

          {isBulkMode ? (
            <div
              className={`${frostedPanelClassName} space-y-2 px-4 py-4 text-sm`}
              data-tour="client-notification-context"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">
                  {t('common.totalRecords', { count: visibleClientCount })}
                </span>
                <span className={compactPillClassName}>
                  {t('crud.clientNotificationChannel', undefined, 'Канал')}: Telegram
                </span>
              </div>
            </div>
          ) : (
            <>
              {context.isLoading ? (
                <div className={`${frostedPanelClassName} px-4 py-8 text-sm text-muted-foreground`}>
                  {t('common.loadingLabel')}
                </div>
              ) : null}
              {context.error ? <ErrorNotice error={context.error} /> : null}
              {context.data ? (
                <div
                  className={`${frostedPanelClassName} space-y-3 px-4 py-4 text-sm`}
                  data-tour="client-notification-context"
                >
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 bg-card px-3 py-2">
                      <p className="text-xs text-muted-foreground">
                        {t('crud.debtOpenCount', undefined, 'Открытых долгов')}
                      </p>
                      <p className="text-base font-semibold text-foreground">
                        {context.data.debt_summary.open_count}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-card px-3 py-2">
                      <p className="text-xs text-muted-foreground">
                        {t('crud.debtOutstanding', undefined, 'Остаток долга')}
                      </p>
                      <p className="text-base font-semibold text-foreground">
                        {`${context.data.debt_summary.outstanding_amount} ${context.data.debt_summary.currency}`}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      {t('crud.recentPurchases', undefined, 'Последние покупки')}
                    </p>
                    {context.data.recent_purchases.slice(0, 3).map((purchase, index) => (
                      <div
                        key={`${purchase.purchased_on ?? 'purchase'}:${index}`}
                        className="rounded-2xl border border-border/70 bg-card px-3 py-2"
                      >
                        <p className="text-sm text-foreground">
                          {`${String(purchase.purchased_on ?? emptyLabel)} · ${String(
                            purchase.item_name ?? emptyLabel,
                          )}`}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {`${String(purchase.quantity ?? 0)} ${String(
                            purchase.unit ?? '',
                          )} · ${String(purchase.amount ?? 0)} ${String(purchase.currency ?? '')}`}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          )}

          <div
            className={`${frostedPanelClassName} space-y-3 px-4 py-4`}
            data-tour="client-notification-template-tabs"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {t('crud.clientNotificationTemplate', undefined, 'Шаблон')}
            </p>
            <div className="flex flex-wrap gap-2">
              {templates.map((template) => (
                <Button
                  key={template.key}
                  type="button"
                  variant={template.key === templateKey ? 'default' : 'outline'}
                  className="rounded-full"
                  onClick={() => onTemplateKeyChange(template.key as ClientNotificationTemplateKey)}
                  disabled={pendingAction}
                >
                  {template.title}
                </Button>
              ))}
            </div>
          </div>

          <div
            className={`${frostedPanelClassName} space-y-3 px-4 py-4`}
            data-tour="client-notification-message-field"
          >
            <label
              className="text-sm font-medium text-foreground"
              htmlFor="client-notification-message"
            >
              {t('crud.clientNotificationMessage', undefined, 'Сообщение')}
            </label>
            <textarea
              id="client-notification-message"
              value={message}
              onChange={(event) => {
                onMessageChange(event.target.value);
                onMessageTouched();
              }}
              disabled={pendingAction}
              className="min-h-[180px] w-full rounded-2xl border border-border/75 bg-card px-4 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
          </div>

          {bulkResult ? (
            <div className={`${frostedPanelClassName} space-y-2 px-4 py-4`}>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                {t('crud.clientNotificationBulkResult', undefined, 'Итог рассылки')}
              </p>
              <p className="text-sm text-foreground">
                {t(
                  'crud.clientNotificationBulkSent',
                  { sent: bulkResult.sent, failed: bulkResult.failed },
                  `Отправлено: ${bulkResult.sent}, ошибок: ${bulkResult.failed}.`,
                )}
              </p>
            </div>
          ) : null}
        </div>

        <SheetFooter>
          <Button
            type="button"
            variant="outline"
            className="border-border/75 bg-card"
            onClick={onClose}
            disabled={pendingAction}
            data-tour="client-notification-close-button"
          >
            {t('common.close')}
          </Button>
          <Button
            type="button"
            className="shadow-[0_18px_42px_-28px_rgba(234,88,12,0.42)]"
            onClick={onSend}
            disabled={sendDisabled}
            data-tour="client-notification-send-button"
          >
            <Send className="h-4 w-4" />
            {pendingAction
              ? t('common.loadingLabel')
              : t('crud.clientNotificationSend', undefined, 'Отправить')}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
