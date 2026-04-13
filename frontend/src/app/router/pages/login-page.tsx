import { ArrowRight, Eye, EyeOff, Fingerprint, KeyRound, ShieldCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useApiMutation } from '@/shared/api';
import { loginWithCredentials, type AuthLoginResponse } from '@/shared/api/auth';
import { useAuthStore } from '@/shared/auth';
import { ROUTES } from '@/shared/config/routes';
import { APP_NAME, APP_VERSION } from '@/shared/constants/app';
import { buildSubmitHandler, useBaseForm } from '@/shared/forms';
import { useI18n } from '@/shared/i18n';

type RouteLocationState = {
  from?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const { t } = useI18n();
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const loginSchema = useMemo(
    () =>
      z.object({
        username: z.string().trim().min(1, t('login.validation.usernameRequired')),
        password: z.string().trim().min(1, t('login.validation.passwordRequired')),
      }),
    [t],
  );

  const requestedReturnUrl = ((location.state as RouteLocationState | null)?.from ?? '') as string;
  type LoginValues = z.output<typeof loginSchema>;

  const {
    handleSubmit,
    register,
    watch,
    formState: { errors },
  } = useBaseForm<typeof loginSchema>({
    defaultValues: {
      username: '',
      password: '',
    },
    schema: loginSchema,
  });

  const { mutateAsync, error, isPending } = useApiMutation<AuthLoginResponse, Error, LoginValues>({
    mutationKey: ['auth', 'login'],
    mutationFn: loginWithCredentials,
  });
  const usernameValue = watch('username');
  const passwordValue = watch('password');
  const canSubmit = usernameValue.trim().length > 0 && passwordValue.trim().length > 0;

  const onSubmit = async (values: LoginValues): Promise<void> => {
    const session = await mutateAsync(values);

    setSession({
      employeeId: session.employeeId,
      organizationId: session.organizationId,
      departmentId: session.departmentId,
      departmentModuleKey: session.departmentModuleKey,
      headsAnyDepartment: session.headsAnyDepartment,
      username: session.username,
      roles: session.roles,
      permissions: session.permissions,
      accessToken: session.accessToken,
      refreshToken: session.refreshToken,
      expiresAt: session.expiresAt,
    });

    navigate(requestedReturnUrl || ROUTES.home, { replace: true });
  };

  return (
    <section className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-7xl items-center justify-center px-4 py-6 sm:px-6 lg:px-8">
      <div className="grid w-full items-stretch gap-8 lg:grid-cols-[minmax(0,1.2fr)_480px]">
        <div className="animate-surface-in relative hidden overflow-hidden rounded-[36px] border border-border/70 bg-card p-8 shadow-[0_32px_90px_-48px_rgba(15,23,42,0.18)] lg:flex lg:flex-col lg:justify-between xl:p-10">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'radial-gradient(circle at 86% 12%, hsl(var(--accent) / 0.2), transparent 26%), radial-gradient(circle at 10% 0%, hsl(var(--primary) / 0.14), transparent 22%), linear-gradient(155deg, hsl(var(--card)) 0%, hsl(var(--background)) 54%, hsl(var(--secondary) / 0.62) 100%)',
            }}
          />
          <div className="relative flex h-full flex-col justify-between gap-10">
            <div className="space-y-8">
              <Badge
                variant="outline"
                className="w-fit bg-background shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)]"
              >
                {APP_NAME} · v{APP_VERSION}
              </Badge>
              <div className="space-y-4">
                <h1
                  className="max-w-2xl text-5xl leading-none tracking-[-0.06em] text-foreground xl:text-6xl"
                  style={{ fontFamily: 'Fraunces, serif' }}
                >
                  {t('login.title')}
                </h1>
                <p className="max-w-xl text-base leading-7 text-muted-foreground">
                  {t('login.sideDescription')}
                </p>
              </div>
            </div>
            <div className="grid gap-4 xl:grid-cols-3">
              <div className="rounded-[24px] border border-border/70 bg-background p-5 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.12)]">
                <div className="border-primary/18 bg-primary/8 mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border text-primary">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-foreground">{t('login.cardOneTitle')}</p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {t('login.cardOneDescription')}
                </p>
              </div>
              <div className="rounded-[24px] border border-border/70 bg-background p-5 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.12)]">
                <div className="border-primary/18 bg-primary/8 mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border text-primary">
                  <KeyRound className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-foreground">{t('login.cardTwoTitle')}</p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {t('login.cardTwoDescription')}
                </p>
              </div>
              <div className="rounded-[24px] border border-border/70 bg-background p-5 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.12)]">
                <div className="border-primary/18 bg-primary/8 mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border text-primary">
                  <Fingerprint className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-foreground">{t('login.cardThreeTitle')}</p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {t('login.cardThreeDescription')}
                </p>
              </div>
            </div>
          </div>
        </div>

        <Card className="animate-surface-in relative overflow-hidden rounded-[36px] border-border/70 bg-card shadow-[0_32px_96px_-52px_rgba(15,23,42,0.2)]">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/80 via-accent/90 to-primary/50" />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full blur-3xl"
            style={{ background: 'hsl(var(--accent) / 0.12)' }}
          />
          <CardHeader className="relative space-y-5 pb-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Badge variant="outline" className="w-fit bg-background">
                {t('login.formBadge')}
              </Badge>
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                {APP_NAME}
              </p>
            </div>
            <div className="space-y-3">
              <CardTitle
                className="text-3xl tracking-[-0.06em] text-foreground sm:text-4xl"
                style={{ fontFamily: 'Fraunces, serif' }}
              >
                {t('login.title')}
              </CardTitle>
              <CardDescription className="max-w-md text-sm leading-6">
                {t('login.description')}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="relative space-y-6">
            <form
              className="space-y-5"
              onSubmit={(event) => {
                void handleSubmit(buildSubmitHandler<LoginValues>(onSubmit))(event);
              }}
            >
              <div className="rounded-[28px] border border-border/70 bg-background p-4 shadow-[0_18px_44px_-34px_rgba(15,23,42,0.1)]">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-foreground/85" htmlFor="username">
                      {t('login.username')}
                    </Label>
                    <Input
                      id="username"
                      type="text"
                      autoComplete="username"
                      autoFocus
                      className="h-12 rounded-2xl border-border/75 bg-card"
                      {...register('username')}
                    />
                    {errors.username ? (
                      <p className="text-xs text-destructive">{errors.username.message}</p>
                    ) : null}
                  </div>
                  <div className="space-y-2">
                    <Label className="text-foreground/85" htmlFor="password">
                      {t('login.password')}
                    </Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={isPasswordVisible ? 'text' : 'password'}
                        autoComplete="current-password"
                        className="h-12 rounded-2xl border-border/75 bg-card pr-12"
                        {...register('password')}
                      />
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                        onClick={() => setIsPasswordVisible((current) => !current)}
                        aria-label={
                          isPasswordVisible
                            ? t('login.hidePassword', undefined, 'Скрыть пароль')
                            : t('login.showPassword', undefined, 'Показать пароль')
                        }
                      >
                        {isPasswordVisible ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                    {errors.password ? (
                      <p className="text-xs text-destructive">{errors.password.message}</p>
                    ) : null}
                  </div>
                </div>
              </div>
              {error ? <ErrorNotice error={error} /> : null}
              <Button
                type="submit"
                className="h-12 w-full rounded-2xl text-sm font-semibold shadow-[0_24px_44px_-24px_rgba(234,88,12,0.38)]"
                disabled={isPending || !canSubmit}
              >
                {isPending ? (
                  t('login.pending')
                ) : (
                  <>
                    {t('login.submit')}
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
            <div className="rounded-[24px] border border-border/70 bg-background px-4 py-3 text-xs leading-5 text-muted-foreground shadow-[0_16px_40px_-30px_rgba(15,23,42,0.08)]">
              {t('login.afterLogin')}
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
