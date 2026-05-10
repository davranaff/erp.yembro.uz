/**
 * Типы и zod-валидаторы ответов публичного API каталога.
 *
 * Бэкенд отдаёт уже локализованные плоские поля (`name`, `slug`, ...) —
 * сервер сам выбирает язык по `?lang=`. Поэтому здесь типы плоские.
 */
import { z } from "zod";

export const LangSchema = z.enum(["ru", "uz", "en"]);
export type Lang = z.infer<typeof LangSchema>;

export const BrandRefSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  name: z.string(),
});
export type BrandRef = z.infer<typeof BrandRefSchema>;

export const CategoryRefSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  name: z.string(),
});
export type CategoryRef = z.infer<typeof CategoryRefSchema>;

export const BrandSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().default(""),
  logo: z.string().nullable().optional(),
  meta_title: z.string().default(""),
  meta_description: z.string().default(""),
  og_image: z.string().nullable().optional(),
  sort_order: z.number().default(0),
});
export type Brand = z.infer<typeof BrandSchema>;

export const CategoryNodeSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().default(""),
  image: z.string().nullable().optional(),
  direction: z.string(),
  meta_title: z.string().default(""),
  meta_description: z.string().default(""),
  og_image: z.string().nullable().optional(),
  parent_id: z.string().nullable(),
  level: z.number(),
  lft: z.number(),
  rght: z.number(),
  tree_id: z.number(),
  sort_order: z.number().default(0),
});
export type CategoryNode = z.infer<typeof CategoryNodeSchema>;

export const ProductImageSchema = z.object({
  id: z.string(),
  image: z.string().nullable(),
  alt: z.string().default(""),
  sort_order: z.number(),
  is_primary: z.boolean(),
});
export type ProductImage = z.infer<typeof ProductImageSchema>;

export const ProductSpecSchema = z.object({
  protein_pct: z.string().nullable(),
  fat_pct: z.string().nullable(),
  fiber_pct: z.string().nullable(),
  lysine_pct: z.string().nullable(),
  methionine_pct: z.string().nullable(),
  me_kcal_per_kg: z.number().nullable(),
  moisture_pct: z.string().nullable(),
  calcium_pct: z.string().nullable(),
  phosphorus_pct: z.string().nullable(),
  extra: z.record(z.unknown()).default({}),
});
export type ProductSpec = z.infer<typeof ProductSpecSchema>;

export const ProductCardSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  name: z.string(),
  short_description: z.string().default(""),
  brand: BrandRefSchema,
  category: CategoryRefSchema,
  direction: z.string(),
  package_kg: z.string().nullable(),
  age_from_days: z.number().nullable(),
  age_to_days: z.number().nullable(),
  is_featured: z.boolean(),
  primary_image: z.string().nullable(),
});
export type ProductCard = z.infer<typeof ProductCardSchema>;

export const ProductDetailSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  name: z.string(),
  short_description: z.string().default(""),
  description: z.string().default(""),
  application: z.string().default(""),
  brand: BrandSchema,
  category: CategoryNodeSchema,
  direction: z.string(),
  package_kg: z.string().nullable(),
  age_from_days: z.number().nullable(),
  age_to_days: z.number().nullable(),
  meta_title: z.string().default(""),
  meta_description: z.string().default(""),
  og_image: z.string().nullable().optional(),
  images: z.array(ProductImageSchema),
  spec: ProductSpecSchema.nullable(),
  breadcrumbs: z.array(z.object({
    code: z.string(),
    slug: z.string(),
    name: z.string(),
  })),
  related: z.array(ProductCardSchema),
  updated_at: z.string(),
});
export type ProductDetail = z.infer<typeof ProductDetailSchema>;

export const PaginatedSchema = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    count: z.number(),
    next: z.string().nullable(),
    previous: z.string().nullable(),
    results: z.array(item),
  });

export const CatalogPageSchema = z.object({
  id: z.string(),
  code: z.string(),
  slug: z.string(),
  title: z.string(),
  body: z.string().default(""),
  meta_title: z.string().default(""),
  meta_description: z.string().default(""),
  og_image: z.string().nullable().optional(),
  updated_at: z.string(),
});
export type CatalogPage = z.infer<typeof CatalogPageSchema>;

export const SitemapItemSchema = z.object({
  kind: z.enum(["brand", "category", "product", "page"]),
  code: z.string(),
  lastmod: z.string().nullable(),
  changefreq: z.string(),
  priority: z.number(),
  alternates: z.record(z.string()),
});
export type SitemapItem = z.infer<typeof SitemapItemSchema>;

export const SitemapResponseSchema = z.object({
  items: z.array(SitemapItemSchema),
  languages: z.array(z.string()),
});
