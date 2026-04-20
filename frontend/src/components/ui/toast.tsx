'use client';

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { cn } from '@/shared/lib/cn';

export type ToastTone = 'success' | 'error' | 'warning' | 'info';

export type ToastAction = {
  label: string;
  onClick: () => void;
};

export type ToastOptions = {
  id?: string;
  title?: string;
  description?: string;
  tone?: ToastTone;
  durationMs?: number;
  action?: ToastAction;
};

type ToastRecord = Required<Pick<ToastOptions, 'id'>> & ToastOptions;

type ToastContextValue = {
  show: (options: ToastOptions) => string;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION_MS = 4500;

let toastIdCounter = 0;
const nextToastId = () => {
  toastIdCounter += 1;
  return `toast-${toastIdCounter}-${Date.now()}`;
};

const toneIcon: Record<ToastTone, typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const toneClasses: Record<ToastTone, string> = {
  success: 'border-emerald-200/80 bg-emerald-50 text-emerald-950',
  error: 'border-destructive/30 bg-destructive/10 text-destructive-foreground',
  warning: 'border-amber-200/80 bg-amber-50 text-amber-950',
  info: 'border-slate-200 bg-white text-foreground',
};

const toneIconClasses: Record<ToastTone, string> = {
  success: 'text-emerald-600',
  error: 'text-destructive',
  warning: 'text-amber-600',
  info: 'text-primary',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const show = useCallback(
    (options: ToastOptions) => {
      const id = options.id ?? nextToastId();
      const duration = options.durationMs ?? DEFAULT_DURATION_MS;
      setToasts((current) => {
        const withoutDuplicate = current.filter((toast) => toast.id !== id);
        return [...withoutDuplicate, { ...options, id, tone: options.tone ?? 'info' }];
      });
      const existingTimer = timers.current.get(id);
      if (existingTimer) {
        clearTimeout(existingTimer);
      }
      if (duration > 0) {
        const timer = setTimeout(() => dismiss(id), duration);
        timers.current.set(id, timer);
      }
      return id;
    },
    [dismiss],
  );

  useEffect(() => {
    const timersRef = timers.current;
    return () => {
      timersRef.forEach((timer) => clearTimeout(timer));
      timersRef.clear();
    };
  }, []);

  const contextValue = useMemo<ToastContextValue>(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed bottom-4 right-4 z-[90] flex w-full max-w-sm flex-col gap-2 sm:bottom-6 sm:right-6"
      >
        {toasts.map((toast) => {
          const tone: ToastTone = toast.tone ?? 'info';
          const Icon = toneIcon[tone];
          return (
            <div
              key={toast.id}
              role={tone === 'error' ? 'alert' : 'status'}
              className={cn(
                'pointer-events-auto flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-[0_22px_60px_-36px_rgba(15,23,42,0.24)] backdrop-blur-xl transition',
                toneClasses[tone],
              )}
            >
              <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', toneIconClasses[tone])} />
              <div className="min-w-0 flex-1 space-y-0.5">
                {toast.title ? (
                  <p className="text-sm font-semibold leading-snug">{toast.title}</p>
                ) : null}
                {toast.description ? (
                  <p className="text-sm leading-snug opacity-90">{toast.description}</p>
                ) : null}
                {toast.action ? (
                  <button
                    type="button"
                    className="mt-1 inline-flex text-xs font-semibold uppercase tracking-[0.12em] text-current underline-offset-2 hover:underline"
                    onClick={() => {
                      toast.action?.onClick();
                      dismiss(toast.id);
                    }}
                  >
                    {toast.action.label}
                  </button>
                ) : null}
              </div>
              <button
                type="button"
                aria-label="Close"
                className="shrink-0 rounded-md p-1 text-current opacity-60 transition hover:opacity-100"
                onClick={() => dismiss(toast.id)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
