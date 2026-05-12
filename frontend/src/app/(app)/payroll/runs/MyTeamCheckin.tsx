'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import { usePeople } from '@/hooks/usePeople';
import {
  useEmployeeCalendar,
  useSaveWorkShift,
} from '@/hooks/usePayroll';
import type { WorkShiftKind } from '@/types/payroll';

const KIND_LABEL: Record<WorkShiftKind, string> = {
  work:       'Пришёл',
  overtime:   'Переработка',
  vacation:   'Отпуск',
  sick_leave: 'Больничный',
  absence:    'Прогул',
  day_off:    'Выходной',
  holiday:    'Праздник',
};

type BadgeTone = 'success' | 'danger' | 'warn' | 'info' | 'neutral';

const KIND_TONE: Record<WorkShiftKind, BadgeTone> = {
  work:       'success',
  overtime:   'info',
  vacation:   'warn',
  sick_leave: 'warn',
  absence:    'danger',
  day_off:    'neutral',
  holiday:    'info',
};

const QUICK_BUTTONS: { kind: WorkShiftKind; label: string }[] = [
  { kind: 'work',       label: 'Пришёл' },
  { kind: 'vacation',   label: 'Отпуск' },
  { kind: 'sick_leave', label: 'Больничный' },
  { kind: 'absence',    label: 'Прогул' },
];

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function MyTeamCheckin() {
  const today = todayISO();
  const { data: team = [], isLoading } = usePeople({
    my_subordinates: true,
    is_active: 'true',
  });
  const [editing, setEditing] = useState<{
    empId: string;
    empName: string;
    shiftId?: string;
    initialKind: WorkShiftKind;
  } | null>(null);

  if (isLoading) {
    return (
      <Panel title="Отметка явки">
        <div style={{ padding: 24, color: 'var(--fg-3)' }}>Загружаем команду…</div>
      </Panel>
    );
  }

  if (team.length === 0) {
    return (
      <Panel title="Отметка явки моих подчинённых">
        <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
          У вас пока нет подчинённых. Назначьте сотрудникам руководителя
          на странице «Сотрудники» через карточку сотрудника.
        </div>
      </Panel>
    );
  }

  return (
    <>
      <Panel title={`Отметка явки на ${today}`} flush>
        <div style={{
          padding: '6px 12px', fontSize: 11, color: 'var(--fg-3)',
          borderBottom: '1px solid var(--border)',
        }}>
          Жмите кнопку — отметка за день сохраняется мгновенно.
          «Другое…» — для нестандартных причин или часов.
        </div>
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{
              color: 'var(--fg-3)', fontSize: 10, textAlign: 'left',
              textTransform: 'uppercase', letterSpacing: '.04em',
              background: 'var(--bg-raised)',
            }}>
              <th style={{ padding: '6px 12px' }}>Сотрудник</th>
              <th style={{ padding: '6px 12px', width: 160 }}>Сейчас</th>
              <th style={{ padding: '6px 12px' }}>Быстрая отметка</th>
              <th style={{ padding: '6px 12px', width: 100, textAlign: 'right' }}></th>
            </tr>
          </thead>
          <tbody>
            {team.map((m) => (
              <TeamRow
                key={m.id}
                employeeId={m.id}
                employeeName={m.user_full_name || '—'}
                position={m.position_title}
                today={today}
                onOpenOther={(state) => setEditing(state)}
              />
            ))}
          </tbody>
        </table>
      </Panel>

      {editing && (
        <ShiftEditModal
          state={editing}
          date={today}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}

function TeamRow({
  employeeId, employeeName, position, today, onOpenOther,
}: {
  employeeId: string;
  employeeName: string;
  position: string | null;
  today: string;
  onOpenOther: (state: {
    empId: string; empName: string;
    shiftId?: string; initialKind: WorkShiftKind;
  }) => void;
}) {
  const { data: cal } = useEmployeeCalendar(employeeId, today, today);
  const save = useSaveWorkShift();

  // Что сейчас стоит за сегодня: либо actual (фактический WorkShift),
  // либо expected (плановая смена из шаблона) — отдаём приоритет actual.
  const actual = cal?.actual.find((a) => a.date === today);
  const expected = cal?.expected.find((e) => e.date === today);
  const currentKind = (actual?.kind || expected?.kind || null) as WorkShiftKind | null;
  const currentId = actual?.id;
  const isPlanOnly = !actual && !!expected;

  const doQuick = (k: WorkShiftKind) => {
    save.mutate({
      id: currentId,
      employee: currentId ? undefined : employeeId,
      shift_date: currentId ? undefined : today,
      kind: k,
    }, {
      onError: (e) => alert(e.message),
    });
  };

  return (
    <tr style={{ borderTop: '1px solid var(--border)' }}>
      <td style={{ padding: '8px 12px', verticalAlign: 'middle' }}>
        <div style={{ fontWeight: 500 }}>{employeeName}</div>
        {position && (
          <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{position}</div>
        )}
      </td>
      <td style={{ padding: '8px 12px', verticalAlign: 'middle' }}>
        {currentKind ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Badge tone={KIND_TONE[currentKind]} dot>
              {KIND_LABEL[currentKind]}
            </Badge>
            {isPlanOnly && (
              <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>по плану</span>
            )}
          </span>
        ) : (
          <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>—</span>
        )}
      </td>
      <td style={{ padding: '8px 12px', verticalAlign: 'middle' }}>
        <div style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
          {QUICK_BUTTONS.map((b) => {
            const isActive = actual?.kind === b.kind;
            // Активная кнопка = заполненный primary, прогул — danger,
            // остальные — ghost. Это совпадает с общим стилем CTA на других страницах.
            let cls = 'btn btn-sm';
            if (isActive) cls += ' btn-primary';
            else if (b.kind === 'absence') cls += ' btn-danger';
            else cls += ' btn-ghost';
            return (
              <button
                key={b.kind}
                type="button"
                className={cls}
                disabled={save.isPending}
                onClick={() => doQuick(b.kind)}
                title={isActive ? `Стоит сейчас: ${b.label}` : `Поставить: ${b.label}`}
              >
                {b.label}
              </button>
            );
          })}
        </div>
      </td>
      <td style={{ padding: '8px 12px', textAlign: 'right', verticalAlign: 'middle' }}>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => onOpenOther({
            empId: employeeId,
            empName: employeeName,
            shiftId: currentId,
            initialKind: currentKind || 'work',
          })}
        >
          Другое…
        </button>
      </td>
    </tr>
  );
}

function ShiftEditModal({
  state, date, onClose,
}: {
  state: {
    empId: string; empName: string;
    shiftId?: string; initialKind: WorkShiftKind;
  };
  date: string;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<WorkShiftKind>(state.initialKind);
  const [hours, setHours] = useState('');
  const [notes, setNotes] = useState('');
  const save = useSaveWorkShift();

  const handleSave = async () => {
    try {
      await save.mutateAsync({
        id: state.shiftId,
        employee: state.shiftId ? undefined : state.empId,
        shift_date: state.shiftId ? undefined : date,
        kind, hours: hours || null, notes,
      });
      onClose();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const options = useMemo(
    () => (Object.keys(KIND_LABEL) as WorkShiftKind[]),
    [],
  );

  return (
    <Modal
      title={`${state.empName} · ${date}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary btn-sm"
            disabled={save.isPending}
            onClick={handleSave}
          >
            {save.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gap: 10 }}>
        <div className="field">
          <label>Что было в этот день</label>
          <select
            className="input"
            value={kind}
            onChange={(e) => setKind(e.target.value as WorkShiftKind)}
          >
            {options.map((k) => (
              <option key={k} value={k}>{KIND_LABEL[k]}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Часов (если отличается от стандарта)</label>
          <input
            className="input"
            inputMode="decimal"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            placeholder="например 8"
          />
        </div>
        <div className="field">
          <label>Заметка / причина</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Опоздание на 1ч / отгул семейный / …"
          />
        </div>
      </div>
    </Modal>
  );
}
