import { isValidUuid } from '@/shared/lib/uuid';

type ReadableReferenceLabelOptions = {
  fieldName?: string;
  fieldLabel?: string;
  optionValue: string;
  optionLabel: string;
};

const humanizeFieldName = (fieldName: string): string => {
  return fieldName
    .split('_')
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : ''))
    .join(' ')
    .trim();
};

export const getReadableReferenceLabel = ({
  fieldName = '',
  fieldLabel = '',
  optionValue,
  optionLabel,
}: ReadableReferenceLabelOptions): string => {
  const normalizedValue = optionValue.trim();
  const normalizedLabel = optionLabel.trim();

  if (normalizedLabel && !isValidUuid(normalizedLabel)) {
    return normalizedLabel;
  }

  if (normalizedLabel && normalizedValue && normalizedLabel !== normalizedValue) {
    return normalizedLabel;
  }

  if (normalizedValue && !isValidUuid(normalizedValue)) {
    return normalizedValue;
  }

  if (!normalizedValue) {
    return normalizedLabel || fieldLabel.trim() || humanizeFieldName(fieldName);
  }

  const prefix = fieldLabel.trim() || humanizeFieldName(fieldName) || 'Record';
  return `${prefix} #${normalizedValue.slice(0, 8)}`;
};
