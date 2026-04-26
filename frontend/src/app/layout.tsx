import type { Metadata, Viewport } from 'next';
import { Manrope, JetBrains_Mono } from 'next/font/google';
import { Suspense } from 'react';

import RouteProgress from '@/components/layout/RouteProgress';
import { NavigationProvider } from '@/contexts/NavigationContext';
import QueryProvider from '@/providers/QueryProvider';

import './globals.css';

const manrope = Manrope({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-manrope',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'YemBro ERP',
  description: 'Учётная система птицеводческого предприятия',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className={`${manrope.variable} ${jetbrainsMono.variable}`}>
        <NavigationProvider>
          <Suspense fallback={null}>
            <RouteProgress />
          </Suspense>
          <QueryProvider>{children}</QueryProvider>
        </NavigationProvider>
      </body>
    </html>
  );
}
