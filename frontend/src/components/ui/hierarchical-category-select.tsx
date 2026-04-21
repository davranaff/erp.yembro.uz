'use client';

import { Check, ChevronDown, LoaderCircle } from 'lucide-react';
import { useCallback, useDeferredValue, useMemo, useState } from 'react';

import { listCrudRecords, type CrudRecord } from '@/shared/api/backend-crud';
import { toQueryKey } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from './command';
import { ErrorNotice } from './error-notice';
import { Popover, PopoverContent, PopoverTrigger } from './popover';

interface HierarchicalCategorySelectProps {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
  /**
   * Only categories matching this flow_type are shown (plus their parents).
   * Undefined = show all.
   */
  flowType?: 'income' | 'expense';
}

interface CategoryNode {
  id: string;
  name: string;
  code: string;
  parentId: string | null;
  flowType: string;
  isActive: boolean;
  children: CategoryNode[];
  depth: number;
}

function buildCategoryTree(records: CrudRecord[]): CategoryNode[] {
  const byId = new Map<string, CategoryNode>();
  for (const row of records) {
    const id = String(row.id ?? '').trim();
    if (!id) {
      continue;
    }
    byId.set(id, {
      id,
      name: String(row.name ?? '').trim() || id,
      code: String(row.code ?? '').trim(),
      parentId: row.parent_id ? String(row.parent_id) : null,
      flowType: String(row.flow_type ?? 'expense'),
      isActive: row.is_active !== false,
      children: [],
      depth: 0,
    });
  }

  const roots: CategoryNode[] = [];
  byId.forEach((node) => {
    if (node.parentId && byId.has(node.parentId)) {
      byId.get(node.parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  const sortBy = (a: CategoryNode, b: CategoryNode) => a.name.localeCompare(b.name, 'ru');
  const assignDepth = (node: CategoryNode, depth: number) => {
    node.depth = depth;
    node.children.sort(sortBy);
    for (const child of node.children) {
      assignDepth(child, depth + 1);
    }
  };
  roots.sort(sortBy);
  roots.forEach((root) => assignDepth(root, 0));
  return roots;
}

function flattenTree(
  nodes: CategoryNode[],
  flowType: 'income' | 'expense' | undefined,
  searchLower: string,
): Array<{ node: CategoryNode; isLeaf: boolean }> {
  const out: Array<{ node: CategoryNode; isLeaf: boolean }> = [];
  const matchesFlow = (n: CategoryNode): boolean =>
    flowType === undefined || n.flowType === flowType;

  const matchesSearch = (n: CategoryNode): boolean => {
    if (!searchLower) {
      return true;
    }
    return n.name.toLowerCase().includes(searchLower) || n.code.toLowerCase().includes(searchLower);
  };

  const visit = (node: CategoryNode, inFlow: boolean, parentMatchesSearch: boolean) => {
    const isLeaf = node.children.length === 0;
    const flowOk = inFlow || matchesFlow(node);
    const searchOk = parentMatchesSearch || matchesSearch(node);
    const shouldInclude = flowOk && searchOk && node.isActive;
    const selfHasLeafHit = node.children.some((child) =>
      subtreeHasHit(child, flowType, searchLower),
    );
    if (shouldInclude || selfHasLeafHit) {
      out.push({ node, isLeaf });
      for (const child of node.children) {
        visit(child, flowOk, searchOk);
      }
    }
  };

  const subtreeHasHit = (
    node: CategoryNode,
    ft: 'income' | 'expense' | undefined,
    lower: string,
  ): boolean => {
    const flowOk = ft === undefined || node.flowType === ft;
    const searchOk = !lower || matchesSearch(node);
    if (flowOk && searchOk && node.isActive) {
      return true;
    }
    return node.children.some((c) => subtreeHasHit(c, ft, lower));
  };

  for (const root of nodes) {
    visit(root, false, false);
  }
  return out;
}

export function HierarchicalCategorySelect({
  value,
  onChange,
  disabled,
  className,
  placeholder,
  flowType,
}: HierarchicalCategorySelectProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search);

  const query = useApiQuery({
    queryKey: toQueryKey('crud', 'reference-tree', 'finance', 'expense-categories'),
    queryFn: () => listCrudRecords('finance', 'expense-categories', { limit: 500, offset: 0 }),
    enabled: open,
    staleTime: 60_000,
  });

  const records = useMemo(() => query.data?.items ?? [], [query.data]);
  const tree = useMemo(() => buildCategoryTree(records), [records]);
  const flat = useMemo(
    () => flattenTree(tree, flowType, deferredSearch.trim().toLowerCase()),
    [tree, flowType, deferredSearch],
  );

  const selectedNode = useMemo(() => {
    if (!value) {
      return null;
    }
    return records.find((row) => String(row.id) === value) ?? null;
  }, [records, value]);

  const triggerLabel = useMemo(() => {
    if (selectedNode) {
      return String(selectedNode.name ?? '').trim() || String(selectedNode.id ?? '');
    }
    if (value) {
      return value;
    }
    return placeholder ?? t('common.chooseValue');
  }, [selectedNode, value, placeholder, t]);

  const handlePick = useCallback(
    (node: CategoryNode) => {
      if (node.children.length > 0) {
        return;
      } // non-leaf, ignore
      onChange(node.id);
      setOpen(false);
      setSearch('');
    },
    [onChange],
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={disabled}
        className={cn(
          'inline-flex h-10 w-full items-center justify-between rounded-2xl border border-border/75 bg-card px-3 py-2 text-left text-sm font-normal shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
          !value && 'text-muted-foreground',
          className,
        )}
      >
        <span className="truncate">{triggerLabel}</span>
        <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent className="w-[min(420px,92vw)] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder={t('common.search', undefined, 'Поиск')}
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {query.isLoading ? (
              <div className="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                {t('common.loading', undefined, 'Загрузка...')}
              </div>
            ) : query.error ? (
              <div className="px-3 py-4">
                <ErrorNotice error={query.error} />
              </div>
            ) : flat.length === 0 ? (
              <CommandEmpty>
                {t('crud.referenceNoOptions', undefined, 'Подходящие варианты не найдены.')}
              </CommandEmpty>
            ) : (
              <CommandGroup>
                {flat.map(({ node, isLeaf }) => (
                  <CommandItem
                    key={node.id}
                    value={`${node.name} ${node.code}`}
                    disabled={!isLeaf}
                    onSelect={() => handlePick(node)}
                    className={cn('flex items-center', !isLeaf && 'cursor-default opacity-60')}
                  >
                    <span
                      className="inline-block"
                      style={{ paddingLeft: `${node.depth * 14}px` }}
                    />
                    <span className={cn('truncate', !isLeaf && 'font-semibold text-foreground')}>
                      {node.name}
                    </span>
                    {node.code ? (
                      <span className="ml-2 text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                        {node.code}
                      </span>
                    ) : null}
                    {isLeaf && value === node.id ? (
                      <Check className="ml-auto h-4 w-4 text-primary" />
                    ) : null}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
