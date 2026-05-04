'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';

import { herdsCrud } from '@/hooks/useMatochnik';

const DIRECTION_LABEL: Record<string, string> = {
  broiler_parent: 'Бройлерное родительское',
  layer_parent: 'Яичное родительское',
};

export default function PlacementActPage() {
  const params = useParams<{ id: string }>();
  const { data: herds } = herdsCrud.useList({});
  const herd = herds?.find((h) => h.id === params.id);

  // Автоматически открыть диалог печати
  useEffect(() => {
    if (herd) {
      const t = setTimeout(() => window.print(), 300);
      return () => clearTimeout(t);
    }
  }, [herd]);

  if (!herd) {
    return (
      <div style={{ padding: 24, fontSize: 14 }}>
        Загрузка данных стада…
      </div>
    );
  }

  const today = new Date().toLocaleDateString('ru-RU');

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
        maxWidth: 800,
        margin: '0 auto',
        fontFamily: 'Times, serif',
        fontSize: 13,
        color: 'black',
      }}>
        <div className="no-print" style={{ marginBottom: 20, display: 'flex', gap: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={() => window.print()}>
            Печать
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => window.close()}>
            Закрыть
          </button>
        </div>

        <div style={{ textAlign: 'center', marginBottom: 30 }}>
          <div style={{ fontSize: 16, fontWeight: 'bold' }}>АКТ ПОСАДКИ СТАДА № {herd.doc_number}</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>от {herd.placed_at}</div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 20 }}>
          <tbody>
            <tr>
              <td style={{ padding: '6px 0', width: '40%' }}>Направление:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {DIRECTION_LABEL[herd.direction] ?? herd.direction}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Корпус:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>{herd.block_code ?? '—'}</td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Дата посадки:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>{herd.placed_at}</td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Возраст при посадке:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {herd.age_weeks_at_placement} недель
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Поголовье:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {herd.initial_heads.toLocaleString('ru-RU')} голов
              </td>
            </tr>
          </tbody>
        </table>

        {herd.notes && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 4 }}>Примечание:</div>
            <div style={{ whiteSpace: 'pre-wrap' }}>{herd.notes}</div>
          </div>
        )}

        <div style={{ marginTop: 60 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 60 }}>
            <div>
              <div style={{ borderTop: '1px solid black', paddingTop: 4, fontSize: 11 }}>
                Технолог
              </div>
              <div style={{ marginTop: 30, borderTop: '1px solid black', paddingTop: 4, fontSize: 11 }}>
                Подпись / дата
              </div>
            </div>
            <div>
              <div style={{ borderTop: '1px solid black', paddingTop: 4, fontSize: 11 }}>
                Принял
              </div>
              <div style={{ marginTop: 30, borderTop: '1px solid black', paddingTop: 4, fontSize: 11 }}>
                Подпись / дата
              </div>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 40, textAlign: 'center', fontSize: 10, color: '#666' }}>
          Документ сформирован {today}
        </div>
      </div>
    </>
  );
}
