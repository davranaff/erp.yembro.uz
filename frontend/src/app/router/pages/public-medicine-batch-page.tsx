import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { getPublicMedicineBatch, sellPublicMedicineBatch } from '@/shared/api/medicine';
import { toQueryKey } from '@/shared/api/query-keys';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
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

  const [sellOpen, setSellOpen] = useState(false);
  const [sellQuantity, setSellQuantity] = useState('');
  const [sellAmount, setSellAmount] = useState('');
  const [sellNote, setSellNote] = useState('');
  const [sellSuccess, setSellSuccess] = useState(false);

  const sellMutation = useApiMutation({
    mutationKey: toQueryKey('medicine', 'public-sell', normalizedToken || 'empty'),
    mutationFn: async () => {
      const quantity = sellQuantity.replace(',', '.').trim();
      const amount = sellAmount.replace(',', '.').trim();
      return sellPublicMedicineBatch(normalizedToken, {
        quantity,
        amount,
        note: sellNote.trim() || undefined,
      });
    },
    onSuccess: () => {
      void publicBatchQuery.refetch();
      setSellSuccess(true);
      setSellQuantity('');
      setSellAmount('');
      setSellNote('');
      setSellOpen(false);
    },
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

        <div className="space-y-3 rounded-2xl border border-border/70 bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">
                {t('publicMedicine.sellTitle', undefined, 'Быстрая продажа')}
              </h3>
              <p className="text-xs text-muted-foreground">
                {t(
                  'publicMedicine.sellDescription',
                  undefined,
                  'Фиксирует расход препарата со склада и приход в кассу отдела.',
                )}
              </p>
            </div>
            {!sellOpen ? (
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setSellOpen(true);
                  setSellSuccess(false);
                  sellMutation.reset();
                }}
              >
                {t('publicMedicine.sellButton', undefined, 'Продать')}
              </Button>
            ) : null}
          </div>

          {sellSuccess ? (
            <p className="text-sm text-emerald-700">
              {t('publicMedicine.sellSuccess', undefined, 'Продажа зафиксирована.')}
            </p>
          ) : null}

          {sellOpen ? (
            <form
              className="grid gap-3 md:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                sellMutation.mutate();
              }}
            >
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-foreground">
                  {t('publicMedicine.sellQuantity', undefined, 'Количество')}
                  <span className="ml-1 text-destructive">*</span>
                </span>
                <Input
                  type="text"
                  inputMode="decimal"
                  placeholder={String(batch.remaining_quantity ?? '')}
                  value={sellQuantity}
                  onChange={(event) => setSellQuantity(event.target.value)}
                  required
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-foreground">
                  {t('publicMedicine.sellAmount', undefined, 'Сумма')}
                  <span className="ml-1 text-destructive">*</span>
                </span>
                <Input
                  type="text"
                  inputMode="decimal"
                  placeholder={String(batch.unit_cost ?? '')}
                  value={sellAmount}
                  onChange={(event) => setSellAmount(event.target.value)}
                  required
                />
              </label>
              <label className="flex flex-col gap-1 text-sm md:col-span-2">
                <span className="font-medium text-foreground">
                  {t('publicMedicine.sellNote', undefined, 'Примечание')}
                </span>
                <Input
                  type="text"
                  value={sellNote}
                  onChange={(event) => setSellNote(event.target.value)}
                />
              </label>
              {sellMutation.error ? (
                <div className="md:col-span-2">
                  <ErrorNotice error={sellMutation.error} />
                </div>
              ) : null}
              <div className="flex items-center gap-2 md:col-span-2">
                <Button type="submit" size="sm" disabled={sellMutation.isPending}>
                  {sellMutation.isPending
                    ? t('publicMedicine.sellSubmitting', undefined, 'Сохраняем...')
                    : t('publicMedicine.sellConfirm', undefined, 'Подтвердить продажу')}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSellOpen(false);
                    sellMutation.reset();
                  }}
                >
                  {t('common.cancel', undefined, 'Отмена')}
                </Button>
              </div>
            </form>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
