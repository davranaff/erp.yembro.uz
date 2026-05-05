'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import TablePagination from '@/components/ui/TablePagination';
import { useModules } from '@/hooks/useModules';
import {
  useCategories,
  useDeleteItem,
  useNomenclatureItemsPaginated,
} from '@/hooks/useNomenclature';
import { useHasLevel } from '@/hooks/usePermissions';
import type { Category, NomenclatureItem } from '@/types/auth';

import NomenclatureModal from './NomenclatureModal';

export default function NomenclaturePage() {
  const searchParams = useSearchParams();
  // Дефолт модуля можно передать через ?module_code=vet (например, ссылка
  // из vet-аптеки сразу скоупит на ветпрепараты).
  const [moduleCode, setModuleCode] = useState(searchParams.get('module_code') ?? '');
  const [categoryId, setCategoryId] = useState('');
  const [search, setSearch] = useState('');
  const [draftSearch, setDraftSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sel, setSel] = useState<NomenclatureItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<NomenclatureItem | null>(null);

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('core', 'rw');

  const filter = useMemo(
    () => ({
      category: categoryId || undefined,
      module_code: moduleCode || undefined,
      search: search || undefined,
    }),
    [categoryId, moduleCode, search],
  );

  const { data: pageData, isLoading, error, refetch, isFetching } = useNomenclatureItemsPaginated(filter, page, pageSize);
  const items = pageData?.results ?? [];
  // Категории фильтруются по выбранному модулю — иначе в выпадашке
  // «Все категории» попадаются категории других модулей.
  const { data: categories } = useCategories(moduleCode ? { module_code: moduleCode } : {});
  const { data: modules } = useModules();

  // При смене модуля сбрасываем категорию (она могла принадлежать другому).
  useEffect(() => {
    setCategoryId('');
    setPage(1);
  }, [moduleCode]);
  const del = useDeleteItem();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
  };

  const handleEdit = (it: NomenclatureItem) => {
    setEditing(it);
    setModalOpen(true);
  };

  const handleDelete = (it: NomenclatureItem) => {
    if (!confirm(`Удалить «${it.name}»?`)) return;
    del.mutate(it.id, {
      onSuccess: () => {
        if (sel?.id === it.id) setSel(null);
      },
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  // Группировка по категории (названию). На текущей странице.
  const groups = useMemo<Map<string, { cat: Category | null; items: NomenclatureItem[] }>>(() => {
    const map = new Map<string, { cat: Category | null; items: NomenclatureItem[] }>();
    if (!items) return map;
    const catById = new Map((categories ?? []).map((c) => [c.id, c] as const));
    for (const it of items) {
      const cat = catById.get(it.category) ?? null;
      const key = cat?.name ?? it.category_name ?? 'Без категории';
      const bucket = map.get(key) ?? { cat, items: [] };
      bucket.items.push(it);
      map.set(key, bucket);
    }
    return map;
  }, [items, categories]);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Номенклатура</h1>
          <div className="sub">Справочник номенклатуры компании · иерархия по категориям</div>
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
              Новая позиция
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select
          className="input"
          value={moduleCode}
          onChange={(e) => setModuleCode(e.target.value)}
          style={{ width: 200 }}
          title="Модуль"
        >
          <option value="">Все модули</option>
          {modules?.filter((m) => m.is_active).map((m) => (
            <option key={m.id} value={m.code}>
              {m.name}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={categoryId}
          onChange={(e) => { setCategoryId(e.target.value); setPage(1); }}
          style={{ width: 240 }}
        >
          <option value="">Все категории{moduleCode ? ` (${moduleCode})` : ''}</option>
          {categories?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <div style={{ flex: 1, minWidth: 200 }}>
          <form onSubmit={submitSearch} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              placeholder="Поиск по SKU / названию / штрих-коду…"
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
      ) : !items || items.length === 0 ? (
        <Panel>
          <div style={{ padding: 24, color: 'var(--fg-3)', textAlign: 'center' }}>
            Нет позиций.{' '}
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setEditing(null);
                setModalOpen(true);
              }}
              style={{ marginLeft: 8 }}
            >
              Создать первую
            </button>
          </div>
        </Panel>
      ) : (
        <>
        {Array.from(groups.entries()).map(([catName, bucket]) => (
          <Panel key={catName} title={`${catName} · ${bucket.items.length}`} flush>
            <DataTable<NomenclatureItem>
              rows={bucket.items}
              rowKey={(it) => it.id}
              onRowClick={(it) => setSel(it)}
              rowProps={(it) => ({ active: sel?.id === it.id })}
              columns={[
                { key: 'sku', label: 'Артикул',
                  render: (it) => <span className="badge id">{it.sku}</span> },
                { key: 'name', label: 'Наименование', cellStyle: { fontWeight: 500 },
                  render: (it) => it.name },
                { key: 'unit', label: 'Ед. изм.', mono: true,
                  cellStyle: { fontSize: 12, color: 'var(--fg-2)' },
                  render: (it) => it.unit_code ?? '—' },
                { key: 'barcode', label: 'Штрих-код', mono: true,
                  cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                  render: (it) => it.barcode || '—' },
                { key: 'status', label: 'Статус',
                  render: (it) => it.is_active
                    ? <Badge tone="success" dot>Активна</Badge>
                    : <Badge tone="neutral" dot>Архивная</Badge> },
                { key: 'actions', label: '', width: 60, align: 'right',
                  render: (it) => canEdit ? (
                    <RowActions
                      actions={[
                        { label: 'Редактировать', onClick: () => handleEdit(it) },
                        {
                          label: 'Удалить',
                          danger: true,
                          disabled: del.isPending,
                          onClick: () => handleDelete(it),
                        },
                      ]}
                    />
                  ) : null },
              ]}
            />
          </Panel>
        ))}
        {pageData && (
          <Panel flush>
            <TablePagination
              page={page}
              pageSize={pageSize}
              count={pageData.count}
              hasPrev={Boolean(pageData.previous)}
              hasNext={Boolean(pageData.next)}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          </Panel>
        )}
        </>
      )}

      {sel && (
        <DetailDrawer
          title={sel.name}
          subtitle={`Артикул ${sel.sku} · категория ${sel.category_name ?? '—'}`}
          onClose={() => setSel(null)}
          actions={
            canEdit ? (
              <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(sel)}>
                Редактировать
              </button>
            ) : null
          }
        >
          <KV
            items={[
              { k: 'SKU', v: sel.sku, mono: true },
              { k: 'Ед. измерения', v: sel.unit_code ?? '—', mono: true },
              { k: 'Категория', v: sel.category_name ?? '—' },
              { k: 'Штрих-код', v: sel.barcode || '—', mono: true },
              {
                k: 'Субсчёт учёта',
                v: sel.default_gl_subaccount_code ?? '— (по категории)',
                mono: true,
              },
              {
                k: 'Статус',
                v: sel.is_active ? (
                  <Badge tone="success" dot>Активна</Badge>
                ) : (
                  <Badge tone="neutral" dot>Архивная</Badge>
                ),
              },
              ...(sel.notes ? [{ k: 'Примечание', v: sel.notes }] : []),
            ]}
          />
        </DetailDrawer>
      )}

      {modalOpen && (
        <NomenclatureModal
          initial={editing}
          onClose={() => {
            setModalOpen(false);
            setEditing(null);
          }}
          onSaved={(it) => {
            if (sel?.id === it.id) setSel(it);
          }}
        />
      )}
    </>
  );
}
