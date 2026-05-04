'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import Seg from '@/components/ui/Seg';
import {
  useHerdTimeline,
  type HerdTimelineEvent,
  type HerdTimelineEventType,
} from '@/hooks/useMatochnik';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

const TYPE_LABEL: Record<HerdTimelineEventType, string> = {
  egg: 'Яйцесбор',
  mortality: 'Падёж',
  feed: 'Корм',
  treatment: 'Лечение',
  crystallize: 'Партия',
  move: 'Перемещение',
};

const TYPE_TONE: Record<HerdTimelineEventType, 'success' | 'danger' | 'warn' | 'info' | 'neutral'> = {
  egg: 'success',
  mortality: 'danger',
  feed: 'warn',
  treatment: 'info',
  crystallize: 'info',
  move: 'neutral',
};

const TYPE_ICON: Record<HerdTimelineEventType, string> = {
  egg: '🥚',
  mortality: '☠',
  feed: '🌾',
  treatment: '💉',
  crystallize: '📦',
  move: '↔',
};

const DAYS_OPTIONS = [
  { value: 30, label: '30 дней' },
  { value: 90, label: '90 дней' },
  { value: 365, label: 'Год' },
];

/** Цвет линии слева для каждого типа события. */
function eventBorderColor(type: HerdTimelineEventType): string {
  const map: Record<HerdTimelineEventType, string> = {
    egg: 'var(--success, #10B981)',
    mortality: 'var(--danger, #EF4444)',
    feed: 'var(--warning, #F59E0B)',
    treatment: 'var(--info, #3B82F6)',
    crystallize: 'var(--brand-orange, #E8751A)',
    move: 'var(--fg-3)',
  };
  return map[type];
}

/**
 * Группировка событий по датам для удобного чтения.
 */
function groupByDate(events: HerdTimelineEvent[]): Map<string, HerdTimelineEvent[]> {
  const groups = new Map<string, HerdTimelineEvent[]>();
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

export default function HerdTimelineModal({ herd, onClose }: Props) {
  const [days, setDays] = useState(90);
  const [filter, setFilter] = useState<HerdTimelineEventType | 'all'>('all');

  const { data, isLoading, error } = useHerdTimeline(herd.id, days, true);

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    if (filter === 'all') return data.events;
    return data.events.filter((e) => e.type === filter);
  }, [data, filter]);

  const grouped = useMemo(() => groupByDate(filteredEvents), [filteredEvents]);

  const filterOptions = useMemo(() => {
    if (!data) return [{ value: 'all', label: 'Все' }];
    const opts: Array<{ value: HerdTimelineEventType | 'all'; label: string }> = [
      { value: 'all', label: `Все · ${data.events.length}` },
    ];
    (['egg', 'feed', 'treatment', 'mortality', 'crystallize'] as HerdTimelineEventType[]).forEach((t) => {
      const cnt = data.counts[t] ?? 0;
      if (cnt > 0) {
        opts.push({ value: t, label: `${TYPE_LABEL[t]} · ${cnt}` });
      }
    });
    return opts;
  }, [data]);

  return (
    <Modal
      title={`История стада ${herd.doc_number}`}
      onClose={onClose}
      footer={
        <button className="btn btn-primary" onClick={onClose}>Закрыть</button>
      }
    >
      <div style={{ marginBottom: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Seg
          options={DAYS_OPTIONS.map((d) => ({ value: String(d.value), label: d.label }))}
          value={String(days)}
          onChange={(v) => setDays(parseInt(v, 10))}
        />

        {data && data.events.length > 0 && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {filterOptions.map((opt) => (
              <button
                key={opt.value}
                className={'btn btn-sm ' + (filter === opt.value ? 'btn-primary' : 'btn-ghost')}
                onClick={() => setFilter(opt.value as typeof filter)}
                style={{ fontSize: 12 }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading && (
        <div style={{ padding: 24, color: 'var(--fg-3)' }}>Загрузка…</div>
      )}
      {error && (
        <div style={{ padding: 24, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
      {data && filteredEvents.length === 0 && (
        <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
          Событий не найдено за выбранный период / фильтр.
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
                        <div
                          style={{
                            fontSize: 11,
                            color: 'var(--fg-3)',
                            marginTop: 4,
                            fontStyle: 'italic',
                          }}
                        >
                          {ev.notes}
                        </div>
                      )}
                      {ev.type === 'treatment'
                        && ev.withdrawal_period_days !== undefined
                        && ev.withdrawal_period_days > 0 && (
                        <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
                          ⚠ каренция {ev.withdrawal_period_days} дн
                        </div>
                      )}
                      {ev.cost_uzs && (
                        <div
                          className="mono"
                          style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}
                        >
                          {parseFloat(ev.cost_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум
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
