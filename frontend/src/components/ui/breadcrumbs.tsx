import { ChevronRight, Home } from 'lucide-react';
import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

export type BreadcrumbItem = {
  label: string;
  to?: string;
  icon?: ReactNode;
  isCurrent?: boolean;
};

type BreadcrumbsProps = {
  items: BreadcrumbItem[];
  className?: string;
};

export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  const { t } = useI18n();
  if (items.length === 0) {
    return null;
  }

  return (
    <nav
      aria-label={t('nav.breadcrumb', undefined, 'Навигационная цепочка')}
      className={cn('min-w-0', className)}
    >
      <ol className="flex min-w-0 flex-wrap items-center gap-1 text-xs text-muted-foreground">
        {items.map((item, index) => {
          const isLast = index === items.length - 1 || item.isCurrent;
          const content = (
            <span className="inline-flex items-center gap-1 truncate">
              {item.icon ?? (index === 0 ? <Home className="h-3 w-3" aria-hidden="true" /> : null)}
              <span className="truncate">{item.label}</span>
            </span>
          );
          return (
            <li key={`${item.label}-${index}`} className="flex min-w-0 items-center gap-1">
              {item.to && !isLast ? (
                <Link
                  to={item.to}
                  className="max-w-[14rem] truncate rounded-md px-1.5 py-0.5 transition hover:bg-slate-50 hover:text-foreground"
                >
                  {content}
                </Link>
              ) : (
                <span
                  aria-current={isLast ? 'page' : undefined}
                  className={cn(
                    'max-w-[14rem] truncate px-1.5 py-0.5',
                    isLast ? 'font-medium text-foreground' : null,
                  )}
                >
                  {content}
                </span>
              )}
              {!isLast ? <ChevronRight className="h-3 w-3 opacity-60" aria-hidden="true" /> : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
