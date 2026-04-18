import {
  frostedPanelClassName,
  isAuditSnapshot,
  isStructuredAuditValue,
  type AuditSnapshot,
} from '../module-crud-page.helpers';

export interface AuditSnapshotViewProps {
  snapshot: AuditSnapshot | null | undefined;
  fieldNames: string[];
  emptyLabel: string;
  getFieldLabel: (fieldName: string) => string;
  getFieldDisplayValue: (fieldName: string, value: unknown) => string;
}

export function AuditSnapshotView({
  snapshot,
  fieldNames,
  emptyLabel,
  getFieldLabel,
  getFieldDisplayValue,
}: AuditSnapshotViewProps) {
  if (!isAuditSnapshot(snapshot)) {
    return (
      <div className={`${frostedPanelClassName} px-4 py-6 text-sm text-muted-foreground`}>
        {emptyLabel}
      </div>
    );
  }

  const orderedFieldNames =
    fieldNames.length > 0
      ? fieldNames.filter((fieldName) => fieldName in snapshot)
      : Object.keys(snapshot).sort();

  if (orderedFieldNames.length === 0) {
    return (
      <div className={`${frostedPanelClassName} px-4 py-6 text-sm text-muted-foreground`}>
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {orderedFieldNames.map((fieldName) => {
        const rawValue = snapshot[fieldName];
        const displayValue = getFieldDisplayValue(fieldName, rawValue);

        return (
          <div
            key={fieldName}
            className={`${frostedPanelClassName} border-border/60 px-4 py-3 shadow-none`}
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {getFieldLabel(fieldName)}
            </p>
            {isStructuredAuditValue(rawValue) ? (
              <pre className="mt-2 whitespace-pre-wrap break-all text-xs leading-5 text-foreground">
                {displayValue}
              </pre>
            ) : (
              <p className="mt-1 break-words text-sm text-foreground">{displayValue}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
