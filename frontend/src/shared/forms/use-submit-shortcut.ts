import { useEffect, useRef } from 'react';

type SubmitHandler = () => void;

export function useSubmitShortcut(handler: SubmitHandler, enabled = true): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const listener = (event: KeyboardEvent) => {
      const isSubmit = (event.metaKey || event.ctrlKey) && event.key === 'Enter';
      if (!isSubmit) {
        return;
      }
      event.preventDefault();
      handlerRef.current();
    };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [enabled]);
}
