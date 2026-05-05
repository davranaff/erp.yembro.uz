'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import { recipeComponentsCrud, useFeedDashboard } from '@/hooks/useFeed';
import RawBatchModal from '../RawBatchModal';

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

function fmtMoney(v: string): string {
  const n = parseFloat(v || '0');
  if (!n) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

/**
 * Excel-style сводка дня по модулю «Корма».
 *
 * Идея: один экран, где видно ВСЁ за день:
 *   - Рецептурная матрица (рецепты × ингредиенты × %)
 *   - Приход / Расход / Произведено за день
 *   - Текущие остатки сырья
 *
 * Целевой пользователь — оператор из Excel-эпохи: не любит навигировать
 * между вкладками, хочет видеть всё на одной странице.
 */
export default function FeedDashboardPage() {
  const qc = useQueryClient();
  const [date, setDate] = useState(todayISO());
  const { data, isLoading, error, refetch, isFetching } = useFeedDashboard(date);

  const matrix = data?.recipe_matrix;
  const matrixVersions = matrix?.versions ?? [];
  const matrixIngredients = matrix?.ingredients ?? [];

  // Inline-edit состояние для ячеек матрицы
  const [editingCell, setEditingCell] = useState<{ sku: string; vid: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState<string | null>(null); // key=sku:vid
  const updateComp = recipeComponentsCrud.useUpdate();
  const createComp = recipeComponentsCrud.useCreate();

  // Quick-add Приход
  const [showAddIncoming, setShowAddIncoming] = useState(false);

  // Считаем «итого» по столбцу (для проверки что доли = 100%)
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

    // Без изменений — выходим
    if (trimmed === (oldShare ?? '')) { cancelEdit(); return; }

    // Пустое значение + был компонент → не разрешаем (нужен delete-action)
    if (trimmed === '' && existing) {
      alert('Чтобы убрать ингредиент из рецепта, удалите компонент в /feed → Рецептуры (он может быть привязан к незавершённым замесам).');
      cancelEdit();
      return;
    }
    // Пустое + не было — просто закрыть
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
      // Обновляем dashboard
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

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Сводка дня</h1>
          <div className="sub">
            Корма · приход / расход / производство · текущие остатки на одном экране
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
          💡 Кликните в любую ячейку чтобы изменить долю %. Enter — сохранить, Esc — отмена. «+» = добавить ингредиент в рецепт.
        </div>
        {matrixVersions.length === 0 ? (
          <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 13 }}>
            Нет активных версий рецептур. Создайте в{' '}
            <Link href="/feed" style={{ color: 'var(--brand-orange)' }}>
              /feed → Рецептуры
            </Link>.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%', borderCollapse: 'collapse', fontSize: 12,
              minWidth: 600,
            }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)' }}>
                  <th style={{
                    textAlign: 'left', padding: '8px 10px',
                    borderBottom: '1px solid var(--border)',
                    minWidth: 200, position: 'sticky', left: 0,
                    background: 'var(--bg-soft)',
                  }}>
                    Ингредиент
                  </th>
                  {matrixVersions.map((v) => (
                    <th
                      key={v.id}
                      style={{
                        textAlign: 'right', padding: '8px 10px',
                        borderBottom: '1px solid var(--border)',
                        borderLeft: '1px solid var(--border)',
                        whiteSpace: 'nowrap',
                        fontSize: 11,
                      }}
                      title={v.recipe_name}
                    >
                      <div className="mono" style={{ fontWeight: 600 }}>{v.recipe_code}</div>
                      <div style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
                        v{v.version}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixIngredients.map((ing) => (
                  <tr key={ing.sku} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{
                      padding: '6px 10px', position: 'sticky', left: 0,
                      background: 'var(--bg-card, #fff)',
                      fontSize: 12,
                    }}>
                      <span className="mono" style={{ fontWeight: 500 }}>{ing.sku}</span>
                      <span style={{ color: 'var(--fg-3)', marginLeft: 6, fontSize: 11 }}>
                        {ing.name}
                      </span>
                    </td>
                    {matrixVersions.map((v) => {
                      const info = ing.shares[v.id];
                      const share = info?.share ?? null;
                      const isEditing = editingCell?.sku === ing.sku && editingCell?.vid === v.id;
                      const flashed = savedFlash === `${ing.sku}:${v.id}`;
                      return (
                        <td
                          key={v.id}
                          className="mono"
                          style={{
                            textAlign: 'right', padding: 0,
                            borderLeft: '1px solid var(--border)',
                            fontSize: 12,
                            background: flashed ? 'rgba(34,197,94,0.12)' : undefined,
                            transition: 'background 1.5s',
                          }}
                          onClick={() => !isEditing && startEdit(ing.sku, v.id, share)}
                          title={info ? 'Клик чтобы изменить долю %' : 'Клик чтобы добавить ингредиент в этот рецепт'}
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
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr style={{ background: 'var(--bg-soft)', fontWeight: 700 }}>
                  <td style={{ padding: '8px 10px', position: 'sticky', left: 0, background: 'var(--bg-soft)' }}>
                    Итого
                  </td>
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
          tools={
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setShowAddIncoming(true)}
            >
              <Icon name="plus" size={12} /> Партия сырья
            </button>
          }
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
                      <div className="mono" style={{ fontWeight: 500 }}>{row.sku}</div>
                      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{row.name}</div>
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
                      <div className="mono" style={{ fontWeight: 500 }}>{row.sku}</div>
                      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{row.name}</div>
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
                      <div className="mono" style={{ fontWeight: 500 }}>{p.recipe_code}</div>
                      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{p.recipe_name}</div>
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
                </tr>
              </thead>
              <tbody>
                {data?.stock.map((s) => {
                  const bal = parseFloat(s.balance);
                  return (
                    <tr key={s.sku} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '6px 10px' }}>
                        <span className="mono" style={{ fontWeight: 500 }}>{s.sku}</span>
                        <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--fg-3)' }}>
                          {s.name}
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
        Превратите в партию через действие в /stock или из /feed → «+ Партия сырья».
      </div>

      {showAddIncoming && (
        <RawBatchModal
          onClose={() => {
            setShowAddIncoming(false);
            qc.invalidateQueries({ queryKey: ['feed', 'dashboard'] });
          }}
        />
      )}
    </>
  );
}
