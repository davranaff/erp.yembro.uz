import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: '404 — Страница не найдена | YemBro ERP',
  description: 'Запрошенная страница не существует.',
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', gap: 16, fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: 48, fontWeight: 700, margin: 0 }}>404</h1>
      <p style={{ color: '#666', margin: 0 }}>Страница не найдена</p>
      <Link href="/" style={{ color: '#E8751A', textDecoration: 'none' }}>
        На главную
      </Link>
    </div>
  );
}
