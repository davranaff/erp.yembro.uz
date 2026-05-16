'use client';

import { usePathname } from 'next/navigation';

import RequireRouteAccess from '@/components/auth/RequireRouteAccess';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import ScannerIndicator from '@/components/ScannerIndicator';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { LayoutProvider, useLayout } from '@/contexts/LayoutContext';
import { useBarcodeScanner } from '@/hooks/useBarcodeScanner';
import { useTrackRecentPage } from '@/lib/recentPages';

import AuthGuard from './AuthGuard';

const CRUMB_MAP: Record<string, string[]> = {
  '/dashboard':      ['Сводка'],
  '/traceability':   ['Трассировка партий'],
  '/profile':        ['Профиль'],
  '/settings':       ['Настройки'],

  '/counterparties': ['Люди', 'Контрагенты'],
  '/people':         ['Люди', 'Сотрудники'],

  '/accounts':       ['Аналитика', 'План счетов'],

  '/nomenclature':   ['Справочники', 'Номенклатура'],
  '/blocks':         ['Справочники', 'Блоки'],

  '/matochnik':      ['Производство', 'Маточник'],
  '/incubation':     ['Производство', 'Инкубация'],
  '/feed':           ['Обеспечение', 'Корма'],
  '/feedlot':        ['Производство', 'Фабрика откорма'],
  '/slaughter':      ['Производство', 'Убойня'],
  '/transfers':      ['Производство', 'Межмод. передачи'],

  '/vet':            ['Обеспечение', 'Вет. аптека'],

  '/stock':          ['Учёт', 'Склад и движения'],
  '/ledger':         ['Учёт', 'Проводки'],
  '/reports':        ['Учёт', 'Отчёты'],

  '/roles':          ['Администрирование', 'Роли и права'],
  '/audit-log':      ['Администрирование', 'Журнал аудита'],
  '/holding':        ['Администрирование', 'Холдинг'],
};

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { org } = useAuth();
  const { sidebarOpen, closeSidebar } = useLayout();

  // Запоминаем последние посещённые страницы для CommandPalette (⌘K)
  useTrackRecentPage();

  // Глобальный обработчик HID-сканера штрих-кодов: на любой странице
  // сканер ловит код + Enter и роутит на /scan/<barcode>. Не вмешивается
  // в обычный ввод (если фокус в input/textarea/contenteditable).
  const { scannerActive } = useBarcodeScanner();

  const orgLabel = org?.name ?? 'YemBro ERP';
  const tail = CRUMB_MAP[pathname] ?? [];
  const crumbs = [{ label: orgLabel }, ...tail.map((label) => ({ label }))];

  return (
    <div className={'app' + (sidebarOpen ? ' sidebar-open' : '')}>
      {/* Backdrop — рендерится только на мобиле, виден когда drawer открыт */}
      <div
        className="sidebar-backdrop"
        onClick={closeSidebar}
        aria-hidden={!sidebarOpen}
      />
      <Sidebar />
      <div className="main">
        <Topbar crumbs={crumbs} />
        <div className="content">
          <RequireRouteAccess>{children}</RequireRouteAccess>
        </div>
      </div>
      <ScannerIndicator active={scannerActive} />
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGuard>
        <LayoutProvider>
          <Shell>{children}</Shell>
        </LayoutProvider>
      </AuthGuard>
    </AuthProvider>
  );
}
