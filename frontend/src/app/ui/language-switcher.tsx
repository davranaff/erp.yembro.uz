import { Languages } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useI18n, type Language } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

const options: Language[] = ['uz', 'ru', 'en'];

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { language, setLanguage, t } = useI18n();

  return (
    <div
      aria-label={t('language.label')}
      className={cn(
        'bg-background/99 inline-flex items-center gap-1 rounded-xl border border-border/75 p-1',
        compact
          ? 'w-full justify-between rounded-md border-0 bg-transparent p-0 shadow-none'
          : 'shadow-[0_18px_48px_-36px_rgba(15,23,42,0.14)]',
      )}
    >
      <div
        className={cn(
          'bg-background/99 flex h-8 w-8 items-center justify-center rounded-lg border border-border/75 text-primary',
          compact && 'h-7 w-7 rounded-md',
        )}
      >
        <Languages className="h-4 w-4" />
      </div>
      {options.map((option) => (
        <Button
          key={option}
          type="button"
          variant="ghost"
          size="sm"
          className={cn(
            compact ? 'flex-1 rounded-md px-2' : 'rounded-lg px-3',
            language === option
              ? 'bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground'
              : 'text-muted-foreground hover:bg-background hover:text-foreground',
          )}
          onClick={() => setLanguage(option)}
        >
          {t(`language.${option}`)}
        </Button>
      ))}
    </div>
  );
}
