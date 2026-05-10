import type { MetadataRoute } from "next";

import { defaultLocale, locales } from "@/i18n/config";
import { fetchSitemap } from "@/lib/api";
import { SITE_URL } from "@/lib/env";

// Sitemap пересобираем чаще — это лёгкая операция, и важно чтобы новые
// продукты быстро попадали в индекс поисковиков. Сам fetch к /sitemap/
// бэкенда всё равно кешируется на 15 минут.
export const revalidate = 300;
export const dynamic = "force-dynamic";

type Entry = MetadataRoute.Sitemap[number];

function staticEntries(): Entry[] {
  // Статичные пути с приоритетами и частотой обновления.
  const paths: Array<[string, number, Entry["changeFrequency"]]> = [
    ["", 1.0, "weekly"],
    ["/catalog", 0.9, "weekly"],
    ["/about", 0.6, "monthly"],
    ["/contacts", 0.7, "monthly"],
    ["/erp", 0.85, "weekly"],
  ];
  return paths.flatMap(([p, priority, freq]) =>
    locales.map<Entry>((lng) => ({
      url: `${SITE_URL}/${lng}${p}`,
      lastModified: new Date(),
      changeFrequency: freq,
      priority,
      alternates: {
        languages: Object.fromEntries(
          locales.map((l) => [l, `${SITE_URL}/${l}${p}`]),
        ) as Record<string, string>,
      },
    })),
  );
}

function urlForKind(kind: string, locale: string, slug: string): string {
  switch (kind) {
    case "brand":
      return `${SITE_URL}/${locale}/brand/${slug}`;
    case "category":
      return `${SITE_URL}/${locale}/catalog/${slug}`;
    case "product":
      return `${SITE_URL}/${locale}/product/${slug}`;
    case "page":
      return `${SITE_URL}/${locale}/${slug}`;
    default:
      return `${SITE_URL}/${locale}`;
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const data = await fetchSitemap().catch(() => null);
  const dynamic: Entry[] = [];

  if (data) {
    for (const item of data.items) {
      const langs = locales as readonly string[];
      const alternates: Record<string, string> = {};
      for (const lng of langs) {
        const slug = item.alternates[lng] ?? item.alternates[defaultLocale] ?? item.code;
        alternates[lng] = urlForKind(item.kind, lng, slug);
      }
      // Per-language entry с alternates ─ иначе Google не свяжет 3 версии.
      for (const lng of langs) {
        dynamic.push({
          url: alternates[lng],
          lastModified: item.lastmod ? new Date(item.lastmod) : new Date(),
          changeFrequency: (item.changefreq as Entry["changeFrequency"]) ?? "weekly",
          priority: item.priority,
          alternates: { languages: alternates },
        });
      }
    }
  }

  return [...staticEntries(), ...dynamic];
}
