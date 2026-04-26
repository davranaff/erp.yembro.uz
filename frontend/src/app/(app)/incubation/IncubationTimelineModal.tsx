'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import { useIncubationTimeline } from '@/hooks/useIncubation';
import type {
  IncubationRun,
  IncubationTimelineEvent,
  IncubationTimelineEventType,
} from '@/types/auth';

interface Props {
  run: IncubationRun;
  onClose: () => void;
}

const TYPE_LABEL: Record<IncubationTimelineEventType, string> = {
  load: 'Закладка',
  mirage: 'Овоскопия',
  regime: 'Режим',
  transfer_to_hatcher: 'На вывод',
  hatch: 'Вывод',
  cancel: 'Отмена',
};

const TYPE_TONE: Record<IncubationTimelineEventType, 'success' | 'danger' | 'warn' | 'info' | 'neutral'> = {
  load: 'info',
  mirage: 'warn',
  regime: 'neutral',
  transfer_to_hatcher: 'info',
  hatch: 'success',
  cancel: 'danger',
};

const TYPE_ICON: Record<IncubationTimelineEventType, string> = {
  load: '📦',
  mirage: '🔦',
  regime: '🌡',
  transfer_to_hatcher: '↗',
  hatch: '🐣',
  cancel: '✖',
};

function eventBorderColor(type: IncubationTimelineEventType): string {
  const map: Record<IncubationTimelineEventType, string> = {
    load: 'var(--info, #3B82F6)',
    mirage: 'var(--warning, #F59E0B)',
    regime: 'var(--fg-3)',
    transfer_to_hatcher: 'var(--brand-orange, #E8751A)',
    hatch: 'var(--success, #10B981)',
    cancel: 'var(--danger, #EF4444)',
  };
  return map[type];
}

function groupByDate(events: IncubationTimelineEvent[]): Map<string, IncubationTimelineEvent[]> {
  const groups = new Map<string, IncubationTimelineEvent[]>();
  for (const ev of events) {
    if (!groups.has(ev.date)) groups.set(ev.date, []);
    groups.get(ev.date)!.push(ev);
  }
  return groups;
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' });
}

export default function IncubationTimelineModal({ run, onClose }: Props) {
  const [filter, setFilter] = useState<IncubationTimelineEventType | 'all'>('all');
  const { data, isLoading, error } = useIncubationTimeline(run.id);

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    if (filter === 'all') return data.events;
    return data.events.filter((e) => e.type === filter);
  }, [data, filter]);

  const grouped = useMemo(() => groupByDate(filteredEvents), [filteredEvents]);

  const filterOptions = useMemo(() => {
    if (!data) return [{ value: 'all' as const, label: 'Все' }];
    const opts: Array<{ value: IncubationTimelineEventType | 'all'; label: string }> = [
      { value: 'all', label: `Все · ${data.events.length}` },
    ];
    (
      ['load', 'mirage', 'regime', 'transfer_to_hatcher', 'hatch', 'cancel'] as IncubationTimelineEventType[]
    ).forEach((t) => {
      const cnt = data.counts[t] ?? 0;
      if (cnt > 0) {
        opts.push({ value: t, label: `${TYPE_LABEL[t]} · ${cnt}` });
      }
    });
    return opts;
  }, [data]);

  return (
    <Modal
      title={`История партии ${run.doc_number}`}
      onClose={onClose}
      footer={<button className="btn btn-primary" onClick={onClose}>Закрыть</button>}
    >
      {data && data.events.length > 0 && (
        <div style={{ marginBottom: 12, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {filterOptions.map((opt) => (
            <button
              key={opt.value}
              className={'btn btn-sm ' + (filter === opt.value ? 'btn-primary' : 'btn-ghost')}
              onClick={() => setFilter(opt.value)}
              style={{ fontSize: 12 }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {isLoading && (
        <div style={{ padding: 24, color: 'var(--fg-3)' }}>Загрузка…</div>
      )}
      {error && (
        <div style={{ padding: 24, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
      {data && filteredEvents.length === 0 && (
        <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
          Событий не найдено.
        </div>
      )}

      {data && filteredEvents.length > 0 && (
        <div style={{ maxHeight: 500, overflowY: 'auto' }}>
          {Array.from(grouped.entries()).map(([date, events]) => (
            <div key={date} style={{ marginBottom: 16 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: '.06em',
                  padding: '4px 0',
                  borderBottom: '1px solid var(--border)',
                  marginBottom: 8,
                  position: 'sticky',
                  top: 0,
                  background: 'var(--bg-card, #fff)',
                  zIndex: 1,
                }}
              >
                {fmtDate(date)}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {events.map((ev) => (
                  <div
                    key={`${ev.type}-${ev.id}`}
                    style={{
                      display: 'flex',
                      gap: 10,
                      padding: 10,
                      background: 'var(--bg-card, #fff)',
                      borderRadius: 6,
                      borderLeft: `3px solid ${eventBorderColor(ev.type)}`,
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ fontSize: 16, lineHeight: 1, marginTop: 2 }}>
                      {TYPE_ICON[ev.type]}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                        <Badge tone={TYPE_TONE[ev.type]}>{TYPE_LABEL[ev.type]}</Badge>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{ev.title}</span>
                      </div>
                      {ev.subtitle && (
                        <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>{ev.subtitle}</div>
                      )}
                      {ev.notes && (
                        <div style={{
                          fontSize: 11,
                          color: 'var(--fg-3)',
                          marginTop: 4,
                          fontStyle: 'italic',
                        }}>
                          {ev.notes}
                        </div>
                      )}
                      {ev.inspector_name && (
                        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                          инспектор: {ev.inspector_name}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
