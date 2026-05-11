/**
 * JSON-LD компоненты для structured data.
 * Все компоненты — серверные (без 'use client').
 */
import type { Thing, WithContext } from "schema-dts";

import { ERP_URL, SITE_URL } from "@/lib/env";
import type { ProductDetail } from "@/lib/types";

function jsonLdScript(data: WithContext<Thing>) {
  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data, null, 0) }}
    />
  );
}

export function OrganizationJsonLd({ locale }: { locale: string }) {
  const data: WithContext<Thing> = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Yembro",
    legalName: "Yembro Tech",
    url: `${SITE_URL}/${locale}`,
    logo: `${SITE_URL}/logo.png`,
    image: `${SITE_URL}/logo.png`,
    description: "Производитель полнорационных комбикормов для птицеводства в Узбекистане. Бройлер, несушка, родительское стадо.",
    foundingDate: "2024",
    address: {
      "@type": "PostalAddress",
      addressCountry: "UZ",
      addressRegion: "Tashkent",
    },
    sameAs: [
      ERP_URL,
      "https://t.me/ulugbek_jalolov",
    ],
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "sales",
        telephone: "+998-94-542-77-77",
        email: "info@yembro.uz",
        availableLanguage: ["ru", "uz", "en"],
        areaServed: "UZ",
      },
    ],
  } as WithContext<Thing>;
  return jsonLdScript(data);
}

export function WebSiteJsonLd({ locale }: { locale: string }) {
  const data: WithContext<Thing> = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Yembro",
    url: `${SITE_URL}/${locale}`,
    inLanguage: [locale],
    potentialAction: {
      "@type": "SearchAction",
      target: `${SITE_URL}/${locale}/catalog?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  } as unknown as WithContext<Thing>;
  return jsonLdScript(data);
}

export function ProductJsonLd({
  product,
  locale,
}: {
  product: ProductDetail;
  locale: string;
}) {
  const additional: { "@type": "PropertyValue"; name: string; value: string | number; unitCode?: string }[] = [];
  const spec = product.spec;
  const propUnit = (val: string | null, name: string, unit?: string) => {
    if (val) additional.push({ "@type": "PropertyValue", name, value: val, ...(unit ? { unitCode: unit } : {}) });
  };
  if (spec) {
    propUnit(spec.protein_pct, "Protein", "P1");
    propUnit(spec.fat_pct, "Fat", "P1");
    propUnit(spec.fiber_pct, "Fiber", "P1");
    propUnit(spec.lysine_pct, "Lysine", "P1");
    propUnit(spec.methionine_pct, "Methionine", "P1");
    propUnit(spec.calcium_pct, "Calcium", "P1");
    propUnit(spec.phosphorus_pct, "Phosphorus", "P1");
    if (spec.me_kcal_per_kg) {
      additional.push({ "@type": "PropertyValue", name: "ME (kcal/kg)", value: spec.me_kcal_per_kg });
    }
  }

  const images = product.images.filter((img) => img.image).map((img) => img.image as string);

  const data: WithContext<Thing> = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    sku: product.code,
    description: (product.short_description || product.description || "").slice(0, 5000),
    image: images.length > 0 ? images : undefined,
    brand: { "@type": "Brand", name: product.brand.name },
    category: product.category.name,
    manufacturer: { "@type": "Organization", name: "Yembro", url: `${SITE_URL}/${locale}` },
    additionalProperty: additional.length > 0 ? additional : undefined,
    inLanguage: locale,
  } as unknown as WithContext<Thing>;
  return jsonLdScript(data);
}

export function BreadcrumbJsonLd({
  items,
}: {
  items: { name: string; url: string }[];
}) {
  const data: WithContext<Thing> = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: it.url,
    })),
  } as unknown as WithContext<Thing>;
  return jsonLdScript(data);
}

export function ItemListJsonLd({
  items,
}: {
  items: { position: number; name: string; url: string }[];
}) {
  const data: WithContext<Thing> = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    numberOfItems: items.length,
    itemListElement: items.map((it) => ({
      "@type": "ListItem",
      position: it.position,
      name: it.name,
      url: it.url,
    })),
  } as unknown as WithContext<Thing>;
  return jsonLdScript(data);
}

export function FAQPageJsonLd({
  faqs,
}: {
  faqs: { question: string; answer: string }[];
}) {
  if (faqs.length === 0) return null;
  const data: WithContext<Thing> = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: { "@type": "Answer", text: f.answer },
    })),
  } as unknown as WithContext<Thing>;
  return jsonLdScript(data);
}
