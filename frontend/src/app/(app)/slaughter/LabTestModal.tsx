'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useUser } from '@/hooks/useUser';
import { labTestsCrud } from '@/hooks/useSlaughter';
import { ApiError } from '@/lib/api';
import type { SlaughterLabTest, SlaughterShift } from '@/types/auth';

interface Props {
  shift: SlaughterShift;
  test?: SlaughterLabTest | null;
  onClose: () => void;
}

interface Preset {
  code: string;          // ключ для select
  name: string;          // отображаемое имя
  default_norm: string;  // типичная норма
  hint: string;          // что это
}

/**
 * Типичные показатели для мяса птицы по ТР ТС 021/2011 и ГОСТ 31470-2012.
 * Нормы — ориентир, фактическая норма может отличаться от лаборатории.
 */
const PRESETS: Preset[] = [
  {
    code: 'KMAFAnM',
    name: 'КМАФАнМ',
    default_norm: '<1×10⁵ КОЕ/г',
    hint: 'Количество мезофильных аэробных и факультативно-анаэробных микроорганизмов. Общая микробиологическая чистота.',
  },
  {
    code: 'Salmonella',
    name: 'Сальмонелла',
    default_norm: 'не допускается в 25 г',
    hint: 'Патогенный микроорганизм. Любое обнаружение — отклонение, партия не пригодна к продаже.',
  },
  {
    code: 'Listeria',
    name: 'Листерия (L. monocytogenes)',
    default_norm: 'не допускается в 25 г',
    hint: 'Патоген, вызывающий листериоз. Обнаружение — серьёзное отклонение.',
  },
  {
    code: 'EColi',
    name: 'БГКП (колиформы / E. coli)',
    default_norm: 'не допускается в 0.0001 г',
    hint: 'Бактерии группы кишечной палочки. Маркер фекального загрязнения.',
  },
  {
    code: 'Staphylococcus',
    name: 'Стафилококк (S. aureus)',
    default_norm: 'не допускается в 1 г',
    hint: 'Условно-патогенный. Может вырабатывать термостойкий энтеротоксин.',
  },
  {
    code: 'Moisture',
    name: 'Массовая доля влаги',
    default_norm: '70-75%',
    hint: 'Физико-химия. Показатель свежести мяса.',
  },
  {
    code: 'Fat',
    name: 'Массовая доля жира',
    default_norm: '8-15%',
    hint: 'Зависит от части тушки и кросса бройлера.',
  },
  {
    code: 'Protein',
    name: 'Массовая доля белка',
    default_norm: '18-22%',
    hint: 'Норма для нативного куриного мяса.',
  },
  {
    code: 'Antibiotics',
    name: 'Антибиотики (остаточные)',
    default_norm: 'не допускается',
    hint: 'Левомицетин, тетрациклины, бацитрацин и др. Контроль каренции.',
  },
];

export default function LabTestModal({ shift, test, onClose }: Props) {
  const create = labTestsCrud.useCreate();
  const update = labTestsCrud.useUpdate();
  const { data: user } = useUser();

  // При edit — попытаемся найти пресет по name; иначе считаем custom
  const initialPresetCode = useMemo(() => {
    if (!test) return '';
    const found = PRESETS.find((p) => p.name === test.indicator);
    return found ? found.code : 'CUSTOM';
  }, [test]);

  const [presetCode, setPresetCode] = useState(initialPresetCode);
  const [indicator, setIndicator] = useState(test?.indicator ?? '');
  const [normalRange, setNormalRange] = useState(test?.normal_range ?? '');
  const [actualValue, setActualValue] = useState(test?.actual_value ?? '');
  const [status, setStatus] = useState(test?.status ?? 'pending');
  const [notes, setNotes] = useState(test?.notes ?? '');

  const currentPreset = PRESETS.find((p) => p.code === presetCode) ?? null;
  const isCustom = presetCode === 'CUSTOM';

  const handlePresetChange = (code: string) => {
    setPresetCode(code);
    if (code === '' || code === 'CUSTOM') {
      // не трогаем уже введённое
      return;
    }
    const p = PRESETS.find((pp) => pp.code === code);
    if (p) {
      setIndicator(p.name);
      // если норма ещё не была введена — подставим default
      if (!normalRange) setNormalRange(p.default_norm);
    }
  };

  const isEdit = Boolean(test);
  const action = isEdit ? update : create;
  const error = action.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const submit = async () => {
    const now = new Date().toISOString();
    const body = {
      shift: shift.id,
      indicator,
      normal_range: normalRange,
      actual_value: actualValue,
      status,
      sampled_at: test?.sampled_at ?? now,
      result_at: status === 'pending' ? null : (test?.result_at ?? now),
      operator: user?.id ?? null,
      notes,
    };
    try {
      if (isEdit && test) {
        await update.mutateAsync({ id: test.id, body } as never);
      } else {
        await create.mutateAsync(body as never);
      }
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={isEdit ? 'Редактировать тест' : 'Лабораторный тест'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!indicator || !normalRange || !actualValue || action.isPending}
            onClick={submit}
          >
            {action.isPending ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Записать'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Записать показатель из лаборатории.
        <HelpHint
          text="Зачем это нужно?"
          details="Перед отгрузкой партии мяса требуется протокол испытаний по ТР ТС 021/2011 (микробиология) и ГОСТ 31470-2012 (физ-хим). При FAILED партия не пригодна к продаже без переработки."
        />
        {' '}Статус «В работе» — пробу взяли, ждём результат лаборатории.
      </div>

      <div className="field">
        <label>Показатель *</label>
        <select
          className="input"
          value={presetCode}
          onChange={(e) => handlePresetChange(e.target.value)}
        >
          <option value="">— выберите —</option>
          {PRESETS.map((p) => (
            <option key={p.code} value={p.code}>{p.name}</option>
          ))}
          <option value="CUSTOM">Другое (ввести вручную)</option>
        </select>
        {currentPreset && (
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            {currentPreset.hint}
          </div>
        )}
        {isCustom && (
          <input
            className="input mono"
            style={{ marginTop: 6 }}
            value={indicator}
            onChange={(e) => setIndicator(e.target.value)}
            placeholder="Название показателя"
          />
        )}
        {fieldErrors.indicator && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {Array.isArray(fieldErrors.indicator)
              ? fieldErrors.indicator.join(' · ')
              : String(fieldErrors.indicator)}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>
            Норма *
            <HelpHint text="Допустимое значение по нормативу. Берётся из ТР ТС 021/2011 или паспорта качества." />
          </label>
          <input
            className="input mono"
            value={normalRange}
            onChange={(e) => setNormalRange(e.target.value)}
            placeholder="<1×10⁵ КОЕ/г"
          />
        </div>
        <div className="field">
          <label>
            Факт *
            <HelpHint text="Что лаборатория намерила. Сравнивается с нормой." />
          </label>
          <input
            className="input mono"
            value={actualValue}
            onChange={(e) => setActualValue(e.target.value)}
            placeholder="2×10⁴"
          />
        </div>
      </div>

      <div className="field">
        <label>Результат *</label>
        <select
          className="input"
          value={status}
          onChange={(e) => setStatus(e.target.value as typeof status)}
        >
          <option value="pending">В работе</option>
          <option value="passed">Норма</option>
          <option value="failed">Отклонение</option>
        </select>
      </div>

      <div className="field">
        <label>Заметка</label>
        <input
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
