'use client';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import Icon from '@/components/ui/Icon';
import { shrinkageProfilesCrud, shrinkageStatesCrud } from '@/hooks/useFeed';
import { useHasLevel } from '@/hooks/usePermissions';
import type { FeedLotShrinkageState, FeedShrinkageProfile } from '@/types/auth';


interface Props {
  profile: FeedShrinkageProfile;
  onClose: () => void;
  onEdit: (p: FeedShrinkageProfile) => void;
  onSelectState: (s: FeedLotShrinkageState) => void;
}

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

/**
 * Drawer с детальной информацией о профиле усушки и списком всех партий,
 * которые сейчас под этим профилем (active + frozen). Клик по партии
 * открывает StateDetailDrawer с историей движений.
 */
export default function ProfileDetailDrawer({
  profile, onClose, onEdit, onSelectState,
}: Props) {
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('feed', 'rw');

  const del = shrinkageProfilesCrud.useDelete();
  const update = shrinkageProfilesCrud.useUpdate();

  // Все state'ы с этим profile_id
  const { data: states, isLoading: statesLoading } = shrinkageStatesCrud.useList({
    profile: profile.id,
  });

  const handleToggleActive = async () => {
    if (profile.is_active) {
      if (!confirm(
        `Деактивировать профиль для «${targetLabel(profile)}»?\n\n` +
        `Существующие state-записи останутся, но новые партии не попадут под этот профиль.`,
      )) return;
      await del.mutateAsync(profile.id);
    } else {
      await update.mutateAsync({ id: profile.id, patch: { is_active: true } });
    }
  };

  const active = (states ?? []).filter((s) => !s.is_frozen);
  const frozen = (states ?? []).filter((s) => s.is_frozen);
  const isAuto = profile.note?.toLowerCase().includes('автоматически');

  return (
    <DetailDrawer
      title={`Профиль · ${targetLabel(profile)}`}
      subtitle={
        profile.target_type === 'ingredient' ? 'Сырьё' : 'Готовый корм'
      }
      onClose={onClose}
      actions={
        canEdit ? (
          <>
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleToggleActive}
              disabled={del.isPending || update.isPending}
              style={profile.is_active ? { color: 'var(--danger)' } : undefined}
            >
              {profile.is_active ? 'Деактивировать' : 'Активировать'}
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onEdit(profile)}
            >
              <Icon name="edit" size={12} /> Редактировать
            </button>
          </>
        ) : null
      }
    >
      {/* Параметры профиля */}
      <div style={{
        fontSize: 11, color: 'var(--fg-3)',
        letterSpacing: '.04em', textTransform: 'uppercase',
        fontWeight: 700, marginBottom: 10,
      }}>
        Параметры
      </div>
      <KV
        items={[
          {
            k: 'Тип', v: (
              <Badge tone={profile.target_type === 'ingredient' ? 'info' : 'warn'}>
                {profile.target_type === 'ingredient' ? 'сырьё' : 'готовый корм'}
              </Badge>
            ),
          },
          {
            k: profile.target_type === 'ingredient' ? 'Ингредиент' : 'Рецепт',
            v: targetLabel(profile),
            mono: true,
          },
          { k: 'Склад', v: profile.warehouse_code ?? 'все', mono: true },
          { k: '% / период', v: `${fmtPct(profile.percent_per_period)} / ${profile.period_days} дн`, mono: true },
          { k: 'Максимум всего', v: fmtPct(profile.max_total_percent), mono: true },
          { k: 'Грейс-период', v: `${profile.starts_after_days} дн`, mono: true },
          { k: 'Стоп через', v: profile.stop_after_days != null ? `${profile.stop_after_days} дн` : '∞', mono: true },
          {
            k: 'Статус', v: profile.is_active
              ? <Badge tone="success">активен</Badge>
              : <Badge tone="neutral">выключен</Badge>,
          },
          { k: 'Создан', v: new Date(profile.created_at).toLocaleString('ru'), mono: true },
          { k: 'Обновлён', v: new Date(profile.updated_at).toLocaleString('ru'), mono: true },
        ]}
      />

      {profile.note && (
        <div style={{
          padding: 10, marginBottom: 16, fontSize: 12, lineHeight: 1.5,
          background: isAuto ? 'var(--brand-orange-soft)' : 'var(--bg-soft)',
          borderRadius: 6, color: isAuto ? 'var(--fg-1)' : 'var(--fg-2)',
        }}>
          {isAuto && '✨ '}
          {profile.note}
        </div>
      )}

      {/* Партии под профилем */}
      <div style={{
        fontSize: 11, color: 'var(--fg-3)',
        letterSpacing: '.04em', textTransform: 'uppercase',
        fontWeight: 700, marginTop: 20, marginBottom: 10,
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>Партии под этим профилем</span>
        <span>{(states ?? []).length}</span>
      </div>

      {statesLoading ? (
        <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 12 }}>Загрузка…</div>
      ) : (states ?? []).length === 0 ? (
        <EmptyState
          title="Нет партий"
          description="Партия попадёт сюда после первого срабатывания воркера, если она подходит под этот профиль."
        />
      ) : (
        <>
          {active.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{
                fontSize: 11, color: 'var(--success)', fontWeight: 600,
                marginBottom: 6, letterSpacing: '.04em', textTransform: 'uppercase',
              }}>
                Активные ({active.length})
              </div>
              <DataTable<FeedLotShrinkageState>
                rows={active}
                rowKey={(s) => s.id}
                onRowClick={(s) => onSelectState(s)}
                columns={[
                  {
                    key: 'lot_type', label: 'Тип',
                    render: (s) => s.lot_type === 'raw_arrival' ? 'сырьё' : 'корм',
                  },
                  { key: 'initial', label: 'Начальная', mono: true, align: 'right',
                    render: (s) => s.initial_quantity },
                  { key: 'lost', label: 'Списано', mono: true, align: 'right',
                    render: (s) => s.accumulated_loss },
                  { key: 'pct', label: '%', mono: true, align: 'right',
                    render: (s) => s.accumulated_percent ?? '—' },
                  { key: 'last', label: 'Посл. цикл', muted: true,
                    render: (s) => s.last_applied_on ?? '—' },
                ]}
              />
            </div>
          )}
          {frozen.length > 0 && (
            <div>
              <div style={{
                fontSize: 11, color: 'var(--fg-3)', fontWeight: 600,
                marginBottom: 6, letterSpacing: '.04em', textTransform: 'uppercase',
              }}>
                Заморожены ({frozen.length})
              </div>
              <DataTable<FeedLotShrinkageState>
                rows={frozen}
                rowKey={(s) => s.id}
                onRowClick={(s) => onSelectState(s)}
                columns={[
                  {
                    key: 'lot_type', label: 'Тип',
                    render: (s) => s.lot_type === 'raw_arrival' ? 'сырьё' : 'корм',
                  },
                  { key: 'initial', label: 'Начальная', mono: true, align: 'right',
                    render: (s) => s.initial_quantity },
                  { key: 'lost', label: 'Списано', mono: true, align: 'right',
                    render: (s) => s.accumulated_loss },
                  { key: 'pct', label: '%', mono: true, align: 'right',
                    render: (s) => s.accumulated_percent ?? '—' },
                  { key: 'last', label: 'Заморожена', muted: true,
                    render: (s) => s.last_applied_on ?? '—' },
                ]}
              />
            </div>
          )}
        </>
      )}
    </DetailDrawer>
  );
}
