'use client';

import { Suspense, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

import BarcodeLabel from '@/components/BarcodeLabel';

function VetLabelContent() {
  const params = useSearchParams();
  const barcode = params.get('barcode') ?? '';
  const drug    = params.get('drug') ?? undefined;
  const lot     = params.get('lot') ?? undefined;
  const exp     = params.get('exp') ?? undefined;

  useEffect(() => {
    if (barcode) {
      const t = setTimeout(() => window.print(), 400);
      return () => clearTimeout(t);
    }
  }, [barcode]);

  if (!barcode) {
    return (
      <div style={{ padding: 40, fontFamily: 'sans-serif', color: '#EF4444' }}>
        Штрих-код не указан. Откройте страницу через кнопку «Печать этикетки» в вет.аптеке.
      </div>
    );
  }

  return (
    <>
      <style>{`
        @media print {
          @page { margin: 8mm; }
          body { margin: 0; background: #fff; }
          .no-print { display: none !important; }
        }
        body { margin: 0; background: #f9fafb; }
      `}</style>

      <div className="no-print" style={{
        padding: '12px 20px',
        background: '#fff',
        borderBottom: '1px solid #E5E7EB',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <button
          onClick={() => window.print()}
          style={{
            padding: '8px 16px',
            background: '#E8751A',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Печать / Сохранить PDF
        </button>
        <button
          onClick={() => window.close()}
          style={{
            padding: '8px 12px',
            background: 'transparent',
            border: '1px solid #D1D5DB',
            borderRadius: 6,
            fontSize: 13,
            cursor: 'pointer',
            color: '#6B7280',
          }}
        >
          Закрыть
        </button>
        <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 'auto' }}>
          Наклейте этикетку на упаковку препарата
        </span>
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'flex-start',
        padding: '40px 20px',
        minHeight: 'calc(100vh - 60px)',
        background: '#f9fafb',
      }}>
        <BarcodeLabel
          barcode={barcode}
          drugName={drug}
          lotNumber={lot}
          expirationDate={exp}
          moduleWidth={2}
        />
      </div>
    </>
  );
}

/**
 * /print/vet-label?barcode=VET-...&drug=...&lot=...&exp=...
 *
 * Публичная print-страница. Автоматически открывает диалог печати.
 */
export default function VetLabelPrintPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40 }}>Загрузка…</div>}>
      <VetLabelContent />
    </Suspense>
  );
}
