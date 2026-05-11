"use client";

import { useEffect, useRef } from "react";

/**
 * Тонкая прогресс-полоска сверху страницы, заполняется по мере скролла.
 *
 * Управляем через requestAnimationFrame + CSS transform — это дешевле
 * чем setState на каждый scroll-event, и не вызывает re-render компонента.
 * При prefers-reduced-motion полоса всё равно работает (это не анимация
 * ради анимации, а индикатор состояния).
 */
export function ScrollProgress() {
  const fillRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const fill = fillRef.current;
    if (!fill) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      const ratio = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      fill.style.transform = `scaleX(${ratio})`;
    };
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      aria-hidden
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        zIndex: 40,
        pointerEvents: "none",
        background: "transparent",
      }}
    >
      <div
        ref={fillRef}
        style={{
          height: "100%",
          width: "100%",
          background: "var(--brand-grad-warm)",
          transformOrigin: "left",
          transform: "scaleX(0)",
          willChange: "transform",
          boxShadow: "0 0 12px rgba(224,9,31,0.4)",
        }}
      />
    </div>
  );
}
