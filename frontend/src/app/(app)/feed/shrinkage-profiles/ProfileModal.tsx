'use client';

import { useEffect, useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { recipesCrud, shrinkageProfilesCrud } from '@/hooks/useFeed';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { useWarehouses } from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { FeedShrinkageProfile, Recipe, ShrinkageTargetType } from '@/types/auth';

interface Props {
  initial?: FeedShrinkageProfile | null;
  onClose: () => void;
}

/** Compound-расчёт «через N дней останется X кг» — зеркало backend _compute_loss. */
function previewRemaining({
  initial,
  pctPerPeriod,
  periodDays,
  daysAhead,
  maxTotalPct,
  startsAfter,
}: {
  initial: number;
  pctPerPeriod: number;
  periodDays: number;
  daysAhead: number;
  maxTotalPct: number | null;
  startsAfter: number;
}): { remaining: number; loss: number; lossPct: number; frozen: boolean } {
  if (initial <= 0 || pctPerPeriod <= 0 || periodDays <= 0) {
    return { remaining: initial, loss: 0, lossPct: 0, frozen: false };
  }
  const eligibleDays = Math.max(0, daysAhead - startsAfter);
  const periods = Math.floor(eligibleDays / periodDays);
  if (periods <= 0) {
    return { remaining: initial, loss: 0, lossPct: 0, frozen: false };
  }
  const factor = pctPerPeriod / 100;
  let remaining = initial;
  let totalLoss = 0;
  let frozen = false;
  const maxLoss = maxTotalPct != null ? (initial * maxTotalPct) / 100 : null;
  for (let i = 0; i < periods; i++) {
    let delta = remaining * factor;
    if (maxLoss != null && totalLoss + delta >= maxLoss) {
      delta = Math.max(0, maxLoss - totalLoss);
      totalLoss += delta;
      remaining -= delta;
      frozen = true;
      break;
    }
    totalLoss += delta;
    remaining -= delta;
    if (remaining <= 0) break;
  }
  const lossPct = (totalLoss / initial) * 100;
  return { remaining, loss: totalLoss, lossPct, frozen };
}

export default function ProfileModal({ initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = shrinkageProfilesCrud.useCreate();
  const update = shrinkageProfilesCrud.useUpdate();

  const [targetType, setTargetType] = useState<ShrinkageTargetType>(
    initial?.target_type ?? 'ingredient',
  );
  const [nomenclatureId, setNomenclatureId] = useState<string>(initial?.nomenclature ?? '');
  const [recipeId, setRecipeId] = useState<string>(initial?.recipe ?? '');
  const [warehouseId, setWarehouseId] = useState<string>(initial?.warehouse ?? '');
  const [periodDays, setPeriodDays] = useState<string>(String(initial?.period_days ?? 7));
  const [percent, setPercent] = useState<string>(initial?.percent_per_period ?? '0.8');
  const [maxPercent, setMaxPercent] = useState<string>(initial?.max_total_percent ?? '');
  const [stopAfterDays, setStopAfterDays] = useState<string>(
    initial?.stop_after_days != null ? String(initial.stop_after_days) : '',
  );
  const [startsAfterDays, setStartsAfterDays] = useState<string>(
    String(initial?.starts_after_days ?? 0),
  );
  const [isActive, setIsActive] = useState<boolean>(initial?.is_active ?? true);
  const [note, setNote] = useState<string>(initial?.note ?? '');
  const [error, setError] = useState<string | null>(null);
  const [previewKg, setPreviewKg] = useState<string>('1000');
  const [previewDays, setPreviewDays] = useState<string>('30');

  const { data: noms } = useNomenclatureItems({ module_code: 'feed', is_active: 'true' });
  const { data: recipes } = recipesCrud.useList({ is_active: 'true' });
  const { data: warehouses } = useWarehouses({ module_code: 'feed' });

  // При смене target_type сбрасываем второй FK
  useEffect(() => {
    if (targetType === 'ingredient') setRecipeId('');
    else setNomenclatureId('');
  }, [targetType]);

  const preview = useMemo(() => {
    return previewRemaining({
      initial: parseFloat(previewKg) || 0,
      pctPerPeriod: parseFloat(percent) || 0,
      periodDays: parseInt(periodDays) || 0,
      daysAhead: parseInt(previewDays) || 0,
      maxTotalPct: maxPercent ? parseFloat(maxPercent) : null,
      startsAfter: parseInt(startsAfterDays) || 0,
    });
  }, [previewKg, previewDays, percent, periodDays, maxPercent, startsAfterDays]);

  const handleSave = async () => {
    setError(null);

    // Валидация на фронте до запроса (бэк всё равно проверит)
    if (targetType === 'ingredient' && !nomenclatureId) {
      setError('Выберите ингредиент.');
      return;
    }
    if (targetType === 'feed_type' && !recipeId) {
      setError('Выберите рецептуру.');
      return;
    }
    const periodN = parseInt(periodDays);
    const pctN = parseFloat(percent);
    if (!periodN || periodN <= 0) {
      setError('Период должен быть > 0 дней.');
      return;
    }
    if (Number.isNaN(pctN) || pctN < 0 || pctN > 100) {
      setError('Процент за период — от 0 до 100.');
      return;
    }
    if (maxPercent) {
      const m = parseFloat(maxPercent);
      if (Number.isNaN(m) || m < 0 || m > 100) {
        setError('Максимальный процент — от 0 до 100.');
        return;
      }
    }

    const payload = {
      target_type: targetType,
      nomenclature: targetType === 'ingredient' ? nomenclatureId : null,
      recipe: targetType === 'feed_type' ? recipeId : null,
      warehouse: warehouseId || null,
      period_days: periodN,
      percent_per_period: percent,
      max_total_percent: maxPercent || null,
      stop_after_days: stopAfterDays ? parseInt(stopAfterDays) : null,
      starts_after_days: parseInt(startsAfterDays) || 0,
      is_active: isActive,
      note,
    };

    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch (e) {
      const err = e as ApiError;
      const data = err.data as Record<string, unknown> | undefined;
      const detail =
        (typeof data === 'object' && data &&
          ('detail' in data ? String(data.detail) :
           Object.values(data).flat().join('; '))) ||
        err.message;
      setError(detail || 'Не удалось сохранить.');
    }
  };

  const isPending = create.isPending || update.isPending;

  return (
    <Modal
      title={isEdit ? 'Редактировать профиль усушки' : 'Новый профиль усушки'}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={isPending}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={isPending}
          >
            {isPending ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Создать'}
          </button>
        </>
      }
    >
      {/* target_type radio */}
      <div className="field">
        <label className="label">Что усыхает <HelpHint text="Сырьё привязывается к номенклатурной позиции; готовый корм — к рецептуре (профиль действует на все её версии и партии)." /></label>
        <div style={{ display: 'flex', gap: 16 }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input
              type="radio"
              checked={targetType === 'ingredient'}
              onChange={() => setTargetType('ingredient')}
            />
            Сырьё
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input
              type="radio"
              checked={targetType === 'feed_type'}
              onChange={() => setTargetType('feed_type')}
            />
            Готовый корм
          </label>
        </div>
      </div>

      {/* selector */}
      {targetType === 'ingredient' ? (
        <div className="field" style={{ marginTop: 14 }}>
          <label className="label">Ингредиент *</label>
          <select
            className="input"
            value={nomenclatureId}
            onChange={(e) => setNomenclatureId(e.target.value)}
          >
            <option value="">— выберите —</option>
            {(noms ?? []).map((n) => (
              <option key={n.id} value={n.id}>{n.sku} · {n.name}</option>
            ))}
          </select>
        </div>
      ) : (
        <div className="field" style={{ marginTop: 14 }}>
          <label className="label">Рецептура *</label>
          <select
            className="input"
            value={recipeId}
            onChange={(e) => setRecipeId(e.target.value)}
          >
            <option value="">— выберите —</option>
            {(recipes ?? []).map((r: Recipe) => (
              <option key={r.id} value={r.id}>{r.code} · {r.name}</option>
            ))}
          </select>
        </div>
      )}

      <div className="field" style={{ marginTop: 14 }}>
        <label className="label">
          Склад <HelpHint text="Можно сделать профиль для конкретного склада. Конкретный побеждает общий «для всех складов»." />
        </label>
        <select
          className="input"
          value={warehouseId}
          onChange={(e) => setWarehouseId(e.target.value)}
        >
          <option value="">— Все склады —</option>
          {(warehouses ?? []).map((w) => (
            <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
          ))}
        </select>
      </div>

      {/* numbers grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 14 }}>
        <div className="field">
          <label className="label">% за период *</label>
          <input
            className="input"
            type="number"
            step="0.001"
            min="0"
            max="100"
            value={percent}
            onChange={(e) => setPercent(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="label">Период (дни) *</label>
          <input
            className="input"
            type="number"
            min="1"
            value={periodDays}
            onChange={(e) => setPeriodDays(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="label">
            Максимум всего, % <HelpHint text="Верхний предел накопленной усушки на партию. Когда достигнут — партия замораживается." />
          </label>
          <input
            className="input"
            type="number"
            step="0.001"
            min="0"
            max="100"
            placeholder="без предела"
            value={maxPercent}
            onChange={(e) => setMaxPercent(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="label">
            Стоп через N дней <HelpHint text="Не списывать усушку дольше N дней с поступления партии. Пусто = без ограничения." />
          </label>
          <input
            className="input"
            type="number"
            min="0"
            placeholder="без ограничения"
            value={stopAfterDays}
            onChange={(e) => setStopAfterDays(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="label">
            Грейс-период (дни) <HelpHint text="Первые N дней после поступления усушка не считается. По умолчанию 0." />
          </label>
          <input
            className="input"
            type="number"
            min="0"
            value={startsAfterDays}
            onChange={(e) => setStartsAfterDays(e.target.value)}
          />
        </div>
        <div className="field" style={{ display: 'flex', alignItems: 'flex-end' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Активен
          </label>
        </div>
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label className="label">Заметка</label>
        <textarea
          className="input"
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      {/* live preview */}
      <div style={{
        marginTop: 18, padding: 14, borderRadius: 10,
        background: 'var(--bg-subtle)', border: '1px solid var(--border)',
      }}>
        <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8, fontWeight: 600 }}>
          Прогноз
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
          <div>
            <label className="label" style={{ fontSize: 11 }}>Начальная масса, кг</label>
            <input
              className="input"
              type="number"
              value={previewKg}
              onChange={(e) => setPreviewKg(e.target.value)}
            />
          </div>
          <div>
            <label className="label" style={{ fontSize: 11 }}>Через сколько дней</label>
            <input
              className="input"
              type="number"
              value={previewDays}
              onChange={(e) => setPreviewDays(e.target.value)}
            />
          </div>
        </div>
        <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>
          Через {previewDays} дней: останется ≈{' '}
          <strong>{preview.remaining.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} кг</strong>
          {' '}(списано {preview.loss.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} кг,{' '}
          {preview.lossPct.toFixed(2)}%){preview.frozen && ' — упёрлись в максимум, заморозка'}
        </div>
      </div>

      {error && (
        <div style={{ marginTop: 12, color: 'var(--danger)', fontSize: 13 }}>
          {error}
        </div>
      )}
    </Modal>
  );
}
