'use client';

import { useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { recipeVersionsCrud } from '@/hooks/useFeed';
import type { Recipe, RecipeVersion } from '@/types/auth';

interface Props {
  recipe: Recipe;
  /** Если задано — новая версия будет иметь номер version_number = lastNumber+1. */
  lastNumber?: number;
  /** Если задано — режим редактирования. */
  initial?: RecipeVersion | null;
  onClose: () => void;
}

/** POST/PATCH /api/feed/recipe-versions/ */
export default function VersionModal({ recipe, lastNumber, initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = recipeVersionsCrud.useCreate();
  const update = recipeVersionsCrud.useUpdate();

  const [versionNumber, setVersionNumber] = useState(
    String(initial?.version_number ?? (lastNumber ?? 0) + 1),
  );
  const [status, setStatus] = useState<'draft' | 'active' | 'archived'>(
    initial?.status ?? 'draft',
  );
  const [effectiveFrom, setEffectiveFrom] = useState(
    initial?.effective_from ?? new Date().toISOString().slice(0, 10),
  );
  const [protein, setProtein] = useState(initial?.target_protein_percent ?? '');
  const [fat, setFat] = useState(initial?.target_fat_percent ?? '');
  const [fibre, setFibre] = useState(initial?.target_fibre_percent ?? '');
  const [lysine, setLysine] = useState(initial?.target_lysine_percent ?? '');
  const [me, setMe] = useState(initial?.target_me_kcal_per_kg ?? '');
  const [comment, setComment] = useState(initial?.comment ?? '');

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    const payload = {
      recipe: recipe.id,
      version_number: Number(versionNumber),
      status,
      effective_from: effectiveFrom,
      target_protein_percent: protein || null,
      target_fat_percent: fat || null,
      target_fibre_percent: fibre || null,
      target_lysine_percent: lysine || null,
      target_me_kcal_per_kg: me || null,
      comment,
    };
    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload as never });
      } else {
        await create.mutateAsync(payload as never);
      }
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={isEdit
        ? `Редактирование · ${recipe.code} v${initial?.version_number}`
        : `Новая версия · ${recipe.code}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!versionNumber || create.isPending || update.isPending}
            onClick={handleSubmit}
          >
            {(create.isPending || update.isPending)
              ? 'Сохранение…'
              : (isEdit ? 'Сохранить' : 'Создать версию')}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Версия — это снимок состава корма. Создайте версию, добавьте к ней
        компоненты, переведите в «Активна» — и она будет доступна для заданий
        на замес.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>№ версии *</label>
          <input className="input mono" type="number" value={versionNumber} onChange={(e) => setVersionNumber(e.target.value)} />
          {fieldErrors.version_number && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.version_number.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>
            Статус
            <HelpHint
              text="Жизненный цикл версии."
              details={
                '• Черновик — только что создана, идёт набор компонентов и подгонка показателей. Не доступна для заданий.\n'
                + '• Активна — готова к использованию. Можно создавать задания на замес. У одного рецепта может быть несколько активных версий, но обычно одна.\n'
                + '• Архив — старая версия, выведена из обращения. Прошлые партии остаются «привязанными» к ней для прослеживаемости.'
              }
            />
          </label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            <option value="draft">Черновик</option>
            <option value="active">Активна</option>
            <option value="archived">Архив</option>
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Действует с *</label>
          <input className="input" type="date" value={effectiveFrom} onChange={(e) => setEffectiveFrom(e.target.value)} />
        </div>
        <div style={{ gridColumn: '1/3', fontSize: 11, color: 'var(--fg-3)', marginTop: 4, display: 'inline-flex', alignItems: 'center' }}>
          Целевые показатели (опционально)
          <HelpHint
            text="Что вы хотите получить в готовом корме."
            details={
              'Это рекомендуемый состав корма по нормам кормления птицы. После выпуска партии '
              + 'лаборатория сравнит фактические показатели с этими целями. Не обязательно к заполнению — '
              + 'но без них нет автоматического контроля качества.\n\n'
              + 'Типичные значения для бройлера-старт: белок 22–24%, жир 5–7%, '
              + 'обм. энергия 3000–3050 ккал/кг.'
            }
          />
        </div>
        <div className="field"><label>Белок, %</label><input className="input mono" type="number" step="0.01" value={protein} onChange={(e) => setProtein(e.target.value)} /></div>
        <div className="field"><label>Жир, %</label><input className="input mono" type="number" step="0.01" value={fat} onChange={(e) => setFat(e.target.value)} /></div>
        <div className="field"><label>Клетчатка, %</label><input className="input mono" type="number" step="0.01" value={fibre} onChange={(e) => setFibre(e.target.value)} /></div>
        <div className="field"><label>Лизин, %</label><input className="input mono" type="number" step="0.01" value={lysine} onChange={(e) => setLysine(e.target.value)} /></div>
        <div className="field" style={{ gridColumn: '1/3' }}><label>Обм. энергия, ккал/кг</label><input className="input mono" type="number" step="0.01" value={me} onChange={(e) => setMe(e.target.value)} /></div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Комментарий</label>
          <input className="input" value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
