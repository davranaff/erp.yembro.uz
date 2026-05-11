import { useTranslations } from "next-intl";

import type { ProductSpec } from "@/lib/types";

const ROWS: { key: keyof ProductSpec; max: number; unit: string }[] = [
  { key: "protein_pct", max: 30, unit: "%" },
  { key: "fat_pct", max: 12, unit: "%" },
  { key: "fiber_pct", max: 8, unit: "%" },
  { key: "lysine_pct", max: 1.6, unit: "%" },
  { key: "methionine_pct", max: 0.7, unit: "%" },
  { key: "calcium_pct", max: 5, unit: "%" },
  { key: "phosphorus_pct", max: 1, unit: "%" },
  { key: "moisture_pct", max: 14, unit: "%" },
  { key: "me_kcal_per_kg", max: 3300, unit: "kcal/kg" },
];

function toNumber(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function SpecTable({ spec }: { spec: ProductSpec }) {
  const t = useTranslations("spec");

  const rows = ROWS.flatMap((r) => {
    const num = toNumber(spec[r.key]);
    return num == null ? [] : [{ ...r, num }];
  });

  if (rows.length === 0) return null;

  return (
    <dl style={{ display: "grid", gap: 18, margin: 0 }}>
      {rows.map((r) => {
        const pct = Math.min(1, r.num / r.max);
        return (
          <div key={r.key} style={{ display: "grid", gap: 6 }}>
            <div style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              gap: 12,
            }}>
              <dt style={{
                fontSize: "var(--text-sm)",
                color: "var(--fg-2)",
                fontWeight: 500,
              }}>
                {t(r.key as never)}
              </dt>
              <dd style={{
                margin: 0,
                fontSize: "var(--text-base)",
                fontWeight: 700,
                fontFamily: "var(--font-mono)",
                color: "var(--fg-1)",
              }}>
                {r.num}
                <span style={{
                  marginLeft: 4,
                  fontSize: "var(--text-xs)",
                  color: "var(--fg-3)",
                  fontWeight: 500,
                }}>{r.unit}</span>
              </dd>
            </div>
            <div className="progress" aria-hidden>
              <div className="progress-fill" style={{ ["--p" as string]: pct }} />
            </div>
          </div>
        );
      })}
    </dl>
  );
}
