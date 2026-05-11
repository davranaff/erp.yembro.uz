import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Section } from "@/components/layout/Container";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchBrand, fetchSitemap } from "@/lib/api";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateStaticParams() {
  const sitemap = await fetchSitemap().catch(() => null);
  if (!sitemap) return [];
  return sitemap.items.filter((i) => i.kind === "brand").map((i) => ({ slug: i.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string; slug: string }>;
}): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!isLocale(lang)) return {};
  const brand = await fetchBrand(slug, lang as Locale);
  if (!brand) return {};
  return buildMetadata({
    locale: lang,
    path: `/brand/${brand.code}`,
    title: brand.meta_title || brand.name,
    description: brand.meta_description || brand.description,
    ogImage: brand.og_image ?? brand.logo ?? null,
  });
}

export default async function BrandPage({
  params,
}: {
  params: Promise<{ lang: string; slug: string }>;
}) {
  const { lang, slug } = await params;
  if (!isLocale(lang)) notFound();
  setRequestLocale(lang);
  const locale = lang as Locale;

  const brand = await fetchBrand(slug, locale);
  if (!brand) notFound();

  const t = await getTranslations({ locale, namespace: "home" });

  return (
    <Section>
      <h1 className="h1" style={{ marginBottom: 16 }}>{brand.name}</h1>
      {brand.description && (
        <p className="lead" style={{ marginBottom: 48, maxWidth: 800 }}>{brand.description}</p>
      )}
      {(brand.featured?.length ?? 0) > 0 && (
        <>
          <h2 className="h2" style={{ marginBottom: 24 }}>{t("featuredTitle")}</h2>
          <ProductGrid products={brand.featured!} />
        </>
      )}
    </Section>
  );
}
