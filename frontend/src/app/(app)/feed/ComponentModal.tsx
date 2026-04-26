'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { recipeComponentsCrud, recipeVersionsCrud } from '@/hooks/useFeed';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import type { RecipeComponent, RecipeVersion } from '@/types/auth';

interface Props {
  version: RecipeVersion;
  /** Если задано — режим редактирования компонента. */
  initial?: RecipeComponent | null;
  onClose: () => void;
}

/** POST/PATCH /api/feed/recipe-components/ */
export default function ComponentModal({ version, initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = recipeComponentsCrud.useCreate();
  const update = recipeComponentsCrud.useUpdate();
  const { data: items } = useNomenclatureItems({ is_active: 'true' });
  // Подтягиваем все версии, чтобы найти актуальный список компонентов нашей.
  const { data: allVersions } = recipeVersionsCrud.useList();
  const fullVersion = useMemo(
    () => allVersions?.find((v) => v.id === version.id) ?? version,
    [allVersions, version],
  );

  const [nomenclature, setNomenclature] = useState(initial?.nomenclature ?? '');
  const [share, setShare] = useState(initial?.share_percent ?? '');
  const [minShare, setMinShare] = useState(initial?.min_share_percent ?? '');
  const [maxShare, setMaxShare] = useState(initial?.max_share_percent ?? '');
  const [isMedicated, setIsMedicated] = useState(initial?.is_medicated ?? false);
  const [withdrawalDays, setWithdrawalDays] = useState(
    String(initial?.withdrawal_period_days ?? 0),
  );

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  // При редактировании текущую долю исключаем — она уже учтена.
  const otherShare = useMemo(() => {
    return fullVersion.components.reduce(
      (sum, c) => {
        if (initial && c.id === initial.id) return sum;
        return sum + parseFloat(c.share_percent || '0');
      },
      0,
    );
  }, [fullVersion, initial]);
  const newTotal = otherShare + parseFloat(share || '0');
  const remaining = 100 - otherShare;

  const handleSubmit = async () => {
    const payload = {
      recipe_version: version.id,
      nomenclature,
      share_percent: share,
      min_share_percent: minShare || null,
      max_share_percent: maxShare || null,
      is_medicated: isMedicated,
      withdrawal_period_days: Number(withdrawalDays || 0),
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
        ? `Редактирование компонента · ${version.recipe_code ?? '—'} v${version.version_number}`
        : `Компонент в версию ${version.recipe_code ?? '—'} v${version.version_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!nomenclature || !share || create.isPending || update.isPending}
            onClick={handleSubmit}
          >
            {(create.isPending || update.isPending)
              ? 'Сохранение…'
              : (isEdit ? 'Сохранить' : 'Добавить')}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Компонент — это ингредиент рецепта (кукуруза, шрот, премикс) с указанной долей.
        Сумма долей всех компонентов должна составлять 100%.
      </div>

      {/* Текущий состав версии (без редактируемого компонента) */}
      {fullVersion.components.length > 0 && (
        <div style={{
          marginBottom: 14, padding: 8, background: 'var(--bg-soft)',
          borderRadius: 6, fontSize: 12,
        }}>
          <div style={{
            fontWeight: 600, marginBottom: 6,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span>
              {isEdit ? 'Другие компоненты версии' : 'Уже в версии'}
              {' '}({isEdit
                ? fullVersion.components.length - 1
                : fullVersion.components.length})
            </span>
            <span className="mono" style={{
              color: otherShare > 100 ? 'var(--danger)'
                : otherShare === 100 ? 'var(--success)'
                : 'var(--fg-3)',
            }}>
              Σ {otherShare.toFixed(2)}%
            </span>
          </div>
          <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
            <tbody>
              {fullVersion.components
                .filter((c) => !initial || c.id !== initial.id)
                .map((c) => (
                  <tr key={c.id}>
                    <td style={{ padding: '2px 4px', color: 'var(--fg-3)' }} className="mono">
                      {c.nomenclature_sku ?? ''}
                    </td>
                    <td style={{ padding: '2px 4px' }}>{c.nomenclature_name ?? '—'}</td>
                    <td style={{ padding: '2px 4px', textAlign: 'right' }} className="mono">
                      {c.share_percent}%
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          {remaining > 0 && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
              Свободно: {remaining.toFixed(2)}% — можно занять под эту долю
            </div>
          )}
          {remaining < 0 && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4 }}>
              Сумма уже превышает 100% — отредактируйте существующие компоненты.
            </div>
          )}
        </div>
      )}

      <div className="field">
        <label>
          Сырьё *
          <HelpHint
            text="Ингредиент из справочника номенклатуры."
            details={
              'Выбирайте позиции из категории «сырьё для кормов»: зерно, шрот, премикс, '
              + 'витаминно-минеральные добавки, ракушка и т.д. Если нужного SKU нет — '
              + 'создайте его в /nomenclature.'
            }
          />
        </label>
        <select className="input" value={nomenclature} onChange={(e) => setNomenclature(e.target.value)}>
          <option value="">—</option>
          {items?.map((it) => (
            <option key={it.id} value={it.id}>{it.sku} · {it.name}</option>
          ))}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>
            Доля, % *
            <HelpHint
              text="Сколько % этого компонента в готовом корме."
              details="Например 50% кукурузы означает: на каждые 1000 кг корма уйдёт 500 кг кукурузы. Сумма долей всех компонентов = 100%."
            />
          </label>
          <input className="input mono" type="number" step="0.01" value={share} onChange={(e) => setShare(e.target.value)} />
          {share && newTotal > 100 && (
            <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 2 }}>
              Σ станет {newTotal.toFixed(2)}% — превысит 100%
            </div>
          )}
          {fieldErrors.share_percent && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.share_percent.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>
            Min, %
            <HelpHint
              text="Минимально допустимая доля."
              details="Опционально. Используется для контроля если понадобится подменять компоненты или корректировать доли при дефиците сырья."
            />
          </label>
          <input className="input mono" type="number" step="0.01" value={minShare} onChange={(e) => setMinShare(e.target.value)} />
        </div>
        <div className="field">
          <label>Max, %</label>
          <input className="input mono" type="number" step="0.01" value={maxShare} onChange={(e) => setMaxShare(e.target.value)} />
        </div>
      </div>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, marginTop: 6 }}>
        <input type="checkbox" checked={isMedicated} onChange={(e) => setIsMedicated(e.target.checked)} />
        Медикаментозный компонент
        <HelpHint
          text="Лекарственное сырьё (антибиотик, кокцидиостат и т.п.)."
          details="Если хотя бы один компонент медикаментозный — вся партия корма помечается как медикаментозная и для птицы устанавливается период каренции."
        />
      </label>
      {isMedicated && (
        <div className="field" style={{ marginTop: 6 }}>
          <label>Каренция, дн</label>
          <input className="input mono" type="number" value={withdrawalDays} onChange={(e) => setWithdrawalDays(e.target.value)} style={{ width: 100 }} />
        </div>
      )}

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
