'use client';

import Link from 'next/link';
import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import {
  useCollectionTasks,
  type CollectionTask,
  type CollectionTaskPriority,
  type CollectionTaskType,
} from '@/hooks/useSales';

function fmt(uzs: string): string {
  const n = parseFloat(uzs);
  if (Number.isNaN(n) || n === 0) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

const PRIO_TONE: Record<CollectionTaskPriority, 'danger' | 'warn' | 'info'> = {
  high: 'danger',
  medium: 'warn',
  low: 'info',
};

const PRIO_LABEL: Record<CollectionTaskPriority, string> = {
  high: 'Срочно',
  medium: 'Важно',
  low: 'План',
};

interface SectionConfig {
  type: CollectionTaskType;
  title: string;
  desc: string;
}

const SECTIONS: SectionConfig[] = [
  {
    type: 'escalation',
    title: 'Эскалация — нужна реакция руководителя',
    desc: 'Долг 60+ дней, последнее касание было больше 7 дней назад (или вообще не было).',
  },
  {
    type: 'promise_broken',
    title: 'Клиент не сдержал обещание',
    desc: 'Прошёл срок который САМ клиент назвал, но оплата не пришла.',
  },
  {
    type: 'forecast_due',
    title: 'Не пришла прогнозная оплата',
    desc: 'Менеджер прогнозировал оплату к этой дате, но её нет.',
  },
  {
    type: 'callback_due',
    title: 'Запланированный обзвон',
    desc: 'Касания с next_action_date ≤ сегодня.',
  },
];

/**
 * Страница задач сборщика дебиторки.
 *
 * Объединяет 4 типа задач: эскалация / нарушенные обещания / прогноз не сбылся
 * / плановый обзвон. По умолчанию показывает «мои» — только касания текущего
 * пользователя; эскалации остаются глобальными (это решение руководителя).
 */
export default function TasksPage() {
  const [scope, setScope] = useState<'mine' | 'all'>('mine');
  const { data, isLoading, error } = useCollectionTasks({
    mine: scope === 'mine',
  });

  const counts = data?.counts;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Задачи по долгам</h1>
          <div className="sub">
            На <strong>{data?.as_of ?? '—'}</strong>:{' '}
            что нужно сделать сегодня по сбору дебиторки
          </div>
        </div>
        <Seg
          options={[
            { value: 'mine', label: 'Мои' },
            { value: 'all', label: 'Все' },
          ]}
          value={scope}
          onChange={(v) => setScope(v as 'mine' | 'all')}
        />
      </div>

      <div className="kpi-row">
        <KpiCard
          tone="red"
          iconName="bag"
          label="Эскалация"
          sub="60+ дн без касаний"
          value={String(counts?.escalation ?? 0)}
        />
        <KpiCard
          tone="orange"
          iconName="bag"
          label="Не сдержал обещание"
          sub="срок прошёл"
          value={String(counts?.promise_broken ?? 0)}
        />
        <KpiCard
          tone="orange"
          iconName="chart"
          label="Прогноз не сбылся"
          sub="ожидали оплату"
          value={String(counts?.forecast_due ?? 0)}
        />
        <KpiCard
          tone="blue"
          iconName="users"
          label="Плановый обзвон"
          sub="назначено на сегодня"
          value={String(counts?.callback_due ?? 0)}
        />
      </div>

      {error && (
        <div style={{
          marginTop: 14, padding: 10,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 13,
        }}>
          Не удалось загрузить задачи: {error.message}
        </div>
      )}

      {isLoading && (
        <div style={{ padding: 20, fontSize: 12, color: 'var(--fg-3)' }}>
          Загружаем…
        </div>
      )}

      {data && data.total === 0 && (
        <Panel title="Сегодня всё под контролем" style={{ marginTop: 14 }}>
          <div style={{
            padding: 32, textAlign: 'center',
            color: 'var(--fg-3)', fontSize: 13,
          }}>
            Задач нет — нет открытых обещаний, прогнозов и эскалаций.
            Хорошая работа!
          </div>
        </Panel>
      )}

      {data && data.total > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14 }}>
          {SECTIONS.map((s) => {
            const tasks = (data[s.type] ?? []) as CollectionTask[];
            if (tasks.length === 0) return null;
            return (
              <TaskSection
                key={s.type}
                title={`${s.title} (${tasks.length})`}
                desc={s.desc}
                tasks={tasks}
              />
            );
          })}
        </div>
      )}
    </>
  );
}

function TaskSection({
  title, desc, tasks,
}: {
  title: string;
  desc: string;
  tasks: CollectionTask[];
}) {
  return (
    <Panel title={title} flush>
      <div style={{
        padding: '6px 12px', fontSize: 11,
        color: 'var(--fg-3)', borderBottom: '1px solid var(--border)',
      }}>
        {desc}
      </div>
      <table style={{
        width: '100%', fontSize: 12, borderCollapse: 'collapse',
      }}>
        <thead>
          <tr style={{
            color: 'var(--fg-3)', fontSize: 10, textAlign: 'left',
            textTransform: 'uppercase', letterSpacing: '.04em',
            background: 'var(--bg-raised)',
          }}>
            <th style={{ padding: '6px 12px', width: 64 }}>Прио</th>
            <th style={{ padding: '6px 12px' }}>Клиент / документ</th>
            <th style={{ padding: '6px 12px', width: 90 }}>Просрочка</th>
            <th style={{ padding: '6px 12px' }}>Детали</th>
            <th style={{ padding: '6px 12px', width: 160 }}>Менеджер</th>
            <th style={{ padding: '6px 12px', textAlign: 'right', width: 130 }}>
              Сумма, сум
            </th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t, idx) => (
            <TaskRow key={`${t.order_id}-${idx}`} task={t} />
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function TaskRow({ task }: { task: CollectionTask }) {
  return (
    <tr style={{ borderTop: '1px solid var(--border)' }}>
      <td style={{ padding: '8px 12px', verticalAlign: 'middle' }}>
        <Badge tone={PRIO_TONE[task.priority]}>{PRIO_LABEL[task.priority]}</Badge>
      </td>
      <td style={{ padding: '8px 12px', verticalAlign: 'middle' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Link
            href={`/counterparties/${task.customer_id}`}
            style={{
              fontWeight: 500, color: 'var(--fg-1)', textDecoration: 'none',
            }}
          >
            {task.customer_name}
          </Link>
          <span className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
            {task.customer_code}
          </span>
          <span style={{ color: 'var(--fg-3)' }}>·</span>
          <Link
            href={`/sales?doc=${task.order_doc}`}
            className="mono"
            style={{
              fontSize: 11, color: 'var(--brand-orange)', textDecoration: 'none',
            }}
          >
            {task.order_doc}
          </Link>
        </div>
      </td>
      <td className="mono" style={{
        padding: '8px 12px', verticalAlign: 'middle',
        color: task.days_overdue >= 30 ? 'var(--danger)' : 'var(--fg-2)',
      }}>
        {task.days_overdue} дн
      </td>
      <td style={{
        padding: '8px 12px', verticalAlign: 'middle',
        color: 'var(--fg-2)',
      }}>
        {task.detail}
      </td>
      <td style={{
        padding: '8px 12px', verticalAlign: 'middle',
        fontSize: 11, color: 'var(--fg-3)',
      }}>
        {task.contacted_by_name ?? '—'}
      </td>
      <td className="mono" style={{
        padding: '8px 12px', textAlign: 'right', verticalAlign: 'middle',
        fontWeight: 600, color: 'var(--brand-orange)',
      }}>
        {fmt(task.outstanding_uzs)}
      </td>
    </tr>
  );
}
