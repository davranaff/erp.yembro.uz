'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';

import { herdMortalityCrud, herdsCrud } from '@/hooks/useMatochnik';

const DIRECTION_LABEL: Record<string, string> = {
  broiler_parent: 'Бройлерное родительское',
  layer_parent: 'Яичное родительское',
};

export default function DepopulationActPage() {
  const params = useParams<{ id: string }>();
  const { data: herds } = herdsCrud.useList({});
  const herd = herds?.find((h) => h.id === params.id);
  const { data: mortality } = herdMortalityCrud.useList(
    herd ? { herd: herd.id } : {},
  );

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

  const lost = herd.initial_heads - herd.current_heads;
  const lostPct = herd.initial_heads > 0
    ? (lost / herd.initial_heads) * 100
    : 0;

  const today = new Date().toLocaleDateString('ru-RU');
  const mortalityTotal = (mortality ?? []).reduce((s, m) => s + m.dead_count, 0);

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
          <div style={{ fontSize: 16, fontWeight: 'bold' }}>АКТ СНЯТИЯ СТАДА № {herd.doc_number}</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>от {today}</div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 20 }}>
          <tbody>
            <tr>
              <td style={{ padding: '6px 0', width: '40%' }}>Стадо:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>{herd.doc_number}</td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Направление:</td>
              <td style={{ padding: '6px 0' }}>
                {DIRECTION_LABEL[herd.direction] ?? herd.direction}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Корпус:</td>
              <td style={{ padding: '6px 0' }}>{herd.block_code ?? '—'}</td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Посажено:</td>
              <td style={{ padding: '6px 0' }}>
                {herd.placed_at}, возраст {herd.age_weeks_at_placement} недель
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Поголовье начальное:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {herd.initial_heads.toLocaleString('ru-RU')} голов
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Поголовье остаток:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {herd.current_heads.toLocaleString('ru-RU')} голов
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>Выбыло всего:</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {lost.toLocaleString('ru-RU')} голов ({lostPct.toFixed(1)}%)
              </td>
            </tr>
            <tr>
              <td style={{ padding: '6px 0' }}>В т.ч. падёж (по журналу):</td>
              <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                {mortalityTotal.toLocaleString('ru-RU')} голов
              </td>
            </tr>
          </tbody>
        </table>

        {mortality && mortality.length > 0 && (
          <div style={{ marginTop: 20, marginBottom: 20 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 8 }}>Журнал падежа:</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid black', padding: 4 }}>Дата</th>
                  <th style={{ textAlign: 'right', borderBottom: '1px solid black', padding: 4 }}>Голов</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid black', padding: 4 }}>Причина</th>
                </tr>
              </thead>
              <tbody>
                {mortality.slice(0, 30).map((m) => (
                  <tr key={m.id}>
                    <td style={{ padding: 4 }}>{m.date}</td>
                    <td style={{ padding: 4, textAlign: 'right' }}>{m.dead_count}</td>
                    <td style={{ padding: 4 }}>{m.cause || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
