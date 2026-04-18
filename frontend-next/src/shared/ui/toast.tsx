import * as ToastPrimitive from '@radix-ui/react-toast';
import { X } from 'lucide-react';
import { createContext, useContext, useMemo, useState } from 'react';

import { cn } from '@/lib/cn';

type Tone = 'default' | 'danger' | 'ok';

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: Tone;
}

interface ToastContextValue {
  push: (toast: Omit<ToastItem, 'id'> & { tone?: Tone }) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const value = useMemo<ToastContextValue>(
    () => ({
      push: ({ title, description, tone = 'default' }) => {
        const id = nextId++;
        setItems((list) => [...list, { id, title, description, tone }]);
        setTimeout(() => {
          setItems((list) => list.filter((i) => i.id !== id));
        }, 5000);
      },
    }),
    [],
  );

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider swipeDirection="right" duration={5000}>
        {children}
        {items.map((item) => (
          <ToastPrimitive.Root
            key={item.id}
            open
            onOpenChange={(open) => {
              if (!open) setItems((list) => list.filter((i) => i.id !== item.id));
            }}
            className={cn(
              'group grid grid-cols-[auto_min-content] items-start gap-3 rounded-md border px-3 py-2 shadow-pop',
              'data-[state=open]:animate-slide-in-right',
              item.tone === 'danger' && 'border-danger/50 bg-danger-soft text-ink',
              item.tone === 'ok' && 'border-ok/40 bg-ok-soft text-ink',
              item.tone === 'default' && 'border-line bg-bg-surface text-ink',
            )}
          >
            <div className="flex flex-col gap-0.5">
              <ToastPrimitive.Title className="text-sm font-medium">
                {item.title}
              </ToastPrimitive.Title>
              {item.description ? (
                <ToastPrimitive.Description className="text-xs text-ink-soft">
                  {item.description}
                </ToastPrimitive.Description>
              ) : null}
            </div>
            <ToastPrimitive.Close className="rounded p-0.5 text-ink-muted hover:bg-bg-inset">
              <X className="h-3.5 w-3.5" />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
