import { zodResolver } from '@hookform/resolvers/zod';
import {
  type DefaultValues,
  type FieldValues,
  type SubmitHandler,
  useForm,
  type UseFormProps,
  type UseFormReturn,
} from 'react-hook-form';

import type { ZodTypeAny, input as ZodInput, output as ZodOutput } from 'zod';

export const baseFormConfig = {
  mode: 'onBlur',
  reValidateMode: 'onChange',
  shouldUnregister: false,
  shouldFocusError: true,
  criteriaMode: 'all',
} as const;

export type FormInput<TSchema extends ZodTypeAny> = ZodInput<TSchema>;
export type FormOutput<TSchema extends ZodTypeAny> = ZodOutput<TSchema>;

type BaseFormProps<TSchema extends ZodTypeAny> = Omit<
  UseFormProps<FormInput<TSchema>, unknown, FormOutput<TSchema>>,
  'resolver'
> & {
  schema: TSchema;
  defaultValues?: DefaultValues<FormInput<TSchema>>;
};

export function useBaseForm<TSchema extends ZodTypeAny>(
  options: BaseFormProps<TSchema>,
): UseFormReturn<FormInput<TSchema>, unknown, FormOutput<TSchema>> {
  const { schema, ...rest } = options;

  return useForm<FormInput<TSchema>, unknown, FormOutput<TSchema>>({
    ...baseFormConfig,
    ...rest,
    resolver: zodResolver(schema),
  });
}

export const buildSubmitHandler = <TValues>(
  onSubmit: (data: TValues) => Promise<void> | void,
): SubmitHandler<TValues> => {
  return (data) => onSubmit(data);
};

export const getFirstFieldError = <TValues extends FieldValues>(
  errors: Partial<Record<keyof TValues, unknown>>,
): string | undefined => {
  const values = Object.values(errors);
  const first = values.find(
    (error) =>
      typeof error === 'object' &&
      error !== null &&
      'message' in error &&
      typeof (error as { message?: unknown }).message === 'string',
  );

  return first ? (first as { message: string }).message : undefined;
};
