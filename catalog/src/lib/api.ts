/**
 * Серверные fetch-обёртки к публичному API каталога.
 *
 * Все запросы идут с `next: { revalidate, tags }` — Next.js кеширует
 * результаты на edge на ISR_REVALIDATE_SECONDS секунд, а бэкенд при
 * правке контента дёргает /api/revalidate с теми же тегами для
 * мгновенной инвалидации.
 */
import "server-only";

import { z } from "zod";

import type { Lang } from "./types";
import {
  BrandSchema,
  CatalogPageSchema,
  CategoryNodeSchema,
  PaginatedSchema,
  ProductCardSchema,
  ProductDetailSchema,
  SitemapResponseSchema,
} from "./types";
import { API_URL, ISR_REVALIDATE_SECONDS } from "./env";

type FetchOpts = {
  tags?: string[];
  revalidate?: number | false;
  lang?: Lang;
  searchParams?: Record<string, string | number | undefined>;
};

async function apiGet<T extends z.ZodTypeAny>(
  schema: T,
  path: string,
  { tags = [], revalidate = ISR_REVALIDATE_SECONDS, lang, searchParams }: FetchOpts = {},
): Promise<z.infer<T> | null> {
  const url = new URL(API_URL.replace(/\/+$/, "") + "/" + path.replace(/^\/+/, ""));
  if (lang) url.searchParams.set("lang", lang);
  if (searchParams) {
    for (const [k, v] of Object.entries(searchParams)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    }
  }
  try {
    // При server-side fetch мы ходим к API через docker-internal hostname
    // (например http://prod-api:30000), а сериализаторы Django по умолчанию
    // строят абсолютные URL картинок через `request.build_absolute_uri()` —
    // в итоге картинки получают URL `http://prod-api:30000/media/...`,
    // недоступный извне.
    //
    // X-Forwarded-Host/Proto уважается Django при USE_X_FORWARDED_HOST=True,
    // и сериализатор отдаёт правильный публичный URL media-файлов.
    const headers: Record<string, string> = {};
    if (lang) headers["Accept-Language"] = lang;
    // Внутренний хост ловим по env-переменной (server-side only).
    if (process.env.CATALOG_API_URL_INTERNAL) {
      try {
        const publicHost = new URL(
          process.env.NEXT_PUBLIC_API_URL ?? "https://api.erp.yembro.uz",
        ).host;
        headers["X-Forwarded-Host"] = publicHost;
        headers["X-Forwarded-Proto"] = "https";
      } catch { /* malformed env — пропускаем */ }
    }
    const res = await fetch(url.toString(), {
      next: { revalidate, tags },
      headers: Object.keys(headers).length > 0 ? headers : undefined,
    });
    if (!res.ok) {
      // Любой 4xx/5xx — возвращаем null. Страница либо отрендерит "пустое",
      // либо сделает notFound(). Так сборка не падает, если API недоступен.
      if (res.status >= 500) {
        console.warn(`[catalog/api] ${res.status} on ${url.pathname}`);
      }
      return null;
    }
    return schema.parse(await res.json());
  } catch (err) {
    // Сетевая ошибка / парс-ошибка zod — лог + null.
    // Это нужно чтобы `next build` не падал на этапе SSG, когда бэкенд
    // недоступен (например первичная сборка образа в CI без API).
    console.warn(`[catalog/api] fetch failed on ${url.pathname}:`, err instanceof Error ? err.message : err);
    return null;
  }
}

export async function fetchBrands(lang: Lang) {
  return apiGet(PaginatedSchema(BrandSchema), "brands/", {
    lang,
    tags: ["brands"],
  });
}

export async function fetchBrand(code: string, lang: Lang) {
  const schema = BrandSchema.extend({
    featured: z.array(ProductCardSchema).optional(),
  });
  return apiGet(schema, `brands/${code}/`, {
    lang,
    tags: [`brand:${code}`, "brands"],
  });
}

export async function fetchCategories(lang: Lang) {
  return apiGet(z.array(CategoryNodeSchema), "categories/", {
    lang,
    tags: ["categories"],
  });
}

export async function fetchCategory(code: string, lang: Lang) {
  const schema = CategoryNodeSchema.extend({
    breadcrumbs: z.array(z.object({
      code: z.string(),
      slug: z.string(),
      name: z.string(),
    })),
    children: z.array(CategoryNodeSchema),
  });
  return apiGet(schema, `categories/${code}/`, {
    lang,
    tags: [`category:${code}`, "categories"],
  });
}

export type ProductListParams = {
  category?: string;
  brand?: string;
  direction?: string;
  protein_gte?: number;
  protein_lte?: number;
  age_days?: number;
  is_featured?: boolean;
  search?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
};

export async function fetchProducts(lang: Lang, params: ProductListParams = {}) {
  return apiGet(PaginatedSchema(ProductCardSchema), "products/", {
    lang,
    tags: ["products", params.category ? `category:${params.category}` : null, params.brand ? `brand:${params.brand}` : null].filter(Boolean) as string[],
    searchParams: {
      ...params,
      is_featured: params.is_featured == null ? undefined : params.is_featured ? "true" : "false",
    } as Record<string, string | number | undefined>,
  });
}

export async function fetchProduct(code: string, lang: Lang) {
  return apiGet(ProductDetailSchema, `products/${code}/`, {
    lang,
    tags: [`product:${code}`, "products"],
  });
}

export async function fetchPage(code: string, lang: Lang) {
  return apiGet(CatalogPageSchema, `pages/${code}/`, {
    lang,
    tags: [`page:${code}`],
  });
}

export async function fetchSitemap() {
  return apiGet(SitemapResponseSchema, "sitemap/", {
    tags: ["sitemap"],
    revalidate: ISR_REVALIDATE_SECONDS,
  });
}
