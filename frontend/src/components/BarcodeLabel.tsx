'use client';

import { encode128svg } from '@/lib/barcode128';

interface Props {
  barcode: string;
  drugName?: string | null;
  lotNumber?: string | null;
  expirationDate?: string | null;
  moduleWidth?: number;
}

export default function BarcodeLabel({
  barcode,
  drugName,
  lotNumber,
  expirationDate,
  moduleWidth = 2,
}: Props) {
  const svg = encode128svg(barcode, { height: 56, moduleWidth, quiet: 8 });

  return (
    <div style={{
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 6,
      padding: '10px 14px',
      background: '#fff',
      border: '1px solid #E5E7EB',
      borderRadius: 6,
      fontFamily: 'monospace',
    }}>
      {drugName && (
        <div style={{
          fontSize: 11, fontWeight: 700, color: '#111827',
          maxWidth: 240, textAlign: 'center', lineHeight: 1.2,
        }}>
          {drugName}
        </div>
      )}
      <div
        dangerouslySetInnerHTML={{ __html: svg }}
        style={{ lineHeight: 0 }}
      />
      {(lotNumber || expirationDate) && (
        <div style={{ fontSize: 10, color: '#6B7280', textAlign: 'center' }}>
          {lotNumber && <span>Lot: {lotNumber}</span>}
          {lotNumber && expirationDate && <span> · </span>}
          {expirationDate && <span>До: {expirationDate}</span>}
        </div>
      )}
    </div>
  );
}
