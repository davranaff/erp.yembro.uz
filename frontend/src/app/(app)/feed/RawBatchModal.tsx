'use client';

import { useEffect, useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useCounterparties } from '@/hooks/useCounterparties';
import { rawBatchesCrud } from '@/hooks/useFeed';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { useWarehouses } from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { NomenclatureItem, RawMaterialBatch } from '@/types/auth';

interface Props {
  initial?: RawMaterialBatch | null;
  onClose: () => void;
}

type ShrinkMode = 'duval' | 'direct' | 'none';

/**
 * Чистый расчёт зачётного веса (зеркало backend services/shrinkage.py)
 * для live-preview в форме.
 */
function duvalShrinkPct(actual: number, base: number): number {
  if (!actual || !base || actual <= base) return 0;
  if (base >= 100) return 0;
  return (100 * (actual - base)) / (100 - base);
}

function settlementFromGross(gross: number, shrinkPct: number): number {
  if (gross <= 0) return 0;
  if (shrinkPct <= 0) return gross;
  return gross * (1 - shrinkPct / 100);
}

function fmtKg(v: number): string {
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
}

function fmtMoney(v: number): string {
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' сум';
}

export default function RawBatchModal({ initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = rawBatchesCrud.useCreate();
  const update = rawBatchesCrud.useUpdate();

  // Сырьё корма — только из nomenclature модуля feed
  const { data: noms } = useNomenclatureItems({ module_code: 'feed', is_active: 'true' });
  const { data: warehouses } = useWarehouses({ module_code: 'feed' });
  const { data: suppliers } = useCounterparties({ kind: 'supplier' });
  const { data: bins } = useProductionBlocks({
    module_code: 'feed', kind: 'storage_bin', is_active: 'true',
  });

  const [nomenclatureId, setNomenclatureId] = useState(initial?.nomenclature ?? '');
  const [supplierId, setSupplierId] = useState(initial?.supplier ?? '');
  const [warehouseId, setWarehouseId] = useState(initial?.warehouse ?? '');
  const [storageBin, setStorageBin] = useState(initial?.storage_bin ?? '');
  const [receivedDate, setReceivedDate] = useState(
    initial?.received_date ?? new Date().toISOString().slice(0, 10),
  );
  const [pricePerUnit, setPricePerUnit] = useState(initial?.price_per_unit_uzs ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');

  // Веса / усушка
  const [shrinkMode, setShrinkMode] = useState<ShrinkMode>('duval');
  const [grossKg, setGrossKg] = useState(initial?.gross_weight_kg ?? '');
  const [moistureActual, setMoistureActual] = useState(initial?.moisture_pct_actual ?? '');
  const [dockageActual, setDockageActual] = useState(initial?.dockage_pct_actual ?? '0');
  const [directShrink, setDirectShrink] = useState(initial?.shrinkage_pct ?? '');
  const [legacyQuantity, setLegacyQuantity] = useState(initial?.quantity ?? '');

  // Карантин
  const [putToQuarantine, setPutToQuarantine] = useState(true);
  const [quarantineUntil, setQuarantineUntil] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().slice(0, 10);
  });

  const selectedNom = useMemo<NomenclatureItem | undefined>(
    () => noms?.find((n) => n.id === nomenclatureId),
    [noms, nomenclatureId],
  );
  const baseMoisture = selectedNom?.base_moisture_pct
    ? parseFloat(selectedNom.base_moisture_pct)
    : null;

  // Авто-фокус режима, когда выбрана номенклатура: если у неё есть base_moisture
  // — режим Дюваля, иначе — direct.
  useEffect(() => {
    if (!isEdit && selectedNom) {
      setShrinkMode(baseMoisture != null ? 'duval' : 'direct');
    }
  }, [isEdit, selectedNom, baseMoisture]);

  // ── Live preview ──────────────────────────────────────────────────────
  const preview = useMemo(() => {
    const gross = parseFloat(grossKg || '0');
    const price = parseFloat(pricePerUnit || '0');

    if (shrinkMode === 'none') {
      const q = parseFloat(legacyQuantity || '0');
      return {
        settlement: q,
        shrinkPct: 0,
        total: q * price,
        mode: 'legacy',
      };
    }
    if (gross <= 0) {
      return { settlement: 0, shrinkPct: 0, total: 0, mode: shrinkMode };
    }

    if (shrinkMode === 'duval') {
      const actual = parseFloat(moistureActual || '0');
      const dockage = parseFloat(dockageActual || '0');
      if (baseMoisture == null || actual <= 0) {
        return { settlement: gross, shrinkPct: 0, total: gross * price, mode: 'duval-empty' };
      }
      const duv = duvalShrinkPct(actual, baseMoisture);
      const total = duv + dockage;
      const settlement = settlementFromGross(gross, total);
      return {
        settlement,
        shrinkPct: total,
        total: settlement * price,
        mode: 'duval',
      };
    }
    // direct
    const sh = parseFloat(directShrink || '0');
    const settlement = settlementFromGross(gross, sh);
    return {
      settlement,
      shrinkPct: sh,
      total: settlement * price,
      mode: 'direct',
    };
  }, [
    shrinkMode, grossKg, pricePerUnit, legacyQuantity,
    moistureActual, dockageActual, baseMoisture, directShrink,
  ]);

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const canSubmit =
    nomenclatureId &&
    warehouseId &&
    receivedDate &&
    pricePerUnit &&
    (shrinkMode === 'none' ? legacyQuantity : grossKg) &&
    !create.isPending &&
    !update.isPending;

  const handleSave = async () => {
    if (!selectedNom) return;
    const payload = {
      nomenclature: nomenclatureId,
      supplier: supplierId || null,
      warehouse: warehouseId,
      storage_bin: storageBin,
      received_date: receivedDate,
      unit: selectedNom.unit,
      price_per_unit_uzs: pricePerUnit,
      notes,
      status: putToQuarantine ? 'quarantine' as const : 'available' as const,
      quarantine_until: putToQuarantine ? quarantineUntil : null,
      // Веса
      ...(shrinkMode === 'none'
        ? { quantity: legacyQuantity }
        : {
            gross_weight_kg: grossKg,
            ...(shrinkMode === 'duval'
              ? {
                  moisture_pct_actual: moistureActual || undefined,
                  dockage_pct_actual: dockageActual || undefined,
                }
              : { shrinkage_pct: directShrink || undefined }),
          }),
    };

    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch { /* */ }
  };

  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  return (
    <Modal
      title={isEdit ? `Партия сырья · ${initial?.doc_number}` : 'Новая партия сырья'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={handleSave}>
            {(create.isPending || update.isPending) ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Приёмка сырья на склад модуля «Корма». При повышенной влажности
        зачётный вес рассчитается по формуле Дюваля.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Номенклатура (сырьё) *</label>
          <select
            className="input"
            value={nomenclatureId}
            onChange={(e) => setNomenclatureId(e.target.value)}
            disabled={isEdit}
          >
            <option value="">—</option>
            {noms?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.sku} · {n.name}
                {n.base_moisture_pct ? ` (базис. вл. ${n.base_moisture_pct}%)` : ''}
              </option>
            ))}
          </select>
          {getErr('nomenclature') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('nomenclature')}</div>
          )}
        </div>

        <div className="field">
          <label>Дата приёмки *</label>
          <input
            className="input"
            type="date"
            value={receivedDate}
            onChange={(e) => setReceivedDate(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Цена за 1 кг (UZS) *</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={pricePerUnit}
            onChange={(e) => setPricePerUnit(e.target.value)}
            placeholder="3200"
          />
        </div>

        <div className="field">
          <label>Поставщик</label>
          <select
            className="input"
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
          >
            <option value="">—</option>
            {suppliers?.map((s) => (
              <option key={s.id} value={s.id}>{s.code} · {s.name}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>
            Склад *
            <HelpHint
              text="Склад модуля «Корма»."
              details="Каждая партия должна лежать на конкретном складе. Если складов нет — создайте их в /stock."
            />
          </label>
          <select
            className="input"
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
          >
            <option value="">—</option>
            {warehouses?.filter((w) => w.module_code === 'feed').map((w) => (
              <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>
            Бункер / секция
            <HelpHint
              text="Где физически хранится партия на складе."
              details={
                'Бункер — это конкретная ёмкость (силос, бункер, секция) на складе сырья. '
                + 'Выбираем из блоков типа «Бункер хранения» (создаются в /blocks). '
                + 'Используется для печати акта и логистики.'
              }
            />
          </label>
          <select
            className="input"
            value={storageBin}
            onChange={(e) => setStorageBin(e.target.value)}
          >
            <option value="">— не выбран —</option>
            {bins?.map((b) => (
              <option key={b.id} value={b.code}>
                {b.code} · {b.name}
              </option>
            ))}
          </select>
          {bins && bins.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 4 }}>
              Нет блоков-бункеров. Создайте в{' '}
              <a href="/blocks" target="_blank" rel="noreferrer"
                 style={{ color: 'var(--brand-orange)', textDecoration: 'underline' }}>
                /blocks
              </a>
              {' '}— тип «Бункер хранения», модуль «feed».
            </div>
          )}
        </div>
      </div>

      {/* ── Веса и усушка ────────────────────────────────────────────── */}
      <div style={{ marginTop: 14, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
        <b style={{ fontSize: 13 }}>Веса и усушка</b>
        <HelpHint
          text="Расчёт зачётного веса."
          details={
            'Усушка — потеря массы сырья при сушке из-за испарения влаги. '
            + 'Если фактическая влажность выше базисной (14% по ГОСТ для зерна), '
            + 'часть массы «уйдёт» при сушке. Формула Дюваля: '
            + 'Хв = 100×(A−B)/(100−B). Зачётный вес = брутто × (1 − усушка/100). '
            + 'Поставщику платят именно за зачётный вес.'
          }
        />
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
        <button
          type="button"
          className={'btn btn-sm ' + (shrinkMode === 'duval' ? 'btn-primary' : 'btn-ghost')}
          onClick={() => setShrinkMode('duval')}
          style={{ flex: 1, fontSize: 12 }}
        >
          По влажности (Дюваль)
        </button>
        <button
          type="button"
          className={'btn btn-sm ' + (shrinkMode === 'direct' ? 'btn-primary' : 'btn-ghost')}
          onClick={() => setShrinkMode('direct')}
          style={{ flex: 1, fontSize: 12 }}
        >
          Указать % напрямую
        </button>
        <button
          type="button"
          className={'btn btn-sm ' + (shrinkMode === 'none' ? 'btn-primary' : 'btn-ghost')}
          onClick={() => setShrinkMode('none')}
          style={{ flex: 1, fontSize: 12 }}
        >
          Без расчёта
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {shrinkMode === 'duval' && (
          <>
            <div className="field">
              <label>
                Брутто вес, кг *
                <HelpHint
                  text="Физический вес на весах при приёмке."
                  details="Это фактическая масса как привезли, до любых поправок."
                />
              </label>
              <input
                className="input mono"
                type="number"
                step="0.001"
                value={grossKg}
                onChange={(e) => setGrossKg(e.target.value)}
                placeholder="10000.000"
              />
            </div>

            <div className="field">
              <label>
                Влажность факт, %
                <HelpHint
                  text="По лаборатории или сертификату."
                  details={
                    `Базисная влажность для этого SKU: ${baseMoisture ?? '—'}%. `
                    + 'Если фактическая выше — считается усушка по Дювалю.'
                  }
                />
              </label>
              <input
                className="input mono"
                type="number"
                step="0.01"
                value={moistureActual}
                onChange={(e) => setMoistureActual(e.target.value)}
                placeholder={baseMoisture != null ? `> ${baseMoisture}` : '18.00'}
                disabled={baseMoisture == null}
              />
              {baseMoisture == null && nomenclatureId && (
                <div style={{ fontSize: 10, color: 'var(--warning)', marginTop: 2 }}>
                  Базисная влажность не задана у этой номенклатуры
                </div>
              )}
              {baseMoisture != null && (
                <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 2 }}>
                  Базисная: {baseMoisture}%
                </div>
              )}
            </div>

            <div className="field" style={{ gridColumn: '1/3' }}>
              <label>
                Сорность, %
                <HelpHint
                  text="Доля примесей."
                  details="Прибавляется к усушке Дюваля. Если измерения нет — оставьте 0."
                />
              </label>
              <input
                className="input mono"
                type="number"
                step="0.01"
                value={dockageActual}
                onChange={(e) => setDockageActual(e.target.value)}
                placeholder="0"
              />
            </div>
          </>
        )}

        {shrinkMode === 'direct' && (
          <>
            <div className="field">
              <label>
                Брутто вес, кг *
                <HelpHint
                  text="Физический вес на весах."
                  details="Фактическая масса как привезли."
                />
              </label>
              <input
                className="input mono"
                type="number"
                step="0.001"
                value={grossKg}
                onChange={(e) => setGrossKg(e.target.value)}
                placeholder="10000.000"
              />
            </div>
            <div className="field">
              <label>
                Усушка, % *
                <HelpHint
                  text="Прямой % потери массы от брутто."
                  details="Например по опыту работы с поставщиком: «обычно скидывает 3%». Settlement = брутто × (1 − %/100)."
                />
              </label>
              <input
                className="input mono"
                type="number"
                step="0.01"
                value={directShrink}
                onChange={(e) => setDirectShrink(e.target.value)}
                placeholder="3.00"
              />
            </div>
          </>
        )}

        {shrinkMode === 'none' && (
          <div className="field" style={{ gridColumn: '1/3' }}>
            <label>
              Зачётный вес, кг *
              <HelpHint
                text="Учётный вес без расчётов."
                details="Используйте если усушка уже учтена в накладной поставщика."
              />
            </label>
            <input
              className="input mono"
              type="number"
              step="0.001"
              value={legacyQuantity}
              onChange={(e) => setLegacyQuantity(e.target.value)}
              placeholder="9700.000"
            />
          </div>
        )}
      </div>

      {/* Live preview — компактнее */}
      <div style={{
        marginTop: 8, padding: '8px 10px', background: 'var(--bg-soft)',
        borderRadius: 6, fontSize: 12,
        display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap',
      }}>
        <span>
          Зачёт. вес:{' '}
          <b className="mono" style={{ fontSize: 13 }}>
            {fmtKg(preview.settlement)} кг
          </b>
          {preview.shrinkPct > 0 && (
            <span style={{ color: 'var(--fg-3)', marginLeft: 4 }}>
              (− {preview.shrinkPct.toFixed(2)}%)
            </span>
          )}
        </span>
        <span style={{ color: 'var(--fg-2)' }}>
          К оплате: <b className="mono">{fmtMoney(preview.total)}</b>
        </span>
      </div>

      {/* Карантин и заметки в одной строке */}
      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, alignItems: 'end' }}>
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 4 }}>
            <input
              type="checkbox"
              checked={putToQuarantine}
              onChange={(e) => setPutToQuarantine(e.target.checked)}
            />
            <span>Положить в карантин до анализа</span>
            <HelpHint
              text="Пауза до результата лаборатории."
              details={
                'Партия в карантине не может использоваться в замесе. '
                + 'Снять карантин или отклонить можно через кнопку в drawer\'е партии.'
              }
            />
          </label>
          {putToQuarantine && (
            <input
              className="input"
              type="date"
              value={quarantineUntil}
              onChange={(e) => setQuarantineUntil(e.target.value)}
            />
          )}
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Заметки</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="напр. контракт №14"
          />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
