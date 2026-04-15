import { zodResolver } from '@hookform/resolvers/zod';
import { LockKeyhole, Pencil, Save, ShieldCheck, UserRound, type LucideIcon } from 'lucide-react';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CrudDrawer, CrudDrawerFooter } from '@/components/ui/crud-drawer';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { Sheet } from '@/components/ui/sheet';
import {
  createAuthProfileUpdateSchema,
  getMyProfile,
  updateMyProfile,
  type AuthProfileUpdate,
} from '@/shared/api/auth';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
import { useAuthStore } from '@/shared/auth';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

import {
  drawerPrimaryButtonClassName,
  getProfileInitials,
  settingsAvatarTileClassName,
  settingsCardClassName,
  settingsGlassPanelSoftClassName,
  settingsHeroCardClassName,
  settingsIconTileClassName,
} from './settings-page.helpers';

const EMPTY_AUTH_ITEMS: string[] = [];

const defaultValues: AuthProfileUpdate = {
  firstName: '',
  lastName: '',
  email: '',
  phone: '',
  currentPassword: '',
  newPassword: '',
  confirmNewPassword: '',
};

export function SettingsPage() {
  const { t } = useI18n();
  const authSession = useAuthStore((state) => state.session);
  const schema = useMemo(() => createAuthProfileUpdateSchema(t), [t]);
  const [isAccountSheetOpen, setIsAccountSheetOpen] = useState(false);
  const profileQuery = useApiQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMyProfile,
  });

  const form = useForm<AuthProfileUpdate>({
    resolver: zodResolver(schema),
    defaultValues,
    mode: 'onSubmit',
  });

  useEffect(() => {
    if (!profileQuery.data) {
      return;
    }

    form.reset({
      firstName: profileQuery.data.firstName,
      lastName: profileQuery.data.lastName,
      email: profileQuery.data.email ?? '',
      phone: profileQuery.data.phone ?? '',
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    });
  }, [form, profileQuery.data]);

  const updateProfileMutation = useApiMutation({
    mutationKey: ['auth', 'me', 'update'],
    mutationFn: (values: AuthProfileUpdate) => {
      const currentPassword = values.currentPassword ?? '';
      const newPassword = values.newPassword ?? '';

      return updateMyProfile({
        firstName: values.firstName.trim(),
        lastName: values.lastName.trim(),
        email: values.email?.trim() || undefined,
        phone: values.phone?.trim() || undefined,
        currentPassword: currentPassword.trim() || undefined,
        newPassword: newPassword.trim() || undefined,
      });
    },
    onSuccess: (profile) => {
      form.reset({
        firstName: profile.firstName,
        lastName: profile.lastName,
        email: profile.email ?? '',
        phone: profile.phone ?? '',
        currentPassword: '',
        newPassword: '',
        confirmNewPassword: '',
      });
      setIsAccountSheetOpen(false);
      void profileQuery.refetch();
    },
  });

  const sessionRoles = authSession?.roles ?? profileQuery.data?.roles ?? EMPTY_AUTH_ITEMS;
  const sessionPermissions =
    authSession?.permissions ?? profileQuery.data?.permissions ?? EMPTY_AUTH_ITEMS;
  const profileInitials = getProfileInitials(
    profileQuery.data?.firstName,
    profileQuery.data?.lastName,
    profileQuery.data?.username,
  );
  const overviewItems = useMemo<
    Array<{ key: string; label: string; value: string; icon: LucideIcon; caption?: string }>
  >(
    () => [
      {
        key: 'username',
        label: t('settings.username'),
        value: profileQuery.data?.username ?? t('common.empty'),
        icon: UserRound,
      },
      {
        key: 'roles',
        label: t('settings.rolesTitle'),
        value: String(sessionRoles.length),
        icon: ShieldCheck,
        caption: sessionRoles.length > 0 ? sessionRoles.join(', ') : t('common.empty'),
      },
      {
        key: 'permissions',
        label: t('settings.permissionsTitle'),
        value: String(sessionPermissions.length),
        icon: LockKeyhole,
        caption: t('common.totalRecords', { count: sessionPermissions.length }),
      },
    ],
    [profileQuery.data?.username, sessionPermissions, sessionRoles, t],
  );
  const onSubmit = form.handleSubmit((values) => {
    updateProfileMutation.mutate(values);
  });

  return (
    <div className="space-y-6" data-tour="settings-page">
      <Card className={settingsHeroCardClassName} data-tour="settings-tabs">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(circle at 88% 10%, hsl(var(--accent) / 0.14), transparent 24%), radial-gradient(circle at 12% 0%, hsl(var(--primary) / 0.12), transparent 18%)',
          }}
        />
        <CardContent className="relative space-y-5 p-4 sm:p-5">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl space-y-4">
              <div className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('settings.title', undefined, 'Настройки')}
                </p>
                <h1 className="text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">
                  {t('settings.profileTitle')}
                </h1>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                  {t(
                    'settings.heroDescription',
                    undefined,
                    'Управляйте профилем, безопасностью и текущим рабочим контекстом.',
                  )}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <span
                  data-tour="settings-tab-account"
                  className="inline-flex items-center rounded-full border border-primary/20 bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-[0_18px_42px_-28px_rgba(234,88,12,0.42)]"
                >
                  {t('settings.profileTitle')}
                </span>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:w-[min(100%,25rem)]">
              {overviewItems.map((item) => (
                <SettingsOverviewTile
                  key={item.key}
                  label={item.label}
                  value={item.value}
                  caption={item.caption}
                  icon={item.icon}
                />
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.12fr)_minmax(22rem,0.88fr)]">
        <Card className={settingsCardClassName} data-tour="settings-account-profile">
          <CardHeader className="gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className={settingsIconTileClassName}>
                <UserRound className="h-4 w-4 text-primary" />
              </div>
              <div className="space-y-2">
                <CardTitle className="text-2xl tracking-[-0.04em]">
                  {t('settings.profileTitle')}
                </CardTitle>
                <CardDescription>{t('settings.accountTabDescription')}</CardDescription>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className={settingsAvatarTileClassName}>{profileInitials}</div>
              <Button
                type="button"
                onClick={() => setIsAccountSheetOpen(true)}
                disabled={profileQuery.isLoading}
                data-tour="settings-open-account-drawer"
              >
                <Pencil className="h-4 w-4" />
                {t('common.edit')}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {profileQuery.error ? <ErrorNotice error={profileQuery.error} /> : null}

            <div className="grid gap-4 md:grid-cols-2">
              <Field
                label={t('settings.username')}
                value={profileQuery.data?.username ?? ''}
                readOnly
              />
              <Field
                label={t('settings.firstName')}
                value={profileQuery.data?.firstName ?? ''}
                readOnly
              />
              <Field
                label={t('settings.lastName')}
                value={profileQuery.data?.lastName ?? ''}
                readOnly
              />
              <Field label={t('settings.email')} value={profileQuery.data?.email ?? ''} readOnly />
              <Field label={t('settings.phone')} value={profileQuery.data?.phone ?? ''} readOnly />
              <Field
                label={t('fields.organization_id')}
                value={profileQuery.data?.organizationId ?? authSession?.organizationId ?? ''}
                readOnly
              />
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className={settingsCardClassName} data-tour="settings-access-summary">
            <CardHeader className="space-y-3">
              <div className={settingsIconTileClassName}>
                <ShieldCheck className="h-4 w-4 text-primary" />
              </div>
              <div className="space-y-2">
                <CardTitle className="text-2xl tracking-[-0.04em]">
                  {t('settings.accessTitle')}
                </CardTitle>
                <CardDescription>{t('settings.accessDescription')}</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className={cn(settingsGlassPanelSoftClassName, 'space-y-3 p-4')}>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('settings.rolesTitle')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {sessionRoles.length > 0 ? (
                    sessionRoles.map((role) => (
                      <span
                        key={role}
                        className="rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs font-medium text-foreground"
                      >
                        {role}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">{t('common.empty')}</span>
                  )}
                </div>
              </div>

              <div
                className={cn(settingsGlassPanelSoftClassName, 'space-y-2 p-4')}
                data-tour="settings-context-summary"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('settings.permissionsTitle')}
                </p>
                <p className="text-2xl font-semibold tracking-[-0.04em] text-foreground">
                  {sessionPermissions.length}
                </p>
              </div>

              <div className={cn(settingsGlassPanelSoftClassName, 'space-y-2 p-4')}>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('settings.contextTitle')}
                </p>
                <div className="grid gap-3">
                  <Field
                    label={t('fields.organization_id')}
                    value={profileQuery.data?.organizationId ?? authSession?.organizationId ?? ''}
                    readOnly
                  />
                  <Field
                    label={t('fields.department_id')}
                    value={
                      profileQuery.data?.departmentId ??
                      authSession?.departmentId ??
                      t('common.empty')
                    }
                    readOnly
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className={settingsCardClassName} data-tour="settings-account-security">
            <CardHeader className="space-y-3">
              <div className={settingsIconTileClassName}>
                <LockKeyhole className="h-4 w-4 text-primary" />
              </div>
              <div className="space-y-2">
                <CardTitle className="text-2xl tracking-[-0.04em]">
                  {t('settings.securityTitle')}
                </CardTitle>
                <CardDescription>{t('settings.securityDescription')}</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                type="button"
                className="w-full"
                onClick={() => setIsAccountSheetOpen(true)}
                data-tour="settings-open-account-drawer"
              >
                <LockKeyhole className="h-4 w-4" />
                {t('settings.securityTitle')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Sheet open={isAccountSheetOpen} onOpenChange={setIsAccountSheetOpen}>
        <CrudDrawer
          dataTour="settings-account-drawer"
          size="wide"
          title={t('settings.profileTitle')}
          description={t(
            'settings.description',
            undefined,
            'Редактирование личных данных и параметров безопасности.',
          )}
          bodyClassName="flex-1 space-y-6 overflow-y-auto bg-background px-4 py-4 sm:px-6 sm:py-5 xl:px-8"
          formProps={{
            onSubmit: (event) => {
              void onSubmit(event);
            },
          }}
          footer={
            <CrudDrawerFooter
              closeLabel={t('common.close')}
              closeDisabled={updateProfileMutation.isPending}
              onClose={() => setIsAccountSheetOpen(false)}
            >
              <Button
                type="submit"
                className={drawerPrimaryButtonClassName}
                disabled={profileQuery.isLoading || updateProfileMutation.isPending}
              >
                <Save className="h-4 w-4" />
                {t('common.save')}
              </Button>
            </CrudDrawerFooter>
          }
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <Card className={settingsCardClassName}>
              <CardHeader>
                <div className={settingsIconTileClassName}>
                  <UserRound className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-xl tracking-[-0.04em]">
                  {t('settings.profileTitle')}
                </CardTitle>
                <CardDescription>{t('settings.profileDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Field
                  label={t('settings.username')}
                  value={profileQuery.data?.username ?? ''}
                  readOnly
                />
                <ControlledField
                  label={t('settings.firstName')}
                  error={form.formState.errors.firstName?.message}
                >
                  <Input {...form.register('firstName')} />
                </ControlledField>
                <ControlledField
                  label={t('settings.lastName')}
                  error={form.formState.errors.lastName?.message}
                >
                  <Input {...form.register('lastName')} />
                </ControlledField>
                <ControlledField
                  label={t('settings.email')}
                  error={form.formState.errors.email?.message}
                >
                  <Input {...form.register('email')} type="email" />
                </ControlledField>
                <ControlledField
                  label={t('settings.phone')}
                  error={form.formState.errors.phone?.message}
                >
                  <Input {...form.register('phone')} />
                </ControlledField>
              </CardContent>
            </Card>

            <Card className={settingsCardClassName}>
              <CardHeader>
                <div className={settingsIconTileClassName}>
                  <LockKeyhole className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-xl tracking-[-0.04em]">
                  {t('settings.securityTitle')}
                </CardTitle>
                <CardDescription>{t('settings.securityDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <ControlledField
                  label={t('settings.currentPassword')}
                  error={form.formState.errors.currentPassword?.message}
                >
                  <Input {...form.register('currentPassword')} type="password" />
                </ControlledField>
                <ControlledField
                  label={t('settings.newPassword')}
                  error={form.formState.errors.newPassword?.message}
                >
                  <Input {...form.register('newPassword')} type="password" />
                </ControlledField>
                <ControlledField
                  label={t('settings.confirmNewPassword')}
                  error={form.formState.errors.confirmNewPassword?.message}
                >
                  <Input {...form.register('confirmNewPassword')} type="password" />
                </ControlledField>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-2">
            {profileQuery.error ? <ErrorNotice error={profileQuery.error} /> : null}
            {updateProfileMutation.error ? (
              <ErrorNotice error={updateProfileMutation.error} />
            ) : null}
            {updateProfileMutation.isSuccess ? (
              <p className="text-sm text-primary">{t('settings.success')}</p>
            ) : null}
          </div>
        </CrudDrawer>
      </Sheet>
    </div>
  );
}

function SettingsOverviewTile({
  label,
  value,
  caption,
  icon: Icon,
}: {
  label: string;
  value: string;
  caption?: string;
  icon: LucideIcon;
}) {
  return (
    <div className={cn(settingsGlassPanelSoftClassName, 'p-4')}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </p>
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl border border-border/70 bg-background text-primary shadow-[0_12px_28px_-24px_rgba(15,23,42,0.12)]">
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-3 line-clamp-2 text-lg font-semibold leading-6 tracking-[-0.03em] text-foreground">
        {value}
      </p>
      {caption ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{caption}</p> : null}
    </div>
  );
}

function ControlledField({
  children,
  label,
  error,
  className,
}: {
  children: ReactNode;
  label: string;
  error?: string;
  className?: string;
}) {
  return (
    <div className={cn('space-y-2', className)}>
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function Field({
  label,
  value,
  readOnly = false,
}: {
  label: string;
  value: string;
  readOnly?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <Input value={value} readOnly={readOnly} />
    </div>
  );
}
