import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, RefreshCw, Search, Users } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { cn } from '@/lib/cn';
import { getClient, listClients, updateClient, type Client } from '@/shared/api/clients';
import { useI18n } from '@/shared/i18n/i18n';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { EmptyState } from '@/shared/ui/empty-state';
import { Input } from '@/shared/ui/input';
import { Kbd } from '@/shared/ui/kbd';
import { Label } from '@/shared/ui/label';
import { Spinner } from '@/shared/ui/spinner';
import { useToast } from '@/shared/ui/toast';

import { TopBar } from '../shell/top-bar';

export function ClientsPage() {
  const { t } = useI18n();
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(search.trim()), 180);
    return () => clearTimeout(handle);
  }, [search]);

  const query = useQuery({
    queryKey: ['clients', debounced],
    queryFn: () => listClients({ search: debounced || undefined, limit: 100 }),
  });

  const items = query.data?.items ?? [];

  useEffect(() => {
    if (!selectedId && items[0]) setSelectedId(items[0].id);
    if (selectedId && !items.some((item) => item.id === selectedId) && items[0]) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLElement) {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
      }
      if (items.length === 0) return;
      const currentIndex = Math.max(0, items.findIndex((i) => i.id === selectedId));
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        const next = items[Math.min(currentIndex + 1, items.length - 1)];
        if (next) setSelectedId(next.id);
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        const next = items[Math.max(currentIndex - 1, 0)];
        if (next) setSelectedId(next.id);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [items, selectedId]);

  return (
    <>
      <TopBar
        title={t('clients.title')}
        right={
          <>
            <Button variant="ghost" size="sm" onClick={() => query.refetch()} title={t('common.refresh')}>
              <RefreshCw className={cn('h-3 w-3', query.isFetching && 'animate-spin')} />
            </Button>
            <Button variant="primary" size="sm">
              <Plus className="h-3 w-3" />
              <span>{t('common.create')}</span>
            </Button>
          </>
        }
      />

      <div className="flex min-h-0 flex-1">
        <div className="flex w-[420px] min-w-0 flex-col border-r border-line">
          <div className="flex h-10 shrink-0 items-center gap-2 border-b border-line bg-bg-subtle/50 px-3">
            <Search className="h-3 w-3 text-ink-muted" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('clients.search')}
              className="h-7 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
            <div className="flex items-center gap-1 text-2xs text-ink-muted">
              <Kbd>j</Kbd>
              <Kbd>k</Kbd>
            </div>
          </div>

          <div ref={listRef} className="flex-1 overflow-y-auto">
            {query.isLoading ? (
              <div className="flex items-center justify-center py-10 text-xs text-ink-muted">
                <Spinner />
              </div>
            ) : items.length === 0 ? (
              <EmptyState icon={Users} title={t('clients.empty')} />
            ) : (
              items.map((client) => (
                <ClientRow
                  key={client.id}
                  client={client}
                  selected={selectedId === client.id}
                  onSelect={() => setSelectedId(client.id)}
                />
              ))
            )}
          </div>

          <div className="flex h-8 shrink-0 items-center justify-between border-t border-line bg-bg-subtle/30 px-3 text-2xs text-ink-muted">
            <span>
              {items.length} / {query.data?.total ?? items.length}
            </span>
            <span className="flex items-center gap-1">
              <span>Нав.</span>
              <Kbd>j</Kbd>
              <Kbd>k</Kbd>
            </span>
          </div>
        </div>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {selectedId ? (
            <ClientInspector clientId={selectedId} />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState icon={Users} title={t('clients.inspector.none')} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function ClientRow({
  client,
  selected,
  onSelect,
}: {
  client: Client;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex w-full items-center gap-3 border-b border-line-soft px-3 py-2 text-left transition-colors',
        selected ? 'bg-bg-inset' : 'hover:bg-bg-subtle/50',
      )}
    >
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-bg-subtle font-mono text-2xs uppercase text-ink-soft">
        {(client.name ?? '?').slice(0, 2)}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm text-ink">{client.name || '—'}</span>
          {client.client_type ? <Badge tone="neutral">{client.client_type}</Badge> : null}
        </div>
        <div className="flex items-center gap-2 text-2xs text-ink-muted">
          {client.phone ? <span className="font-mono">{client.phone}</span> : null}
          {client.email ? <span className="truncate">{client.email}</span> : null}
        </div>
      </div>
    </button>
  );
}

function ClientInspector({ clientId }: { clientId: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ['clients', 'detail', clientId], queryFn: () => getClient(clientId) });
  const [draft, setDraft] = useState<Partial<Client> | null>(null);

  useEffect(() => {
    setDraft(null);
  }, [clientId]);

  const effective = useMemo<Partial<Client> | undefined>(
    () => (draft ? { ...query.data, ...draft } : query.data),
    [draft, query.data],
  );

  const updateMutation = useMutation({
    mutationFn: (patch: Partial<Client>) => updateClient(clientId, patch),
    onSuccess: (data) => {
      qc.setQueryData(['clients', 'detail', clientId], data);
      qc.invalidateQueries({ queryKey: ['clients'] });
      toast.push({ title: 'Сохранено', tone: 'ok' });
      setDraft(null);
    },
    onError: (error: Error) => {
      toast.push({ title: t('common.error'), description: error.message, tone: 'danger' });
    },
  });

  if (query.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!effective) return null;

  const setField = (key: keyof Client, value: string) => {
    setDraft((prev) => ({ ...(prev ?? {}), [key]: value }));
  };

  const hasChanges = Boolean(draft && Object.keys(draft).length > 0);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line bg-bg-subtle/50 px-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink font-mono text-2xs uppercase text-ink-invert">
            {(effective.name ?? '?').slice(0, 2)}
          </div>
          <div className="truncate text-sm font-medium">{effective.name || '—'}</div>
          {effective.is_active ? (
            <Badge tone="ok">active</Badge>
          ) : (
            <Badge tone="neutral">inactive</Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          {hasChanges ? (
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
              {t('common.cancel')}
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="primary"
            disabled={!hasChanges || updateMutation.isPending}
            onClick={() => draft && updateMutation.mutate(draft)}
          >
            {updateMutation.isPending ? <Spinner /> : null}
            <span>{t('common.save')}</span>
          </Button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field
            label={t('clients.column.name')}
            value={effective.name ?? ''}
            onChange={(v) => setField('name', v)}
          />
          <Field
            label={t('clients.column.phone')}
            value={effective.phone ?? ''}
            onChange={(v) => setField('phone', v)}
          />
          <Field
            label={t('clients.column.email')}
            value={effective.email ?? ''}
            onChange={(v) => setField('email', v)}
          />
          <Field
            label="ИНН"
            value={effective.inn ?? ''}
            onChange={(v) => setField('inn', v)}
          />
          <Field
            label="Адрес"
            value={effective.address ?? ''}
            onChange={(v) => setField('address', v)}
            className="sm:col-span-2"
          />
          <Field
            label="Заметки"
            value={effective.notes ?? ''}
            onChange={(v) => setField('notes', v)}
            className="sm:col-span-2"
            multiline
          />
        </section>

        <section className="rounded-md border border-line bg-bg-surface">
          <div className="border-b border-line px-3 py-2 text-2xs uppercase tracking-wide text-ink-muted">
            Метаданные
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 px-3 py-2 font-mono text-2xs">
            <dt className="text-ink-muted">ID</dt>
            <dd className="truncate text-ink-soft">{effective.id}</dd>
            <dt className="text-ink-muted">Создан</dt>
            <dd className="text-ink-soft">{effective.created_at ?? '—'}</dd>
            <dt className="text-ink-muted">Обновлён</dt>
            <dd className="text-ink-soft">{effective.updated_at ?? '—'}</dd>
          </dl>
        </section>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  className,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  multiline?: boolean;
}) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label>{label}</Label>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className={cn(
            'w-full rounded border border-line bg-bg-subtle px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-faint',
            'transition-colors hover:border-line-strong focus:border-accent',
          )}
        />
      ) : (
        <Input value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  );
}
