'use client';

import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useDeleteTemplate,
  useSaveTemplate,
  useScheduleTemplates,
} from '@/hooks/usePayroll';
import type { WorkScheduleTemplate } from '@/types/payroll';

const KIND_LABEL: Record<string, string> = {
  weekday_mask: 'По дням недели',
  rotation: 'Сменный',
};

export default function TemplatesPage() {
  const { data: templates = [], isLoading, error } = useScheduleTemplates();
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('hr', 'rw');
  const del = useDeleteTemplate();
  const save = useSaveTemplate();

  const [editing, setEditing] = useState<WorkScheduleTemplate | null>(null);
  const [creating, setCreating] = useState(false);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Графики работы</h1>
          <div className="sub">Шаблоны рабочего времени для назначения сотрудникам</div>
        </div>
        {canEdit && (
          <div className="actions">
            <button className="btn btn-primary btn-sm" onClick={() => setCreating(true)}>
              <Icon name="plus" size={14} /> Новый шаблон
            </button>
          </div>
        )}
      </div>

      <Panel flush>
        <DataTable
          isLoading={isLoading}
          rows={templates}
          rowKey={(t) => t.id}
          error={error}
          emptyMessage="Шаблонов ещё нет."
          columns={[
            { key: 'code', label: 'Код', mono: true, render: (t) => t.code },
            { key: 'name', label: 'Название', render: (t) => t.name },
            { key: 'kind', label: 'Тип', render: (t) => <Badge tone="info">{KIND_LABEL[t.pattern_kind] ?? t.pattern_kind}</Badge> },
            { key: 'desc', label: 'Описание', cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
              render: (t) => describePattern(t) },
            { key: 'active', label: 'Активность',
              render: (t) => t.is_active
                ? <Badge tone="success" dot>Активен</Badge>
                : <Badge tone="neutral" dot>Архив</Badge> },
            ...(canEdit ? [{ key: 'act', label: '', width: 60, align: 'right' as const,
              render: (t: WorkScheduleTemplate) => (
                <RowActions
                  actions={[
                    { label: 'Редактировать', onClick: () => setEditing(t) },
                    {
                      label: t.is_active ? 'Архивировать' : 'Восстановить',
                      onClick: () => {
                        save.mutate({
                          id: t.id,
                          code: t.code,
                          name: t.name,
                          pattern_kind: t.pattern_kind,
                          pattern: t.pattern as unknown as Record<string, unknown>,
                          is_active: !t.is_active,
                        }, { onError: (e) => alert(e.message) });
                      },
                    },
                    { label: 'Удалить', danger: true, onClick: () => {
                      if (!confirm(`Удалить шаблон «${t.code}»?`)) return;
                      del.mutate(t.id, { onError: (e) => alert(e.message) });
                    } },
                  ]}
                />
              ),
            }] : []),
          ]}
        />
      </Panel>

      {(editing || creating) && (
        <TemplateModal
          initial={editing}
          onClose={() => { setEditing(null); setCreating(false); }}
        />
      )}
    </>
  );
}

function describePattern(t: WorkScheduleTemplate): string {
  if (t.pattern_kind === 'weekday_mask') {
    const p = t.pattern as {
      weekdays: number[]; start: string; end: string; duration_hours: number;
    };
    const names = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
    const days = (p.weekdays || []).map((d) => names[d]).join(', ');
    return `${days} · ${p.start}–${p.end} (${p.duration_hours} ч)`;
  }
  if (t.pattern_kind === 'rotation') {
    const p = t.pattern as {
      work_days: number; rest_days: number; start: string; end: string; duration_hours: number;
    };
    return `${p.work_days}/${p.rest_days} · ${p.start}–${p.end} (${p.duration_hours} ч)`;
  }
  return '';
}

function TemplateModal({
  initial, onClose,
}: { initial: WorkScheduleTemplate | null; onClose: () => void }) {
  const save = useSaveTemplate();
  const [code, setCode] = useState(initial?.code ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [kind, setKind] = useState<'weekday_mask' | 'rotation'>(initial?.pattern_kind ?? 'weekday_mask');

  // weekday_mask state
  const wm = (initial?.pattern_kind === 'weekday_mask' ? initial.pattern : null) as
    | { weekdays: number[]; start: string; end: string; duration_hours: number }
    | null;
  const [weekdays, setWeekdays] = useState<Set<number>>(
    new Set(wm?.weekdays ?? [0, 1, 2, 3, 4]),
  );
  const [wmStart, setWmStart] = useState(wm?.start ?? '09:00');
  const [wmEnd, setWmEnd] = useState(wm?.end ?? '18:00');
  const [wmHours, setWmHours] = useState(String(wm?.duration_hours ?? 8));

  // rotation state
  const rt = (initial?.pattern_kind === 'rotation' ? initial.pattern : null) as
    | { work_days: number; rest_days: number; anchor_date: string; start: string; end: string; duration_hours: number }
    | null;
  const today = new Date().toISOString().slice(0, 10);
  const [rtWork, setRtWork] = useState(String(rt?.work_days ?? 2));
  const [rtRest, setRtRest] = useState(String(rt?.rest_days ?? 2));
  const [rtAnchor, setRtAnchor] = useState(rt?.anchor_date ?? today);
  const [rtStart, setRtStart] = useState(rt?.start ?? '08:00');
  const [rtEnd, setRtEnd] = useState(rt?.end ?? '20:00');
  const [rtHours, setRtHours] = useState(String(rt?.duration_hours ?? 12));

  const toggleWeekday = (d: number) => {
    const next = new Set(weekdays);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    setWeekdays(next);
  };

  const handleSubmit = () => {
    if (!code || !name) { alert('Заполните код и название.'); return; }
    let pattern: Record<string, unknown>;
    if (kind === 'weekday_mask') {
      if (weekdays.size === 0) { alert('Выберите хотя бы один день недели.'); return; }
      pattern = {
        weekdays: Array.from(weekdays).sort(),
        start: wmStart, end: wmEnd,
        duration_hours: Number(wmHours),
      };
    } else {
      pattern = {
        work_days: Number(rtWork),
        rest_days: Number(rtRest),
        anchor_date: rtAnchor,
        start: rtStart, end: rtEnd,
        duration_hours: Number(rtHours),
      };
    }
    save.mutate({
      id: initial?.id,
      code, name,
      pattern_kind: kind,
      pattern,
    }, {
      onSuccess: () => onClose(),
      onError: (e) => alert(e.message),
    });
  };

  return (
    <Modal
      title={initial ? `Шаблон · ${initial.code}` : 'Новый шаблон'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary btn-sm" onClick={handleSubmit} disabled={save.isPending}>
            {save.isPending ? 'Сохраняем…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gap: 10 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
          <div>
            <label>Код</label>
            <input className="input" value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div>
            <label>Название</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>

        <label>Тип</label>
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value as never)}>
          <option value="weekday_mask">По дням недели</option>
          <option value="rotation">Сменный (work/rest)</option>
        </select>

        {kind === 'weekday_mask' ? (
          <>
            <label>Рабочие дни</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((d, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => toggleWeekday(i)}
                  className={weekdays.has(i) ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm'}
                  style={{ minWidth: 44 }}
                >
                  {d}
                </button>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              <div><label>Начало</label><input className="input" type="time" value={wmStart} onChange={(e) => setWmStart(e.target.value)} /></div>
              <div><label>Конец</label><input className="input" type="time" value={wmEnd} onChange={(e) => setWmEnd(e.target.value)} /></div>
              <div><label>Часов</label><input className="input" inputMode="decimal" value={wmHours} onChange={(e) => setWmHours(e.target.value)} /></div>
            </div>
          </>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              <div><label>Рабочих дней</label><input className="input" inputMode="numeric" value={rtWork} onChange={(e) => setRtWork(e.target.value)} /></div>
              <div><label>Выходных</label><input className="input" inputMode="numeric" value={rtRest} onChange={(e) => setRtRest(e.target.value)} /></div>
              <div><label>Якорная дата</label><input className="input" type="date" value={rtAnchor} onChange={(e) => setRtAnchor(e.target.value)} /></div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              <div><label>Начало</label><input className="input" type="time" value={rtStart} onChange={(e) => setRtStart(e.target.value)} /></div>
              <div><label>Конец</label><input className="input" type="time" value={rtEnd} onChange={(e) => setRtEnd(e.target.value)} /></div>
              <div><label>Часов</label><input className="input" inputMode="decimal" value={rtHours} onChange={(e) => setRtHours(e.target.value)} /></div>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
