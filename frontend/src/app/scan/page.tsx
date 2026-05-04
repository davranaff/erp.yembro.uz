'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { getSellerLabel, getSellerToken } from '@/lib/sellerApi';


/**
 * /scan — главная сканера. Если в localStorage есть токен — даём поле для ручного
 * ввода barcode (или сканер физически переходит на /scan/<barcode>).
 * Если токена нет — редирект на /scan/login.
 */
export default function ScanIndexPage() {
  const router = useRouter();
  const [barcode, setBarcode] = useState('');
  const [hasToken, setHasToken] = useState<boolean | null>(null);
  const [label, setLabel] = useState('');

  if (hasToken === null && typeof window !== 'undefined') {
    setHasToken(Boolean(getSellerToken()));
    setLabel(getSellerLabel());
  }

  const go = () => {
    const code = barcode.trim();
    if (!code) return;
    router.push(`/scan/${encodeURIComponent(code)}`);
  };

  if (hasToken === false) {
    if (typeof window !== 'undefined') router.push('/scan/login');
    return null;
  }

  return (
    <div style={{
      minHeight: '100vh',
      padding: 20,
      background: '#FFF7ED',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      <div style={{
        maxWidth: 480, width: '100%',
        background: '#fff', borderRadius: 12,
        border: '1px solid #E5E7EB',
        padding: 24,
        boxShadow: '0 4px 12px rgba(0,0,0,.05)',
      }}>
        <h1 style={{ margin: 0, fontSize: 22, color: '#E8751A' }}>
          🐔 Сканер вет.аптеки
        </h1>
        {label && (
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 16 }}>
            {label}
          </div>
        )}

        <p style={{ fontSize: 14, color: '#374151', marginTop: 16 }}>
          Отсканируйте штрих-код препарата — сканер автоматически откроет
          страницу лота. Или введите код вручную:
        </p>

        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && go()}
            placeholder="VET-..."
            style={{
              flex: 1,
              padding: '10px 12px',
              fontSize: 16,
              fontFamily: 'monospace',
              border: '1px solid #D1D5DB',
              borderRadius: 6,
            }}
            autoFocus
          />
          <button
            onClick={go}
            disabled={!barcode.trim()}
            style={{
              padding: '10px 16px',
              background: barcode.trim() ? '#E8751A' : '#D1D5DB',
              color: '#fff', border: 'none',
              borderRadius: 6, fontSize: 14, fontWeight: 600,
              cursor: barcode.trim() ? 'pointer' : 'not-allowed',
            }}
          >
            Открыть
          </button>
        </div>

        <a href="/scan/login" style={{
          display: 'block', textAlign: 'center',
          fontSize: 12, color: '#6B7280',
          textDecoration: 'underline',
        }}>
          Сменить токен
        </a>
      </div>
    </div>
  );
}
