import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Section } from "@/components/layout/Container";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchPage } from "@/lib/api";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) return {};
  const t = await getTranslations({ locale: lang, namespace: "nav" });
  const page = await fetchPage("about", lang as Locale);
  return buildMetadata({
    locale: lang,
    path: "/about",
    title: page?.meta_title || page?.title || t("about"),
    description: page?.meta_description || page?.body?.slice(0, 160) || t("about"),
    ogImage: page?.og_image ?? null,
  });
}

export default async function AboutPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) return null;
  setRequestLocale(lang);
  const locale = lang as Locale;
  const t = await getTranslations({ locale, namespace: "nav" });
  const page = await fetchPage("about", locale);

  return (
    <Section>
      <h1 className="h1" style={{ marginBottom: 24 }}>{page?.title || t("about")}</h1>
      {page?.body && (
        <div
          style={{
            fontSize: "var(--text-lg)",
            color: "var(--fg-2)",
            lineHeight: 1.7,
            maxWidth: 800,
            whiteSpace: "pre-wrap",
          }}
        >
          {page.body}
        </div>
      )}
    </Section>
  );
}
