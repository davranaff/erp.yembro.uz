'use client';

import { useIsFetching, useIsMutating } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

export function TopProgressBar() {
  const fetchingCount = useIsFetching();
  const mutatingCount = useIsMutating();
  const isActive = fetchingCount > 0 || mutatingCount > 0;
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    if (isActive) {
      setShouldRender(true);
      return;
    }
    const timer = setTimeout(() => setShouldRender(false), 300);
    return () => clearTimeout(timer);
  }, [isActive]);

  if (!shouldRender) {
    return null;
  }

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 top-0 z-[95] h-0.5 overflow-hidden bg-transparent"
    >
      <div
        className={`h-full origin-left bg-gradient-to-r from-primary/50 via-primary to-accent transition-opacity duration-300 ${
          isActive ? 'animate-[topProgress_1.1s_ease-in-out_infinite] opacity-100' : 'opacity-0'
        }`}
        style={{ width: '100%' }}
      />
      <style>{`
        @keyframes topProgress {
          0% { transform: translateX(-100%) scaleX(0.35); }
          50% { transform: translateX(0) scaleX(0.75); }
          100% { transform: translateX(100%) scaleX(0.35); }
        }
      `}</style>
    </div>
  );
}
