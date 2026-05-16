'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import Icon from '@/components/ui/Icon';
import { useDashboardSummary } from '@/hooks/useDashboard';

import PurchaseOrderModal from '../purchases/PurchaseOrderModal';
import ModuleSection from './ModuleSection';

function formatPeriod(from: string, to: string): string {
  const f = new Date(from);
  const t = new Date(to);
  const sameMonth = f.getMonth() === t.getMonth() && f.getFullYear() === t.getFullYear();
  if (sameMonth) {
    return `${f.getDate()}–${t.getDate()} ${t.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' })}`;
  }
  return `${f.toLocaleDateString('ru-RU')} – ${t.toLocaleDateString('ru-RU')}`;
}

export default function DashboardPage() {
  const router = useRouter();
  const [purchaseModalOpen, setPurchaseModalOpen] = useState(false);

  const { data: summary, isLoading, error, refetch, isFetching } = useDashboardSummary();

  const prefetch = (path: string) => () => router.prefetch(path);

  if (isLoading) {
    return (
      <>
        <div className="page-hdr">
          <div>
            <h1>Сводка</h1>
            <div className="sub">Загрузка показателей…</div>
          </div>
        </div>
      </>
    );
  }

  if (error || !summary) {
    return (
      <>
        <div className="page-hdr">
          <div>
            <h1>Сводка</h1>
          </div>
        </div>
        <div style={{ padding: 24, color: 'var(--danger)', fontSize: 13 }}>
          Ошибка загрузки: {error?.message ?? 'нет данных'}
        </div>
      </>
    );
  }

  const k = summary.kpis;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Сводка</h1>
          <div className="sub">
            Финансы и производство · период {formatPeriod(k.period.from, k.period.to)}
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
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setPurchaseModalOpen(true)}
            onMouseEnter={prefetch('/purchases')}
          >
            <Icon name="plus" size={14} /> Новый закуп
          </button>
        </div>
      </div>

      {/* ───── Per-module sections — видны по правам доступа к модулю ───── */}
      {summary.module_kassas?.map((mk) => (
        <ModuleSection
          key={mk.module_code}
          moduleCode={mk.module_code}
          moduleName={mk.module_name}
        />
      ))}

      {purchaseModalOpen && (
        <PurchaseOrderModal onClose={() => setPurchaseModalOpen(false)} />
      )}
    </>
  );
}

