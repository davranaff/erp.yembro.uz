'use client';

import { useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';

import { feedBatchesCrud, recipesCrud, recipeVersionsCrud, tasksCrud } from '@/hooks/useFeed';

function fmt(v: string | null | undefined, digits = 2): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

export default function FeedBatchActPage() {
  const params = useParams<{ batchId: string }>();
  const { data: batches } = feedBatchesCrud.useList({});
  const { data: tasks } = tasksCrud.useList({});
  const { data: versions } = recipeVersionsCrud.useList({});
  const { data: recipes } = recipesCrud.useList({});

  const batch = batches?.find((b) => b.id === params.batchId);
  const task = useMemo(
    () => tasks?.find((t) => t.id === batch?.produced_by_task),
    [tasks, batch],
  );
  const version = useMemo(
    () => versions?.find((v) => v.id === batch?.recipe_version),
    [versions, batch],
  );
  const recipe = useMemo(
    () => recipes?.find((r) => r.id === version?.recipe),
    [recipes, version],
  );

  useEffect(() => {
    if (batch) {
      const t = setTimeout(() => window.print(), 400);
      return () => clearTimeout(t);
    }
  }, [batch]);

  if (!batch) {
    return <div style={{ padding: 24 }}>Загрузка партии…</div>;
  }

  return (
    <>
      <style jsx global>{`
        @media print {
          .sidebar, .page-hdr, .no-print, header, nav { display: none !important; }
          body { background: white !important; }
          main { margin: 0 !important; padding: 0 !important; max-width: 100% !important; }
        }
      `}</style>

      <div style={{
        background: 'white',
        padding: '40px 60px',
        maxWidth: 820,
        margin: '0 auto',
        fontFamily: 'Times, serif',
        fontSize: 13,
        color: 'black',
      }}>
        <div className="no-print" style={{ marginBottom: 20, display: 'flex', gap: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={() => window.print()}>Печать</button>
          <button className="btn btn-ghost btn-sm" onClick={() => window.close()}>Закрыть</button>
        </div>

        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 16, fontWeight: 'bold' }}>
            АКТ О ВЫРАБОТКЕ КОМБИКОРМА № {batch.doc_number}
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            от {new Date(batch.produced_at).toLocaleDateString('ru-RU')}
          </div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 20 }}>
          <tbody>
            <tr>
              <td style={{ padding: '6px 0', width: '40%' }}>Рецептура:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {recipe ? `${recipe.code} · ${recipe.name}` : (batch.recipe_code ?? '—')}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Версия рецепта:</td>
              <td style={{ padding: '6px 0' }}>
                v{version?.version_number ?? '—'}
                {version?.effective_from ? ` (от ${version.effective_from})` : ''}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Задание на замес:</td>
              <td style={{ padding: '6px 0', fontFamily: 'monospace' }}>
                {task?.doc_number ?? '—'}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Бункер хранения:</td>
              <td style={{ padding: '6px 0' }}>{batch.storage_bin_code ?? '—'}</td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Медикаментозный:</td>
              <td style={{ padding: '6px 0' }}>
                {batch.is_medicated ? `Да (каренция ${batch.withdrawal_period_days} дн)` : 'Нет'}
              </td>
            </tr>
          </tbody>
        </table>

        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>Показатели партии</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 20, fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid black', fontWeight: 'bold' }}>
              <td style={{ padding: '6px 4px' }}>Показатель</td>
              <td style={{ padding: '6px 4px', textAlign: 'right' }}>Значение</td>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ padding: '4px' }}>План замеса, кг</td>
              <td style={{ padding: '4px', textAlign: 'right', fontFamily: 'monospace' }}>
                {fmt(task?.planned_quantity_kg, 0)}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '4px' }}>Фактический выпуск, кг</td>
              <td style={{ padding: '4px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 'bold' }}>
                {fmt(batch.quantity_kg, 0)}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '4px' }}>Себестоимость, всего</td>
              <td style={{ padding: '4px', textAlign: 'right', fontFamily: 'monospace' }}>
                {fmt(batch.total_cost_uzs, 0)} сум
              </td>
            </tr>
            <tr>
              <td style={{ padding: '4px' }}>Себестоимость единицы, сум/кг</td>
              <td style={{ padding: '4px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 'bold' }}>
                {fmt(batch.unit_cost_uzs, 2)}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '4px' }}>Паспорт качества</td>
              <td style={{ padding: '4px', textAlign: 'right' }}>
                {batch.quality_passport_status}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '4px' }}>Статус партии</td>
              <td style={{ padding: '4px', textAlign: 'right' }}>{batch.status}</td>
            </tr>
          </tbody>
        </table>

        <div style={{ marginTop: 60, display: 'flex', justifyContent: 'space-between', gap: 40 }}>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ borderBottom: '1px solid black', height: 30 }} />
            <div style={{ fontSize: 11, marginTop: 4 }}>Технолог</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ borderBottom: '1px solid black', height: 30 }} />
            <div style={{ fontSize: 11, marginTop: 4 }}>Оператор линии</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ borderBottom: '1px solid black', height: 30 }} />
            <div style={{ fontSize: 11, marginTop: 4 }}>Лаборант</div>
          </div>
        </div>
      </div>
    </>
  );
}
