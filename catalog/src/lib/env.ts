/**
 * Public env-vars (NEXT_PUBLIC_*) и server-only секреты.
 * Используем `process.env` напрямую — Next.js inline'ит NEXT_PUBLIC_*
 * на этапе сборки, а server-only переменные доступны только в RSC/route handlers.
 */
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/+$/, "") ?? "https://yembro.uz";

/**
 * URL бэкенда. На сервере (RSC, route handlers, sitemap) предпочитаем
 * `CATALOG_API_URL_INTERNAL` — это docker-сетевое имя (например
 * http://api:30000), которое доступно изнутри контейнера. На клиенте
 * (`'use client'` компоненты) `process.env.CATALOG_API_URL_INTERNAL`
 * отсутствует, и используется `NEXT_PUBLIC_API_URL` — публичный URL
 * который браузер может резолвить.
 */
export const API_URL = (
  process.env.CATALOG_API_URL_INTERNAL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.yembro.uz/api/catalog/v1"
).replace(/\/+$/, "");

export const ERP_URL =
  process.env.NEXT_PUBLIC_ERP_URL?.replace(/\/+$/, "") ?? "https://erp.yembro.uz";

export const YM_ID = process.env.NEXT_PUBLIC_YM_ID ?? "";
export const GA_ID = process.env.NEXT_PUBLIC_GA_ID ?? "";

export const REVALIDATE_SECRET = process.env.REVALIDATE_SECRET ?? "";

/** ISR-окно для большинства страниц (1 час). */
export const ISR_REVALIDATE_SECONDS = 3600;
