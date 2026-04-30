'use client';

import { useMemo, useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import OpexButton from '@/components/OpexButton';
import { OpenSaleFromModule } from '@/components/SellBatchButton';
import ShrinkageWidget from '@/components/ShrinkageWidget';
import DataTable from '@/components/ui/DataTable';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import HelpHint from '@/components/ui/HelpHint';
import Icon from '@/components/ui/Icon';
import KpiCard from '@/components/ui/KpiCard';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import Seg from '@/components/ui/Seg';
import {
  feedBatchesCrud,
  rawBatchesCrud,
  recipeComponentsCrud,
  recipesCrud,
  recipeVersionsCrud,
  tasksCrud,
  useApprovePassport,
  useCancelTask,
  useRejectPassport,
  useRejectQuarantine,
  useReleaseQuarantine,
} from '@/hooks/useFeed';
import { useHasLevel } from '@/hooks/usePermissions';
import { getFinancesVisible } from '@/lib/permissions';
import type {
  FeedBatch,
  ProductionTask,
  ProductionTaskStatus,
  RawMaterialBatch,
  RawMaterialBatchStatus,
  Recipe,
  RecipeComponent,
  RecipeVersion,
} from '@/types/auth';

import ComponentModal from './ComponentModal';
import ExecuteTaskModal from './ExecuteTaskModal';
import RawBatchModal from './RawBatchModal';
import RecipeModal from './RecipeModal';
import TaskModal from './TaskModal';
import VersionModal from './VersionModal';

type TabKey = 'recipes' | 'raw' | 'tasks' | 'batches';

const TASK_STATUS_LABEL: Record<ProductionTaskStatus, string> = {
  planned: 'План',
  running: 'В работе',
  paused: 'Пауза',
  done: 'Закрыто',
  cancelled: 'Отменено',
};

const TASK_STATUS_TONE: Record<ProductionTaskStatus, 'info' | 'warn' | 'success' | 'neutral'> = {
  planned: 'info',
  running: 'warn',
  paused: 'warn',
  done: 'success',
  cancelled: 'neutral',
};

const RAW_STATUS_LABEL: Record<RawMaterialBatchStatus, string> = {
  quarantine: 'Карантин',
  available: 'Доступна',
  rejected: 'Отклонена',
  depleted: 'Исчерпана',
};

const RAW_STATUS_TONE: Record<RawMaterialBatchStatus, 'warn' | 'success' | 'danger' | 'neutral'> = {
  quarantine: 'warn',
  available: 'success',
  rejected: 'danger',
  depleted: 'neutral',
};

function fmtNum(v: string | null | undefined, digits = 2): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

export default function FeedPage() {
  const [tab, setTab] = useState<TabKey>('recipes');
  const [taskStatus, setTaskStatus] = useState('');
  const [rawStatus, setRawStatus] = useState('');

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('feed', 'rw');

  const { data: recipes, isLoading: recipesLoading } = recipesCrud.useList();
  const { data: versions } = recipeVersionsCrud.useList();
  const { data: tasks, isLoading: tasksLoading } = tasksCrud.useList(
    taskStatus ? { status: taskStatus } : {},
  );
  const { data: rawBatches, isLoading: rawLoading } = rawBatchesCrud.useList(
    rawStatus ? { status: rawStatus } : {},
  );
  const { data: feedBatches, isLoading: feedBatchesLoading } = feedBatchesCrud.useList();

  // Selection
  const [selRecipe, setSelRecipe] = useState<Recipe | null>(null);
  const [selRaw, setSelRaw] = useState<RawMaterialBatch | null>(null);
  const [selTask, setSelTask] = useState<ProductionTask | null>(null);
  const [selBatch, setSelBatch] = useState<FeedBatch | null>(null);

  // Modals
  const [recipeModalOpen, setRecipeModalOpen] = useState(false);
  const [editingRecipe, setEditingRecipe] = useState<Recipe | null>(null);
  const [executeFor, setExecuteFor] = useState<ProductionTask | null>(null);
  const [taskOpen, setTaskOpen] = useState(false);
  const [versionFor, setVersionFor] = useState<Recipe | null>(null);
  const [editingVersion, setEditingVersion] = useState<RecipeVersion | null>(null);
  const [componentFor, setComponentFor] = useState<RecipeVersion | null>(null);
  const [editingComponent, setEditingComponent] = useState<RecipeComponent | null>(null);
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(new Set());
  const [rawModalOpen, setRawModalOpen] = useState(false);
  const [editingRaw, setEditingRaw] = useState<RawMaterialBatch | null>(null);

  // Mutations
  const recipeDel = recipesCrud.useDelete();
  const versionDel = recipeVersionsCrud.useDelete();
  const versionUpdate = recipeVersionsCrud.useUpdate();
  const componentDel = recipeComponentsCrud.useDelete();
  const rawDel = rawBatchesCrud.useDelete();
  const cancelTask = useCancelTask();
  const releaseQuarantine = useReleaseQuarantine();
  const rejectQuarantine = useRejectQuarantine();
  const approvePassport = useApprovePassport();
  const rejectPassport = useRejectPassport();

  const totals = useMemo(() => ({
    recipesCount: recipes?.length ?? 0,
    activeVersions: versions?.filter((v) => v.status === 'active').length ?? 0,
    rawTotal: rawBatches?.length ?? 0,
    rawQuarantine: rawBatches?.filter((b) => b.status === 'quarantine').length ?? 0,
    feedBatchesTotal: feedBatches?.length ?? 0,
    tasksCount: tasks?.length ?? 0,
  }), [recipes, versions, rawBatches, feedBatches, tasks]);

  const handleDeleteRecipe = (r: Recipe) => {
    if (!confirm(`Удалить рецептуру ${r.code}?`)) return;
    recipeDel.mutate(r.id, {
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  const handleCancelTask = (t: ProductionTask) => {
    const reason = prompt(`Причина отмены ${t.doc_number}?`);
    if (reason === null) return;
    cancelTask.mutate({ id: t.id, body: { reason } });
  };

  const handleDeleteRaw = (r: RawMaterialBatch) => {
    if (!confirm(`Удалить партию сырья ${r.doc_number}?`)) return;
    rawDel.mutate(r.id, { onError: (err) => alert(err.message) });
  };

  const handleReleaseQuarantine = (r: RawMaterialBatch) => {
    if (!confirm(`Снять карантин с партии ${r.doc_number}?`)) return;
    releaseQuarantine.mutate(
      { id: r.id },
      {
        onSuccess: () => { if (selRaw?.id === r.id) setSelRaw({ ...r, status: 'available' }); },
        onError: (err) => alert('Не удалось: ' + err.message),
      },
    );
  };

  const handleRejectQuarantine = (r: RawMaterialBatch) => {
    const reason = prompt(`Причина отклонения партии ${r.doc_number}?`);
    if (!reason) return;
    rejectQuarantine.mutate(
      { id: r.id, body: { reason } },
      { onError: (err) => alert('Не удалось: ' + err.message) },
    );
  };

  const newButton = () => {
    if (!canEdit) return null;
    if (tab === 'recipes') {
      return (
        <button
          className="btn btn-primary btn-sm"
          onClick={() => { setEditingRecipe(null); setRecipeModalOpen(true); }}
        >
          <Icon name="plus" size={14} /> Новая рецептура
        </button>
      );
    }
    if (tab === 'raw') {
      return (
        <button
          className="btn btn-primary btn-sm"
          onClick={() => { setEditingRaw(null); setRawModalOpen(true); }}
        >
          <Icon name="plus" size={14} /> Партия сырья
        </button>
      );
    }
    if (tab === 'tasks') {
      return (
        <button className="btn btn-primary btn-sm" onClick={() => setTaskOpen(true)}>
          <Icon name="plus" size={14} /> Новое задание
        </button>
      );
    }
    return null;
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Корма</h1>
          <div className="sub">Рецептуры · приёмка сырья · задания на замес · готовые партии</div>
        </div>
        <div className="actions">
          <OpexButton moduleCode="feed" suggestedContraCode="20.05" />
          <OpenSaleFromModule moduleCode="feed" />
          {newButton()}
        </div>
      </div>

      <div className="kpi-row">
        <KpiCard tone="orange" iconName="bag" label="Рецептур" sub="всего" value={String(totals.recipesCount)} />
        <KpiCard tone="blue" iconName="box" label="Партий сырья" sub={`карантин ${totals.rawQuarantine}`} value={String(totals.rawTotal)} />
        <KpiCard tone="green" iconName="factory" label="Готовых партий" sub="на складе" value={String(totals.feedBatchesTotal)} />
        <KpiCard tone="red" iconName="chart" label="Заданий" sub="в фильтре" value={String(totals.tasksCount)} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Seg
          options={[
            { value: 'recipes', label: 'Рецептуры' },
            { value: 'raw', label: 'Сырьё' },
            { value: 'tasks', label: 'Задания на замес' },
            { value: 'batches', label: 'Готовые партии' },
          ]}
          value={tab}
          onChange={(v) => setTab(v as TabKey)}
        />
        {tab === 'tasks' && (
          <select
            className="input"
            value={taskStatus}
            onChange={(e) => setTaskStatus(e.target.value)}
            style={{ width: 180 }}
          >
            <option value="">Все статусы</option>
            <option value="planned">План</option>
            <option value="running">В работе</option>
            <option value="paused">Пауза</option>
            <option value="done">Закрыто</option>
            <option value="cancelled">Отменено</option>
          </select>
        )}
        {tab === 'raw' && (
          <select
            className="input"
            value={rawStatus}
            onChange={(e) => setRawStatus(e.target.value)}
            style={{ width: 180 }}
          >
            <option value="">Все статусы</option>
            <option value="quarantine">Карантин</option>
            <option value="available">Доступна</option>
            <option value="rejected">Отклонена</option>
            <option value="depleted">Исчерпана</option>
          </select>
        )}
      </div>

      {/* ── Tab: Рецептуры ────────────────────────────────────────────── */}
      {tab === 'recipes' && (
        <Panel flush>
          <DataTable<Recipe>
            isLoading={recipesLoading}
            rows={recipes}
            rowKey={(r) => r.id}
            emptyMessage={
              <EmptyState
                icon="book"
                title="Рецептур пока нет"
                description="Рецептура — это «чертёж» комбикорма: какие ингредиенты, в каких долях, для каких возрастов птицы. На её основе создаются задания на замес."
                steps={[
                  { label: 'Создайте рецептуру (например «Старт бройлера»)' },
                  { label: 'Добавьте версию рецептуры — конкретный набор показателей' },
                  { label: 'В версию добавьте компоненты (кукуруза 50%, шрот 30% и т.д.)' },
                  { label: 'После — переходите в таб «Задания на замес»' },
                ]}
                action={{
                  label: 'Новая рецептура',
                  onClick: () => { setEditingRecipe(null); setRecipeModalOpen(true); },
                }}
                hint="Версии нужны чтобы исторически фиксировать состав — рецепт может меняться, но прошлые партии останутся со своими версиями."
              />
            }
            onRowClick={(r) => setSelRecipe(r)}
            rowProps={(r) => ({ active: selRecipe?.id === r.id })}
            columns={[
              { key: 'code', label: 'Код',
                render: (r) => <span className="badge id">{r.code}</span> },
              { key: 'name', label: 'Название', cellStyle: { fontWeight: 500 },
                render: (r) => r.name },
              { key: 'age', label: 'Возраст', cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                render: (r) => r.age_range },
              { key: 'dir', label: 'Направление', cellStyle: { fontSize: 12 },
                render: (r) => r.direction },
              { key: 'versions', label: 'Версий', align: 'right', mono: true,
                render: (r) => r.versions_count },
              { key: 'med', label: 'Мед.',
                render: (r) => r.is_medicated ? <Badge tone="warn">мед</Badge> : '—' },
              { key: 'status', label: 'Статус',
                render: (r) => r.is_active
                  ? <Badge tone="success" dot>Активна</Badge>
                  : <Badge tone="neutral" dot>Архив</Badge> },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (r) => canEdit ? (
                  <RowActions
                    actions={[
                      {
                        label: 'Редактировать',
                        onClick: () => { setEditingRecipe(r); setRecipeModalOpen(true); },
                      },
                      { label: 'Удалить', danger: true, onClick: () => handleDeleteRecipe(r) },
                    ]}
                  />
                ) : null },
            ]}
          />
        </Panel>
      )}

      {/* ── Tab: Сырьё ────────────────────────────────────────────────── */}
      {tab === 'raw' && (
        <Panel flush>
          <DataTable<RawMaterialBatch>
            isLoading={rawLoading}
            rows={rawBatches}
            rowKey={(r) => r.id}
            emptyMessage={
              <EmptyState
                icon="box"
                title="Сырья на складе нет"
                description="Сырьё — это ингредиенты для замеса (зерно, шрот, премикс). Партия фиксирует поступление на склад с учётом усушки и карантина."
                steps={[
                  { label: 'Нажмите «Партия сырья»' },
                  { label: 'Выберите номенклатуру (зерно/шрот/премикс) и поставщика' },
                  { label: 'Введите вес и влажность — система рассчитает зачётный вес и сумму' },
                  { label: 'Партия попадёт в карантин до результата лаборатории' },
                  { label: 'После «Снять карантин» сырьё доступно для замеса' },
                ]}
                action={{
                  label: 'Партия сырья',
                  onClick: () => { setEditingRaw(null); setRawModalOpen(true); },
                }}
                hint="Если у номенклатуры задана базисная влажность (14% по ГОСТ для зерна) — зачётный вес считается по формуле Дюваля автоматически."
              />
            }
            onRowClick={(r) => setSelRaw(r)}
            rowProps={(r) => ({ active: selRaw?.id === r.id })}
            columns={[
              { key: 'doc', label: 'Документ',
                render: (r) => <span className="badge id">{r.doc_number}</span> },
              { key: 'nom', label: 'Номенклатура',
                render: (r) => (
                  <>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', marginRight: 6 }}>
                      {r.nomenclature_sku}
                    </span>
                    {r.nomenclature_name}
                  </>
                ) },
              { key: 'sup', label: 'Поставщик', cellStyle: { fontSize: 12 },
                render: (r) => r.supplier_name ?? '—' },
              { key: 'wh', label: 'Склад · Бункер', mono: true, cellStyle: { fontSize: 12 },
                render: (r) => `${r.warehouse_code ?? '—'}${r.storage_bin ? ' · ' + r.storage_bin : ''}` },
              { key: 'date', label: 'Прибыло', mono: true, cellStyle: { fontSize: 12 },
                render: (r) => r.received_date },
              { key: 'gross', label: 'Брутто кг', align: 'right', mono: true, cellStyle: { fontSize: 12 },
                render: (r) => fmtNum(r.gross_weight_kg, 0) },
              { key: 'settle', label: 'Зачёт. кг', align: 'right', mono: true,
                cellStyle: { fontWeight: 600 },
                render: (r) => fmtNum(r.settlement_weight_kg ?? r.quantity, 0) },
              { key: 'shrink', label: 'Усушка %', align: 'right', mono: true, cellStyle: { fontSize: 12 },
                render: (r) => r.shrinkage_pct ? r.shrinkage_pct + '%' : '—' },
              { key: 'remain', label: 'Остаток кг', align: 'right', mono: true,
                render: (r) => fmtNum(r.current_quantity, 0) },
              ...(getFinancesVisible(rawBatches) ? [{
                key: 'price', label: 'Цена/кг', align: 'right' as const, mono: true,
                cellStyle: { fontSize: 12 },
                render: (r: RawMaterialBatch) => fmtNum(r.price_per_unit_uzs, 0),
              }] : []),
              { key: 'status', label: 'Статус',
                render: (r) => (
                  <Badge tone={RAW_STATUS_TONE[r.status]} dot>
                    {RAW_STATUS_LABEL[r.status]}
                  </Badge>
                ) },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (r) => canEdit ? (
                  <RowActions
                    actions={[
                      {
                        label: 'Снять карантин',
                        hidden: r.status !== 'quarantine',
                        disabled: releaseQuarantine.isPending,
                        onClick: () => handleReleaseQuarantine(r),
                      },
                      {
                        label: 'Отклонить',
                        danger: true,
                        hidden: r.status !== 'quarantine',
                        disabled: rejectQuarantine.isPending,
                        onClick: () => handleRejectQuarantine(r),
                      },
                      {
                        label: 'Редактировать',
                        onClick: () => { setEditingRaw(r); setRawModalOpen(true); },
                      },
                      {
                        label: 'Удалить',
                        danger: true,
                        disabled: rawDel.isPending,
                        onClick: () => handleDeleteRaw(r),
                      },
                    ]}
                  />
                ) : null },
            ]}
          />
        </Panel>
      )}

      {/* ── Tab: Задания на замес ────────────────────────────────────── */}
      {tab === 'tasks' && (
        <Panel flush>
          <DataTable<ProductionTask>
            isLoading={tasksLoading}
            rows={tasks}
            rowKey={(t) => t.id}
            emptyMessage={
              <EmptyState
                icon="factory"
                title="Заданий на замес пока нет"
                description="Задание — это план «сделать N кг корма по версии рецепта X в смену Y». После проведения замеса рождается готовая партия."
                steps={[
                  {
                    label: 'У вас есть активная версия рецептуры',
                    done: (versions ?? []).some((v) => v.status === 'active'),
                  },
                  {
                    label: 'Сырьё (компоненты) есть на складе и снято с карантина',
                    done: (rawBatches ?? []).some((r) => r.status === 'available'),
                  },
                  { label: 'Создайте задание — укажите версию рецепта, линию, смену, план кг' },
                  { label: 'В нужный момент откройте задание и нажмите «Провести замес»' },
                ]}
                action={{
                  label: 'Новое задание',
                  onClick: () => setTaskOpen(true),
                }}
                hint="Только активные версии рецептур доступны для новых заданий — это защита от случайного использования черновиков или архивных рецептов."
              />
            }
            onRowClick={(t) => setSelTask(t)}
            rowProps={(t) => ({ active: selTask?.id === t.id })}
            columns={[
              { key: 'doc', label: 'Документ',
                render: (t) => <span className="badge id">{t.doc_number}</span> },
              { key: 'sched', label: 'Запланировано', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => new Date(t.scheduled_at).toLocaleString('ru') },
              { key: 'shift', label: 'Смена', cellStyle: { fontSize: 12 },
                render: (t) => t.shift === 'day' ? 'День' : 'Ночь' },
              { key: 'plan', label: 'План, кг', align: 'right', mono: true,
                render: (t) => fmtNum(t.planned_quantity_kg, 0) },
              { key: 'actual', label: 'Факт, кг', align: 'right', mono: true,
                render: (t) => fmtNum(t.actual_quantity_kg, 0) },
              { key: 'status', label: 'Статус',
                render: (t) => (
                  <Badge tone={TASK_STATUS_TONE[t.status]} dot>
                    {TASK_STATUS_LABEL[t.status]}
                  </Badge>
                ) },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (t) => canEdit ? (
                  <RowActions
                    actions={[
                      {
                        label: 'Провести замес',
                        hidden: t.status !== 'planned',
                        onClick: () => setExecuteFor(t),
                      },
                      {
                        label: 'Отменить задание',
                        danger: true,
                        hidden: !(t.status === 'planned' || t.status === 'paused'),
                        onClick: () => handleCancelTask(t),
                      },
                    ]}
                  />
                ) : null },
            ]}
          />
        </Panel>
      )}

      {/* ── Tab: Готовые партии ──────────────────────────────────────── */}
      {tab === 'batches' && (
        <Panel flush>
          <DataTable<FeedBatch>
            isLoading={feedBatchesLoading}
            rows={feedBatches}
            rowKey={(b) => b.id}
            emptyMessage={
              <EmptyState
                icon="bag"
                title="Готовых партий ещё нет"
                description="Готовая партия — это итог замеса: конкретный объём корма по конкретной версии рецепта с зафиксированной себестоимостью. Партии создаются автоматически при проведении задания."
                steps={[
                  { label: 'Создайте рецептуру и активную версию с компонентами' },
                  { label: 'Оприходуйте сырьё на склад и снимите карантин' },
                  { label: 'Создайте задание на замес' },
                  { label: 'Откройте задание и нажмите «Провести замес» — партия появится здесь' },
                ]}
                hint="После замеса партия проходит контроль качества — нужно «выпустить паспорт» прежде чем кормить ею птицу."
              />
            }
            onRowClick={(b) => setSelBatch(b)}
            rowProps={(b) => ({ active: selBatch?.id === b.id })}
            columns={[
              { key: 'doc', label: 'Документ',
                render: (b) => <span className="badge id">{b.doc_number}</span> },
              { key: 'recipe', label: 'Рецепт', cellStyle: { fontSize: 12 },
                render: (b) => b.recipe_code ?? '—' },
              { key: 'date', label: 'Произведено', mono: true, cellStyle: { fontSize: 12 },
                render: (b) => new Date(b.produced_at).toLocaleDateString('ru-RU') },
              { key: 'qty', label: 'Выпуск кг', align: 'right', mono: true,
                render: (b) => fmtNum(b.quantity_kg, 0) },
              { key: 'remain', label: 'Остаток кг', align: 'right', mono: true,
                cellStyle: { fontWeight: 600 },
                render: (b) => fmtNum(b.current_quantity_kg, 0) },
              ...(getFinancesVisible(feedBatches) ? [{
                key: 'unit_cost', label: 'Себест/кг', align: 'right' as const, mono: true,
                cellStyle: { fontSize: 12 },
                render: (b: FeedBatch) => fmtNum(b.unit_cost_uzs, 2) + ' сум',
              }] : []),
              { key: 'med', label: 'Мед.',
                render: (b) => b.is_medicated ? <Badge tone="warn">мед</Badge> : '—' },
              { key: 'status', label: 'Статус', cellStyle: { fontSize: 12 },
                render: (b) => b.status },
              { key: 'passport', label: 'Паспорт', cellStyle: { fontSize: 12 },
                render: (b) => b.quality_passport_status },
            ]}
          />
        </Panel>
      )}

      {/* ── Drawer: Recipe ─────────────────────────────────────────────── */}
      {selRecipe && (() => {
        const recipeVersions = (versions ?? []).filter((v) => v.recipe === selRecipe.id);
        const lastNumber = recipeVersions.reduce((max, v) => Math.max(max, v.version_number), 0);
        return (
          <DetailDrawer
            title={`${selRecipe.code} · ${selRecipe.name}`}
            subtitle={`${selRecipe.direction} · ${selRecipe.age_range}`}
            onClose={() => setSelRecipe(null)}
            actions={
              <>
                <button className="btn btn-secondary btn-sm" onClick={() => setVersionFor(selRecipe)}>
                  + Версия
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => { setEditingRecipe(selRecipe); setRecipeModalOpen(true); }}>
                  Редактировать
                </button>
              </>
            }
          >
            <KV
              items={[
                { k: 'Код', v: selRecipe.code, mono: true },
                { k: 'Направление', v: selRecipe.direction },
                { k: 'Возраст', v: selRecipe.age_range },
                { k: 'Версий', v: String(selRecipe.versions_count) },
                { k: 'Медикаментозная', v: selRecipe.is_medicated ? 'Да' : 'Нет' },
                { k: 'Статус', v: selRecipe.is_active ? 'Активна' : 'Архив' },
                ...(selRecipe.notes ? [{ k: 'Заметка', v: selRecipe.notes }] : []),
              ]}
            />
            <Panel
              title={
                <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                  Версии рецептуры
                  <HelpHint
                    text="Что такое «версия»."
                    details={
                      'Версия — конкретная конфигурация рецепта: набор компонентов с долями + целевые '
                      + 'показатели (белок, жир, обменная энергия). Можно держать несколько версий, '
                      + 'но активной для замеса должна быть одна. Прошлые партии останутся со своими '
                      + 'версиями для прослеживаемости.'
                    }
                  />
                </span> as unknown as string
              }
              flush
            >
              {recipeVersions.length === 0 ? (
                <EmptyState
                  icon="chart"
                  title="Версий нет"
                  description="Чтобы начать делать замесы, добавьте версию: укажите целевые показатели и компоненты (зерно, шрот, премиксы)."
                  action={{
                    label: 'Добавить версию',
                    onClick: () => setVersionFor(selRecipe),
                  }}
                />
              ) : (
                <>
                  {recipeVersions.map((v) => {
                    const isOpen = expandedVersions.has(v.id);
                    const totalShare = v.components.reduce(
                      (s, c) => s + parseFloat(c.share_percent || '0'),
                      0,
                    );
                    return (
                      <div key={v.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        {/* Заголовок версии */}
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '8px 12px', fontSize: 12,
                          background: isOpen ? 'var(--bg-soft)' : 'transparent',
                        }}>
                          <button
                            type="button"
                            onClick={() => {
                              const next = new Set(expandedVersions);
                              if (next.has(v.id)) next.delete(v.id); else next.add(v.id);
                              setExpandedVersions(next);
                            }}
                            style={{
                              background: 'transparent', border: 'none',
                              cursor: 'pointer', padding: 0, color: 'var(--fg-3)',
                              display: 'inline-flex', alignItems: 'center',
                            }}
                            title={isOpen ? 'Свернуть' : 'Раскрыть'}
                          >
                            <Icon name={isOpen ? 'chevron-down' : 'chevron-right'} size={14} />
                          </button>
                          <span className="mono" style={{ fontWeight: 600 }}>v{v.version_number}</span>
                          <span style={{ flex: 1, color: 'var(--fg-2)' }}>
                            {v.components.length === 0 ? (
                              <span style={{ color: 'var(--warning)' }}>
                                нет компонентов · добавьте
                              </span>
                            ) : (
                              <>
                                {v.components.length} комп. ·{' '}
                                <span
                                  className="mono"
                                  style={{
                                    color: totalShare === 100 ? 'var(--success)'
                                      : totalShare > 100 ? 'var(--danger)'
                                      : 'var(--warning)',
                                  }}
                                >
                                  Σ {totalShare.toFixed(2)}%
                                </span>
                              </>
                            )}
                          </span>
                          {v.effective_from && (
                            <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                              c {v.effective_from}
                            </span>
                          )}
                          <Badge tone={
                            v.status === 'active' ? 'success'
                              : v.status === 'archived' ? 'neutral'
                              : 'warn'
                          }>{v.status}</Badge>
                          <RowActions
                            actions={[
                              {
                                label: 'Раскрыть состав',
                                hidden: isOpen,
                                onClick: () => {
                                  const next = new Set(expandedVersions);
                                  next.add(v.id);
                                  setExpandedVersions(next);
                                },
                              },
                              {
                                label: '+ Компонент',
                                hidden: !canEdit,
                                onClick: () => {
                                  setEditingComponent(null);
                                  setComponentFor(v);
                                },
                              },
                              {
                                label: 'Редактировать версию',
                                hidden: !canEdit,
                                onClick: () => setEditingVersion(v),
                              },
                              {
                                label: v.status === 'active' ? 'Перевести в архив' : 'Сделать активной',
                                hidden: !canEdit || (v.status === 'archived' && v.components.length === 0),
                                disabled: versionUpdate.isPending,
                                onClick: () => {
                                  const newStatus = v.status === 'active' ? 'archived' : 'active';
                                  if (newStatus === 'active' && v.components.length === 0) {
                                    alert('Нельзя активировать версию без компонентов.');
                                    return;
                                  }
                                  versionUpdate.mutate({
                                    id: v.id,
                                    patch: { status: newStatus } as never,
                                  });
                                },
                              },
                              {
                                label: 'Удалить версию',
                                danger: true,
                                hidden: !canEdit,
                                disabled: versionDel.isPending,
                                onClick: () => {
                                  if (!window.confirm(
                                    `Удалить версию v${v.version_number}? `
                                    + (v.components.length > 0
                                      ? `Будут удалены и ${v.components.length} компонента.`
                                      : ''),
                                  )) return;
                                  versionDel.mutate(v.id, {
                                    onError: (err) => alert('Не удалось: ' + err.message),
                                  });
                                },
                              },
                            ]}
                          />
                        </div>

                        {/* Раскрытое содержимое: компоненты */}
                        {isOpen && (
                          <div style={{ padding: '4px 12px 10px', background: 'var(--bg-card, #fff)' }}>
                            {/* Целевые показатели если заданы */}
                            {(v.target_protein_percent || v.target_fat_percent
                              || v.target_me_kcal_per_kg) && (
                              <div style={{
                                display: 'flex', gap: 12, flexWrap: 'wrap',
                                fontSize: 11, color: 'var(--fg-3)', marginBottom: 8,
                              }}>
                                {v.target_protein_percent && (
                                  <span>Белок: <b className="mono">{v.target_protein_percent}%</b></span>
                                )}
                                {v.target_fat_percent && (
                                  <span>Жир: <b className="mono">{v.target_fat_percent}%</b></span>
                                )}
                                {v.target_fibre_percent && (
                                  <span>Клетчатка: <b className="mono">{v.target_fibre_percent}%</b></span>
                                )}
                                {v.target_lysine_percent && (
                                  <span>Лизин: <b className="mono">{v.target_lysine_percent}%</b></span>
                                )}
                                {v.target_me_kcal_per_kg && (
                                  <span>МЭ: <b className="mono">{v.target_me_kcal_per_kg}</b> ккал/кг</span>
                                )}
                              </div>
                            )}

                            {/* Таблица компонентов */}
                            {v.components.length === 0 ? (
                              <div style={{
                                padding: 12, fontSize: 12, color: 'var(--fg-3)',
                                textAlign: 'center',
                                border: '1px dashed var(--border)', borderRadius: 4,
                              }}>
                                Компонентов нет.{' '}
                                <button
                                  className="btn btn-ghost btn-sm"
                                  onClick={() => { setEditingComponent(null); setComponentFor(v); }}
                                >
                                  + Компонент
                                </button>
                              </div>
                            ) : (
                              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr style={{
                                    background: 'var(--bg-soft)', color: 'var(--fg-3)',
                                    fontSize: 10, textAlign: 'left',
                                  }}>
                                    <td style={{ padding: '4px 8px' }}>SKU / Название</td>
                                    <td style={{ padding: '4px 8px', textAlign: 'right' }}>Доля</td>
                                    <td style={{ padding: '4px 8px', textAlign: 'right' }}>Min..Max</td>
                                    <td style={{ padding: '4px 8px' }}>Мед.</td>
                                    <td style={{ padding: '4px 8px', width: 50 }} />
                                  </tr>
                                </thead>
                                <tbody>
                                  {v.components.map((c) => (
                                    <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
                                      <td style={{ padding: '4px 8px' }}>
                                        <span
                                          className="mono"
                                          style={{ color: 'var(--fg-3)', marginRight: 6, fontSize: 10 }}
                                        >
                                          {c.nomenclature_sku ?? ''}
                                        </span>
                                        {c.nomenclature_name ?? '—'}
                                      </td>
                                      <td style={{ padding: '4px 8px', textAlign: 'right', fontWeight: 600 }} className="mono">
                                        {c.share_percent}%
                                      </td>
                                      <td style={{ padding: '4px 8px', textAlign: 'right', color: 'var(--fg-3)' }} className="mono">
                                        {c.min_share_percent || c.max_share_percent
                                          ? `${c.min_share_percent ?? '—'} .. ${c.max_share_percent ?? '—'}`
                                          : '—'}
                                      </td>
                                      <td style={{ padding: '4px 8px' }}>
                                        {c.is_medicated ? (
                                          <Badge tone="warn">мед {c.withdrawal_period_days}д</Badge>
                                        ) : '—'}
                                      </td>
                                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                                        {canEdit && <RowActions
                                          actions={[
                                            {
                                              label: 'Редактировать',
                                              onClick: () => {
                                                setComponentFor(v);
                                                setEditingComponent(c);
                                              },
                                            },
                                            {
                                              label: 'Удалить',
                                              danger: true,
                                              disabled: componentDel.isPending,
                                              onClick: () => {
                                                if (!window.confirm(
                                                  `Удалить компонент «${c.nomenclature_name ?? c.nomenclature_sku}» из версии v${v.version_number}?`,
                                                )) return;
                                                componentDel.mutate(c.id, {
                                                  onError: (err) => alert('Не удалось: ' + err.message),
                                                });
                                              },
                                            },
                                          ]}
                                        />}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}

                            {v.comment && (
                              <div style={{
                                marginTop: 8, padding: '6px 8px',
                                fontSize: 11, color: 'var(--fg-3)',
                                background: 'var(--bg-soft)', borderRadius: 4,
                                fontStyle: 'italic',
                              }}>
                                {v.comment}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {selRecipe && (
                    <div style={{ padding: 8, fontSize: 11, color: 'var(--fg-3)', textAlign: 'right' }}>
                      Последний № версии: {lastNumber || '—'}
                    </div>
                  )}
                </>
              )}
            </Panel>
          </DetailDrawer>
        );
      })()}

      {/* ── Drawer: RawMaterialBatch ───────────────────────────────────── */}
      {selRaw && (
        <DetailDrawer
          title={`Сырьё · ${selRaw.doc_number}`}
          subtitle={
            <span style={{ display: 'inline-flex', alignItems: 'center' }}>
              {selRaw.nomenclature_name ?? selRaw.nomenclature_sku ?? ''} · {RAW_STATUS_LABEL[selRaw.status]}
              <HelpHint
                text="Что значит статус партии сырья."
                details={
                  '• Карантин — ждёт результата лаборатории, в замес не пойдёт.\n'
                  + '• Доступна — снят карантин, можно расходовать в замесе.\n'
                  + '• Отклонена — лаборатория забраковала, использовать нельзя.\n'
                  + '• Исчерпана — всё израсходовано.'
                }
              />
            </span> as unknown as string
          }
          onClose={() => setSelRaw(null)}
          actions={
            <>
              {selRaw.status === 'quarantine' && (
                <>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleReleaseQuarantine(selRaw)}
                    disabled={releaseQuarantine.isPending}
                  >
                    Снять карантин
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleRejectQuarantine(selRaw)}
                    style={{ color: 'var(--danger)' }}
                  >
                    Отклонить
                  </button>
                </>
              )}
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => { setEditingRaw(selRaw); setRawModalOpen(true); }}
              >
                Редактировать
              </button>
            </>
          }
        >
          {(() => {
            // Определяем режим приёмки
            const hasMoisture = Boolean(selRaw.moisture_pct_actual);
            const hasShrink = Boolean(selRaw.shrinkage_pct);
            const grossEqualsSettlement =
              selRaw.gross_weight_kg && selRaw.settlement_weight_kg
              && parseFloat(selRaw.gross_weight_kg) === parseFloat(selRaw.settlement_weight_kg);

            const mode: 'duval' | 'direct' | 'none' =
              hasMoisture ? 'duval'
              : (hasShrink && !grossEqualsSettlement) ? 'direct'
              : 'none';

            const modeBadge =
              mode === 'duval' ? <Badge tone="info">по влажности (Дюваль)</Badge>
              : mode === 'direct' ? <Badge tone="warn">прямой % усушки</Badge>
              : <Badge tone="neutral">без расчёта усушки</Badge>;

            return (
              <>
                <div style={{
                  marginBottom: 12, padding: '8px 10px',
                  background: 'var(--bg-soft)', borderRadius: 6,
                  fontSize: 12,
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  gap: 8,
                }}>
                  <span style={{ color: 'var(--fg-3)' }}>Режим приёмки:</span>
                  {modeBadge}
                </div>

                <KV
                  items={[
                    { k: 'Документ', v: selRaw.doc_number, mono: true },
                    { k: 'Номенклатура', v: `${selRaw.nomenclature_sku ?? '—'} · ${selRaw.nomenclature_name ?? ''}` },
                    { k: 'Поставщик', v: selRaw.supplier_name ?? '—' },
                    { k: 'Склад', v: selRaw.warehouse_code ?? '—', mono: true },
                    { k: 'Бункер', v: selRaw.storage_bin || '—' },
                    { k: 'Прибыло', v: selRaw.received_date, mono: true },
                    // Веса всегда показываем
                    { k: 'Брутто (на весах)', v: `${fmtNum(selRaw.gross_weight_kg, 3)} ${selRaw.unit_code ?? ''}`, mono: true },
                    { k: 'Зачётный вес', v: `${fmtNum(selRaw.settlement_weight_kg, 3)} ${selRaw.unit_code ?? ''}`, mono: true },
                    // Усушка — только если была применена
                    ...(mode !== 'none' ? [{
                      k: (
                        <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                          Усушка
                          <HelpHint
                            text="Доля массы, потерянная при сушке/хранении."
                            details="Этот % уже применён к зачётному весу относительно брутто."
                          />
                        </span>
                      ) as unknown as string,
                      v: selRaw.shrinkage_pct ? selRaw.shrinkage_pct + '%' : '—',
                      mono: true,
                    }] : []),
                    // Поля Дюваля — только в режиме duval
                    ...(mode === 'duval' ? [
                      { k: 'Влажность факт.', v: selRaw.moisture_pct_actual ? selRaw.moisture_pct_actual + '%' : '—', mono: true },
                      { k: 'Влажность база (snapshot)', v: selRaw.moisture_pct_base ? selRaw.moisture_pct_base + '%' : '—', mono: true },
                      { k: 'Сорность', v: selRaw.dockage_pct_actual ? selRaw.dockage_pct_actual + '%' : '—', mono: true },
                    ] : []),
                    // Цены и финансы — скрыты для пользователей без доступа к ledger
                    ...(getFinancesVisible(selRaw) ? [
                      { k: 'Цена за кг', v: fmtNum(selRaw.price_per_unit_uzs, 2) + ' сум', mono: true },
                      { k: 'Сумма закупа', v: fmtNum(selRaw.total_cost_uzs, 0) + ' сум', mono: true },
                    ] : []),
                    { k: 'Остаток на складе', v: `${fmtNum(selRaw.current_quantity, 3)} ${selRaw.unit_code ?? ''}`, mono: true },
                    { k: 'Карантин до', v: selRaw.quarantine_until ?? '—', mono: true },
                    ...(selRaw.rejection_reason ? [{ k: 'Причина отклонения', v: selRaw.rejection_reason }] : []),
                    ...(selRaw.notes ? [{ k: 'Заметка', v: selRaw.notes }] : []),
                  ]}
                />

                {mode === 'none' && (
                  <div style={{
                    padding: 10, marginTop: 4, fontSize: 11,
                    background: 'var(--bg-soft)', color: 'var(--fg-3)',
                    borderRadius: 6, lineHeight: 1.5,
                  }}>
                    Эта партия принята <b>без расчёта усушки</b> — введён сразу зачётный вес.
                    Поля «Влажность» и «Сорность» не применяются. Если нужен учёт усушки —
                    при следующей приёмке выберите режим «По влажности (Дюваль)» или
                    «Указать % напрямую».
                  </div>
                )}
                {mode === 'direct' && (
                  <div style={{
                    padding: 10, marginTop: 4, fontSize: 11,
                    background: 'var(--bg-soft)', color: 'var(--fg-3)',
                    borderRadius: 6, lineHeight: 1.5,
                  }}>
                    Усушка указана <b>прямым процентом</b> (без замера влажности).
                    Лабораторных показателей для этой партии нет.
                  </div>
                )}

                <ShrinkageWidget
                  lotType="raw_arrival"
                  lotId={selRaw.id}
                  initialKg={selRaw.quantity}
                  unitLabel={selRaw.unit_code ?? 'кг'}
                />
              </>
            );
          })()}
        </DetailDrawer>
      )}

      {/* ── Drawer: ProductionTask ─────────────────────────────────────── */}
      {selTask && (() => {
        const taskVersion = (versions ?? []).find((v) => v.id === selTask.recipe_version);
        const taskRecipe = (recipes ?? []).find((r) => r.id === taskVersion?.recipe);
        return (
          <DetailDrawer
            title={`Замес · ${selTask.doc_number}`}
            subtitle={`${TASK_STATUS_LABEL[selTask.status]} · план ${fmtNum(selTask.planned_quantity_kg, 0)} кг`}
            onClose={() => setSelTask(null)}
            actions={
              <>
                {selTask.status === 'planned' && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setExecuteFor(selTask)}
                  >
                    Провести замес
                  </button>
                )}
                {(selTask.status === 'planned' || selTask.status === 'paused') && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleCancelTask(selTask)}
                    style={{ color: 'var(--danger)' }}
                  >
                    Отменить
                  </button>
                )}
              </>
            }
          >
            <KV
              items={[
                { k: 'Документ', v: selTask.doc_number, mono: true },
                { k: 'Запланировано', v: new Date(selTask.scheduled_at).toLocaleString('ru'), mono: true },
                { k: 'Смена', v: selTask.shift === 'day' ? 'День' : 'Ночь' },
                {
                  k: 'Рецепт · версия',
                  v: taskRecipe && taskVersion
                    ? `${taskRecipe.code} · ${taskRecipe.name} · v${taskVersion.version_number}`
                    : selTask.recipe_version,
                  mono: true,
                },
                { k: 'Линия', v: selTask.production_line, mono: true },
                { k: 'План кг', v: fmtNum(selTask.planned_quantity_kg, 0), mono: true },
                { k: 'Факт кг', v: fmtNum(selTask.actual_quantity_kg, 0), mono: true },
                { k: 'Медикаментозный', v: selTask.is_medicated ? 'Да' : 'Нет' },
                ...(selTask.withdrawal_period_days ? [{
                  k: 'Каренция, дн', v: String(selTask.withdrawal_period_days), mono: true,
                }] : []),
                {
                  k: (
                    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                      Статус
                      <HelpHint
                        text="Жизненный цикл задания на замес."
                        details={
                          '• План — задание создано, ожидает проведения. Можно отменить.\n'
                          + '• В работе — замес идёт прямо сейчас.\n'
                          + '• Пауза — оператор приостановил замес (например, поломка линии).\n'
                          + '• Закрыто — замес проведён, создана партия готового корма.\n'
                          + '• Отменено — задание не будет выполняться.'
                        }
                      />
                    </span>
                  ) as unknown as string,
                  v: TASK_STATUS_LABEL[selTask.status],
                },
                ...(selTask.notes ? [{ k: 'Заметка', v: selTask.notes }] : []),
              ]}
            />

            {/* Состав замеса — реальные task.components с привязкой к партиям сырья */}
            <Panel
              title={
                <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                  Состав замеса
                  <HelpHint
                    text="Что войдёт в эту партию корма."
                    details={
                      'При создании задания каждому компоненту автоматически назначается '
                      + 'партия сырья со склада (FIFO — первая по дате прихода, доступная). '
                      + 'Если для какого-то ингредиента нет доступной партии — она помечена красным; '
                      + 'провести замес нельзя пока не оприходовать сырьё.'
                    }
                  />
                </span> as unknown as string
              }
              flush
            >
              {(!selTask.components || selTask.components.length === 0) ? (
                <div style={{ padding: 12, fontSize: 12, color: 'var(--warning)' }}>
                  У задания нет компонентов. Это бывает если у выбранной версии
                  рецепта нет компонентов. Откройте рецепт, добавьте компоненты
                  в версию и создайте задание заново.
                </div>
              ) : (
                <>
                  {/* Сводка готовности */}
                  {(() => {
                    const missing = selTask.components.filter((c) => !c.source_batch).length;
                    if (missing > 0) {
                      return (
                        <div style={{
                          padding: '8px 12px', fontSize: 12,
                          background: '#fef2f2', color: 'var(--danger)',
                          borderBottom: '1px solid var(--border)',
                        }}>
                          ⚠ Не назначены партии сырья для {missing} из {selTask.components.length} компонентов.
                          Замес провести нельзя — оприходуйте недостающее сырьё в табе «Сырьё».
                        </div>
                      );
                    }
                    return null;
                  })()}
                  <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-soft)', color: 'var(--fg-3)', fontSize: 11 }}>
                        <td style={{ padding: '6px 10px' }}>SKU / Название</td>
                        <td style={{ padding: '6px 10px', textAlign: 'right' }}>Расход кг</td>
                        <td style={{ padding: '6px 10px' }}>Партия сырья</td>
                        <td style={{ padding: '6px 10px', textAlign: 'right' }}>Цена/кг</td>
                      </tr>
                    </thead>
                    <tbody>
                      {selTask.components.map((c) => (
                        <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
                          <td style={{ padding: '6px 10px' }}>
                            <span
                              className="mono"
                              style={{ color: 'var(--fg-3)', marginRight: 4, fontSize: 10 }}
                            >
                              {c.nomenclature_sku ?? ''}
                            </span>
                            {c.nomenclature_name ?? '—'}
                          </td>
                          <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600 }} className="mono">
                            {fmtNum(c.planned_quantity, 1)}
                          </td>
                          <td style={{ padding: '6px 10px' }}>
                            {c.source_batch_doc_number ? (
                              <span className="mono" style={{ fontSize: 11 }}>
                                {c.source_batch_doc_number}
                              </span>
                            ) : (
                              <span style={{ color: 'var(--danger)', fontSize: 11 }}>
                                нет на складе
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--fg-3)' }} className="mono">
                            {fmtNum(c.planned_price_per_unit_uzs, 2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </Panel>

            {/* Расшифровка целевых показателей версии (для справки) */}
            {taskVersion && (taskVersion.target_protein_percent || taskVersion.target_me_kcal_per_kg) && (
              <div style={{
                marginTop: 8, padding: '6px 12px',
                fontSize: 11, color: 'var(--fg-3)',
                display: 'flex', gap: 12, flexWrap: 'wrap',
              }}>
                <span style={{ fontWeight: 600 }}>Цели версии:</span>
                {taskVersion.target_protein_percent && (
                  <span>Белок {taskVersion.target_protein_percent}%</span>
                )}
                {taskVersion.target_fat_percent && (
                  <span>Жир {taskVersion.target_fat_percent}%</span>
                )}
                {taskVersion.target_me_kcal_per_kg && (
                  <span>МЭ {taskVersion.target_me_kcal_per_kg} ккал/кг</span>
                )}
              </div>
            )}
          </DetailDrawer>
        );
      })()}

      {/* ── Drawer: FeedBatch ──────────────────────────────────────────── */}
      {selBatch && (() => {
        const handleApprovePassport = () => {
          if (!selBatch) return;
          if (!window.confirm(
            `Выпустить паспорт качества для партии ${selBatch.doc_number}?\n\n`
            + `Это подтверждает что корм прошёл лаб-контроль и его можно `
            + `расходовать/продавать. Статус изменится на «Одобрена».`,
          )) return;
          approvePassport.mutate({ id: selBatch.id }, {
            onSuccess: (updated) => setSelBatch(updated),
            onError: (err) => alert('Не удалось: ' + err.message),
          });
        };
        const handleRejectPassport = () => {
          if (!selBatch) return;
          const reason = window.prompt(
            `Причина отклонения партии ${selBatch.doc_number}?\n`
            + `(например: «Превышение микотоксинов», «Влажность выше нормы»)`,
          );
          if (!reason?.trim()) return;
          rejectPassport.mutate({ id: selBatch.id, body: { reason: reason.trim() } }, {
            onSuccess: (updated) => setSelBatch(updated),
            onError: (err) => alert('Не удалось: ' + err.message),
          });
        };

        return (
        <DetailDrawer
          title={`Партия комбикорма · ${selBatch.doc_number}`}
          subtitle={`${selBatch.recipe_code ?? '—'} · ${fmtNum(selBatch.current_quantity_kg, 0)} кг остаток`}
          onClose={() => setSelBatch(null)}
          actions={
            <>
              {selBatch.status === 'quality_check' && (
                <>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleApprovePassport}
                    disabled={approvePassport.isPending}
                  >
                    <Icon name="check" size={14} /> Выпустить паспорт
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={handleRejectPassport}
                    disabled={rejectPassport.isPending}
                    style={{ color: 'var(--danger)' }}
                  >
                    Отклонить
                  </button>
                </>
              )}
              <a
                className="btn btn-secondary btn-sm"
                href={`/feed/${selBatch.id}/print`}
                target="_blank"
                rel="noreferrer"
              >
                <Icon name="book" size={14} /> Акт замеса
              </a>
            </>
          }
        >
          <KV
            items={[
              { k: 'Документ', v: selBatch.doc_number, mono: true },
              { k: 'Рецепт', v: selBatch.recipe_code ?? '—', mono: true },
              { k: 'Произведено', v: new Date(selBatch.produced_at).toLocaleString('ru'), mono: true },
              { k: 'Выпуск, кг', v: fmtNum(selBatch.quantity_kg, 3), mono: true },
              { k: 'Остаток, кг', v: fmtNum(selBatch.current_quantity_kg, 3), mono: true },
              ...(getFinancesVisible(selBatch) ? [
                {
                  k: (
                    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                      Себестоимость / кг
                      <HelpHint
                        text="Стоимость 1 кг этой партии корма."
                        details={
                          'Считается автоматически при проведении замеса как: '
                          + '(сумма стоимости израсходованного сырья) ÷ выпуск кг. '
                          + 'Эта цена идёт в проводки и в расход на птицу/продажу.'
                        }
                      />
                    </span>
                  ) as unknown as string,
                  v: fmtNum(selBatch.unit_cost_uzs, 2) + ' сум',
                  mono: true,
                },
                { k: 'Сумма', v: fmtNum(selBatch.total_cost_uzs, 0) + ' сум', mono: true },
              ] : []),
              { k: 'Бункер', v: selBatch.storage_bin_code ?? '—', mono: true },
              { k: 'Медикаментозный', v: selBatch.is_medicated ? 'Да' : 'Нет' },
              ...(selBatch.withdrawal_period_ends ? [{
                k: 'Каренция до', v: selBatch.withdrawal_period_ends, mono: true,
              }] : []),
              {
                k: (
                  <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                    Статус партии
                    <HelpHint
                      text="Жизненный цикл партии готового корма."
                      details={
                        '• Произведено — только что выпущено, ждёт проверки.\n'
                        + '• Одобрено — паспорт выпущен, можно расходовать.\n'
                        + '• Отклонено — забраковано лабораторией.\n'
                        + '• Отозвано — изъято из обращения.\n'
                        + '• Исчерпана — весь объём израсходован.'
                      }
                    />
                  </span>
                ) as unknown as string,
                v: selBatch.status,
              },
              {
                k: (
                  <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                    Паспорт качества
                    <HelpHint
                      text="Подтверждение лаборатории что корм безопасен."
                      details={
                        'Перед расходом партия должна получить паспорт качества: лаборатория '
                        + 'проверяет белок/жир/влажность/токсины. Состояния: ожидание (ещё не проверено), '
                        + 'пройдено (всё в норме, можно кормить), не пройдено (есть отклонения, кормить нельзя).'
                      }
                    />
                  </span>
                ) as unknown as string,
                v: selBatch.quality_passport_status,
              },
            ]}
          />

          <ShrinkageWidget
            lotType="production_batch"
            lotId={selBatch.id}
            initialKg={selBatch.quantity_kg}
            unitLabel="кг"
          />
        </DetailDrawer>
        );
      })()}

      {/* ── Modals ─────────────────────────────────────────────────────── */}
      {recipeModalOpen && (
        <RecipeModal
          initial={editingRecipe}
          onClose={() => { setRecipeModalOpen(false); setEditingRecipe(null); }}
        />
      )}
      {executeFor && (
        <ExecuteTaskModal task={executeFor} onClose={() => setExecuteFor(null)} />
      )}
      {taskOpen && <TaskModal onClose={() => setTaskOpen(false)} />}
      {versionFor && (
        <VersionModal
          recipe={versionFor}
          lastNumber={(versions ?? []).filter((v) => v.recipe === versionFor.id).reduce((max, v) => Math.max(max, v.version_number), 0)}
          onClose={() => setVersionFor(null)}
        />
      )}
      {editingVersion && selRecipe && (
        <VersionModal
          recipe={selRecipe}
          initial={editingVersion}
          onClose={() => setEditingVersion(null)}
        />
      )}
      {componentFor && (
        <ComponentModal
          version={componentFor}
          initial={editingComponent}
          onClose={() => { setComponentFor(null); setEditingComponent(null); }}
        />
      )}
      {rawModalOpen && (
        <RawBatchModal
          initial={editingRaw}
          onClose={() => { setRawModalOpen(false); setEditingRaw(null); }}
        />
      )}
    </>
  );
}
