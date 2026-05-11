import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { FilterBar } from "@/components/catalog/FilterBar";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Section } from "@/components/layout/Container";
import { ItemListJsonLd } from "@/components/seo/JsonLd";
import { Link } from "@/i18n/routing";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchBrands, fetchCategories, fetchProducts } from "@/lib/api";
import type { ProductListParams } from "@/lib/api";
import { SITE_URL } from "@/lib/env";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

type SearchParams = {
  direction?: string;
  brand?: string;
  protein_gte?: string;
  protein_lte?: string;
  age_days?: string;
  q?: string;
  ordering?: string;
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) return {};
  const t = await getTranslations({ locale: lang, namespace: "catalog" });
  const home = await getTranslations({ locale: lang, namespace: "home" });
  return buildMetadata({
    locale: lang,
    path: "/catalog",
    title: t("title"),
    description: home("heroSubtitle"),
  });
}

export default async function CatalogPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) return null;
  setRequestLocale(lang);
  const locale = lang as Locale;

  const sp = await searchParams;
  const t = await getTranslations({ locale, namespace: "catalog" });

  const apiParams: ProductListParams = {
    direction: sp.direction,
    brand: sp.brand,
    protein_gte: sp.protein_gte ? Number(sp.protein_gte) : undefined,
    protein_lte: sp.protein_lte ? Number(sp.protein_lte) : undefined,
    age_days: sp.age_days ? Number(sp.age_days) : undefined,
    search: sp.q,
    ordering: sp.ordering,
    page_size: 48,
  };

  const [products, categories, brandsResp] = await Promise.all([
    fetchProducts(locale, apiParams),
    fetchCategories(locale),
    fetchBrands(locale),
  ]);

  const items = products?.results ?? [];
  const brands = (brandsResp?.results ?? []).map((b) => ({ code: b.code, name: b.name }));
  const subCategories = (categories ?? []).filter((c) => c.level >= 1);

  return (
    <Section>
      {items.length > 0 && (
        <ItemListJsonLd
          items={items.map((p, i) => ({
            position: i + 1,
            name: p.name,
            url: `${SITE_URL}/${locale}/product/${p.code}`,
          }))}
        />
      )}

      <div style={{ marginBottom: 32 }}>
        <div className="eyebrow anim-fade-in-up">
          {locale === "ru" ? "Полный каталог" : locale === "uz" ? "Toʻliq katalog" : "Complete catalog"}
        </div>
        <h1 className="h1 anim-fade-in-up delay-100" style={{ marginBottom: 12 }}>{t("title")}</h1>
        <p className="lead anim-fade-in-up delay-200" style={{ maxWidth: 760 }}>
          {locale === "ru"
            ? `${products?.count ?? 0} позиций под бройлера, несушку и родительское стадо. Сначала выберите направление, потом — линейку или нужный уровень протеина. Если потеряетесь, напишите нам — соберём программу под ваше стадо за пять минут.`
            : locale === "uz"
            ? `Broyler, tuxum tovuqlari va ota-ona podasiga moʻljallangan ${products?.count ?? 0} ta pozitsiya. Avval yoʻnalishni tanlang, keyin — liniya yoki kerakli protein darajasini. Yoʻqolib qolsangiz, bizga yozing — pod uchun dasturni besh daqiqada yigʻib beramiz.`
            : `${products?.count ?? 0} SKUs across broiler, layer and parent stock. Pick a direction first, then drill into a line or a specific protein level. Lost? Drop us a line — we'll build a program around your flock in five minutes.`}
        </p>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "300px minmax(0, 1fr)",
        gap: 32,
        alignItems: "start",
      }} className="catalog-grid">
        <aside style={{ position: "sticky", top: 96 }} className="catalog-aside">
          <FilterBar brands={brands} />

          {subCategories.length > 0 && (
            <div className="card" style={{ padding: 24 }}>
              <div className="eyebrow" style={{ marginBottom: 12 }}>
                {locale === "ru" ? "Категории" : locale === "uz" ? "Kategoriyalar" : "Categories"}
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
                {subCategories.map((c) => (
                  <li key={c.id}>
                    <Link
                      href={`/catalog/${c.code}`}
                      style={{
                        display: "block",
                        padding: "8px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "var(--text-sm)",
                        color: "var(--fg-2)",
                        marginLeft: c.level > 1 ? 16 : 0,
                        transition: "background 160ms",
                      }}
                    >
                      {c.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

        <div>
          {items.length === 0 ? (
            <div className="card" style={{ padding: 64, textAlign: "center" }}>
              <p className="lead" style={{ margin: 0 }}>{t("empty")}</p>
            </div>
          ) : (
            <ProductGrid products={items} />
          )}
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .catalog-grid { grid-template-columns: 1fr !important; }
          .catalog-aside { position: static !important; }
        }
      `}</style>
    </Section>
  );
}
