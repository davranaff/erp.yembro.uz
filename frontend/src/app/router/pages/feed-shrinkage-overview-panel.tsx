import { Loader2, Snowflake, Wheat } from 'lucide-react';

import { ErrorNotice } from '@/components/ui/error-notice';
import {
  getFeedShrinkageOverview,
  type FeedShrinkageOverview,
  type FeedShrinkageOverviewItem,
} from '@/shared/api/feed-shrinkage';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

const numberFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

const formatKg = (raw: string): string => {
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    return raw;
  }
  return `${numberFormatter.format(value)} кг`;
};

const formatPercent = (raw: string): string => {
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    return raw;
  }
  return `${value.toFixed(2)}%`;
};

const formatDate = (value: string | null | undefined): string => {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleDateString('ru-RU');
  } catch {
    return value;
  }
};

type LotRowProps = {
  item: FeedShrinkageOverviewItem;
};

function LotRow({ item }: LotRowProps) {
  const nameLabel = [item.name, item.code].filter(Boolean).join(' · ');
  return (
    <tr className="border-b border-border/60 last:border-b-0">
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-foreground">{nameLabel || item.lot_id.slice(0, 8)}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {formatDate(item.started_on)}
          {item.warehouse_name ? ` · ${item.warehouse_name}` : ''}
        </div>
      </td>
      <td className="px-4 py-3 text-right align-top text-sm text-muted-foreground">
        {formatKg(item.initial_quantity)}
      </td>
      <td className="px-4 py-3 text-right align-top">
        <div className="text-base font-semibold text-foreground">
          {formatKg(item.current_quantity)}
        </div>
        <div className="mt-0.5 text-xs text-rose-600">
          −{formatKg(item.loss_quantity)} ({formatPercent(item.loss_percent)})
        </div>
      </td>
      <td className="px-4 py-3 align-top text-right text-xs text-muted-foreground">
        {item.is_frozen ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-700 ring-1 ring-inset ring-sky-500/25">
            <Snowflake className="h-3 w-3" />
            заморожено
          </span>
        ) : (
          <span>обн. {formatDate(item.last_applied_on)}</span>
        )}
      </td>
    </tr>
  );
}

type SectionProps = {
  title: string;
  subtitle: string;
  items: FeedShrinkageOverviewItem[];
  emptyLabel: string;
};

function Section({ title, subtitle, items, emptyLabel }: SectionProps) {
  return (
    <section className="space-y-3 rounded-2xl border border-border/70 bg-background/60 p-5 shadow-[0_16px_48px_-32px_rgba(15,23,42,0.14)]">
      <header className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Wheat className="h-4 w-4" />
        </span>
        <div>
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </header>
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
          {emptyLabel}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Партия</th>
                <th className="px-4 py-2 text-right font-medium">Было (приход)</th>
                <th className="px-4 py-2 text-right font-medium">Сейчас</th>
                <th className="px-4 py-2 text-right font-medium">Статус</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <LotRow key={item.state_id} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function FeedShrinkageOverviewPanel() {
  const { t } = useI18n();

  const overviewQuery = useApiQuery<FeedShrinkageOverview>({
    queryKey: ['feed', 'shrinkage', 'overview'],
    queryFn: () => getFeedShrinkageOverview(),
    // Apply-on-view is idempotent via last_applied_on — fine to re-query
    // when the user comes back to the tab, but no need to burn requests.
    staleTime: 30_000,
  });

  const isLoading = overviewQuery.isLoading && !overviewQuery.data;

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            {t('feed.shrinkageOverview.title', undefined, 'Обзор усушки')}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t(
              'feed.shrinkageOverview.subtitle',
              undefined,
              'Автоматически: для каждой партии — сколько было на приходе и сколько осталось с учётом усушки.',
            )}
          </p>
        </div>
      </header>

      {isLoading ? (
        <div
          className={cn(
            'flex items-center gap-2 rounded-2xl border border-dashed border-border/70',
            'bg-muted/20 px-4 py-6 text-sm text-muted-foreground',
          )}
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('common.loadingLabel', undefined, 'Загружаем…')}
        </div>
      ) : null}

      {overviewQuery.error ? <ErrorNotice error={overviewQuery.error} /> : null}

      {overviewQuery.data ? (
        <div className="grid gap-5 xl:grid-cols-2">
          <Section
            title={t('feed.shrinkageOverview.ingredientsTitle', undefined, 'Сырьё')}
            subtitle={t(
              'feed.shrinkageOverview.ingredientsSubtitle',
              undefined,
              'Партии сырья с активным профилем усушки.',
            )}
            items={overviewQuery.data.ingredients}
            emptyLabel={t(
              'feed.shrinkageOverview.ingredientsEmpty',
              undefined,
              'Нет подходящих партий сырья. Заведите профиль для ингредиента и привяжите приход — здесь появится партия.',
            )}
          />
          <Section
            title={t('feed.shrinkageOverview.feedProductsTitle', undefined, 'Готовый корм')}
            subtitle={t(
              'feed.shrinkageOverview.feedProductsSubtitle',
              undefined,
              'Производственные партии с активным профилем усушки.',
            )}
            items={overviewQuery.data.feed_products}
            emptyLabel={t(
              'feed.shrinkageOverview.feedProductsEmpty',
              undefined,
              'Нет подходящих партий готового корма.',
            )}
          />
        </div>
      ) : null}
    </div>
  );
}
