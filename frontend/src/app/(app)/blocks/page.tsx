'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { useProductionBlocks, useDeleteBlock } from '@/hooks/useBlocks';
import { useModules } from '@/hooks/useModules';
import { useHasLevel } from '@/hooks/usePermissions';
import type { BlockKind, ProductionBlock } from '@/types/auth';

import BlockModal from './BlockModal';

const KIND_LABEL: Record<BlockKind, string> = {
  matochnik: 'Корпус маточника',
  incubation: 'Инкубационный шкаф',
  hatcher: 'Выводной шкаф',
  feedlot: 'Птичник откорма',
  slaughter_line: 'Линия разделки',
  warehouse: 'Склад',
  vet_storage: 'Склад ветпрепаратов',
  mixer_line: 'Линия замеса',
  storage_bin: 'Бункер / ёмкость',
  other: 'Прочее',
};

export default function BlocksPage() {
  const { data: modules } = useModules();
  const [moduleId, setModuleId] = useState('');
  const [kind, setKind] = useState('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ProductionBlock | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('core', 'rw');

  const filter = useMemo(
    () => ({
      module: moduleId || undefined,
      kind: kind || undefined,
      search: search || undefined,
    }),
    [moduleId, kind, search],
  );

  const { data, isLoading, error, refetch, isFetching } = useProductionBlocks(filter);
  const del = useDeleteBlock();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
  };

  const handleEdit = (b: ProductionBlock) => {
    setEditing(b);
    setModalOpen(true);
  };

  const handleDelete = (b: ProductionBlock) => {
    if (!confirm(`Удалить блок «${b.name}»?`)) return;
    del.mutate(b.id, {
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  // группировка по модулю
  const groups = useMemo(() => {
    const map = new Map<string, ProductionBlock[]>();
    for (const b of data ?? []) {
      const key = b.module_name ?? b.module_code ?? '—';
      const bucket = map.get(key) ?? [];
      bucket.push(b);
      map.set(key, bucket);
    }
    return map;
  }, [data]);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Блоки</h1>
          <div className="sub">
            Справочник производственных единиц · корпуса, шкафы, птичники, линии, склады
          </div>
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
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                setEditing(null);
                setModalOpen(true);
              }}
            >
              <Icon name="plus" size={14} />
              Новый блок
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select
          className="input"
          value={moduleId}
          onChange={(e) => setModuleId(e.target.value)}
          style={{ width: 200 }}
        >
          <option value="">Все модули</option>
          {modules?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          style={{ width: 220 }}
        >
          <option value="">Все типы</option>
          {(Object.entries(KIND_LABEL) as [BlockKind, string][]).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        <div style={{ flex: 1, minWidth: 200 }}>
          <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              placeholder="Поиск по коду / названию…"
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-secondary btn-sm">
              Найти
            </button>
          </form>
        </div>
      </div>

      {isLoading ? (
        <Panel>
          <div style={{ padding: 24, color: 'var(--fg-3)' }}>Загрузка…</div>
        </Panel>
      ) : error ? (
        <Panel>
          <div style={{ padding: 24, color: 'var(--danger)' }}>
            Ошибка: {error.message}
          </div>
        </Panel>
      ) : !data || data.length === 0 ? (
        <Panel>
          <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
            Нет блоков.{' '}
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setEditing(null);
                setModalOpen(true);
              }}
              style={{ marginLeft: 8 }}
            >
              Создать первый
            </button>
          </div>
        </Panel>
      ) : (
        Array.from(groups.entries()).map(([modName, blocks]) => (
          <Panel key={modName} title={`Модуль: ${modName} · ${blocks.length} блоков`} flush>
            <DataTable<ProductionBlock>
              rows={blocks}
              rowKey={(b) => b.id}
              onRowClick={(b) => handleEdit(b)}
              columns={[
                { key: 'code', label: 'Код',
                  render: (b) => <span className="badge id">{b.code}</span> },
                { key: 'name', label: 'Название', cellStyle: { fontWeight: 500 },
                  render: (b) => b.name },
                { key: 'kind', label: 'Тип',
                  cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                  render: (b) => KIND_LABEL[b.kind] ?? b.kind },
                { key: 'area', label: 'Площадь, м²', align: 'right', mono: true,
                  render: (b) => b.area_m2 ? parseFloat(b.area_m2).toLocaleString('ru-RU') : '—' },
                { key: 'cap', label: 'Ёмкость', align: 'right', mono: true,
                  render: (b) => b.capacity
                    ? `${parseFloat(b.capacity).toLocaleString('ru-RU')}${b.capacity_unit_code ? ' ' + b.capacity_unit_code : ''}`
                    : '—' },
                { key: 'status', label: 'Статус',
                  render: (b) => b.is_active
                    ? <Badge tone="success" dot>Активен</Badge>
                    : <Badge tone="neutral" dot>Отключён</Badge> },
                { key: 'actions', label: '', width: 60, align: 'right',
                  render: (b) => canEdit ? (
                    <RowActions
                      actions={[
                        { label: 'Редактировать', onClick: () => handleEdit(b) },
                        {
                          label: 'Удалить',
                          danger: true,
                          disabled: del.isPending,
                          onClick: () => handleDelete(b),
                        },
                      ]}
                    />
                  ) : null },
              ]}
            />
          </Panel>
        ))
      )}

      {modalOpen && (
        <BlockModal
          initial={editing}
          onClose={() => {
            setModalOpen(false);
            setEditing(null);
          }}
        />
      )}
    </>
  );
}
