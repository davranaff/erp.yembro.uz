import { getErrorMessages } from '@/shared/api/react-query';
import { cn } from '@/shared/lib/cn';

type ErrorNoticeProps = {
  error: unknown;
  className?: string;
};

export function ErrorNotice({ error, className }: ErrorNoticeProps) {
  const messages = getErrorMessages(error);

  if (messages.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-2xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive shadow-[0_16px_42px_-30px_rgba(244,63,94,0.16)]',
        className,
      )}
      role="alert"
    >
      <div className="space-y-1.5">
        {messages.map((message, index) => (
          <p key={`${message}-${index}`} className={index === 0 ? 'font-medium' : 'text-[0.92em]'}>
            {message}
          </p>
        ))}
      </div>
    </div>
  );
}
