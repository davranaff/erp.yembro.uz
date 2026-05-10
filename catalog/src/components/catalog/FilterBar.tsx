"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { ArrowRightIcon, ChickIcon, EggIcon, FeatherIcon, GrainIcon } from "@/components/ui/Icon";

const DIRECTIONS = [
  { code: "broiler", Icon: ChickIcon },
  { code: "layer", Icon: EggIcon },
  { code: "parent", Icon: FeatherIcon },
  { code: "universal", Icon: GrainIcon },
] as const;

export type FilterBarProps = {
  brands: { code: string; name: string }[];
};

export function FilterBar({ brands }: FilterBarProps) {
  const t = useTranslations("catalog");
  const tDir = useTranslations("directions");
  const router = useRouter();
  const params = useParams<{ lang: string }>();
  const sp = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const [search, setSearch] = useState(sp.get("q") ?? "");

  // debounce search
  useEffect(() => {
    const id = setTimeout(() => {
      const cur = sp.get("q") ?? "";
      if (search === cur) return;
      const next = new URLSearchParams(sp.toString());
      if (search) next.set("q", search);
      else next.delete("q");
      startTransition(() => {
        router.replace(`/${params.lang}/catalog?${next.toString()}`, { scroll: false });
      });
    }, 320);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(sp.toString());
    if (!value) next.delete(key);
    else next.set(key, value);
    startTransition(() => {
      router.replace(`/${params.lang}/catalog?${next.toString()}`, { scroll: false });
    });
  };

  const reset = () => {
    setSearch("");
    startTransition(() => {
      router.replace(`/${params.lang}/catalog`, { scroll: false });
    });
  };

  const dir = sp.get("direction");
  const brand = sp.get("brand");
  const proteinGte = sp.get("protein_gte");
  const ordering = sp.get("ordering");

  const hasFilters = !!(dir || brand || proteinGte || sp.get("q") || ordering);

  return (
    <div className="card" style={{ padding: 24, marginBottom: 32, opacity: isPending ? 0.7 : 1, transition: "opacity 200ms" }}>
      {/* Search */}
      <div style={{ position: "relative", marginBottom: 20 }}>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("search") as never as string}
          className="input"
          style={{ paddingLeft: 44 }}
          aria-label="Search"
        />
        <svg
          style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--fg-3)", pointerEvents: "none" }}
          width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </div>

      {/* Direction chips */}
      <div style={{ marginBottom: 20 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>{t("filterDirection")}</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <button
            type="button"
            onClick={() => setParam("direction", null)}
            className={`chip ${!dir ? "chip-active" : ""}`}
          >
            {t("showAll")}
          </button>
          {DIRECTIONS.map(({ code, Icon }) => (
            <button
              key={code}
              type="button"
              onClick={() => setParam("direction", dir === code ? null : code)}
              className={`chip ${dir === code ? "chip-active" : ""}`}
            >
              <Icon width={16} height={16} />
              {tDir(code as never)}
            </button>
          ))}
        </div>
      </div>

      {/* Brand chips */}
      {brands.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>{t("filterBrand")}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button
              type="button"
              onClick={() => setParam("brand", null)}
              className={`chip ${!brand ? "chip-active" : ""}`}
            >
              {t("showAll")}
            </button>
            {brands.map((b) => (
              <button
                key={b.code}
                type="button"
                onClick={() => setParam("brand", brand === b.code ? null : b.code)}
                className={`chip ${brand === b.code ? "chip-active" : ""}`}
              >
                {b.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Protein min + sort */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 12,
        alignItems: "end",
      }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>{t("filterProtein")} ≥</div>
          <select
            className="select"
            value={proteinGte ?? ""}
            onChange={(e) => setParam("protein_gte", e.target.value || null)}
          >
            <option value="">—</option>
            <option value="16">16%</option>
            <option value="18">18%</option>
            <option value="20">20%</option>
            <option value="22">22%</option>
            <option value="24">24%</option>
          </select>
        </div>
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>{t("sort")}</div>
          <select
            className="select"
            value={ordering ?? ""}
            onChange={(e) => setParam("ordering", e.target.value || null)}
          >
            <option value="">—</option>
            <option value="-spec__protein_pct">{t("sortProteinDesc")}</option>
            <option value="spec__protein_pct">{t("sortProteinAsc")}</option>
            <option value="-created_at">{t("sortNewest")}</option>
            <option value="sort_order">{t("sortDefault")}</option>
          </select>
        </div>
      </div>

      {hasFilters && (
        <button
          type="button"
          onClick={reset}
          className="btn btn-ghost"
          style={{
            marginTop: 20,
            color: "var(--brand-orange)",
            fontWeight: 600,
          }}
        >
          {t("reset")} <ArrowRightIcon width={14} height={14} />
        </button>
      )}
    </div>
  );
}
