/**
 * Утилиты для построения метаданных, canonical и hreflang.
 */
import type { Metadata } from "next";

import { defaultLocale, locales, type Locale } from "@/i18n/config";

import { SITE_URL } from "./env";

export function trimTitle(s: string, max = 60) {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

export function trimDescription(s: string, max = 160) {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

export function buildCanonical(locale: Locale, path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${SITE_URL}/${locale}${cleanPath === "/" ? "" : cleanPath}`;
}

export function buildHreflang(path: string): NonNullable<Metadata["alternates"]>["languages"] {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const out: Record<string, string> = {};
  for (const lng of locales) {
    out[lng] = `${SITE_URL}/${lng}${cleanPath === "/" ? "" : cleanPath}`;
  }
  out["x-default"] = `${SITE_URL}/${defaultLocale}${cleanPath === "/" ? "" : cleanPath}`;
  return out;
}

export type BuildMetadataInput = {
  locale: Locale;
  path: string;
  title: string;
  description: string;
  ogImage?: string | null;
  noIndex?: boolean;
};

export function buildMetadata({
  locale,
  path,
  title,
  description,
  ogImage,
  noIndex,
}: BuildMetadataInput): Metadata {
  const canonical = buildCanonical(locale, path);
  return {
    title: trimTitle(title),
    description: trimDescription(description),
    alternates: {
      canonical,
      languages: buildHreflang(path),
    },
    openGraph: {
      type: "website",
      url: canonical,
      siteName: "Yembro",
      title: trimTitle(title),
      description: trimDescription(description),
      locale: locale === "ru" ? "ru_RU" : locale === "uz" ? "uz_UZ" : "en_US",
      images: ogImage
        ? [{ url: ogImage, width: 1200, height: 630, alt: title }]
        : [{ url: `${SITE_URL}/og-default.jpg`, width: 1200, height: 630, alt: "Yembro" }],
    },
    twitter: {
      card: "summary_large_image",
      title: trimTitle(title),
      description: trimDescription(description),
      images: ogImage ? [ogImage] : [`${SITE_URL}/og-default.jpg`],
    },
    robots: noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true, googleBot: { index: true, follow: true } },
  };
}
