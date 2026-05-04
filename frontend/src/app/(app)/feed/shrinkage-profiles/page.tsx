'use client';

import Link from 'next/link';
import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import {
  shrinkageProfilesCrud,
  shrinkageStatesCrud,
  useApplyShrinkage,
} from '@/hooks/useFeed';
import { useHasLevel } from '@/hooks/usePermissions';
import type { FeedLotShrinkageState, FeedShrinkageProfile } from '@/types/auth';

import ProfileDetailDrawer from './ProfileDetailDrawer';
import ProfileModal from './ProfileModal';
import StateDetailDrawer from './StateDetailDrawer';

function fmtPct(v: string | null | undefined): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toFixed(3).replace(/\.?0+$/, '') + ' %';
}

function targetLabel(p: FeedShrinkageProfile): string {
  if (p.target_type === 'ingredient') {
    return p.nomenclature_sku
      ? `${p.nomenclature_sku} · ${p.nomenclature_name ?? ''}`
      : '— ингредиент —';
  }
  return p.recipe_code
    ? `${p.recipe_code} · ${p.recipe_name ?? ''}`
    : '— рецепт —';
}

export default function ShrinkageProfilesPage() {
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('feed', 'rw');
  const canAdmin = hasLevel('feed', 'admin');

  const { data: profiles, isLoading } = shrinkageProfilesCrud.useList();
  const { data: states } = shrinkageStatesCrud.useList();
  const del = shrinkageProfilesCrud.useDelete();
  const apply = useApplyShrinkage();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<FeedShrinkageProfile | null>(null);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);
  const [selProfile, setSelProfile] = useState<FeedShrinkageProfile | null>(null);
  const [selState, setSelState] = useState<FeedLotShrinkageState | null>(null);

  const openCreate = () => { setEditing(null); setModalOpen(true); };
  const openEdit = (p: FeedShrinkageProfile) => {
    setSelProfile(null);
    setEditing(p);
    setModalOpen(true);
  };

  const handleDeactivate = async (p: FeedShrinkageProfile) => {
    if (!confirm(`Деактивировать профиль для «${targetLabel(p)}»?\n\n` +
      `Существующие state-записи останутся, но новые партии не попадут под этот профиль.`)) return;
    await del.mutateAsync(p.id);
  };

  const handleApplyAll = async () => {
    setApplyMsg(null);
    if (!confirm('Прогнать алгоритм усушки сейчас по всем активным партиям организации?')) return;
    try {
      const res = await apply.mutateAsync(undefined);
      const summary = res as { lots_total?: number; lots_applied?: number; loss_kg?: string };
      setApplyMsg(
        `Готово: ${summary.lots_applied ?? 0} из ${summary.lots_total ?? 0} партий, ` +
        `списано ${summary.loss_kg ?? '0'} кг.`,
      );
    } catch {
      setApplyMsg('Ошибка прогона. Подробности — в логах сервера.');
    }
  };

  const activeStates = (states ?? []).filter((s) => !s.is_frozen);
  const frozenStates = (states ?? []).filter((s) => s.is_frozen);

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Link href="/feed" style={{ color: 'var(--fg-3)', fontSize: 13, textDecoration: 'none' }}>
              ← Корма
            </Link>
          </div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, letterSpacing: '-0.02em' }}>
            Профили усушки
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 13 }}>
            Правила периодического списания усушки: «N% каждые M дней до K%». Воркер прогоняет ежедневно в 02:00.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {canAdmin && (
            <button
              className="btn"
              onClick={handleApplyAll}
              disabled={apply.isPending}
              title="Прогнать алгоритм по всем партиям сейчас"
            >
              {apply.isPending ? 'Прогон…' : 'Прогнать сейчас'}
            </button>
          )}
          {canEdit && (
            <button className="btn btn-primary" onClick={openCreate}>
              <Icon name="plus" size={14} /> Новый профиль
            </button>
          )}
        </div>
      </div>

      {applyMsg && (
        <div style={{
          marginBottom: 14, padding: '10px 14px', borderRadius: 8,
          background: 'var(--bg-subtle)', border: '1px solid var(--border)', fontSize: 13,
        }}>
          {applyMsg}
        </div>
      )}

      {/* Profiles */}
      <Panel title="Профили">
        {isLoading ? (
          <div style={{ padding: 24, color: 'var(--fg-3)', fontSize: 13 }}>Загрузка…</div>
        ) : !profiles || profiles.length === 0 ? (
          <EmptyState
            title="Нет профилей"
            description="Создайте первый профиль усушки — после этого партии этого ингредиента или рецепта начнут автоматически усыхать раз в сутки."
          />
        ) : (
          <DataTable<FeedShrinkageProfile>
            rows={profiles}
            rowKey={(p) => p.id}
            onRowClick={(p) => setSelProfile(p)}
            rowProps={(p) => ({ active: selProfile?.id === p.id })}
            columns={[
              {
                key: 'target',
                label: 'Что усыхает',
                render: (p) => (
                  <span>
                    <Badge tone={p.target_type === 'ingredient' ? 'info' : 'warn'}>
                      {p.target_type === 'ingredient' ? 'сырьё' : 'корм'}
                    </Badge>{' '}
                    {targetLabel(p)}
                  </span>
                ),
              },
              {
                key: 'warehouse',
                label: 'Склад',
                render: (p) => p.warehouse_code ?? <span style={{ color: 'var(--fg-3)' }}>все</span>,
              },
              {
                key: 'rate',
                label: '% / период',
                mono: true,
                render: (p) => `${fmtPct(p.percent_per_period)} / ${p.period_days} дн`,
              },
              {
                key: 'max',
                label: 'Максимум',
                mono: true,
                render: (p) => fmtPct(p.max_total_percent),
              },
              {
                key: 'grace',
                label: 'Грейс / стоп',
                mono: true,
                render: (p) => `${p.starts_after_days} / ${p.stop_after_days ?? '∞'}`,
              },
              {
                key: 'active',
                label: 'Статус',
                render: (p) =>
                  p.is_active
                    ? <Badge tone="success">активен</Badge>
                    : <Badge tone="neutral">выкл</Badge>,
              },
              {
                key: 'actions',
                label: '',
                width: '60px',
                render: (p) => canEdit ? (
                  <RowActions
                    actions={[
                      { label: 'Редактировать', onClick: () => openEdit(p), icon: <Icon name="edit" size={14} /> },
                      ...(p.is_active ? [{
                        label: 'Деактивировать',
                        onClick: () => handleDeactivate(p),
                        icon: <Icon name="close" size={14} />,
                        danger: true,
                      }] : []),
                    ]}
                  />
                ) : null,
              },
            ]}
          />
        )}
      </Panel>

      {/* Active states */}
      <div style={{ marginTop: 20 }}>
        <Panel title={`Партии под усушкой (${activeStates.length})`}>
          {activeStates.length === 0 ? (
            <EmptyState
              title="Нет активных партий"
              description="Партия попадает в этот список после первого срабатывания воркера."
            />
          ) : (
            <DataTable<FeedLotShrinkageState>
              rows={activeStates}
              rowKey={(s) => s.id}
              onRowClick={(s) => setSelState(s)}
              rowProps={(s) => ({ active: selState?.id === s.id })}
              columns={[
                { key: 'lot_type', label: 'Тип', render: (s) => s.lot_type === 'raw_arrival' ? 'сырьё' : 'корм' },
                { key: 'profile', label: 'Профиль', render: (s) => s.profile_label },
                { key: 'initial', label: 'Начальная, кг', mono: true, render: (s) => s.initial_quantity },
                { key: 'lost', label: 'Списано, кг', mono: true, render: (s) => s.accumulated_loss },
                { key: 'pct', label: 'Списано %', mono: true, render: (s) => s.accumulated_percent ?? '—' },
                { key: 'last', label: 'Последний цикл', muted: true, render: (s) => s.last_applied_on ?? '—' },
              ]}
            />
          )}
        </Panel>
      </div>

      {frozenStates.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Panel title={`Замороженные (${frozenStates.length})`}>
            <DataTable<FeedLotShrinkageState>
              rows={frozenStates}
              rowKey={(s) => s.id}
              onRowClick={(s) => setSelState(s)}
              rowProps={(s) => ({ active: selState?.id === s.id })}
              columns={[
                { key: 'lot_type', label: 'Тип', render: (s) => s.lot_type === 'raw_arrival' ? 'сырьё' : 'корм' },
                { key: 'profile', label: 'Профиль', render: (s) => s.profile_label },
                { key: 'initial', label: 'Начальная, кг', mono: true, render: (s) => s.initial_quantity },
                { key: 'lost', label: 'Списано, кг', mono: true, render: (s) => s.accumulated_loss },
                { key: 'pct', label: 'Списано %', mono: true, render: (s) => s.accumulated_percent ?? '—' },
                { key: 'last', label: 'Заморожена', muted: true, render: (s) => s.last_applied_on ?? '—' },
              ]}
            />
          </Panel>
        </div>
      )}

      {modalOpen && (
        <ProfileModal initial={editing} onClose={() => setModalOpen(false)} />
      )}

      {selProfile && (
        <ProfileDetailDrawer
          profile={selProfile}
          onClose={() => setSelProfile(null)}
          onEdit={openEdit}
          onSelectState={(s) => {
            setSelProfile(null);
            setSelState(s);
          }}
        />
      )}

      {selState && (
        <StateDetailDrawer
          state={selState}
          onClose={() => setSelState(null)}
        />
      )}
    </div>
  );
}
