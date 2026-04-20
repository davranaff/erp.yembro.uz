import { format } from 'date-fns';
import { Loader2, Plus } from 'lucide-react';
import { type FormEvent, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SearchableReferenceSelect } from '@/components/ui/searchable-reference-select';
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useToast } from '@/components/ui/toast';
import {
  getCrudResourceMeta,
  type CrudFieldMeta,
  type CrudResourceMeta,
} from '@/shared/api/backend-crud';
import {
  consumeMedicine,
  type MedicineConsumeRequest,
  type MedicineConsumeResponse,
} from '@/shared/api/medicine';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { getErrorMessage, useApiMutation, useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';

const todayIso = (): string => format(new Date(), 'yyyy-MM-dd');

type MedicineConsumeButtonProps = {
  departmentId?: string;
  disabled?: boolean;
  onSuccess?: () => void;
};

export function MedicineConsumeButton({
  departmentId,
  disabled,
  onSuccess,
}: MedicineConsumeButtonProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        type="button"
        className="rounded-full px-5 shadow-[0_18px_42px_-28px_rgba(234,88,12,0.42)]"
        onClick={() => setOpen(true)}
        disabled={disabled}
      >
        <Plus className="h-4 w-4" />
        {t('medicine.consume.button', undefined, 'Списать (FEFO)')}
      </Button>
      <MedicineConsumeSheet
        open={open}
        onOpenChange={setOpen}
        defaultDepartmentId={departmentId}
        onSuccess={onSuccess}
      />
    </>
  );
}

type MedicineConsumeSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultDepartmentId?: string;
  onSuccess?: () => void;
};

const findField = (meta: CrudResourceMeta | undefined, name: string): CrudFieldMeta | undefined =>
  meta?.fields.find((field) => field.name === name);

function MedicineConsumeSheet({
  open,
  onOpenChange,
  defaultDepartmentId,
  onSuccess,
}: MedicineConsumeSheetProps) {
  const { t } = useI18n();
  const { show } = useToast();

  const [medicineTypeId, setMedicineTypeId] = useState<string>('');
  const [quantity, setQuantity] = useState<string>('');
  const [consumedOn, setConsumedOn] = useState<string>(todayIso);
  const [factoryFlockId, setFactoryFlockId] = useState<string>('');
  const [clientId, setClientId] = useState<string>('');
  const [purpose, setPurpose] = useState<string>('');
  const [formError, setFormError] = useState<string>('');
  const [allocations, setAllocations] = useState<MedicineConsumeResponse | null>(null);

  const metaQuery = useApiQuery<CrudResourceMeta>({
    queryKey: baseQueryKeys.crud.meta('medicine', 'consumptions'),
    queryFn: () => getCrudResourceMeta('medicine', 'consumptions'),
    enabled: open,
  });

  const medicineTypeField = useMemo(
    () => findField(metaQuery.data, 'medicine_type_id'),
    [metaQuery.data],
  );
  const factoryFlockField = useMemo(
    () => findField(metaQuery.data, 'factory_flock_id'),
    [metaQuery.data],
  );
  const clientField = useMemo(() => findField(metaQuery.data, 'client_id'), [metaQuery.data]);

  const resetForm = () => {
    setMedicineTypeId('');
    setQuantity('');
    setConsumedOn(todayIso());
    setFactoryFlockId('');
    setClientId('');
    setPurpose('');
    setFormError('');
    setAllocations(null);
  };

  const consumeMutation = useApiMutation<MedicineConsumeResponse, Error, MedicineConsumeRequest>({
    mutationKey: ['medicine', 'consume'],
    mutationFn: (payload) => consumeMedicine(payload),
    onSuccess: (response) => {
      setAllocations(response);
      show({
        tone: 'success',
        title: t('medicine.consume.success', undefined, 'Списано'),
      });
      onSuccess?.();
    },
    onError: (error) => {
      setFormError(getErrorMessage(error));
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError('');

    const trimmedQuantity = quantity.trim().replace(',', '.');
    const parsedQuantity = Number.parseFloat(trimmedQuantity);
    if (!medicineTypeId.trim()) {
      setFormError(t('medicine.consume.errMedicine', undefined, 'Выберите препарат'));
      return;
    }
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setFormError(
        t('medicine.consume.errQuantity', undefined, 'Введите положительное количество'),
      );
      return;
    }
    if (!consumedOn.trim()) {
      setFormError(t('medicine.consume.errDate', undefined, 'Укажите дату'));
      return;
    }

    const payload: MedicineConsumeRequest = {
      medicine_type_id: medicineTypeId.trim(),
      quantity: parsedQuantity,
      consumed_on: consumedOn.trim(),
    };
    if (defaultDepartmentId) {
      payload.department_id = defaultDepartmentId;
    }
    if (factoryFlockId.trim()) {
      payload.factory_flock_id = factoryFlockId.trim();
    }
    if (clientId.trim()) {
      payload.client_id = clientId.trim();
    }
    if (purpose.trim()) {
      payload.purpose = purpose.trim();
    }

    consumeMutation.mutate(payload);
  };

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next);
    if (!next) {
      resetForm();
      consumeMutation.reset();
    }
  };

  const isPending = consumeMutation.isPending;

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        className="data-[side=right]:w-[96vw] data-[side=right]:sm:max-w-xl"
      >
        <SheetHeader>
          <SheetTitle>
            {t('medicine.consume.title', undefined, 'Списать лекарство (FEFO)')}
          </SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
            {formError ? <ErrorNotice error={formError} /> : null}
            {metaQuery.error ? <ErrorNotice error={metaQuery.error} /> : null}

            <div className="space-y-1.5">
              <Label htmlFor="medicine-consume-type">
                {t('medicine.consume.medicineLabel', undefined, 'Препарат')} *
              </Label>
              {medicineTypeField ? (
                <SearchableReferenceSelect
                  moduleKey="medicine"
                  resourcePath="consumptions"
                  field={medicineTypeField}
                  value={medicineTypeId}
                  onChange={(value) =>
                    setMedicineTypeId(typeof value === 'string' ? value : (value[0] ?? ''))
                  }
                  disabled={isPending || metaQuery.isLoading}
                />
              ) : (
                <div className="text-sm text-muted-foreground">
                  {metaQuery.isLoading
                    ? t('common.loadingLabel', undefined, 'Загружаем…')
                    : t('common.notAvailable', undefined, 'Недоступно')}
                </div>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="medicine-consume-quantity">
                  {t('medicine.consume.quantityLabel', undefined, 'Количество')} *
                </Label>
                <Input
                  id="medicine-consume-quantity"
                  type="number"
                  inputMode="decimal"
                  step="0.001"
                  min="0"
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                  disabled={isPending}
                  placeholder="0.000"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="medicine-consume-date">
                  {t('medicine.consume.dateLabel', undefined, 'Дата')} *
                </Label>
                <Input
                  id="medicine-consume-date"
                  type="date"
                  value={consumedOn}
                  onChange={(event) => setConsumedOn(event.target.value)}
                  disabled={isPending}
                />
              </div>
            </div>

            {factoryFlockField ? (
              <div className="space-y-1.5">
                <Label>{t('medicine.consume.flockLabel', undefined, 'Стадо (опц.)')}</Label>
                <SearchableReferenceSelect
                  moduleKey="medicine"
                  resourcePath="consumptions"
                  field={factoryFlockField}
                  value={factoryFlockId}
                  onChange={(value) =>
                    setFactoryFlockId(typeof value === 'string' ? value : (value[0] ?? ''))
                  }
                  disabled={isPending}
                />
              </div>
            ) : null}

            {clientField ? (
              <div className="space-y-1.5">
                <Label>{t('medicine.consume.clientLabel', undefined, 'Клиент (опц.)')}</Label>
                <SearchableReferenceSelect
                  moduleKey="medicine"
                  resourcePath="consumptions"
                  field={clientField}
                  value={clientId}
                  onChange={(value) =>
                    setClientId(typeof value === 'string' ? value : (value[0] ?? ''))
                  }
                  disabled={isPending}
                />
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="medicine-consume-purpose">
                {t('medicine.consume.purposeLabel', undefined, 'Назначение / комментарий')}
              </Label>
              <Input
                id="medicine-consume-purpose"
                value={purpose}
                onChange={(event) => setPurpose(event.target.value)}
                disabled={isPending}
              />
            </div>

            {allocations ? (
              <div className="rounded-2xl border border-emerald-300/40 bg-emerald-50/70 p-4 text-sm text-emerald-900">
                <div className="mb-2 font-semibold">
                  {t('medicine.consume.allocationsTitle', undefined, 'Распределение по партиям')}
                </div>
                <div className="space-y-1.5">
                  {allocations.allocations.map((allocation) => (
                    <div
                      key={allocation.consumption_id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white/70 px-3 py-2"
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">
                          {allocation.batch_code || allocation.batch_id.slice(0, 8)}
                        </span>
                        {allocation.expiry_date ? (
                          <span className="text-xs text-emerald-700/70">
                            {t('medicine.consume.expires', undefined, 'до')}:{' '}
                            {allocation.expiry_date}
                          </span>
                        ) : null}
                      </div>
                      <span className="font-mono text-sm">{String(allocation.quantity)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex justify-between text-xs text-emerald-800">
                  <span>{t('medicine.consume.requested', undefined, 'Запрошено')}</span>
                  <span className="font-mono">{String(allocations.requested)}</span>
                </div>
                <div className="flex justify-between text-xs text-emerald-800">
                  <span>{t('medicine.consume.consumedTotal', undefined, 'Списано всего')}</span>
                  <span className="font-mono">{String(allocations.consumed_total)}</span>
                </div>
              </div>
            ) : null}
          </div>

          <SheetFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isPending}
            >
              {t('common.close', undefined, 'Закрыть')}
            </Button>
            <Button type="submit" disabled={isPending || metaQuery.isLoading}>
              {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {t('medicine.consume.submit', undefined, 'Списать')}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
