'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  clearSellerToken,
  getSellerLabel,
  getSellerToken,
  setSellerToken,
} from '@/lib/sellerApi';


export default function ScanLoginPage() {
  const router = useRouter();
  const [tok, setTok] = useState('');
  const [label, setLabel] = useState('');
  const [hasExisting, setHasExisting] = useState(false);
  const [existingLabel, setExistingLabel] = useState('');

  useEffect(() => {
    const existing = getSellerToken();
    if (existing) {
      setHasExisting(true);
      setExistingLabel(getSellerLabel());
    }
  }, []);

  const submit = () => {
    const trimmed = tok.trim();
    if (!trimmed) return;
    setSellerToken(trimmed, label.trim());
    alert('Токен сохранён. Сканируйте штрих-код препарата.');
    router.push('/scan');
  };

  const logout = () => {
    if (!confirm('Удалить сохранённый токен с этого устройства?')) return;
    clearSellerToken();
    setHasExisting(false);
    setExistingLabel('');
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20,
      background: '#FFF7ED',
    }}>
      <div style={{
        maxWidth: 420, width: '100%',
        background: '#fff', borderRadius: 12,
        border: '1px solid #E5E7EB',
        padding: 24,
        boxShadow: '0 4px 12px rgba(0,0,0,.05)',
      }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: '#E8751A' }}>
          🐔 Сканер вет.аптеки
        </h1>
        <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 20 }}>
          Введите токен продавца, выданный администратором.
        </p>

        {hasExisting && (
          <div style={{
            background: '#ECFDF5',
            border: '1px solid #10B981',
            borderRadius: 8,
            padding: 12, marginBottom: 16,
            fontSize: 13,
          }}>
            ✓ Токен уже сохранён
            {existingLabel && <strong> ({existingLabel})</strong>}
            . Можно сразу сканировать.
            <button
              onClick={logout}
              style={{
                display: 'block',
                marginTop: 8,
                background: 'none', border: 'none',
                color: '#EF4444', fontSize: 12, cursor: 'pointer',
                padding: 0,
              }}
            >
              Удалить токен с устройства
            </button>
          </div>
        )}

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
            Токен *
          </label>
          <input
            type="password"
            value={tok}
            onChange={(e) => setTok(e.target.value)}
            placeholder="вставьте токен сюда"
            style={{
              width: '100%',
              padding: '10px 12px',
              fontSize: 16,
              fontFamily: 'monospace',
              border: '1px solid #D1D5DB',
              borderRadius: 6,
            }}
            autoFocus
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
            Метка устройства (опц.)
          </label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Магазин Юнусабад"
            style={{
              width: '100%',
              padding: '10px 12px',
              fontSize: 14,
              border: '1px solid #D1D5DB',
              borderRadius: 6,
            }}
          />
        </div>

        <button
          onClick={submit}
          disabled={!tok.trim()}
          style={{
            width: '100%',
            padding: '12px 16px',
            background: tok.trim() ? '#E8751A' : '#D1D5DB',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            fontSize: 15,
            fontWeight: 600,
            cursor: tok.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          Сохранить и сканировать
        </button>

        <p style={{
          fontSize: 11, color: '#9CA3AF', marginTop: 16, marginBottom: 0,
          textAlign: 'center',
        }}>
          Токен хранится только на этом устройстве (localStorage).
        </p>
      </div>
    </div>
  );
}
