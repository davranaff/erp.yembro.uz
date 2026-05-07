'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import {
  rawBatchesCrud,
  recipeComponentsCrud,
  recipesCrud,
  useFeedDashboard,
} from '@/hooks/useFeed';
import { getFinancesVisible } from '@/lib/permissions';

import RawBatchModal from '../RawBatchModal';
import RecipeModal from '../RecipeModal';
import TaskModal from '../TaskModal';
import VersionModal from '../VersionModal';
import type { Recipe } from '@/types/auth';

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function fmtNum(v: string | number, digits = 0): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function fmtMoney(v: string | number): string {
  const n = typeof v === 'string' ? parseFloat(v || '0') : v;
  if (!n || Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

/**
 * Excel-style сводка дня по модулю «Корма».
 *
 * Один экран — все ключевые операции:
 *   - Рецептурная матрица с inline-редактированием долей
 *   - What-if калькулятор: «произвести X тонн» → сколько каждого нужно,
 *     красная подсветка где не хватает
 *   - Per-recipe сводка в шапке: bottleneck-yield (макс тонн который можно
 *     намешать) и себестоимость 1 кг (по текущим взвешенным ценам сырья)
 *   - Sticky-колонка остатков рядом с SKU
 *   - Reorder hint: что докупить
 *   - Quick actions: партия сырья / замес / рецепт / расфасовка
 *   - Приход/Расход/Произведено/Остатки за день
 *
 * Целевой пользователь — оператор «из Excel-эпохи». Каждая ячейка-формула
 * считается на frontend из существующих endpoint'ов, в backend новой
 * бизнес-логики не добавляли.
 */
export default function FeedDashboardPage() {
  const qc = useQueryClient();
  const [date, setDate] = useState(todayISO());
  const { data, isLoading, error, refetch, isFetching } = useFeedDashboard(date);

  // Дополнительный источник: активные партии сырья (с остатком и ценой) —
  // для расчёта взвешенной средней цены ингредиента и bottleneck-yield.
  const { data: rawBatchesPage } = rawBatchesCrud.useListPaginated(
    { status: 'available' }, 1, 500,
  );
  const rawBatches = rawBatchesPage?.results ?? [];
  const { data: recipes } = recipesCrud.useList({});

  const matrix = data?.recipe_matrix;
  const matrixVersions = matrix?.versions ?? [];
  const matrixIngredients = matrix?.ingredients ?? [];

  // Финансовые данные показываются только пользователю с доступом к ledger.
  // Если raw batch вернулся без _finances_visible — доступа нет, цены прячем.
  const financesVisible = rawBatches.length === 0
    ? true
    : getFinancesVisible(rawBatches[0]);

  // ── Inline-edit для ячеек ──────────────────────────────────────────────
  const [editingCell, setEditingCell] = useState<{ sku: string; vid: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState<string | null>(null);
  const updateComp = recipeComponentsCrud.useUpdate();
  const createComp = recipeComponentsCrud.useCreate();

  // ── Modals ──────────────────────────────────────────────────────────────
  const [showAddIncoming, setShowAddIncoming] = useState(false);
  const [showAddTask, setShowAddTask] = useState(false);
  const [showAddRecipe, setShowAddRecipe] = useState(false);
  const [showAddVersion, setShowAddVersion] = useState<Recipe | null>(null);

  // ── What-if калькулятор ────────────────────────────────────────────────
  const [whatIfTons, setWhatIfTons] = useState(''); // '' = выкл
  const whatIfKg = useMemo(() => {
    const n = parseFloat(whatIfTons);
    return Number.isFinite(n) && n > 0 ? n * 1000 : 0;
  }, [whatIfTons]);

  // ── Stock map (sku → balance kg) для подсветки нехватки ───────────────
  const stockBySku = useMemo(() => {
    const map: Record<string, number> = {};
    for (const s of data?.stock ?? []) {
      map[s.sku] = parseFloat(s.balance || '0');
    }
    return map;
  }, [data?.stock]);

  // ── Взвешенная средняя цена ингредиента ────────────────────────────────
  // Берём все доступные RawMaterialBatch, группируем по nomenclature_sku,
  // считаем avg = Σ(qty × price) / Σ(qty). Это «текущая закупочная цена,
  // которую сейчас стоит ингредиент на складе».
  const priceBySku = useMemo(() => {
    const acc: Record<string, { qty: number; cost: number }> = {};
    for (const b of rawBatches) {
      if (!b.nomenclature_sku) continue;
      const qty = parseFloat(b.current_quantity || '0');
      const price = parseFloat(b.price_per_unit_uzs || '0');
      if (qty <= 0 || !Number.isFinite(price)) continue;
      const e = acc[b.nomenclature_sku] ?? { qty: 0, cost: 0 };
      e.qty += qty;
      e.cost += qty * price;
      acc[b.nomenclature_sku] = e;
    }
    const result: Record<string, number> = {};
    for (const [sku, { qty, cost }] of Object.entries(acc)) {
      if (qty > 0) result[sku] = cost / qty;
    }
    return result;
  }, [rawBatches]);

  // ── Per-recipe summary (yield + cost-per-kg) ───────────────────────────
  // yield kg = min по ингредиентам (stock_kg / share%) × 100
  // cost-per-kg = Σ(share% × avg_price_kg) / 100
  const recipeSummary = useMemo(() => {
    const summary: Record<string, { yieldKg: number | null; costPerKg: number | null; bottleneckSku: string | null }> = {};
    for (const v of matrixVersions) {
      let bestYield: number = Infinity;
      let bottleneck: string | null = null;
      let cost = 0;
      let costKnown = true;
      let totalShare = 0;
      for (const ing of matrixIngredients) {
        const info = ing.shares[v.id];
        if (!info) continue;
        const share = parseFloat(info.share || '0');
        if (share <= 0) continue;
        totalShare += share;

        // Yield: сколько кг готового можно сделать из текущего остатка
        // этого ингредиента. ингр_кг = (yield_кг × share/100) → yield = ингр_кг × 100/share.
        const stock = stockBySku[ing.sku] ?? 0;
        const possible = (stock * 100) / share;
        if (possible < bestYield) {
          bestYield = possible;
          bottleneck = ing.sku;
        }

        // Cost per kg готового: ингредиент_per_kg × share/100
        const price = priceBySku[ing.sku];
        if (price === undefined) {
          costKnown = false;
        } else {
          cost += price * share / 100;
        }
      }
      summary[v.id] = {
        yieldKg: bestYield === Infinity ? null : bestYield,
        costPerKg: (totalShare > 0 && costKnown) ? cost : null,
        bottleneckSku: bottleneck,
      };
    }
    return summary;
  }, [matrixVersions, matrixIngredients, stockBySku, priceBySku]);

  // ── Reorder hint: ингредиенты у которых < 1 тонна и они есть в рецептах
  const reorderList = useMemo(() => {
    const usedSkus = new Set<string>();
    for (const ing of matrixIngredients) {
      const usedInAny = Object.values(ing.shares).some(
        (s) => parseFloat(s.share || '0') > 0,
      );
      if (usedInAny) usedSkus.add(ing.sku);
    }
    const rows: Array<{ sku: string; name: string; balance: number }> = [];
    for (const s of data?.stock ?? []) {
      if (!usedSkus.has(s.sku)) continue;
      const bal = parseFloat(s.balance || '0');
      if (bal < 1000) {
        rows.push({ sku: s.sku, name: s.name, balance: bal });
      }
    }
    rows.sort((a, b) => a.balance - b.balance);
    return rows;
  }, [matrixIngredients, data?.stock]);

  // ── Column totals (sum of % per recipe) ────────────────────────────────
  const columnTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    for (const v of matrixVersions) totals[v.id] = 0;
    for (const ing of matrixIngredients) {
      for (const [vid, info] of Object.entries(ing.shares)) {
        totals[vid] = (totals[vid] ?? 0) + parseFloat(info.share || '0');
      }
    }
    return totals;
  }, [matrixVersions, matrixIngredients]);

  // ── Edit handlers ─────────────────────────────────────────────────────
  const startEdit = (sku: string, vid: string, current: string | null) => {
    setEditingCell({ sku, vid });
    setEditValue(current ?? '');
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue('');
  };

  const saveEdit = async () => {
    if (!editingCell) return;
    const { sku, vid } = editingCell;
    const ingredient = matrixIngredients.find((i) => i.sku === sku);
    if (!ingredient) { cancelEdit(); return; }

    const trimmed = editValue.trim();
    const existing = ingredient.shares[vid];
    const oldShare = existing?.share ?? null;
    if (trimmed === (oldShare ?? '')) { cancelEdit(); return; }

    if (trimmed === '' && existing) {
      alert('Чтобы убрать ингредиент, удалите компонент в /feed → Рецептуры (он может быть привязан к незавершённым замесам).');
      cancelEdit();
      return;
    }
    if (trimmed === '' && !existing) { cancelEdit(); return; }

    const num = parseFloat(trimmed);
    if (Number.isNaN(num) || num < 0 || num > 100) {
      alert('Доля должна быть числом от 0 до 100.');
      return;
    }

    setSaving(true);
    try {
      if (existing) {
        await updateComp.mutateAsync({
          id: existing.id,
          patch: { share_percent: trimmed } as never,
        });
      } else {
        await createComp.mutateAsync({
          recipe_version: vid,
          nomenclature: ingredient.nomenclature_id,
          share_percent: trimmed,
        } as never);
      }
      qc.invalidateQueries({ queryKey: ['feed', 'dashboard'] });
      setSavedFlash(`${sku}:${vid}`);
      setTimeout(() => setSavedFlash(null), 1500);
      cancelEdit();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Не удалось сохранить';
      alert(msg);
    } finally {
      setSaving(false);
    }
  };

  // Сколько каждого ингредиента нужно для what-if (если активен).
  const requiredKg = (sharePercent: string | null): number | null => {
    if (!whatIfKg || !sharePercent) return null;
    const share = parseFloat(sharePercent);
    if (!Number.isFinite(share) || share <= 0) return null;
    return (whatIfKg * share) / 100;
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Сводка дня</h1>
          <div className="sub">
            Корма · приход / расход / производство · текущие остатки + калькулятор «сколько произвести»
          </div>
        </div>
        <div className="actions">
          <Link href="/feed" className="btn btn-ghost btn-sm">
            <Icon name="chevron-left" size={12} /> К модулю
          </Link>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} /> {isFetching ? '…' : 'Обновить'}
          </button>
        </div>
      </div>

      {/* Date navigation */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14,
        padding: 10, background: 'var(--bg-soft)', borderRadius: 6,
      }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setDate((d) => shiftDate(d, -1))}
        >
          ← пред
        </button>
        <input
          className="input mono"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ width: 160 }}
        />
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setDate(todayISO())}
        >
          Сегодня
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setDate((d) => shiftDate(d, 1))}
        >
          след →
        </button>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>
          {new Date(date).toLocaleDateString('ru-RU', {
            weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
          })}
        </span>
      </div>

      {/* ── Quick actions toolbar ──────────────────────────────────────── */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14,
        padding: 10, border: '1px dashed var(--border)', borderRadius: 6,
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
          textTransform: 'uppercase', letterSpacing: '.04em',
          alignSelf: 'center', marginRight: 4,
        }}>
          Быстрые действия:
        </span>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setShowAddIncoming(true)}
        >
          <Icon name="plus" size={12} /> Партия сырья
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setShowAddTask(true)}
        >
          <Icon name="plus" size={12} /> Замес
        </button>
        <Link href="/feed" className="btn btn-secondary btn-sm">
          <Icon name="bag" size={12} /> Партии корма
        </Link>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setShowAddRecipe(true)}
        >
          <Icon name="plus" size={12} /> Рецепт
        </button>
        {recipes && recipes.length > 0 && (
          <select
            className="input"
            style={{ height: 30, fontSize: 13, padding: '0 8px' }}
            defaultValue=""
            onChange={(e) => {
              const r = recipes.find((x) => x.id === e.target.value);
              if (r) {
                setShowAddVersion(r);
                e.target.value = '';
              }
            }}
          >
            <option value="">+ Версия рецепта…</option>
            {recipes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.code} · {r.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* KPI */}
      <div className="kpi-row" style={{ marginBottom: 14 }}>
        <KpiCard
          tone="green" iconName="bag" label="Приход"
          sub={`${data?.summary.incoming_count ?? 0} операций`}
          value={isLoading ? '…' : String(data?.summary.incoming_count ?? 0)}
        />
        <KpiCard
          tone="red" iconName="close" label="Расход"
          sub={`${data?.summary.outgoing_count ?? 0} операций`}
          value={isLoading ? '…' : String(data?.summary.outgoing_count ?? 0)}
        />
        <KpiCard
          tone="orange" iconName="chart" label="Произведено"
          sub="готового корма"
          value={isLoading ? '…' : `${fmtNum(data?.summary.production_total_kg ?? '0', 0)} кг`}
        />
        <KpiCard
          tone="blue" iconName="box" label="SKU на складе"
          sub="ингредиентов с остатком"
          value={isLoading ? '…' : String(
            (data?.stock ?? []).filter((s) => parseFloat(s.balance) > 0).length
          )}
        />
      </div>

      {error && (
        <div style={{
          padding: 12, marginBottom: 14, background: '#fef2f2',
          color: 'var(--danger)', borderRadius: 6, fontSize: 13,
        }}>
          Не удалось загрузить сводку: {error.message}
        </div>
      )}

      {/* ── Reorder hint ────────────────────────────────────────────────── */}
      {reorderList.length > 0 && (
        <div style={{
          padding: 12, marginBottom: 14,
          background: 'var(--warning-soft, #FEF3C7)',
          border: '1px solid var(--warning, #F59E0B)',
          borderRadius: 6, fontSize: 13, color: '#7C2D12',
        }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>
            ⚠ Срочно докупить · {reorderList.length} ингредиент{reorderList.length === 1 ? '' : 'ов'} с низким остатком
          </div>
          <div style={{ fontSize: 12, color: '#92400E' }}>
            Меньше 1000 кг на складе и используется в активных рецептах.
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
            {reorderList.map((r) => (
              <span key={r.sku} style={{
                padding: '4px 8px', background: '#fff',
                border: '1px solid var(--warning, #F59E0B)', borderRadius: 999,
                fontSize: 11,
              }}>
                <strong>{r.name}</strong>
                <span className="mono" style={{ color: 'var(--fg-3)', marginLeft: 4 }}>
                  {r.sku}
                </span>
                <span style={{ color: 'var(--fg-3)', marginLeft: 4 }}>
                  · {fmtNum(r.balance, 0)} кг
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── What-if banner above matrix ─────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: 10, marginBottom: 0,
        background: whatIfKg > 0 ? 'rgba(232,117,26,0.08)' : 'var(--bg-soft)',
        // Используем longhand-свойства целиком: React ругается если
        // смешивать shorthand `border` с longhand `borderBottom: none`,
        // потому что при rerender'е порядок применения непредсказуем.
        borderTop: `1px solid ${whatIfKg > 0 ? 'var(--brand-orange)' : 'var(--border)'}`,
        borderLeft: `1px solid ${whatIfKg > 0 ? 'var(--brand-orange)' : 'var(--border)'}`,
        borderRight: `1px solid ${whatIfKg > 0 ? 'var(--brand-orange)' : 'var(--border)'}`,
        borderTopLeftRadius: 6, borderTopRightRadius: 6,
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
          textTransform: 'uppercase', letterSpacing: '.04em',
        }}>
          Калькулятор «Произвести»:
        </span>
        <input
          type="number"
          className="input mono"
          placeholder="напр. 5"
          value={whatIfTons}
          onChange={(e) => setWhatIfTons(e.target.value)}
          style={{ width: 100, fontSize: 13 }}
          min="0" step="0.1"
        />
        <span style={{ fontSize: 13 }}>тонн готового корма</span>
        {whatIfKg > 0 && (
          <>
            <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>=</span>
            <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
              {fmtNum(whatIfKg, 0)} кг
            </span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setWhatIfTons('')}
              style={{ marginLeft: 'auto' }}
            >
              Сбросить
            </button>
          </>
        )}
        {!whatIfKg && (
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--fg-3)' }}>
            Ячейки покажут «нужно кг», красные = на складе не хватает
          </span>
        )}
      </div>

      {/* ── Recipe matrix ─────────────────────────────────────────────── */}
      <Panel
        title={`Рецептурная матрица · ${matrixVersions.length} рецептов × ${matrixIngredients.length} ингредиентов`}
        flush
        style={{ marginBottom: 14 }}
      >
        <div style={{
          padding: '6px 12px', fontSize: 11, color: 'var(--fg-3)',
          borderBottom: '1px solid var(--border)',
        }}>
          💡 Клик — изменить долю %. Enter — сохранить. Esc — отмена. «+» = добавить ингредиент в рецепт.
        </div>
        {matrixVersions.length === 0 ? (
          <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
            Нет активных версий рецептур. Создайте через кнопку «Рецепт» выше или в{' '}
            <Link href="/feed" style={{ color: 'var(--brand-orange)' }}>
              /feed → Рецептуры
            </Link>.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%', borderCollapse: 'collapse', fontSize: 12,
              minWidth: 700,
            }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)' }}>
                  <th style={{
                    textAlign: 'left', padding: '8px 10px',
                    borderBottom: '1px solid var(--border)',
                    minWidth: 200, position: 'sticky', left: 0,
                    background: 'var(--bg-soft)', zIndex: 2,
                  }}>
                    Ингредиент
                  </th>
                  <th style={{
                    textAlign: 'right', padding: '8px 10px',
                    borderBottom: '1px solid var(--border)',
                    borderLeft: '1px solid var(--border)',
                    minWidth: 90, position: 'sticky', left: 200,
                    background: 'var(--bg-soft)', zIndex: 2,
                    fontSize: 11,
                  }}>
                    Остаток
                  </th>
                  {matrixVersions.map((v) => {
                    const sum = recipeSummary[v.id];
                    const totalOk = Math.abs((columnTotals[v.id] ?? 0) - 100) < 0.5;
                    return (
                      <th
                        key={v.id}
                        style={{
                          textAlign: 'right', padding: '8px 10px',
                          borderBottom: '1px solid var(--border)',
                          borderLeft: '1px solid var(--border)',
                          whiteSpace: 'nowrap',
                          fontSize: 11,
                          minWidth: 130,
                        }}
                        title={v.recipe_name}
                      >
                        <div className="mono" style={{ fontWeight: 600 }}>{v.recipe_code}</div>
                        <div style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
                          v{v.version}
                        </div>
                        {/* Yield */}
                        {sum?.yieldKg != null && totalOk && (
                          <div style={{
                            marginTop: 4, fontSize: 10, fontWeight: 500,
                            color: sum.yieldKg < 100 ? 'var(--danger)' : 'var(--success)',
                          }}>
                            ≈ {fmtNum(sum.yieldKg / 1000, 1)} т max
                          </div>
                        )}
                        {/* Cost */}
                        {financesVisible && sum?.costPerKg != null && (
                          <div style={{
                            marginTop: 2, fontSize: 10, color: 'var(--fg-2)',
                            fontWeight: 400,
                          }}>
                            {fmtMoney(sum.costPerKg)}/кг
                          </div>
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {matrixIngredients.map((ing) => {
                  const stock = stockBySku[ing.sku] ?? 0;
                  return (
                    <tr key={ing.sku} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{
                        padding: '6px 10px', position: 'sticky', left: 0,
                        background: 'var(--bg-card, #fff)',
                        fontSize: 12, zIndex: 1,
                      }}>
                        <span style={{ fontWeight: 500, color: 'var(--fg-1)' }}>
                          {ing.name}
                        </span>
                        <span className="mono" style={{
                          color: 'var(--fg-3)', marginLeft: 6, fontSize: 11,
                        }}>
                          {ing.sku}
                        </span>
                      </td>
                      <td className="mono" style={{
                        padding: '6px 10px', textAlign: 'right',
                        position: 'sticky', left: 200,
                        background: 'var(--bg-card, #fff)',
                        borderLeft: '1px solid var(--border)',
                        fontSize: 12, zIndex: 1,
                        color: stock > 0 ? 'var(--fg-1)' : 'var(--fg-3)',
                        fontWeight: stock > 0 ? 600 : 400,
                      }}>
                        {fmtNum(stock, 0)}
                      </td>
                      {matrixVersions.map((v) => {
                        const info = ing.shares[v.id];
                        const share = info?.share ?? null;
                        const isEditing = editingCell?.sku === ing.sku && editingCell?.vid === v.id;
                        const flashed = savedFlash === `${ing.sku}:${v.id}`;
                        const need = requiredKg(share);
                        const shortage = need !== null && need > stock;
                        return (
                          <td
                            key={v.id}
                            className="mono"
                            style={{
                              textAlign: 'right', padding: 0,
                              borderLeft: '1px solid var(--border)',
                              fontSize: 12,
                              background: flashed
                                ? 'rgba(34,197,94,0.12)'
                                : shortage
                                ? 'rgba(239,68,68,0.10)'
                                : undefined,
                              transition: 'background 1.5s',
                            }}
                            onClick={() => !isEditing && startEdit(ing.sku, v.id, share)}
                            title={
                              info
                                ? need !== null
                                  ? shortage
                                    ? `Нужно ${fmtNum(need, 0)} кг, на складе ${fmtNum(stock, 0)} кг — НЕ ХВАТАЕТ`
                                    : `Нужно ${fmtNum(need, 0)} кг (на складе ${fmtNum(stock, 0)} кг)`
                                  : 'Клик чтобы изменить долю %'
                                : 'Клик чтобы добавить ингредиент в этот рецепт'
                            }
                          >
                            {isEditing ? (
                              <input
                                autoFocus
                                type="number" step="0.01" min="0" max="100"
                                className="mono"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onBlur={saveEdit}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') saveEdit();
                                  else if (e.key === 'Escape') cancelEdit();
                                }}
                                disabled={saving}
                                style={{
                                  width: '100%', height: '100%', padding: '6px 10px',
                                  border: '2px solid var(--brand-orange)', borderRadius: 0,
                                  textAlign: 'right', fontSize: 12, fontWeight: 600,
                                  outline: 'none', background: 'rgba(232,117,26,0.06)',
                                }}
                              />
                            ) : (
                              <div style={{
                                padding: '6px 10px',
                                fontWeight: share ? 500 : 400,
                                color: share ? 'var(--fg-1)' : 'var(--fg-3)',
                                cursor: 'cell',
                              }}>
                                {share ? `${parseFloat(share).toFixed(2)}%` : '+'}
                                {need !== null && (
                                  <div style={{
                                    fontSize: 10, fontWeight: 600,
                                    color: shortage ? 'var(--danger)' : 'var(--fg-2)',
                                    marginTop: 2,
                                  }}>
                                    {fmtNum(need, 0)} кг {shortage && '⚠'}
                                  </div>
                                )}
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
                <tr style={{ background: 'var(--bg-soft)', fontWeight: 700 }}>
                  <td style={{
                    padding: '8px 10px', position: 'sticky', left: 0,
                    background: 'var(--bg-soft)', zIndex: 1,
                  }}>
                    Итого
                  </td>
                  <td style={{
                    padding: '8px 10px', position: 'sticky', left: 200,
                    background: 'var(--bg-soft)', zIndex: 1,
                    borderLeft: '1px solid var(--border)',
                  }} />
                  {matrixVersions.map((v) => {
                    const t = columnTotals[v.id] ?? 0;
                    const ok = Math.abs(t - 100) < 0.5;
                    return (
                      <td
                        key={v.id}
                        className="mono"
                        style={{
                          textAlign: 'right', padding: '8px 10px',
                          borderLeft: '1px solid var(--border)',
                          color: ok ? 'var(--success)' : 'var(--danger)',
                        }}
                      >
                        {t.toFixed(2)}%
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ── Day flow: Приход / Расход (2 колонки) ─────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 14, marginBottom: 14 }}>
        <Panel
          title={`Приход · ${data?.incoming.length ?? 0}`}
          flush
        >
          {isLoading ? (
            <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
          ) : (data?.incoming.length ?? 0) === 0 ? (
            <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
              За день поступлений не было.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 10px' }}>Док</th>
                  <th style={{ padding: '6px 10px' }}>SKU</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Кг</th>
                  <th style={{ padding: '6px 10px' }}>Поставщик</th>
                </tr>
              </thead>
              <tbody>
                {data?.incoming.map((row, i) => (
                  <tr key={`${row.doc}-${i}`} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '6px 10px' }}>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{row.doc}</span>
                      {row.kind === 'movement' && (
                        <Badge tone="warn" style={{ marginLeft: 4, fontSize: 9 }}>сирота</Badge>
                      )}
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <div style={{ fontWeight: 500 }}>{row.name}</div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{row.sku}</div>
                    </td>
                    <td className="mono" style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600 }}>
                      {fmtNum(row.qty, 1)}
                    </td>
                    <td style={{ padding: '6px 10px', fontSize: 11, color: 'var(--fg-2)' }}>
                      {row.supplier ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title={`Расход · ${data?.outgoing.length ?? 0}`} flush>
          {isLoading ? (
            <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
          ) : (data?.outgoing.length ?? 0) === 0 ? (
            <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
              За день расхода не было.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 10px' }}>Док</th>
                  <th style={{ padding: '6px 10px' }}>SKU</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Кг</th>
                  <th style={{ padding: '6px 10px' }}>Тип</th>
                </tr>
              </thead>
              <tbody>
                {data?.outgoing.map((row, i) => (
                  <tr key={`${row.doc}-${i}`} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '6px 10px' }}>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{row.doc}</span>
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <div style={{ fontWeight: 500 }}>{row.name}</div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{row.sku}</div>
                    </td>
                    <td className="mono" style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600 }}>
                      {fmtNum(row.qty, 1)}
                    </td>
                    <td style={{ padding: '6px 10px', fontSize: 11 }}>
                      <Badge tone={row.kind === 'write_off' ? 'warn' : 'neutral'}>
                        {row.kind === 'write_off' ? 'списание' : 'расход'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      {/* ── Production / Stock (2 колонки) ─────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 14 }}>
        <Panel title={`Произведено · ${data?.production.length ?? 0} партий`} flush>
          {isLoading ? (
            <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
          ) : (data?.production.length ?? 0) === 0 ? (
            <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
              За день замесов не было.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 10px' }}>Партия</th>
                  <th style={{ padding: '6px 10px' }}>Рецепт</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Замешано</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Остаток</th>
                  <th style={{ padding: '6px 10px' }}>Статус</th>
                </tr>
              </thead>
              <tbody>
                {data?.production.map((p) => (
                  <tr key={p.doc} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="mono" style={{ padding: '6px 10px', fontSize: 11, color: 'var(--fg-3)' }}>{p.doc}</td>
                    <td style={{ padding: '6px 10px' }}>
                      <div style={{ fontWeight: 500 }}>{p.recipe_name}</div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{p.recipe_code}</div>
                    </td>
                    <td className="mono" style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600 }}>
                      {fmtNum(p.qty_kg, 0)} кг
                    </td>
                    <td className="mono" style={{ padding: '6px 10px', textAlign: 'right' }}>
                      {fmtNum(p.current_kg, 0)} кг
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <Badge tone={p.status === 'approved' ? 'success' : 'warn'}>
                        {p.status === 'approved' ? 'одобрена' : p.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title={`Остатки сырья · ${data?.stock.length ?? 0} SKU`} flush>
          {isLoading ? (
            <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
          ) : (data?.stock.length ?? 0) === 0 ? (
            <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
              На складе пусто.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 10px' }}>SKU</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Σ Приход</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Σ Расход</th>
                  <th style={{ padding: '6px 10px', textAlign: 'right' }}>Остаток</th>
                  {financesVisible && (
                    <th style={{ padding: '6px 10px', textAlign: 'right' }}>≈ Цена/кг</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {data?.stock.map((s) => {
                  const bal = parseFloat(s.balance);
                  const price = priceBySku[s.sku];
                  return (
                    <tr key={s.sku} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '6px 10px' }}>
                        <span style={{ fontWeight: 500, color: 'var(--fg-1)' }}>
                          {s.name}
                        </span>
                        <span className="mono" style={{
                          marginLeft: 6, fontSize: 11, color: 'var(--fg-3)',
                        }}>
                          {s.sku}
                        </span>
                      </td>
                      <td className="mono" style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--success)' }}>
                        +{fmtNum(s.incoming_total, 0)}
                      </td>
                      <td className="mono" style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--danger)' }}>
                        −{fmtNum(s.outgoing_total, 0)}
                      </td>
                      <td className="mono" style={{
                        padding: '6px 10px', textAlign: 'right',
                        fontWeight: 700,
                        color: bal > 0 ? 'var(--fg-1)' : 'var(--fg-3)',
                      }}>
                        {fmtNum(s.balance, 0)} кг
                      </td>
                      {financesVisible && (
                        <td className="mono" style={{
                          padding: '6px 10px', textAlign: 'right',
                          fontSize: 11, color: 'var(--fg-2)',
                        }}>
                          {price !== undefined ? fmtMoney(price) : '—'}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div style={{ marginTop: 12, fontSize: 11, color: 'var(--fg-3)' }}>
        💡 «Сирота» в приходе — ручное движение в /stock без партии сырья.
        Превратите в партию через действие в /stock или из «+ Партия сырья» наверху.
      </div>

      {showAddIncoming && (
        <RawBatchModal
          onClose={() => {
            setShowAddIncoming(false);
            qc.invalidateQueries({ queryKey: ['feed', 'dashboard'] });
            qc.invalidateQueries({ queryKey: ['feed', 'raw-batches'] });
          }}
        />
      )}
      {showAddTask && (
        <TaskModal
          onClose={() => {
            setShowAddTask(false);
            qc.invalidateQueries({ queryKey: ['feed', 'dashboard'] });
          }}
        />
      )}
      {showAddRecipe && (
        <RecipeModal
          onClose={() => {
            setShowAddRecipe(false);
            qc.invalidateQueries({ queryKey: ['feed', 'dashboard'] });
            qc.invalidateQueries({ queryKey: ['feed', 'recipes'] });
          }}
        />
      )}
      {showAddVersion && (
        <VersionModal
          recipe={showAddVersion}
          onClose={() => {
            setShowAddVersion(null);
            qc.invalidateQueries({ queryKey: ['feed', 'dashboard'] });
          }}
        />
      )}
    </>
  );
}
