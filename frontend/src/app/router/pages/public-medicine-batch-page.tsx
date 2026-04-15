import { useMemo } from 'react';
import { useParams } from 'react-router-dom';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorNotice } from '@/components/ui/error-notice';
import { getPublicMedicineBatch } from '@/shared/api/medicine';
import { toQueryKey } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';

type DetailRow = {
  label: string;
  value: string;
};

const formatValue = (value: unknown, fallback: string): string => {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'bigint') {
    return String(value);
  }
  return JSON.stringify(value);
};

export function PublicMedicineBatchPage() {
  const { token = '' } = useParams<{ token: string }>();
  const { t } = useI18n();
  const normalizedToken = token.trim();
  const emptyLabel = t('common.empty', undefined, '—');

  const publicBatchQuery = useApiQuery({
    queryKey: toQueryKey('medicine', 'public-batch', normalizedToken || 'empty'),
    queryFn: () => getPublicMedicineBatch(normalizedToken),
    enabled: normalizedToken.length > 0,
  });

  const detailRows = useMemo<DetailRow[]>(() => {
    if (!publicBatchQuery.data) {
      return [];
    }
    const batch = publicBatchQuery.data;
    const supplierName = formatValue(batch.supplier.name, emptyLabel);
    const arrivedQuantity = [
      formatValue(batch.received_quantity, emptyLabel),
      formatValue(batch.unit, ''),
    ]
      .join(' ')
      .trim();
    const remainingQuantity = [
      formatValue(batch.remaining_quantity, emptyLabel),
      formatValue(batch.unit, ''),
    ]
      .join(' ')
      .trim();
    const unitCost = [formatValue(batch.unit_cost, emptyLabel), formatValue(batch.currency, '')]
      .join(' ')
      .trim();

    return [
      {
        label: t('fields.batch_code', undefined, 'Код партии'),
        value: formatValue(batch.batch_code, emptyLabel),
      },
      {
        label: t('fields.barcode', undefined, 'Штрихкод'),
        value: formatValue(batch.barcode, emptyLabel),
      },
      {
        label: t('fields.arrived_on', undefined, 'Дата поступления'),
        value: formatValue(batch.arrived_on, emptyLabel),
      },
      {
        label: t('fields.expiry_date', undefined, 'Срок годности'),
        value: formatValue(batch.expiry_date, emptyLabel),
      },
      {
        label: t('fields.received_quantity', undefined, 'Принято'),
        value: arrivedQuantity || emptyLabel,
      },
      {
        label: t('fields.remaining_quantity', undefined, 'Остаток'),
        value: remainingQuantity || emptyLabel,
      },
      { label: t('fields.unit_cost', undefined, 'Цена за ед.'), value: unitCost || emptyLabel },
      {
        label: t('fields.department_id', undefined, 'Подразделение'),
        value: formatValue(batch.department.name, emptyLabel),
      },
      {
        label: t('fields.organization_id', undefined, 'Организация'),
        value: formatValue(batch.organization.name, emptyLabel),
      },
      { label: t('fields.supplier_client_id', undefined, 'Поставщик'), value: supplierName },
      {
        label: t('fields.note', undefined, 'Комментарий'),
        value: formatValue(batch.note, emptyLabel),
      },
    ];
  }, [emptyLabel, publicBatchQuery.data, t]);

  if (!normalizedToken) {
    return (
      <Card className="w-full max-w-3xl rounded-[28px] border-border/75 bg-card">
        <CardHeader>
          <CardTitle>
            {t('publicMedicine.invalidTokenTitle', undefined, 'Некорректная ссылка')}
          </CardTitle>
          <CardDescription>
            {t(
              'publicMedicine.invalidTokenDescription',
              undefined,
              'В ссылке отсутствует токен для публичной карточки товара.',
            )}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (publicBatchQuery.isLoading) {
    return (
      <Card className="w-full max-w-3xl rounded-[28px] border-border/75 bg-card">
        <CardHeader>
          <CardTitle>{t('common.loadingLabel', undefined, 'Загрузка')}</CardTitle>
          <CardDescription>
            {t('publicMedicine.loadingDescription', undefined, 'Получаем данные о товаре...')}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (publicBatchQuery.error || !publicBatchQuery.data) {
    return (
      <div className="w-full max-w-3xl space-y-4">
        {publicBatchQuery.error ? <ErrorNotice error={publicBatchQuery.error} /> : null}
        <Card className="rounded-[28px] border-border/75 bg-card">
          <CardHeader>
            <CardTitle>
              {t('publicMedicine.notFoundTitle', undefined, 'Карточка не найдена')}
            </CardTitle>
            <CardDescription>
              {t(
                'publicMedicine.notFoundDescription',
                undefined,
                'Ссылка недействительна или срок действия QR-кода истёк.',
              )}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const batch = publicBatchQuery.data;

  return (
    <Card className="w-full max-w-3xl rounded-[28px] border-border/75 bg-card shadow-[0_26px_76px_-44px_rgba(15,23,42,0.18)]">
      <CardHeader className="space-y-2">
        <CardTitle className="text-2xl tracking-[-0.03em]">
          {formatValue(
            batch.medicine_type.name,
            t('publicMedicine.unnamedProduct', undefined, 'Товар'),
          )}
        </CardTitle>
        <CardDescription>
          {t('publicMedicine.subtitle', undefined, 'Публичная карточка товара из ветаптеки')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <dl className="grid gap-3 md:grid-cols-2">
          {detailRows.map((row) => (
            <div key={row.label} className="rounded-2xl border border-border/70 bg-card px-4 py-3">
              <dt className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                {row.label}
              </dt>
              <dd className="mt-1 text-sm text-foreground">{row.value}</dd>
            </div>
          ))}
        </dl>

        {batch.attachment?.url ? (
          <a
            href={batch.attachment.url}
            className="inline-flex items-center rounded-full border border-border/75 bg-card px-4 py-2 text-sm font-medium text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] transition-colors hover:bg-muted"
          >
            {t('publicMedicine.downloadAttachment', undefined, 'Скачать вложение')}
          </a>
        ) : null}
      </CardContent>
    </Card>
  );
}
