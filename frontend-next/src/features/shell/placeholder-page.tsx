import { Sparkles } from 'lucide-react';

import { EmptyState } from '@/shared/ui/empty-state';

import { TopBar } from './top-bar';

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <TopBar title={title} />
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          icon={Sparkles}
          title="Скоро"
          description="Эта часть будет перенесена в ходе миграции на новый UX."
        />
      </div>
    </>
  );
}
