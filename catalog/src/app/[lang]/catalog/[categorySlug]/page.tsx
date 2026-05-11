import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Section } from "@/components/layout/Container";
import { BreadcrumbJsonLd } from "@/components/seo/JsonLd";
import { Link } from "@/i18n/routing";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchCategory, fetchProducts, fetchSitemap } from "@/lib/api";
import { SITE_URL } from "@/lib/env";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateStaticParams() {
  const sitemap = await fetchSitemap().catch(() => null);
  if (!sitemap) return [];
  return sitemap.items
    .filter((i) => i.kind === "category")
    .map((i) => ({ categorySlug: i.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string; categorySlug: string }>;
}): Promise<Metadata> {
  const { lang, categorySlug } = await params;
  if (!isLocale(lang)) return {};
  const cat = await fetchCategory(categorySlug, lang as Locale);
  if (!cat) return {};
  const fallback = await getTranslations({ locale: lang, namespace: "home" });
  return buildMetadata({
    locale: lang,
    path: `/catalog/${cat.code}`,
    title: cat.meta_title || cat.name,
    description: cat.meta_description || cat.description || fallback("heroSubtitle"),
    ogImage: cat.og_image ?? null,
  });
}

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ lang: string; categorySlug: string }>;
}) {
  const { lang, categorySlug } = await params;
  if (!isLocale(lang)) notFound();
  setRequestLocale(lang);
  const locale = lang as Locale;

  const [cat, products] = await Promise.all([
    fetchCategory(categorySlug, locale),
    fetchProducts(locale, { category: categorySlug, page_size: 48 }),
  ]);
  if (!cat) notFound();

  const t = await getTranslations({ locale, namespace: "catalog" });

  const breadcrumbItems = [
    { name: "Yembro", url: `${SITE_URL}/${locale}` },
    { name: t("title"), url: `${SITE_URL}/${locale}/catalog` },
    ...cat.breadcrumbs.map((b) => ({
      name: b.name,
      url: `${SITE_URL}/${locale}/catalog/${b.code}`,
    })),
  ];

  return (
    <Section>
      <BreadcrumbJsonLd items={breadcrumbItems} />

      <nav aria-label="Breadcrumb" style={{ marginBottom: 16, fontSize: "var(--text-sm)", color: "var(--fg-3)" }}>
        <Link href="/catalog">{t("title")}</Link>
        {cat.breadcrumbs.map((b, i) => (
          <span key={b.code}>
            <span aria-hidden style={{ margin: "0 6px" }}>›</span>
            {i === cat.breadcrumbs.length - 1 ? (
              <span style={{ color: "var(--fg-1)" }}>{b.name}</span>
            ) : (
              <Link href={`/catalog/${b.code}`}>{b.name}</Link>
            )}
          </span>
        ))}
      </nav>

      <h1 className="h1" style={{ marginBottom: 16 }}>{cat.name}</h1>
      {cat.description && (
        <p className="lead" style={{ marginBottom: 32, maxWidth: 720 }}>{cat.description}</p>
      )}

      {(cat.children?.length ?? 0) > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 32 }}>
          {cat.children.map((ch) => (
            <Link
              key={ch.id}
              href={`/catalog/${ch.code}`}
              style={{
                padding: "8px 14px",
                borderRadius: "var(--radius-pill)",
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                fontSize: "var(--text-sm)",
                fontWeight: 500,
              }}
            >
              {ch.name}
            </Link>
          ))}
        </div>
      )}

      {(products?.results.length ?? 0) === 0 ? (
        <p className="lead">{t("empty")}</p>
      ) : (
        <ProductGrid products={products!.results} />
      )}
    </Section>
  );
}
