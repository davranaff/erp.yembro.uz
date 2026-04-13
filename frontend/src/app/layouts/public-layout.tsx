import { type ReactNode } from 'react';
import { Outlet } from 'react-router-dom';

import { LanguageSwitcher } from '@/app/ui/language-switcher';


type PublicLayoutProps = {
  children?: ReactNode;
};

export function PublicLayout({ children }: PublicLayoutProps) {
  return (
    <section className="flex min-h-screen w-full items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
      <div className="fixed right-4 top-4 z-50">
        <LanguageSwitcher compact />
      </div>
      {children ?? <Outlet />}
    </section>
  );
}
