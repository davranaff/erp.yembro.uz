'use client';

import Panel from '@/components/ui/Panel';

/**
 * Журнал аудита переехал в отдельный раздел `/audit-log` — там полная страница
 * с KPI, фильтрами по дате/пользователю/сущности, drawer'ом с diff и
 * CSV-экспортом. В настройках оставлен placeholder-link на новую страницу.
 */
export default function AuditSection() {
  return (
    <Panel title="Журнал аудита">
      <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-2)' }}>
        Журнал аудита переехал в отдельный раздел.{' '}
        <a href="/audit-log" style={{ color: 'var(--brand-orange)' }}>
          Открыть журнал →
        </a>
      </div>
    </Panel>
  );
}
