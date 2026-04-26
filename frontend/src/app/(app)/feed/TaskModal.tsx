'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { recipeVersionsCrud, recipesCrud, tasksCrud } from '@/hooks/useFeed';
import { useModules } from '@/hooks/useModules';
import { usePeople } from '@/hooks/usePeople';

interface Props {
  onClose: () => void;
}

/** POST /api/feed/production-tasks/ — создание задания на замес */
export default function TaskModal({ onClose }: Props) {
  const create = tasksCrud.useCreate();
  const { data: modules } = useModules();
  const { data: versions } = recipeVersionsCrud.useList({ status: 'active' });
  const { data: recipes } = recipesCrud.useList();
  const { data: lines } = useProductionBlocks({ kind: 'mixer_line' });
  const { data: people } = usePeople({ is_active: 'true' });

  const feedModuleId = modules?.find((m) => m.code === 'feed')?.id ?? '';

  const today = new Date();
  const local = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
    .toISOString().slice(0, 16);

  const [docNumber, setDocNumber] = useState('');
  const [recipeVersion, setRecipeVersion] = useState('');
  const [productionLine, setProductionLine] = useState('');
  const [shift, setShift] = useState<'day' | 'night'>('day');
  const [scheduledAt, setScheduledAt] = useState(local);
  const [plannedKg, setPlannedKg] = useState('');
  const [tech, setTech] = useState('');
  const [isMedicated, setIsMedicated] = useState(false);
  const [withdrawalDays, setWithdrawalDays] = useState('0');
  const [notes, setNotes] = useState('');

  const error = create.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const selectedVersion = useMemo(
    () => versions?.find((v) => v.id === recipeVersion),
    [versions, recipeVersion],
  );
  const selectedRecipe = useMemo(
    () => recipes?.find((r) => r.id === selectedVersion?.recipe),
    [recipes, selectedVersion],
  );

  const handleSubmit = async () => {
    if (!feedModuleId) { alert('Модуль feed не найден'); return; }
    try {
      await create.mutateAsync({
        doc_number: docNumber,
        module: feedModuleId,
        recipe_version: recipeVersion,
        production_line: productionLine,
        shift,
        scheduled_at: new Date(scheduledAt).toISOString(),
        planned_quantity_kg: plannedKg,
        is_medicated: isMedicated,
        withdrawal_period_days: Number(withdrawalDays || 0),
        technologist: tech,
        notes,
      } as never);
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title="Новое задание на замес"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!docNumber || !recipeVersion || !productionLine || !plannedKg || !tech || create.isPending}
            onClick={handleSubmit}
          >
            {create.isPending ? 'Создание…' : 'Создать'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        План «сделать N кг корма по версии рецепта в смену Y». При проведении задание
        автоматически спишет нужное сырьё и создаст готовую партию.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="field">
          <label>Документ *</label>
          <input className="input mono" value={docNumber} onChange={(e) => setDocNumber(e.target.value)} placeholder="ЗМ-001" />
          {fieldErrors.doc_number && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.doc_number.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>
            Версия рецепта *
            <HelpHint
              text="Конкретная конфигурация рецепта."
              details={
                'Версия — это снимок состава корма (компоненты + доли) и целевые показатели '
                + '(белок, жир, обменная энергия). Только активные версии доступны для новых '
                + 'заданий — это защита от случайного использования черновиков или архивных '
                + 'рецептов. Если списка пуст — создайте версию в драйвере рецепта.'
              }
            />
          </label>
          <select className="input" value={recipeVersion} onChange={(e) => setRecipeVersion(e.target.value)}>
            <option value="">—</option>
            {versions?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.recipe_code ?? '—'} v{v.version_number} · {v.components.length} компонентов
              </option>
            ))}
          </select>
          {selectedRecipe && selectedVersion && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
              {selectedRecipe.name} · {selectedRecipe.direction} · {selectedRecipe.age_range}
            </div>
          )}
        </div>
        <div className="field">
          <label>
            Линия замеса *
            <HelpHint
              text="Производственная линия (смеситель)."
              details="Физическая линия где будет происходить замес. Если линий нет — создайте блок типа mixer_line в /blocks."
            />
          </label>
          <select className="input" value={productionLine} onChange={(e) => setProductionLine(e.target.value)}>
            <option value="">—</option>
            {lines?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Смена</label>
          <select className="input" value={shift} onChange={(e) => setShift(e.target.value as typeof shift)}>
            <option value="day">День</option>
            <option value="night">Ночь</option>
          </select>
        </div>
        <div className="field">
          <label>Запланировано *</label>
          <input className="input" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
        </div>
        <div className="field">
          <label>
            План, кг *
            <HelpHint
              text="Сколько корма планируем получить."
              details="Сырьё рассчитается автоматически по долям компонентов из версии. Например, если версия задаёт кукурузу 50% и план 1000 кг — спишется 500 кг кукурузы со склада."
            />
          </label>
          <input className="input mono" type="number" step="0.001" value={plannedKg} onChange={(e) => setPlannedKg(e.target.value)} />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Технолог *</label>
          <select className="input" value={tech} onChange={(e) => setTech(e.target.value)}>
            <option value="">—</option>
            {people?.map((p) => (
              <option key={p.user} value={p.user}>{p.user_full_name} · {p.position_title || p.user_email}</option>
            ))}
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3', flexDirection: 'row', alignItems: 'center', gap: 16, display: 'flex' }}>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 12 }}>
            <input type="checkbox" checked={isMedicated} onChange={(e) => setIsMedicated(e.target.checked)} />
            Медикаментозный
            <HelpHint
              text="Корм с лекарственным компонентом."
              details="Если в составе вет.препарат (антибиотик и т.п.) — птица не должна идти на убой, пока не закончится период каренции. Каренция указывается в днях."
            />
          </label>
          {isMedicated && (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 12 }}>Каренция (дн):</span>
              <input
                className="input mono"
                type="number"
                value={withdrawalDays}
                onChange={(e) => setWithdrawalDays(e.target.value)}
                style={{ width: 80 }}
              />
            </div>
          )}
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметка</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      {/* Превью состава выбранной версии */}
      {selectedVersion && (
        <div style={{
          marginTop: 12, padding: 10, background: 'var(--bg-soft)',
          borderRadius: 6, fontSize: 12,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13 }}>
            Состав замеса
            {plannedKg && ` (на ${parseFloat(plannedKg).toLocaleString('ru-RU')} кг)`}
          </div>
          {selectedVersion.components.length === 0 ? (
            <div style={{ color: 'var(--warning)' }}>
              ⚠ В этой версии нет компонентов — задание не получится провести.
              Сначала добавьте компоненты в drawer'е рецепта.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <tbody>
                {selectedVersion.components.map((c) => {
                  const planned = parseFloat(plannedKg || '0');
                  const share = parseFloat(c.share_percent || '0');
                  const needKg = (planned * share) / 100;
                  return (
                    <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '4px 6px', color: 'var(--fg-3)' }} className="mono">
                        {c.nomenclature_sku ?? ''}
                      </td>
                      <td style={{ padding: '4px 6px' }}>{c.nomenclature_name ?? '—'}</td>
                      <td style={{ padding: '4px 6px', textAlign: 'right' }} className="mono">
                        {share}%
                      </td>
                      {plannedKg && (
                        <td style={{ padding: '4px 6px', textAlign: 'right', fontWeight: 600 }} className="mono">
                          {needKg.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} кг
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
