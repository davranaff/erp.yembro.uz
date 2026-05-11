import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ProductGrid } from "@/components/catalog/ProductGrid";
import { SpecTable } from "@/components/catalog/SpecTable";
import { Section } from "@/components/layout/Container";
import { LogoMark } from "@/components/layout/Logo";
import { BreadcrumbJsonLd, ProductJsonLd } from "@/components/seo/JsonLd";
import {
  ArrowRightIcon,
  CheckIcon,
  DirectionIcon,
} from "@/components/ui/Icon";
import { Link } from "@/i18n/routing";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchProduct, fetchSitemap } from "@/lib/api";
import { SITE_URL } from "@/lib/env";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateStaticParams() {
  const sitemap = await fetchSitemap().catch(() => null);
  if (!sitemap) return [];
  return sitemap.items
    .filter((i) => i.kind === "product")
    .map((i) => ({ slug: i.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string; slug: string }>;
}): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!isLocale(lang)) return {};
  const product = await fetchProduct(slug, lang as Locale);
  if (!product) return {};
  return buildMetadata({
    locale: lang,
    path: `/product/${product.code}`,
    title: product.meta_title || product.name,
    description: product.meta_description || product.short_description || product.description.slice(0, 160),
    ogImage: product.og_image ?? product.images[0]?.image ?? null,
  });
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ lang: string; slug: string }>;
}) {
  const { lang, slug } = await params;
  if (!isLocale(lang)) notFound();
  setRequestLocale(lang);
  const locale = lang as Locale;

  const product = await fetchProduct(slug, locale);
  if (!product) notFound();

  const t = await getTranslations({ locale, namespace: "product" });
  const tCatalog = await getTranslations({ locale, namespace: "catalog" });
  const tDir = await getTranslations({ locale, namespace: "directions" });

  const breadcrumbItems = [
    { name: "Yembro", url: `${SITE_URL}/${locale}` },
    { name: tCatalog("title"), url: `${SITE_URL}/${locale}/catalog` },
    ...product.breadcrumbs.map((b) => ({
      name: b.name,
      url: `${SITE_URL}/${locale}/catalog/${b.code}`,
    })),
    { name: product.name, url: `${SITE_URL}/${locale}/product/${product.code}` },
  ];

  const primaryImage = product.images.find((i) => i.is_primary) ?? product.images[0];
  const advantages = product.application
    ? product.application.split(/\.\s+|\n/).filter((x) => x.trim().length > 5).slice(0, 4)
    : [];

  return (
    <>
      <ProductJsonLd product={product} locale={locale} />
      <BreadcrumbJsonLd items={breadcrumbItems} />

      {/* HERO + IMAGE */}
      <section className="bg-grad-soft" style={{ position: "relative", overflow: "hidden" }}>
        <div className="blob" style={{ width: 480, height: 480, top: -160, right: -120, background: "var(--brand-yellow)", opacity: 0.35 }} aria-hidden />
        <div className="container" style={{ position: "relative", zIndex: 1, paddingTop: 32, paddingBottom: 64 }}>
          <nav aria-label="Breadcrumb" style={{ marginBottom: 24, fontSize: "var(--text-sm)", color: "var(--fg-3)" }}>
            <Link href="/catalog">{tCatalog("title")}</Link>
            {product.breadcrumbs.map((b) => (
              <span key={b.code}>
                <span aria-hidden style={{ margin: "0 8px" }}>›</span>
                <Link href={`/catalog/${b.code}`}>{b.name}</Link>
              </span>
            ))}
          </nav>

          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
            gap: 56,
            alignItems: "start",
          }} className="product-grid">
            {/* IMAGE */}
            <div className="anim-fade-in-up" style={{
              position: "relative",
              aspectRatio: "1 / 1",
              background: "linear-gradient(135deg, var(--bg-card) 0%, var(--brand-red-soft) 100%)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-2xl)",
              overflow: "hidden",
              boxShadow: "var(--shadow-menu)",
            }}>
              {primaryImage?.image ? (
                <Image
                  src={primaryImage.image}
                  alt={primaryImage.alt || product.name}
                  fill
                  sizes="(max-width: 1024px) 100vw, 600px"
                  priority
                  style={{
                    // contain — мешок целиком виден, не обрезается
                    objectFit: "contain",
                    padding: 48,
                  }}
                />
              ) : (
                <div style={{
                  position: "absolute",
                  inset: 0,
                  display: "grid",
                  placeItems: "center",
                  background: "linear-gradient(135deg, var(--bg-card) 0%, var(--brand-red-soft) 100%)",
                }} aria-hidden>
                  <LogoMark size={200} alt="" />
                </div>
              )}
              {/* gallery thumbs */}
              {product.images.length > 1 && (
                <div style={{
                  position: "absolute",
                  bottom: 16,
                  left: 16,
                  display: "flex",
                  gap: 8,
                }}>
                  {product.images.slice(0, 5).map((img) => (
                    <div key={img.id} style={{
                      width: 48,
                      height: 48,
                      borderRadius: 8,
                      overflow: "hidden",
                      border: "2px solid var(--bg-card)",
                      boxShadow: "var(--shadow-card)",
                      position: "relative",
                    }}>
                      {img.image && (
                        <Image src={img.image} alt={img.alt} fill sizes="48px" style={{ objectFit: "cover" }} />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* INFO */}
            <div className="anim-fade-in-up delay-200">
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
                <span className="badge badge-orange" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <DirectionIcon direction={product.direction} width={12} height={12} />
                  {tDir(product.direction as never)}
                </span>
                <span className="badge badge-blue">{product.brand.name}</span>
              </div>
              <h1 className="h1" style={{ fontSize: "clamp(28px,4vw,var(--text-4xl))", marginBottom: 16 }}>{product.name}</h1>
              {product.short_description && (
                <p className="lead" style={{ marginBottom: 32 }}>{product.short_description}</p>
              )}

              {/* Quick spec cards */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                gap: 12,
                marginBottom: 32,
              }}>
                {(product.age_from_days != null || product.age_to_days != null) && (
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--fg-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                      {t("ageRange")}
                    </div>
                    <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      {product.age_from_days ?? "?"}–{product.age_to_days ?? "?"} d
                    </div>
                  </div>
                )}
                {product.package_kg && (
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--fg-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                      {t("package")}
                    </div>
                    <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      {product.package_kg} kg
                    </div>
                  </div>
                )}
                {product.spec?.protein_pct && (
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--fg-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                      Protein
                    </div>
                    <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      {product.spec.protein_pct}%
                    </div>
                  </div>
                )}
                {product.spec?.me_kcal_per_kg && (
                  <div className="card" style={{ padding: 16 }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--fg-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                      ME
                    </div>
                    <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      {product.spec.me_kcal_per_kg}
                    </div>
                  </div>
                )}
              </div>

              <Link href="/contacts" className="btn btn-primary btn-xl">
                {t("ctaContact")} <ArrowRightIcon width={18} height={18} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* DESCRIPTION + SPEC */}
      <Section>
        <div style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)",
          gap: 56,
          alignItems: "start",
        }} className="product-grid">
          <div>
            {product.description && (
              <div className="anim-fade-in-up">
                <h2 className="h3" style={{ marginBottom: 16 }}>{t("applicationTitle")}</h2>
                <div style={{
                  fontSize: "var(--text-base)",
                  color: "var(--fg-2)",
                  lineHeight: 1.7,
                  whiteSpace: "pre-wrap",
                  marginBottom: 32,
                }}>
                  {product.description}
                </div>
              </div>
            )}

            {advantages.length > 0 && (
              <div className="anim-fade-in-up delay-200">
                <h2 className="h3" style={{ marginBottom: 16 }}>
                  {locale === "ru" ? "Что важно знать о корме"
                    : locale === "uz" ? "Yem haqida bilish kerak boʻlgan narsalar"
                    : "What to know about this feed"}
                </h2>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
                  {advantages.map((a, i) => (
                    <li key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                      <span style={{
                        flex: "0 0 24px",
                        width: 24,
                        height: 24,
                        borderRadius: "50%",
                        background: "var(--brand-grad-soft)",
                        color: "var(--brand-orange)",
                        display: "grid",
                        placeItems: "center",
                        marginTop: 2,
                      }}>
                        <CheckIcon width={14} height={14} />
                      </span>
                      <span style={{ color: "var(--fg-2)", lineHeight: 1.6 }}>{a}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {product.spec && (
            <aside className="card anim-fade-in-up delay-300" style={{
              padding: 32,
              position: "sticky",
              top: 96,
            }}>
              <div className="eyebrow" style={{ marginBottom: 12 }}>{t("specTitle")}</div>
              <h2 className="h3" style={{ marginBottom: 24 }}>
                {locale === "ru" ? "Что внутри одного килограмма"
                  : locale === "uz" ? "Bir kilogramm ichida nima bor"
                  : "What's inside a kilogram"}
              </h2>
              <SpecTable spec={product.spec} />
            </aside>
          )}
        </div>
      </Section>

      {/* RELATED */}
      {product.related.length > 0 && (
        <Section style={{ background: "var(--bg-card)" }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>
            {locale === "ru" ? "Следующий шаг по программе кормления"
              : locale === "uz" ? "Boqish dasturidagi keyingi qadam"
              : "Next step in the feeding program"}
          </div>
          <h2 className="h2" style={{ marginBottom: 32 }}>{t("relatedTitle")}</h2>
          <ProductGrid products={product.related} />
        </Section>
      )}

      <style>{`
        @media (max-width: 900px) {
          .product-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  );
}
