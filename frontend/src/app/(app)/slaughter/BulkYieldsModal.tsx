'use client';

import { useEffect, useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import { useBulkYields, yieldsCrud } from '@/hooks/useSlaughter';
import { ApiError } from '@/lib/api';
import type { NomenclatureItem, SlaughterShift } from '@/types/auth';

interface Props {
  shift: SlaughterShift;
  onClose: () => void;
}

/**
 * Стандартные нормы выхода по бройлеру (% от живого веса).
 * Источник: ROSS-308 / COBB-500. Должны совпадать с backend BROILER_YIELD_NORMS.
 */
const BROILER_NORMS: Record<string, number> = {
  'CARCASS-WHOLE': 72.0,
  'BREAST':        25.0,
  'LEG':           28.0,
  'WING':           8.5,
  'OFFAL':          8.0,
  'FEET':           4.0,
  'HEAD':           3.0,
  'NECK':           3.5,
};

interface YieldRow {
  nom: NomenclatureItem;
  enabled: boolean;
  qty: string;     // строка для контролируемого инпута
  pctEdited: boolean;  // последняя редакция была через % (чтобы не было loop)
}

function fmtNum(n: number, digits = 2): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

export default function BulkYieldsModal({ shift, onClose }: Props) {
  const { data: existing } = yieldsCrud.useList({ shift: shift.id });
  const { data: items } = useNomenclatureItems({
    module_code: 'slaughter',
    is_active: 'true',
  });
  const bulk = useBulkYields();

  const liveKg = parseFloat(shift.live_weight_kg_total || '0');

  // Инициализация строк по items + предзаполнение из existing
  const [rows, setRows] = useState<YieldRow[]>([]);
  const [replaceExisting, setReplaceExisting] = useState(false);

  useEffect(() => {
    if (!items) return;
    const existingByNom = new Map<string, string>();
    if (existing) {
      for (const e of existing) {
        // Только kg-выходы
        if (e.unit_code === 'kg' || e.unit_code === 'кг') {
          existingByNom.set(e.nomenclature, e.quantity);
        }
      }
    }
    setRows(
      items.map((it) => {
        const existingQty = existingByNom.get(it.id);
        return {
          nom: it,
          enabled: Boolean(existingQty),
          qty: existingQty ?? '',
          pctEdited: false,
        };
      }),
    );
  }, [items, existing]);

  const totalKg = useMemo<number>(
    () => rows.reduce<number>((sum, r) => {
      if (!r.enabled) return sum;
      const v = parseFloat(r.qty || '0');
      return sum + (Number.isFinite(v) ? v : 0);
    }, 0),
    [rows],
  );
  const totalPct = liveKg > 0 ? (totalKg / liveKg) * 100 : 0;
  const wasteKg = Math.max(0, liveKg - totalKg);
  const wastePct = Math.max(0, 100 - totalPct);
  const overflow = liveKg > 0 && totalKg > liveKg;

  const updateRow = (idx: number, patch: Partial<YieldRow>) => {
    setRows((prev) => prev.map((r, i) => i === idx ? { ...r, ...patch } : r));
  };

  const handleQtyChange = (idx: number, value: string) => {
    updateRow(idx, { qty: value, enabled: value !== '' && parseFloat(value) > 0, pctEdited: false });
  };

  const handlePctChange = (idx: number, pct: string) => {
    const p = parseFloat(pct);
    if (!Number.isFinite(p) || liveKg <= 0) {
      updateRow(idx, { qty: '', pctEdited: true });
      return;
    }
    const kg = (liveKg * p / 100).toFixed(3);
    updateRow(idx, { qty: kg, enabled: p > 0, pctEdited: true });
  };

  const fillByNorms = () => {
    if (liveKg <= 0) return;
    setRows((prev) => prev.map((r) => {
      const norm = BROILER_NORMS[r.nom.sku.toUpperCase()];
      if (norm === undefined) return r;
      const kg = (liveKg * norm / 100).toFixed(3);
      return { ...r, enabled: true, qty: kg, pctEdited: false };
    }));
  };

  const clearAll = () => {
    setRows((prev) => prev.map((r) => ({ ...r, enabled: false, qty: '', pctEdited: false })));
  };

  const submit = async () => {
    const payload = rows
      .filter((r) => r.enabled && parseFloat(r.qty) > 0)
      .map((r) => {
        const qty = parseFloat(r.qty);
        const pct = liveKg > 0 ? (qty / liveKg) * 100 : 0;
        return {
          nomenclature: r.nom.id,
          quantity: r.qty,
          share_percent: pct.toFixed(3),
        };
      });
    if (payload.length === 0) {
      alert('Выберите хотя бы один выход');
      return;
    }
    try {
      await bulk.mutateAsync({
        shiftId: shift.id,
        yields: payload,
        replaceExisting,
      });
      onClose();
    } catch { /* fieldErrors показываются ниже */ }
  };

  const error = bulk.error;
  const errBody = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : ({} as Record<string, unknown>);
  const errYieldsRaw = errBody.yields;
  const errYieldsText: string | null =
    Array.isArray(errYieldsRaw)
      ? errYieldsRaw.map((e) => String(e)).join(' · ')
      : errYieldsRaw != null
        ? String(errYieldsRaw)
        : null;

  if (items && items.length === 0) {
    return (
      <Modal title="Разделка партии" onClose={onClose} footer={<button className="btn btn-primary" onClick={onClose}>OK</button>}>
        <div style={{ color: 'var(--danger)', padding: 12 }}>
          Нет SKU готовой продукции в модуле убойни. Добавьте через /nomenclature
          (категория с привязкой к модулю «Убойня»).
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      title={`Разделка партии · смена ${shift.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-secondary"
            onClick={fillByNorms}
            disabled={liveKg <= 0 || bulk.isPending}
            title="Заполнить типовыми нормами для бройлера"
          >
            По нормам
          </button>
          <button
            className="btn btn-ghost"
            onClick={clearAll}
            disabled={bulk.isPending}
          >
            Очистить
          </button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={overflow || totalKg <= 0 || bulk.isPending}
          >
            {bulk.isPending ? 'Сохранение…' : 'Сохранить все'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 8 }}>
        Введите кг по каждой части тушки или нажмите{' '}
        <strong>«По нормам»</strong> для типового распределения бройлера.
        <HelpHint
          text="Распределение себестоимости"
          details="При проведении смены накопленная себестоимость партии (живая птица + корм − падёж) распределяется между всеми выходами пропорционально доле share_percent. Отходы стоимости не получают."
        />
      </div>

      {/* Шапка — живой вес */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        padding: 8, marginBottom: 10,
        background: 'var(--bg-soft)', border: '1px solid var(--border)', borderRadius: 6,
        fontSize: 13,
      }}>
        <div>
          <span style={{ color: 'var(--fg-3)' }}>Живой вес: </span>
          <strong className="mono">{fmtNum(liveKg, 2)} кг</strong>
        </div>
        <div>
          <span style={{ color: 'var(--fg-3)' }}>Голов: </span>
          <strong className="mono">{shift.live_heads_received}</strong>
        </div>
      </div>

      {/* Таблица строк */}
      <div style={{ marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '24px 1fr 110px 80px 80px 110px',
          gap: 8, padding: '6px 4px', fontSize: 10, fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--fg-3)',
          borderBottom: '1px solid var(--border)',
        }}>
          <div></div>
          <div>SKU / Наименование</div>
          <div style={{ textAlign: 'right' }}>Кг</div>
          <div style={{ textAlign: 'right' }}>%</div>
          <div style={{ textAlign: 'right' }}>Норма</div>
          <div style={{ textAlign: 'right' }}>Δ</div>
        </div>

        {rows.map((r, idx) => {
          const norm = BROILER_NORMS[r.nom.sku.toUpperCase()];
          const qty = parseFloat(r.qty || '0');
          const pct = liveKg > 0 && qty > 0 ? (qty / liveKg) * 100 : null;
          const dev = pct !== null && norm !== undefined ? pct - norm : null;
          const offNorm = dev !== null && Math.abs(dev) > 2;
          return (
            <div
              key={r.nom.id}
              style={{
                display: 'grid', gridTemplateColumns: '24px 1fr 110px 80px 80px 110px',
                gap: 8, padding: '6px 4px', alignItems: 'center',
                background: r.enabled ? 'var(--bg-card, #fff)' : 'transparent',
                borderRadius: 4,
              }}
            >
              <input
                type="checkbox"
                checked={r.enabled}
                onChange={(e) => updateRow(idx, { enabled: e.target.checked })}
              />
              <div style={{ fontSize: 12 }}>
                <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 11 }}>
                  {r.nom.sku}
                </span>{' '}
                {r.nom.name}
              </div>
              <input
                className="input mono"
                type="number"
                step="0.001"
                value={r.qty}
                onChange={(e) => handleQtyChange(idx, e.target.value)}
                style={{ textAlign: 'right' }}
                placeholder="0"
              />
              <input
                className="input mono"
                type="number"
                step="0.01"
                value={pct !== null ? pct.toFixed(2) : ''}
                onChange={(e) => handlePctChange(idx, e.target.value)}
                style={{ textAlign: 'right', fontSize: 12 }}
                placeholder="—"
              />
              <div className="mono" style={{ textAlign: 'right', fontSize: 11, color: 'var(--fg-3)' }}>
                {norm !== undefined ? norm.toFixed(1) + '%' : '—'}
              </div>
              <div className="mono" style={{
                textAlign: 'right', fontSize: 11,
                color: dev === null
                  ? 'var(--fg-3)'
                  : offNorm ? 'var(--danger)' : 'var(--fg-2)',
              }}>
                {dev !== null
                  ? `${dev > 0 ? '+' : ''}${dev.toFixed(2)}%`
                  : '—'}
              </div>
            </div>
          );
        })}
      </div>

      {/* Итог */}
      <div
        style={{
          padding: 10,
          borderRadius: 6,
          background: overflow ? 'rgba(239,68,68,.1)' : 'var(--bg-soft)',
          border: '1px solid ' + (overflow ? 'var(--danger)' : 'var(--border)'),
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 13,
        }}
      >
        <div>
          <strong>Итого выходы: </strong>
          <span
            className="mono"
            style={{ color: overflow ? 'var(--danger)' : undefined }}
          >
            {fmtNum(totalKg, 2)} кг ({totalPct.toFixed(1)}%)
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--fg-3)' }}>Отходы: </span>
          <strong className="mono" style={{ color: 'var(--danger)' }}>
            {fmtNum(wasteKg, 2)} кг ({wastePct.toFixed(1)}%)
          </strong>
        </div>
      </div>

      {overflow && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>
          Сумма выходов превысила живой вес. Уменьшите количество.
        </div>
      )}

      {/* Replace toggle */}
      {existing && existing.length > 0 && (
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={replaceExisting}
            onChange={(e) => setReplaceExisting(e.target.checked)}
          />
          Заменить существующие выходы (удалить {existing.filter(e => e.unit_code === 'kg' || e.unit_code === 'кг').length} kg-записей перед сохранением)
        </label>
      )}

      {errYieldsText && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>
          {errYieldsText}
        </div>
      )}
      {error && error.status !== 400 && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
