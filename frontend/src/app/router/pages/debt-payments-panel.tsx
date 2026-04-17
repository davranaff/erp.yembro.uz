import { format } from 'date-fns';
import { HandCoins, Plus, Trash2 } from 'lucide-react';
import { type FormEvent, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { CustomSelect } from '@/components/ui/custom-select';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  createCrudRecord,
  deleteCrudRecord,
  listCrudRecords,
  type CrudListResponse,
  type CrudRecord,
} from '@/shared/api/backend-crud';
import { baseQueryKeys, toQueryKey } from '@/shared/api/query-keys';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

type DebtDirection = 'incoming' | 'outgoing';

type DebtPaymentsPanelProps = {
  debt: CrudRecord;
  direction: DebtDirection;
  onChanged: () => void | Promise<void>;
};

type CashAccountRecord = CrudRecord & {
  id?: string;
  name?: string;
  code?: string;
  currency?: string;
  department_id?: string;
};

type DebtPaymentRecord = CrudRecord & {
  id?: string;
  client_debt_id?: string | null;
  supplier_debt_id?: string | null;
  amount?: string | number;
  currency?: string;
  paid_on?: string;
  method?: string;
  reference_no?: string | null;
  cash_account_id?: string | null;
  note?: string | null;
};

const PAYMENT_METHODS = ['cash', 'bank', 'card', 'transfer', 'offset', 'other'] as const;
type PaymentMethod = (typeof PAYMENT_METHODS)[number];

const getDebtId = (debt: CrudRecord): string => {
  const rawId = (debt as { id?: unknown }).id;
  return typeof rawId === 'string' ? rawId : '';
};

const getDebtStringField = (debt: CrudRecord, field: string): string => {
  const value = (debt as Record<string, unknown>)[field];
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return '';
};

const parseDecimal = (value: unknown): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

const formatAmount = (value: number): string => {
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

const todayIso = (): string => format(new Date(), 'yyyy-MM-dd');

const statusPillClass = (status: string): string => {
  const normalized = status.toLowerCase();
  if (normalized === 'closed') {
    return 'bg-emerald-500/10 text-emerald-700 ring-1 ring-inset ring-emerald-500/25';
  }
  if (normalized === 'partially_paid') {
    return 'bg-amber-500/10 text-amber-700 ring-1 ring-inset ring-amber-500/30';
  }
  if (normalized === 'cancelled') {
    return 'bg-muted text-muted-foreground ring-1 ring-inset ring-border/60';
  }
  return 'bg-orange-500/10 text-orange-700 ring-1 ring-inset ring-orange-500/30';
};

export function DebtPaymentsPanel({ debt, direction, onChanged }: DebtPaymentsPanelProps) {
  const { t } = useI18n();
  const debtId = getDebtId(debt);
  const debtCurrency = getDebtStringField(debt, 'currency');
  const debtDepartmentId = getDebtStringField(debt, 'department_id');
  const debtStatus = getDebtStringField(debt, 'status') || 'open';
  const amountTotal = parseDecimal((debt as Record<string, unknown>).amount_total);
  const amountPaid = parseDecimal((debt as Record<string, unknown>).amount_paid);
  const amountRemaining = Math.max(amountTotal - amountPaid, 0);

  const [amountInput, setAmountInput] = useState('');
  const [paidOnInput, setPaidOnInput] = useState<string>(todayIso);
  const [methodInput, setMethodInput] = useState<PaymentMethod>('cash');
  const [cashAccountInput, setCashAccountInput] = useState('');
  const [referenceNoInput, setReferenceNoInput] = useState('');
  const [noteInput, setNoteInput] = useState('');
  const [formError, setFormError] = useState('');
  const [mutationError, setMutationError] = useState<unknown>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState('');

  const paymentsQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('finance', `debt-payments:${direction}:${debtId}`),
    queryFn: () =>
      listCrudRecords('finance', 'debt-payments', {
        orderBy: '-paid_on',
        departmentId: debtDepartmentId || undefined,
      }),
    enabled: Boolean(debtId),
  });

  const linkedPayments = useMemo(() => {
    const items = (paymentsQuery.data?.items ?? []) as DebtPaymentRecord[];
    return items.filter((payment) => {
      const parentId = direction === 'incoming' ? payment.client_debt_id : payment.supplier_debt_id;
      return typeof parentId === 'string' && parentId === debtId;
    });
  }, [debtId, direction, paymentsQuery.data]);

  const cashAccountsQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('finance', 'cash-accounts:payments-panel'),
    queryFn: () => listCrudRecords('finance', 'cash-accounts', { limit: 200 }),
    enabled: Boolean(debtId),
  });

  const cashAccountOptions = useMemo(() => {
    const items = (cashAccountsQuery.data?.items ?? []) as CashAccountRecord[];
    return items
      .filter((account) => typeof account.id === 'string' && account.id.length > 0)
      .filter((account) =>
        debtDepartmentId && typeof account.department_id === 'string'
          ? account.department_id === debtDepartmentId
          : true,
      )
      .map((account) => ({
        value: String(account.id),
        label: account.name
          ? `${account.name}${account.currency ? ` · ${account.currency}` : ''}`
          : String(account.code ?? account.id),
      }));
  }, [cashAccountsQuery.data, debtDepartmentId]);

  const methodOptions = PAYMENT_METHODS.map((method) => ({
    value: method,
    label: t(`debtPayments.methods.${method}`, undefined, method),
  }));

  const refreshData = async () => {
    await paymentsQuery.refetch();
    await onChanged();
  };

  const createMutation = useApiMutation<CrudRecord, Error, CrudRecord>({
    mutationKey: toQueryKey('debt-payments', 'create', direction, debtId),
    mutationFn: (payload) => createCrudRecord('finance', 'debt-payments', payload),
    onSuccess: async () => {
      setAmountInput('');
      setReferenceNoInput('');
      setNoteInput('');
      setFormError('');
      setMutationError(null);
      await refreshData();
    },
    onError: (error) => {
      setMutationError(error);
    },
  });

  const deleteMutation = useApiMutation<{ deleted?: boolean }, Error, string>({
    mutationKey: toQueryKey('debt-payments', 'delete', direction, debtId),
    mutationFn: (paymentId) => deleteCrudRecord('finance', 'debt-payments', paymentId),
    onSuccess: async () => {
      setPendingDeleteId('');
      setMutationError(null);
      await refreshData();
    },
    onError: (error) => {
      setMutationError(error);
    },
  });

  const submitting = createMutation.isPending;
  const deleting = deleteMutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedAmount = Number.parseFloat(amountInput.replace(',', '.'));
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setFormError(
        t('debtPayments.errors.amountPositive', undefined, 'Введите положительную сумму.'),
      );
      return;
    }
    if (parsedAmount > amountRemaining + 0.0001) {
      setFormError(
        t(
          'debtPayments.errors.amountExceedsRemaining',
          undefined,
          'Сумма оплаты превышает остаток долга.',
        ),
      );
      return;
    }
    if (!paidOnInput) {
      setFormError(t('debtPayments.errors.paidOnRequired', undefined, 'Укажите дату оплаты.'));
      return;
    }
    setFormError('');

    const payload: CrudRecord = {
      direction,
      amount: parsedAmount.toFixed(2),
      currency: debtCurrency,
      paid_on: paidOnInput,
      method: methodInput,
      ...(cashAccountInput ? { cash_account_id: cashAccountInput } : {}),
      ...(referenceNoInput.trim() ? { reference_no: referenceNoInput.trim() } : {}),
      ...(noteInput.trim() ? { note: noteInput.trim() } : {}),
    };
    if (direction === 'incoming') {
      payload.client_debt_id = debtId;
    } else {
      payload.supplier_debt_id = debtId;
    }
    if (debtDepartmentId) {
      payload.department_id = debtDepartmentId;
    }

    createMutation.mutate(payload);
  };

  const handleDelete = (paymentId: string) => {
    if (!paymentId) {
      return;
    }
    if (pendingDeleteId !== paymentId) {
      setPendingDeleteId(paymentId);
      return;
    }
    deleteMutation.mutate(paymentId);
  };

  const paymentsLoading = paymentsQuery.isLoading || paymentsQuery.isFetching;
  const canAddPayment = amountRemaining > 0 && Boolean(debtId);

  return (
    <section className="space-y-5 rounded-2xl border border-border/70 bg-background/60 p-5 shadow-[0_16px_48px_-32px_rgba(15,23,42,0.14)]">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <HandCoins className="h-4 w-4 text-primary" />
          {direction === 'incoming'
            ? t('debtPayments.headerIncoming', undefined, 'Оплаты по долгу клиента')
            : t('debtPayments.headerOutgoing', undefined, 'Оплаты поставщику')}
        </div>
        <span
          className={cn(
            'inline-flex items-center rounded-full px-3 py-1 text-xs font-medium',
            statusPillClass(debtStatus),
          )}
        >
          {t(`debtPayments.status.${debtStatus}`, undefined, debtStatus)}
        </span>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryTile
          label={t('debtPayments.summary.total', undefined, 'Сумма долга')}
          value={`${formatAmount(amountTotal)} ${debtCurrency}`}
        />
        <SummaryTile
          label={t('debtPayments.summary.paid', undefined, 'Оплачено')}
          value={`${formatAmount(amountPaid)} ${debtCurrency}`}
          tone="success"
        />
        <SummaryTile
          label={t('debtPayments.summary.remaining', undefined, 'Остаток')}
          value={`${formatAmount(amountRemaining)} ${debtCurrency}`}
          tone={amountRemaining > 0 ? 'warning' : 'success'}
        />
      </div>

      {mutationError ? <ErrorNotice error={mutationError} /> : null}

      <div className="space-y-3">
        <h4 className="text-sm font-medium text-foreground">
          {t('debtPayments.history.title', undefined, 'История оплат')}
        </h4>
        {paymentsLoading ? (
          <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
            {t('common.loadingLabel', undefined, 'Загрузка…')}
          </div>
        ) : linkedPayments.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
            {t('debtPayments.history.empty', undefined, 'Оплат пока нет.')}
          </div>
        ) : (
          <ul className="space-y-2">
            {linkedPayments.map((payment) => {
              const paymentId = typeof payment.id === 'string' ? payment.id : '';
              const confirmDelete = pendingDeleteId === paymentId;
              const deletingThis = deleting && pendingDeleteId === paymentId;
              return (
                <li
                  key={paymentId || JSON.stringify(payment)}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                      <span>{`${formatAmount(parseDecimal(payment.amount))} ${payment.currency ?? debtCurrency}`}</span>
                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                        {t(
                          `debtPayments.methods.${payment.method ?? 'other'}`,
                          undefined,
                          payment.method ?? '',
                        )}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      {payment.paid_on ? <span>{payment.paid_on}</span> : null}
                      {payment.reference_no ? <span>№ {payment.reference_no}</span> : null}
                      {payment.note ? <span className="truncate">{payment.note}</span> : null}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant={confirmDelete ? 'destructive' : 'outline'}
                    onClick={() => handleDelete(paymentId)}
                    disabled={!paymentId || deleting}
                  >
                    <Trash2 className="mr-1 h-3.5 w-3.5" />
                    {deletingThis
                      ? t('common.loadingLabel', undefined, '…')
                      : confirmDelete
                        ? t('debtPayments.confirmDelete', undefined, 'Подтвердите')
                        : t('common.delete', undefined, 'Удалить')}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-xl border border-border/70 bg-card p-4"
      >
        <h4 className="text-sm font-semibold text-foreground">
          {t('debtPayments.form.title', undefined, 'Добавить оплату')}
        </h4>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="debt-payment-amount">
              {t('debtPayments.fields.amount', undefined, 'Сумма')}
            </Label>
            <Input
              id="debt-payment-amount"
              type="number"
              step="0.01"
              min={0}
              value={amountInput}
              placeholder={formatAmount(amountRemaining)}
              onChange={(event) => setAmountInput(event.target.value)}
              disabled={submitting || !canAddPayment}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="debt-payment-paid-on">
              {t('debtPayments.fields.paidOn', undefined, 'Дата оплаты')}
            </Label>
            <Input
              id="debt-payment-paid-on"
              type="date"
              value={paidOnInput}
              onChange={(event) => setPaidOnInput(event.target.value)}
              disabled={submitting || !canAddPayment}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t('debtPayments.fields.method', undefined, 'Способ оплаты')}</Label>
            <CustomSelect
              value={methodInput}
              options={methodOptions}
              onChange={(nextValue) => setMethodInput(nextValue as PaymentMethod)}
              disabled={submitting || !canAddPayment}
              placeholder={t('debtPayments.fields.method', undefined, 'Способ оплаты')}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t('debtPayments.fields.cashAccount', undefined, 'Касса')}</Label>
            <CustomSelect
              value={cashAccountInput}
              options={[
                {
                  value: '',
                  label: t('debtPayments.fields.cashAccountNone', undefined, 'Без кассы'),
                },
                ...cashAccountOptions,
              ]}
              onChange={(nextValue) => setCashAccountInput(nextValue)}
              disabled={submitting || !canAddPayment || cashAccountsQuery.isLoading}
              placeholder={t('debtPayments.fields.cashAccount', undefined, 'Касса')}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="debt-payment-reference">
              {t('debtPayments.fields.referenceNo', undefined, 'Номер документа')}
            </Label>
            <Input
              id="debt-payment-reference"
              value={referenceNoInput}
              onChange={(event) => setReferenceNoInput(event.target.value)}
              disabled={submitting || !canAddPayment}
            />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="debt-payment-note">
              {t('debtPayments.fields.note', undefined, 'Примечание')}
            </Label>
            <Input
              id="debt-payment-note"
              value={noteInput}
              onChange={(event) => setNoteInput(event.target.value)}
              disabled={submitting || !canAddPayment}
            />
          </div>
        </div>
        {formError ? (
          <div className="rounded-xl border border-amber-300/50 bg-amber-50/80 px-3 py-2 text-sm text-amber-800">
            {formError}
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            {canAddPayment
              ? t(
                  'debtPayments.form.remainingHint',
                  { amount: `${formatAmount(amountRemaining)} ${debtCurrency}` },
                  `Можно оплатить ещё ${formatAmount(amountRemaining)} ${debtCurrency}.`,
                )
              : t('debtPayments.form.fullyPaid', undefined, 'Долг полностью погашен.')}
          </span>
          <Button type="submit" size="sm" disabled={submitting || !canAddPayment}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {submitting
              ? t('common.loadingLabel', undefined, '…')
              : t('debtPayments.form.submit', undefined, 'Добавить оплату')}
          </Button>
        </div>
      </form>
    </section>
  );
}

type SummaryTileProps = {
  label: string;
  value: string;
  tone?: 'default' | 'success' | 'warning';
};

function SummaryTile({ label, value, tone = 'default' }: SummaryTileProps) {
  return (
    <div
      className={cn(
        'rounded-xl border px-4 py-3 shadow-[0_12px_32px_-24px_rgba(15,23,42,0.14)]',
        tone === 'success' && 'border-emerald-500/30 bg-emerald-500/5',
        tone === 'warning' && 'border-amber-500/30 bg-amber-500/5',
        tone === 'default' && 'border-border/70 bg-card',
      )}
    >
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-base font-semibold text-foreground">{value}</div>
    </div>
  );
}
