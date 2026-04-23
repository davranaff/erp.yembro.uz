import { Check, Copy, ExternalLink, Loader2, Send } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useToast } from '@/components/ui/toast';
import { useApiMutation } from '@/shared/api/react-query';
import {
  createTelegramDeepLink,
  type TelegramDeepLink,
  type TelegramDeepLinkTarget,
} from '@/shared/api/telegram-bot';
import { useI18n } from '@/shared/i18n';

export interface TelegramInviteSheetProps {
  open: boolean;
  target: TelegramDeepLinkTarget;
  // Human-readable label shown in the title, e.g. "Марат Ахмедов" or
  // "ООО «Агросоюз»". Keeps the sheet generic across resources.
  subjectLabel: string;
  employeeId?: string;
  clientId?: string;
  onOpenChange: (open: boolean) => void;
}

const formatExpiry = (iso: string | undefined): string => {
  if (!iso) {
    return '';
  }
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
};

export function TelegramInviteSheet({
  open,
  target,
  subjectLabel,
  employeeId,
  clientId,
  onOpenChange,
}: TelegramInviteSheetProps) {
  const { t } = useI18n();
  const { show: showToast } = useToast();
  const [link, setLink] = useState<TelegramDeepLink | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useApiMutation<TelegramDeepLink, Error, void>({
    mutationFn: () =>
      createTelegramDeepLink({
        target,
        ...(target === 'employee' && employeeId ? { employee_id: employeeId } : {}),
        ...(target === 'client' && clientId ? { client_id: clientId } : {}),
      }),
    onSuccess: (data) => {
      setLink(data);
      setCopied(false);
    },
    onError: (error) => {
      showToast({
        tone: 'error',
        title: t('telegramInvite.errorTitle', undefined, 'Не удалось получить ссылку'),
        description: error.message,
      });
    },
  });

  // Fresh link on every open — the backend-issued token is short-lived,
  // so caching across sessions would just surface expired URLs.
  useEffect(() => {
    if (!open) {
      setLink(null);
      setCopied(false);
      return;
    }
    mutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, target, employeeId, clientId]);

  const handleCopy = async () => {
    if (!link) {
      return;
    }
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
      showToast({
        tone: 'success',
        title: t('telegramInvite.copied', undefined, 'Ссылка скопирована'),
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select the input for manual copy.
      showToast({
        tone: 'error',
        title: t('telegramInvite.copyFailed', undefined, 'Скопируйте вручную'),
      });
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Send className="h-4 w-4 text-primary" />
            {t('telegramInvite.title', undefined, 'Пригласить в бот')}
          </SheetTitle>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          <div className="rounded-xl border border-border/70 bg-muted/30 p-4 text-sm">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {target === 'employee'
                ? t('telegramInvite.forEmployee', undefined, 'Для сотрудника')
                : t('telegramInvite.forClient', undefined, 'Для клиента')}
            </div>
            <div className="mt-1 font-medium text-foreground">{subjectLabel}</div>
          </div>

          <p className="text-sm text-muted-foreground">
            {t(
              'telegramInvite.description',
              undefined,
              'Отправьте эту ссылку получателю. При переходе он нажмёт «Start» — бот свяжется с его аккаунтом и начнёт присылать уведомления.',
            )}
          </p>

          {mutation.isPending && !link ? (
            <div className="flex items-center gap-2 rounded-xl border border-dashed border-border/70 bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('common.loadingLabel', undefined, 'Загружаем…')}
            </div>
          ) : null}

          {mutation.error ? <ErrorNotice error={mutation.error} /> : null}

          {link ? (
            <div className="space-y-3">
              <div className="break-all rounded-xl border border-border/70 bg-background px-3 py-2.5 font-mono text-xs text-foreground">
                {link.url}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={() => {
                    void handleCopy();
                  }}
                >
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copied
                    ? t('telegramInvite.copiedButton', undefined, 'Скопировано')
                    : t('telegramInvite.copyButton', undefined, 'Скопировать')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  render={
                    <a href={link.url} target="_blank" rel="noreferrer">
                      <ExternalLink className="h-4 w-4" />
                      {t('telegramInvite.openButton', undefined, 'Открыть в Telegram')}
                    </a>
                  }
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {t(
                  'telegramInvite.expiryHint',
                  { time: formatExpiry(link.expires_at) },
                  'Ссылка действует до {time}.',
                )}
              </p>
            </div>
          ) : null}
        </div>

        <SheetFooter className="mt-8">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.close', undefined, 'Закрыть')}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
