import type { Metadata, Viewport } from 'next';
import { Manrope, JetBrains_Mono } from 'next/font/google';
import Script from 'next/script';
import { Suspense } from 'react';

import RouteProgress from '@/components/layout/RouteProgress';
import OfflineIndicator from '@/components/OfflineIndicator';
import ServiceWorkerRegistration from '@/components/ServiceWorkerRegistration';
import TgFrameSync from '@/components/telegram/TgFrameSync';
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
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || 'https://erp.yembro.uz',
  ),
  title: 'YemBro ERP',
  description: 'Учётная система птицеводческого предприятия',
  manifest: '/manifest.webmanifest',
  icons: {
    icon: [
      { url: '/logo.png', type: 'image/png' },
    ],
    shortcut: '/logo.png',
    apple: '/logo.png',
  },
  appleWebApp: {
    capable: true,
    title: 'YemBro',
    statusBarStyle: 'default',
    startupImage: ['/logo.png'],
  },
  // Параллельно с public/googlee98924015a261f40.html — meta-тег как страховка.
  // Search Console принимает любой из методов; meta безопасен при возможной
  // перенастройке прокси на /static/.
  verification: {
    google: 'googlee98924015a261f40',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  themeColor: '#E8751A',
  // viewport-fit=cover нужен чтобы iOS Safari / Telegram WebView пробрасывал
  // env(safe-area-inset-*). Без него в full-screen Mini App статус-бар и
  // home-indicator налезают на UI.
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className={`${manrope.variable} ${jetbrainsMono.variable}`}>
        {/* Telegram WebApp SDK — грузим глобально, чтобы insets можно было
            читать на любой странице (refresh на /dashboard внутри Mini App).
            На не-Telegram страницах SDK ничего не делает. */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="afterInteractive"
        />
        <TgFrameSync />
        <NavigationProvider>
          <Suspense fallback={null}>
            <RouteProgress />
          </Suspense>
          <QueryProvider>{children}</QueryProvider>
          <OfflineIndicator />
          <ServiceWorkerRegistration />
        </NavigationProvider>
      </body>
    </html>
  );
}
