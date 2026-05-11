"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

/**
 * Полноэкранная заставка при первом заходе на сайт.
 * Показывается один раз за сессию (sessionStorage).
 *
 * Стадии: showing → exiting → gone. На стадии exiting добавляется
 * opacity:0 + pointer-events:none, чтобы пользователь мог скроллить
 * прямо сквозь неё, пока она доуплывает.
 *
 * SSR-safe: первый рендер всегда возвращает заставку (без проверки
 * sessionStorage, потому что её нет на сервере), а useEffect сразу
 * прячет её, если пользователь уже видел splash.
 */
type Stage = "showing" | "exiting" | "gone";

const SHOW_MS = 500;
const EXIT_MS = 300;

export function SplashScreen() {
  const [stage, setStage] = useState<Stage>("showing");

  useEffect(() => {
    // Splash появляется при каждой полной загрузке страницы.
    // Client-side navigation между страницами его не пере-монтирует
    // (layout сохраняется), поэтому пользователя он не раздражает.
    const exitTimer = setTimeout(() => setStage("exiting"), SHOW_MS);
    const goneTimer = setTimeout(() => setStage("gone"), SHOW_MS + EXIT_MS);

    // Скролл лочим только пока splash виден.
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      clearTimeout(exitTimer);
      clearTimeout(goneTimer);
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  // Снимаем lock как только начали выходить — чтобы под кадром можно было скроллить.
  useEffect(() => {
    if (stage !== "showing") {
      document.body.style.overflow = "";
    }
  }, [stage]);

  if (stage === "gone") return null;

  const isExiting = stage === "exiting";

  return (
    <div
      aria-hidden
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 999,
        background:
          "radial-gradient(ellipse at 30% 20%, rgba(224,9,31,0.18), transparent 60%)," +
          "radial-gradient(ellipse at 70% 80%, rgba(245,183,0,0.18), transparent 60%)," +
          "var(--bg-page)",
        display: "grid",
        placeItems: "center",
        opacity: isExiting ? 0 : 1,
        pointerEvents: isExiting ? "none" : "auto",
        transition: `opacity ${EXIT_MS}ms var(--ease)`,
        overflow: "hidden",
      }}
    >
      {/* decorative blobs */}
      <div
        className="blob"
        style={{ width: 480, height: 480, top: "-160px", left: "-120px", background: "var(--brand-red)", opacity: 0.18 }}
      />
      <div
        className="blob"
        style={{ width: 380, height: 380, bottom: "-120px", right: "-80px", background: "var(--brand-yellow)", opacity: 0.22, animationDelay: "-6s" }}
      />

      <div
        style={{
          position: "relative",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
        }}
      >
        {/* glow ring under logo */}
        <div
          style={{
            position: "absolute",
            top: 30,
            width: 220,
            height: 220,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(224,9,31,0.22) 0%, transparent 70%)",
            animation: "splash-glow 1.6s ease-in-out infinite",
            zIndex: 0,
          }}
        />

        {/* logo */}
        <div
          style={{
            position: "relative",
            zIndex: 1,
            animation: "splash-pop 700ms cubic-bezier(0.34, 1.56, 0.64, 1) backwards",
          }}
        >
          <Image
            src="/mark.png"
            alt="Yembro"
            width={140}
            height={239}
            priority
            style={{
              width: "auto",
              height: 140,
              objectFit: "contain",
              animation: "splash-bob 2s ease-in-out infinite 700ms",
            }}
          />
        </div>

        {/* wordmark */}
        <div
          style={{
            position: "relative",
            zIndex: 1,
            fontSize: 40,
            fontWeight: 800,
            color: "var(--fg-1)",
            letterSpacing: "-0.02em",
            animation: "splash-up 600ms ease 350ms backwards",
          }}
        >
          Yembro
        </div>
        <div
          style={{
            position: "relative",
            zIndex: 1,
            fontSize: 14,
            fontWeight: 600,
            color: "var(--fg-3)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            animation: "splash-up 600ms ease 550ms backwards",
          }}
        >
          Yuqori sifat — yuqori samaradorlik
        </div>

        {/* loading bar */}
        <div
          style={{
            position: "relative",
            zIndex: 1,
            width: 200,
            height: 3,
            borderRadius: 999,
            background: "var(--bg-subtle)",
            overflow: "hidden",
            marginTop: 8,
            animation: "splash-up 600ms ease 700ms backwards",
          }}
        >
          <div
            style={{
              height: "100%",
              background: "var(--brand-grad)",
              borderRadius: 999,
              animation: `splash-bar ${SHOW_MS}ms linear forwards`,
              transformOrigin: "left",
              transform: "scaleX(0)",
            }}
          />
        </div>
      </div>

      <style>{`
        @keyframes splash-pop {
          0% { opacity: 0; transform: scale(0.6) rotate(-8deg); }
          60% { opacity: 1; transform: scale(1.04) rotate(2deg); }
          100% { opacity: 1; transform: scale(1) rotate(0); }
        }
        @keyframes splash-up {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes splash-bob {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes splash-glow {
          0%, 100% { transform: scale(0.95); opacity: 0.6; }
          50% { transform: scale(1.15); opacity: 1; }
        }
        @keyframes splash-bar {
          0% { transform: scaleX(0); }
          100% { transform: scaleX(1); }
        }
        @media (prefers-reduced-motion: reduce) {
          [aria-hidden] :is(.blob, [style*="splash"]) { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
