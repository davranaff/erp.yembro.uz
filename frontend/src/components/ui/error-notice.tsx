import { RotateCw } from 'lucide-react';

import { getErrorMessages } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

type ErrorNoticeProps = {
  error: unknown;
  className?: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  retryLabel?: string;
};

export function ErrorNotice({
  error,
  className,
  onRetry,
  isRetrying = false,
  retryLabel,
}: ErrorNoticeProps) {
  const { t } = useI18n();
  const messages = getErrorMessages(error);

  if (messages.length === 0) {
    return null;
  }

  const retryText = retryLabel ?? t('common.retry', undefined, 'Повторить');

  return (
    <div
      className={cn(
        'rounded-2xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive shadow-[0_16px_42px_-30px_rgba(244,63,94,0.16)]',
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          {messages.map((message, index) => (
            <p
              key={`${message}-${index}`}
              className={index === 0 ? 'font-medium' : 'text-[0.92em]'}
            >
              {message}
            </p>
          ))}
        </div>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/10 px-3 py-1 text-xs font-semibold text-destructive transition hover:bg-destructive/15 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RotateCw
              className={cn('h-3.5 w-3.5', isRetrying ? 'animate-spin' : null)}
              aria-hidden="true"
            />
            {retryText}
          </button>
        ) : null}
      </div>
    </div>
  );
}
