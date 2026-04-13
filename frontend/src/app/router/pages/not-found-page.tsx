import { ArrowLeft, CircleOff, Compass, Map } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { APP_NAME } from '@/shared/constants/app';
import { ROUTES } from '@/shared/config/routes';
import { useI18n } from '@/shared/i18n';

export function NotFoundPage() {
  const { t } = useI18n();

  return (
    <section
      className="mx-auto flex w-full max-w-6xl items-center justify-center px-4 py-10 sm:px-6 lg:px-8"
      data-tour="notfound-page"
    >
      <div className="grid w-full items-stretch gap-8 lg:grid-cols-[minmax(0,1.15fr)_460px]">
        <div
          className="animate-surface-in relative hidden overflow-hidden rounded-[36px] border border-border/70 bg-card p-8 shadow-[0_32px_90px_-48px_rgba(15,23,42,0.18)] lg:flex lg:flex-col lg:justify-between"
          data-tour="notfound-showcase"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'radial-gradient(circle at 84% 12%, hsl(var(--accent) / 0.18), transparent 24%), radial-gradient(circle at 14% 0%, hsl(var(--primary) / 0.14), transparent 20%), linear-gradient(145deg, hsl(var(--card)) 0%, hsl(var(--background)) 58%, hsl(var(--secondary) / 0.62) 100%)',
            }}
          />
          <div className="relative space-y-10">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/75 bg-background px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)]">
                <CircleOff className="h-3.5 w-3.5 text-primary" />
                404
              </div>
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">{APP_NAME}</p>
                <h1
                  className="max-w-xl text-5xl leading-none tracking-[-0.05em] text-foreground"
                  style={{ fontFamily: 'Fraunces, serif' }}
                >
                  {t('notFound.sideTitle')}
                </h1>
                <p className="max-w-lg text-sm leading-6 text-muted-foreground">
                  {t('notFound.sideDescription')}
                </p>
              </div>
            </div>
            <div className="grid gap-4 xl:grid-cols-3">
              <div className="rounded-[24px] border border-border/70 bg-background p-5 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.12)]">
                <div className="border-primary/18 bg-primary/8 mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border text-primary">
                  <Map className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-foreground">
                  {t('notFound.cardOneTitle')}
                </p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {t('notFound.cardOneDescription')}
                </p>
              </div>
              <div className="rounded-[24px] border border-border/70 bg-background p-5 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.12)]">
                <div className="border-primary/18 bg-primary/8 mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border text-primary">
                  <Compass className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-foreground">
                  {t('notFound.cardTwoTitle')}
                </p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {t('notFound.cardTwoDescription')}
                </p>
              </div>
              <div className="rounded-[24px] border border-border/70 bg-background p-5 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.12)]">
                <div className="border-primary/18 bg-primary/8 mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border text-primary">
                  <ArrowLeft className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-foreground">
                  {t('notFound.cardThreeTitle')}
                </p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {t('notFound.cardThreeDescription')}
                </p>
              </div>
            </div>
          </div>
        </div>

        <Card
          className="animate-surface-in relative overflow-hidden rounded-[36px] border-border/70 bg-card text-center shadow-[0_32px_96px_-52px_rgba(15,23,42,0.18)]"
          data-tour="notfound-card"
        >
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/80 via-accent/90 to-primary/50" />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full blur-3xl"
            style={{ background: 'hsl(var(--accent) / 0.12)' }}
          />
          <CardHeader className="relative space-y-5 pb-6">
            <div className="mx-auto inline-flex w-fit items-center rounded-full border border-border/70 bg-background px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              404
            </div>
            <CardTitle
              className="text-4xl tracking-[-0.05em] text-foreground sm:text-5xl"
              style={{ fontFamily: 'Fraunces, serif' }}
            >
              {t('notFound.title')}
            </CardTitle>
            <CardDescription className="mx-auto max-w-md text-sm leading-6">
              {t('notFound.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="relative">
            <div className="flex flex-wrap justify-center gap-2">
              <Link to={ROUTES.home} className="inline-flex" data-tour="notfound-back">
                <Button variant="outline" className="h-11 rounded-2xl px-6 text-sm font-semibold">
                  <ArrowLeft className="h-4 w-4" />
                  {t('notFound.goHome', undefined, 'На главную')}
                </Button>
              </Link>
              <Link to={ROUTES.login} className="inline-flex">
                <Button className="h-11 rounded-2xl px-6 text-sm font-semibold">
                  {t('nav.login', undefined, 'Войти')}
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
