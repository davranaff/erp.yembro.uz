'use client';

import { Dialog as SheetPrimitive } from '@base-ui/react/dialog';
import { Maximize2, Minimize2, XIcon } from 'lucide-react';
import { type ComponentProps, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import {
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';
import { useCrudShellModeStore } from '@/shared/preferences/crud-shell-mode';

type CrudDrawerSize = 'default' | 'wide' | 'xwide' | 'audit' | 'audit-wide';

type CrudDrawerProps = {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: CrudDrawerSize;
  dataTour?: string;
  className?: string;
  headerClassName?: string;
  bodyClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
  formProps?: Omit<ComponentProps<'form'>, 'children'>;
};

type CrudDrawerFooterProps = {
  children?: ReactNode;
  closeLabel: ReactNode;
  closeDisabled?: boolean;
  closeButtonClassName?: string;
  className?: string;
  actionsClassName?: string;
  align?: 'auto' | 'between' | 'end';
  onClose: () => void;
};

const drawerSizeClassNames: Record<CrudDrawerSize, string> = {
  default: 'data-[side=right]:sm:max-w-[760px]',
  wide: 'data-[side=right]:xl:max-w-[1080px]',
  xwide: 'data-[side=right]:xl:max-w-[1140px]',
  audit: 'data-[side=right]:sm:max-w-[860px]',
  'audit-wide': 'data-[side=right]:sm:max-w-[880px]',
};

const modalSizeClassNames: Record<CrudDrawerSize, string> = {
  default: 'sm:max-w-[960px]',
  wide: 'sm:max-w-[1200px]',
  xwide: 'sm:max-w-[1320px]',
  audit: 'sm:max-w-[1100px]',
  'audit-wide': 'sm:max-w-[1180px]',
};

const drawerContentBaseClassName =
  'border-primary/16 w-full min-h-0 gap-0 border-l p-0 shadow-[0_32px_120px_-56px_rgba(15,23,42,0.28)]';

const modalPopupBaseClassName =
  'data-ending-style:opacity-0 data-starting-style:opacity-0 data-ending-style:scale-[0.98] data-starting-style:scale-[0.98] supports-[backdrop-filter]:bg-background/96 bg-background/99 fixed left-1/2 top-1/2 z-50 flex max-h-[92dvh] w-[min(96vw,1200px)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-[28px] border border-primary/16 shadow-[0_32px_120px_-56px_rgba(15,23,42,0.32)] backdrop-blur-xl transition duration-200 ease-out';

const bodyBaseClassName =
  'min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain bg-background px-4 py-4 sm:space-y-5 sm:px-6 sm:py-5';

const closeButtonBaseClassName =
  'bg-card border-border/75 shadow-[0_16px_38px_-28px_rgba(15,23,42,0.1)]';

const headerActionButtonClassName =
  'border-primary/18 bg-background/98 shadow-[0_14px_32px_-26px_rgba(15,23,42,0.14)]';

function ShellModeToggle() {
  const { t } = useI18n();
  const mode = useCrudShellModeStore((state) => state.mode);
  const toggleMode = useCrudShellModeStore((state) => state.toggleMode);
  const isModal = mode === 'modal';

  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      className={headerActionButtonClassName}
      onClick={toggleMode}
      aria-label={
        isModal
          ? t('crudShell.switchToDrawer', undefined, 'Перевести в боковую панель')
          : t('crudShell.switchToModal', undefined, 'Перевести в окно по центру')
      }
      title={
        isModal
          ? t('crudShell.switchToDrawer', undefined, 'Перевести в боковую панель')
          : t('crudShell.switchToModal', undefined, 'Перевести в окно по центру')
      }
    >
      {isModal ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
    </Button>
  );
}

function HeaderActions() {
  const { t } = useI18n();

  return (
    <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
      <ShellModeToggle />
      <SheetPrimitive.Close
        data-slot="sheet-close"
        aria-label={t('common.close')}
        render={
          <Button
            variant="outline"
            className={headerActionButtonClassName}
            size="icon-sm"
            aria-label={t('common.close')}
          />
        }
      >
        <XIcon className="h-4 w-4" />
        <span className="sr-only">{t('common.close')}</span>
      </SheetPrimitive.Close>
    </div>
  );
}

function CrudModalContent({
  size,
  dataTour,
  className,
  children,
}: {
  size: CrudDrawerSize;
  dataTour?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Backdrop
        data-slot="sheet-overlay"
        className="data-ending-style:opacity-0 data-starting-style:opacity-0 fixed inset-0 z-50 bg-[rgba(15,23,42,0.28)] backdrop-blur-[3px] transition-opacity duration-200 ease-out"
      />
      <SheetPrimitive.Popup
        data-slot="sheet-content"
        data-side="center"
        data-tour={dataTour}
        className={cn(modalPopupBaseClassName, modalSizeClassNames[size], className)}
      >
        {children}
      </SheetPrimitive.Popup>
    </SheetPrimitive.Portal>
  );
}

export function CrudDrawer({
  title,
  description,
  children,
  footer,
  size = 'default',
  dataTour,
  className,
  headerClassName,
  bodyClassName,
  titleClassName,
  descriptionClassName,
  formProps,
}: CrudDrawerProps) {
  const mode = useCrudShellModeStore((state) => state.mode);
  const isModal = mode === 'modal';

  const body = <div className={cn(bodyBaseClassName, bodyClassName)}>{children}</div>;

  const inner = (
    <>
      <SheetHeader className={cn('gap-2 px-4 py-4 sm:px-6 sm:py-5', headerClassName)}>
        <SheetTitle className={cn('text-xl tracking-[-0.04em] sm:text-2xl', titleClassName)}>
          {title}
        </SheetTitle>
        {description ? (
          <SheetDescription className={cn('leading-6', descriptionClassName)}>
            {description}
          </SheetDescription>
        ) : null}
      </SheetHeader>

      {formProps ? (
        <form {...formProps} className={cn('flex min-h-0 flex-1 flex-col', formProps.className)}>
          {body}
          {footer}
        </form>
      ) : (
        <>
          {body}
          {footer}
        </>
      )}

      <HeaderActions />
    </>
  );

  if (isModal) {
    return (
      <CrudModalContent size={size} dataTour={dataTour} className={className}>
        {inner}
      </CrudModalContent>
    );
  }

  return (
    <SheetContent
      side="right"
      showCloseButton={false}
      data-tour={dataTour}
      className={cn(drawerContentBaseClassName, drawerSizeClassNames[size], className)}
    >
      {inner}
    </SheetContent>
  );
}

export function CrudDrawerFooter({
  children,
  closeLabel,
  closeDisabled = false,
  closeButtonClassName,
  className,
  actionsClassName,
  align = 'auto',
  onClose,
}: CrudDrawerFooterProps) {
  const resolvedAlign = align === 'auto' ? (children ? 'between' : 'end') : align;

  return (
    <SheetFooter
      className={cn(
        'px-4 py-4 sm:flex-row sm:items-center sm:px-6 sm:py-5',
        resolvedAlign === 'between' ? 'sm:justify-between' : 'sm:justify-end',
        className,
      )}
    >
      {children ? (
        <div
          className={cn(
            'flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap',
            actionsClassName,
          )}
        >
          {children}
        </div>
      ) : null}
      <Button
        type="button"
        variant="outline"
        className={cn(closeButtonBaseClassName, 'w-full sm:w-auto', closeButtonClassName)}
        onClick={onClose}
        disabled={closeDisabled}
      >
        {closeLabel}
      </Button>
    </SheetFooter>
  );
}
