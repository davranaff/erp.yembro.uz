import { ArrowRight, Eye, EyeOff, Loader2, LockKeyhole, UserRound } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useApiMutation } from '@/shared/api';
import { loginWithCredentials, type AuthLoginResponse } from '@/shared/api/auth';
import { useAuthStore } from '@/shared/auth';
import { ROUTES } from '@/shared/config/routes';
import { APP_NAME } from '@/shared/constants/app';
import { buildSubmitHandler, useBaseForm } from '@/shared/forms';
import { useI18n } from '@/shared/i18n';

type RouteLocationState = {
  from?: string;
};

const logoPath = '/logo/logo.png';

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
    <section className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-md items-center justify-center px-3 py-6 sm:px-6 sm:py-10">
      <div className="bg-background/86 supports-[backdrop-filter]:bg-background/76 fixed left-4 top-4 z-40 rounded-[22px] border border-border/70 px-3 py-3 shadow-[0_20px_44px_-34px_rgba(15,23,42,0.18)] backdrop-blur-xl">
        <img
          src={logoPath}
          alt={APP_NAME}
          className="h-auto w-full max-w-[8.5rem] object-contain sm:max-w-[9.5rem]"
        />
      </div>

      <Card className="animate-surface-in relative w-full overflow-hidden rounded-[34px] border-border/70 bg-card shadow-[0_32px_96px_-52px_rgba(15,23,42,0.2)]">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/80 via-accent/90 to-primary/50" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(circle at top right, hsl(var(--accent) / 0.16), transparent 24%), radial-gradient(circle at top left, hsl(var(--primary) / 0.14), transparent 18%), radial-gradient(circle at 50% 100%, hsl(var(--secondary) / 0.18), transparent 30%)',
          }}
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 h-40 w-40 -translate-x-1/2 rounded-full blur-3xl"
          style={{ background: 'hsl(var(--primary) / 0.08)' }}
        />

        <CardContent className="relative p-5 sm:p-6">
          <form
            className="space-y-4"
            onSubmit={(event) => {
              void handleSubmit(buildSubmitHandler<LoginValues>(onSubmit))(event);
            }}
          >
            <div className="space-y-4 text-center">
              <div className="space-y-1.5">
                <h1
                  className="text-3xl tracking-[-0.06em] text-foreground sm:text-4xl"
                  style={{ fontFamily: 'Fraunces, serif' }}
                >
                  {t('login.title')}
                </h1>
              </div>
            </div>

            <div className="bg-background/94 supports-[backdrop-filter]:bg-background/88 rounded-[28px] border border-border/70 p-4 shadow-[0_22px_52px_-34px_rgba(15,23,42,0.12)] backdrop-blur-xl sm:p-5">
              <div className="space-y-5">
                <div className="space-y-2">
                  <Label className="text-foreground/85" htmlFor="username">
                    {t('login.username')}
                  </Label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-xl border border-border/70 bg-background text-muted-foreground shadow-[0_12px_24px_-22px_rgba(15,23,42,0.18)]">
                      <UserRound className="h-4 w-4" />
                    </span>
                    <Input
                      id="username"
                      type="text"
                      autoComplete="username"
                      autoFocus
                      className="h-12 rounded-2xl border-border/75 bg-card pl-14"
                      {...register('username')}
                    />
                  </div>
                  {errors.username ? (
                    <p className="text-xs text-destructive">{errors.username.message}</p>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <Label className="text-foreground/85" htmlFor="password">
                    {t('login.password')}
                  </Label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-xl border border-border/70 bg-background text-muted-foreground shadow-[0_12px_24px_-22px_rgba(15,23,42,0.18)]">
                      <LockKeyhole className="h-4 w-4" />
                    </span>
                    <Input
                      id="password"
                      type={isPasswordVisible ? 'text' : 'password'}
                      autoComplete="current-password"
                      className="h-12 rounded-2xl border-border/75 bg-card pl-14 pr-12"
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

            <div className="border-primary/18 bg-background/86 supports-[backdrop-filter]:bg-background/78 rounded-[24px] border p-2 shadow-[0_18px_44px_-30px_rgba(234,88,12,0.18)] backdrop-blur-xl">
              <Button
                type="submit"
                className="h-12 w-full rounded-2xl text-sm font-semibold shadow-[0_24px_44px_-24px_rgba(234,88,12,0.38)]"
                disabled={isPending || !canSubmit}
              >
                {isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    {t('login.pending')}
                  </>
                ) : (
                  <>
                    {t('login.submit')}
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}
