import { CircleAlert, LoaderCircle, ShieldAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

type RouteStatusScreenProps = {
  label: string;
  title: string;
  description: string;
  status?: 'loading' | 'forbidden' | 'error';
  actionLabel?: string;
  onAction?: () => void;
};

export function RouteStatusScreen({
  label,
  title,
  description,
  status = 'loading',
  actionLabel,
  onAction,
}: RouteStatusScreenProps) {
  const isForbidden = status === 'forbidden';
  const isError = status === 'error';

  return (
    <section className="mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
      <Card className="animate-surface-in relative w-full max-w-2xl overflow-hidden rounded-[36px] border-border/70 bg-card shadow-[0_32px_96px_-52px_rgba(15,23,42,0.18)]">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/80 via-accent/90 to-primary/50" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-0 top-0 h-40 w-40 rounded-full blur-3xl"
          style={{ background: 'hsl(var(--primary) / 0.14)' }}
        />
        <CardHeader className="relative space-y-5 pb-6 text-center">
          <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-[20px] border border-border/70 bg-background shadow-[0_18px_44px_-30px_rgba(15,23,42,0.12)]">
            {isForbidden ? (
              <ShieldAlert className="h-6 w-6 text-destructive" />
            ) : isError ? (
              <CircleAlert className="h-6 w-6 text-destructive" />
            ) : (
              <LoaderCircle className="h-6 w-6 animate-spin text-primary" />
            )}
          </div>
          <div className="mx-auto inline-flex w-fit items-center gap-2 rounded-full border border-border/75 bg-background px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </div>
          <CardTitle
            className="text-3xl tracking-[-0.05em] text-foreground sm:text-4xl"
            style={{ fontFamily: 'Fraunces, serif' }}
          >
            {title}
          </CardTitle>
          <CardDescription className="mx-auto max-w-md text-sm leading-6">{description}</CardDescription>
        </CardHeader>
        <CardContent className="relative space-y-5">
          <div className="mx-auto h-2 w-32 overflow-hidden rounded-full bg-background shadow-[inset_0_1px_3px_hsl(var(--border)/0.65)]">
            <div
              className="h-full rounded-full bg-gradient-to-r"
              style={{
                width: isForbidden || isError ? '100%' : '50%',
                backgroundImage: isForbidden || isError
                  ? 'linear-gradient(to right, hsl(var(--destructive)), hsl(var(--destructive) / 0.72))'
                  : 'linear-gradient(to right, hsl(var(--primary)), hsl(var(--accent)), hsl(var(--primary)))',
              }}
            />
          </div>
          {actionLabel && onAction ? (
            <div className="flex justify-center">
              <Button
                type="button"
                variant={isForbidden || isError ? 'outline' : 'default'}
                className="rounded-full"
                onClick={onAction}
              >
                {actionLabel}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
