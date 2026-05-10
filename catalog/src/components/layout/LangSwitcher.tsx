"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { localeNames, locales, type Locale } from "@/i18n/config";
import { usePathname, useRouter } from "@/i18n/routing";

export function LangSwitcher() {
  const pathname = usePathname();
  const router = useRouter();
  const params = useParams<{ lang: string }>();
  const current = params.lang as Locale;
  const [open, setOpen] = useState(false);

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        className="btn btn-ghost"
        onClick={() => setOpen((o) => !o)}
        aria-label="Switch language"
        style={{ padding: "8px 12px", fontSize: "var(--text-sm)" }}
      >
        {current?.toUpperCase()}
        <span aria-hidden style={{ marginLeft: 4 }}>▾</span>
      </button>
      {open && (
        <div
          className="card"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            right: 0,
            minWidth: 160,
            padding: 4,
            zIndex: 50,
          }}
        >
          {locales.map((lng) => (
            <button
              key={lng}
              type="button"
              onClick={() => {
                setOpen(false);
                router.replace(pathname, { locale: lng });
              }}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 12px",
                background: lng === current ? "var(--bg-active)" : "transparent",
                color: lng === current ? "var(--brand-orange)" : "var(--fg-1)",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
                fontWeight: lng === current ? 600 : 400,
                fontSize: "var(--text-sm)",
              }}
            >
              {localeNames[lng]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
