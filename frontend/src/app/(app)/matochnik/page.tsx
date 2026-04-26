'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import OpexButton from '@/components/OpexButton';
import { OpenSaleFromModule } from '@/components/SellBatchButton';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import { useProductionBlocks } from '@/hooks/useBlocks';
import Sparkline from '@/components/ui/Sparkline';
import { dailyEggCrud, herdsCrud, herdMortalityCrud, useHerdStats } from '@/hooks/useMatochnik';
import { useHasLevel } from '@/hooks/usePermissions';
import type { BreedingHerd, DailyEggProduction } from '@/types/auth';

import CrystallizeModal from './CrystallizeModal';
import DepopulateModal from './DepopulateModal';
import EggBatchesPanel from './EggBatchesPanel';
import EggProductionModal from './EggProductionModal';
import FeedConsumptionPanel from './FeedConsumptionPanel';
import HerdModal from './HerdModal';
import HerdTimelineModal from './HerdTimelineModal';
import MortalityModal from './MortalityModal';
import MoveHerdModal from './MoveHerdModal';

const DIRECTION_LABEL: Record<string, string> = {
  broiler_parent: 'Бройлерное',
  layer_parent: 'Яичное',
};

const STATUS_LABEL: Record<string, string> = {
  growing: 'Разгон',
  producing: 'Продуктив',
  depopulated: 'Снято',
};

const STATUS_TONE: Record<string, 'success' | 'info' | 'neutral'> = {
  growing: 'info',
  producing: 'success',
  depopulated: 'neutral',
};

export default function MatochnikPage() {
  const [status, setStatus] = useState('');
  const [direction, setDirection] = useState('');
  const [blockFilter, setBlockFilter] = useState('');
  const [sel, setSel] = useState<BreedingHerd | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<BreedingHerd | null>(null);
  const [crystallizeFor, setCrystallizeFor] = useState<BreedingHerd | null>(null);
  const [depopulateFor, setDepopulateFor] = useState<BreedingHerd | null>(null);
  const [eggModalFor, setEggModalFor] = useState<BreedingHerd | null>(null);
  const [mortalityModalFor, setMortalityModalFor] = useState<BreedingHerd | null>(null);
  const [moveModalFor, setMoveModalFor] = useState<BreedingHerd | null>(null);
  const [timelineFor, setTimelineFor] = useState<BreedingHerd | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('matochnik', 'rw');

  const filter = useMemo(
    () => ({
      status: status || undefined,
      direction: direction || undefined,
      block: blockFilter || undefined,
    }),
    [status, direction, blockFilter],
  );

  const { data: herds, isLoading, error, refetch, isFetching } = herdsCrud.useList(filter);
  const { data: blocks } = useProductionBlocks({ kind: 'matochnik' });
  const del = herdsCrud.useDelete();

  const { data: eggRecords } = dailyEggCrud.useList(
    sel ? { herd: sel.id } : {},
  );
  const { data: mortalityRecords } = herdMortalityCrud.useList(
    sel ? { herd: sel.id } : {},
  );
  const { data: stats } = useHerdStats(sel?.id, 30);

  const totals = useMemo(() => {
    if (!herds) return { herds: 0, heads: 0 };
    return {
      herds: herds.length,
      heads: herds.reduce((a, h) => a + (h.current_heads || 0), 0),
    };
  }, [herds]);

  const todayEggs = useMemo(() => {
    if (!eggRecords || !sel) return 0;
    const today = new Date().toISOString().slice(0, 10);
    const rec = eggRecords.find((e) => e.date === today);
    return rec ? rec.eggs_collected - rec.unfit_eggs : 0;
  }, [eggRecords, sel]);

  const handleDelete = (h: BreedingHerd) => {
    if (!confirm(`Удалить стадо ${h.doc_number}?`)) return;
    del.mutate(h.id, {
      onSuccess: () => {
        if (sel?.id === h.id) setSel(null);
      },
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Маточник</h1>
          <div className="sub">Родительское стадо · яйцесбор · вакцинации</div>
        </div>
        <div className="actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <Icon name="chart" size={14} />
            {isFetching ? '…' : 'Обновить'}
          </button>
          {canEdit && (
            <>
              <OpexButton moduleCode="matochnik" suggestedContraCode="20.01" />
              <OpenSaleFromModule moduleCode="matochnik" />
              <button
                className="btn btn-primary btn-sm"
                onClick={() => { setEditing(null); setCreateOpen(true); }}
              >
                <Icon name="plus" size={14} /> Новое стадо
              </button>
            </>
          )}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard
          tone="orange"
          iconName="egg"
          label="Стад"
          sub="активных"
          value={String(totals.herds)}
          meta="всего"
        />
        <KpiCard
          tone="blue"
          iconName="users"
          label="Поголовье"
          sub="сумма current_heads"
          value={totals.heads.toLocaleString('ru-RU')}
          meta="гол"
        />
        <KpiCard
          tone="green"
          iconName="chart"
          label="Яиц сегодня"
          sub={sel ? sel.doc_number : 'выберите стадо'}
          value={todayEggs.toLocaleString('ru-RU')}
          meta="шт (чистые)"
        />
        <KpiCard
          tone="red"
          iconName="close"
          label="Падежей"
          sub={sel ? sel.doc_number : '—'}
          value={mortalityRecords?.length?.toString() ?? '—'}
          meta="записей"
        />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Seg
          options={[
            { value: '', label: 'Все' },
            { value: 'growing', label: 'Разгон' },
            { value: 'producing', label: 'Продуктив' },
            { value: 'depopulated', label: 'Снятые' },
          ]}
          value={status}
          onChange={setStatus}
        />
        <select
          className="input"
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
          style={{ width: 200 }}
        >
          <option value="">Все направления</option>
          <option value="broiler_parent">Бройлерное</option>
          <option value="layer_parent">Яичное</option>
        </select>
        <select
          className="input"
          value={blockFilter}
          onChange={(e) => setBlockFilter(e.target.value)}
          style={{ width: 200 }}
        >
          <option value="">Все корпуса</option>
          {blocks?.map((b) => (
            <option key={b.id} value={b.id}>{b.code} · {b.name}</option>
          ))}
        </select>
      </div>

      <Panel flush>
        <DataTable<BreedingHerd>
          isLoading={isLoading}
          rows={herds}
          rowKey={(h) => h.id}
          error={error}
          emptyMessage={
            <>
              Нет стад.{' '}
              <button className="btn btn-ghost btn-sm" onClick={() => setCreateOpen(true)}>
                Добавить первое
              </button>
            </>
          }
          onRowClick={(h) => setSel(h)}
          rowProps={(h) => ({ active: sel?.id === h.id })}
          columns={[
            { key: 'doc', label: 'Номер',
              render: (h) => <span className="badge id">{h.doc_number}</span> },
            { key: 'dir', label: 'Направление', cellStyle: { fontSize: 12 },
              render: (h) => DIRECTION_LABEL[h.direction] ?? h.direction },
            { key: 'block', label: 'Корпус', mono: true, cellStyle: { fontSize: 12 },
              render: (h) => h.block_code ?? '—' },
            { key: 'age', label: 'Возраст, нед', align: 'right', mono: true,
              render: (h) => h.current_age_weeks ?? h.age_weeks_at_placement },
            { key: 'heads', label: 'Поголовье', align: 'right', mono: true,
              render: (h) => (
                <>
                  {h.current_heads.toLocaleString('ru-RU')}
                  <span style={{ color: 'var(--fg-3)', fontSize: 11, marginLeft: 4 }}>
                    / {h.initial_heads.toLocaleString('ru-RU')}
                  </span>
                </>
              ) },
            { key: 'placed', label: 'Посажено', mono: true, cellStyle: { fontSize: 12 },
              render: (h) => h.placed_at },
            { key: 'status', label: 'Статус',
              render: (h) => (
                <Badge tone={STATUS_TONE[h.status]} dot>
                  {STATUS_LABEL[h.status] ?? h.status}
                </Badge>
              ) },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (h) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'Редактировать',
                      onClick: () => { setEditing(h); setCreateOpen(true); },
                    },
                    { label: 'Удалить', danger: true, onClick: () => handleDelete(h) },
                  ]}
                />
              ) : null },
          ]}
        />
      </Panel>

      {sel && (
        <DetailDrawer
          title={`Стадо · ${sel.doc_number}`}
          subtitle={`${DIRECTION_LABEL[sel.direction]} · ${sel.block_code ?? '—'} · ${STATUS_LABEL[sel.status]}`}
          onClose={() => setSel(null)}
          actions={
            <>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setTimelineFor(sel)}
                title="Вся история: яйцесбор, падёж, корма, лечения"
              >
                <Icon name="chart" size={12} /> История
              </button>
              {canEdit && (
                <>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setCrystallizeFor(sel)}
                    disabled={sel.status === 'depopulated'}
                  >
                    <Icon name="egg" size={12} /> Сформировать партию
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setMoveModalFor(sel)}
                    disabled={sel.status === 'depopulated'}
                    title={sel.status === 'depopulated' ? 'Стадо снято' : 'Перевести в другой корпус'}
                  >
                    <Icon name="chart" size={12} /> Перевести
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setDepopulateFor(sel)}
                  >
                    Снятие
                  </button>
                </>
              )}
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => window.open(`/matochnik/${sel.id}/print/placement`, '_blank')}
                title="Акт посадки (печать)"
              >
                <Icon name="download" size={12} /> Акт посадки
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => window.open(`/matochnik/${sel.id}/print/depopulation`, '_blank')}
                title="Акт снятия (печать)"
              >
                <Icon name="download" size={12} /> Акт снятия
              </button>
            </>
          }
        >
          {stats?.active_withdrawal_until && (
            <div
              style={{
                padding: '10px 12px',
                background: '#fffbeb',
                border: '1px solid var(--warning, #F59E0B)',
                borderRadius: 6,
                marginBottom: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 13,
              }}
            >
              <span style={{ fontSize: 18 }}>⚠</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: '#92400E' }}>
                  Стадо в каренции до {new Date(stats.active_withdrawal_until).toLocaleDateString('ru-RU')}
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>
                  Яйца и продукция не должны использоваться до окончания периода ожидания.
                </div>
              </div>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setTimelineFor(sel)}
                style={{ color: '#92400E' }}
              >
                Подробнее
              </button>
            </div>
          )}

          <KV
            items={[
              { k: 'Номер', v: sel.doc_number, mono: true },
              { k: 'Направление', v: DIRECTION_LABEL[sel.direction] },
              { k: 'Корпус', v: sel.block_code ?? '—', mono: true },
              { k: 'Посажено', v: sel.placed_at, mono: true },
              { k: 'Возраст при посадке', v: `${sel.age_weeks_at_placement} нед` },
              { k: 'Текущий возраст', v: sel.current_age_weeks != null ? `${sel.current_age_weeks} нед` : '—' },
              { k: 'Поголовье нач.', v: sel.initial_heads.toLocaleString('ru-RU'), mono: true },
              { k: 'Поголовье тек.', v: sel.current_heads.toLocaleString('ru-RU'), mono: true },
              { k: 'Статус', v: <Badge tone={STATUS_TONE[sel.status]}>{STATUS_LABEL[sel.status]}</Badge> },
            ]}
          />

          {stats && (
            <Panel title="Метрики за 30 дней" style={{ marginTop: 12 }}>
              <div className="grid-4" style={{ marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Яйценоскость, средняя</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>
                    {parseFloat(stats.productivity_avg_pct).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                    сегодня {parseFloat(stats.productivity_today_pct).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Чистых яиц за период</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>
                    {stats.eggs_total_clean.toLocaleString('ru-RU')}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>шт</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Корма</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>
                    {parseFloat(stats.feed_total_kg).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} кг
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                    {parseFloat(stats.feed_cost_total_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} сум
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>FCR (кг корма / кг яйца)</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600, color: stats.fcr ? undefined : 'var(--fg-3)' }}>
                    {stats.fcr ?? '—'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                    вес яйца {stats.egg_weight_g} г
                  </div>
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 4 }}>
                  Яйцесбор · {stats.from} → {stats.to}
                </div>
                <Sparkline
                  values={stats.series.map((p) => p.eggs_clean)}
                  width={560}
                  height={48}
                  label="Динамика яйцесбора"
                />
              </div>
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 4 }}>
                  Падёж
                </div>
                <Sparkline
                  values={stats.series.map((p) => p.mortality)}
                  width={560}
                  height={36}
                  stroke="var(--danger)"
                  fill="rgba(239, 68, 68, 0.12)"
                  label="Динамика падежа"
                />
              </div>
            </Panel>
          )}

          <Panel
            title={`Яйцесбор · последние ${eggRecords?.length ?? 0} записей`}
            flush
            tools={
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setEggModalFor(sel)}
                disabled={sel.status === 'depopulated'}
                title={sel.status === 'depopulated' ? 'Стадо снято' : undefined}
              >
                <Icon name="plus" size={12} /> Запись
              </button>
            }
          >
            <DataTable<DailyEggProduction>
              rows={eggRecords?.slice(0, 15) ?? []}
              rowKey={(e) => e.id}
              emptyMessage="Нет записей"
              columns={[
                { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
                  render: (e) => e.date },
                { key: 'coll', label: 'Собрано', align: 'right', mono: true,
                  render: (e) => e.eggs_collected.toLocaleString('ru-RU') },
                { key: 'unfit', label: 'Брак', align: 'right', mono: true,
                  cellStyle: { color: 'var(--danger)' },
                  render: (e) => e.unfit_eggs > 0 ? `−${e.unfit_eggs.toLocaleString('ru-RU')}` : '0' },
                { key: 'clean', label: 'Чистые', align: 'right', mono: true,
                  cellStyle: { fontWeight: 600 },
                  render: (e) => (e.eggs_collected - e.unfit_eggs).toLocaleString('ru-RU') },
                { key: 'batch', label: 'Партия', mono: true,
                  render: (e) => (
                    <span style={{ fontSize: 11, color: e.outgoing_batch ? 'var(--success)' : 'var(--fg-3)' }}>
                      {e.outgoing_batch ? '✓ сдано' : 'свободно'}
                    </span>
                  ) },
              ]}
            />
          </Panel>

          <div style={{ marginTop: 12 }}>
            <Panel
              title={`Падёж · ${mortalityRecords?.length ?? 0} записей`}
              flush
              tools={
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setMortalityModalFor(sel)}
                  disabled={sel.status === 'depopulated' || sel.current_heads <= 0}
                >
                  <Icon name="plus" size={12} /> Падёж
                </button>
              }
            >
              <DataTable
                rows={mortalityRecords?.slice(0, 15) ?? []}
                rowKey={(m) => m.id}
                emptyMessage="Нет записей о падеже"
                columns={[
                  { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
                    render: (m) => m.date },
                  { key: 'dead', label: 'Пало', align: 'right', mono: true,
                    cellStyle: { color: 'var(--danger)', fontWeight: 600 },
                    render: (m) => `−${m.dead_count.toLocaleString('ru-RU')}` },
                  { key: 'cause', label: 'Причина', cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                    render: (m) => m.cause || '—' },
                  { key: 'notes', label: 'Заметки', cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                    render: (m) => m.notes || '' },
                ]}
              />
            </Panel>
          </div>

          <div style={{ marginTop: 12 }}>
            <EggBatchesPanel herd={sel} />
          </div>
          <div style={{ marginTop: 12 }}>
            <FeedConsumptionPanel herd={sel} />
          </div>
        </DetailDrawer>
      )}

      {createOpen && (
        <HerdModal
          initial={editing}
          onClose={() => { setCreateOpen(false); setEditing(null); }}
          onSaved={(h) => { if (sel?.id === h.id) setSel(h); }}
        />
      )}
      {crystallizeFor && (
        <CrystallizeModal herd={crystallizeFor} onClose={() => setCrystallizeFor(null)} />
      )}
      {depopulateFor && (
        <DepopulateModal herd={depopulateFor} onClose={() => setDepopulateFor(null)} />
      )}
      {eggModalFor && (
        <EggProductionModal herd={eggModalFor} onClose={() => setEggModalFor(null)} />
      )}
      {mortalityModalFor && (
        <MortalityModal herd={mortalityModalFor} onClose={() => setMortalityModalFor(null)} />
      )}
      {moveModalFor && (
        <MoveHerdModal herd={moveModalFor} onClose={() => setMoveModalFor(null)} />
      )}
      {timelineFor && (
        <HerdTimelineModal herd={timelineFor} onClose={() => setTimelineFor(null)} />
      )}
    </>
  );
}
