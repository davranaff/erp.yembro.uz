import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/env";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      // Основные поисковики
      { userAgent: "Googlebot", allow: "/", disallow: ["/api/", "/_next/"] },
      { userAgent: "Yandex", allow: "/", disallow: ["/api/", "/_next/"] },
      { userAgent: "Bingbot", allow: "/", disallow: ["/api/", "/_next/"] },
      // Запрет AI-скрейперов на маркетинговый контент (по желанию владельца)
      { userAgent: "GPTBot", disallow: "/" },
      { userAgent: "ChatGPT-User", disallow: "/" },
      { userAgent: "CCBot", disallow: "/" },
      { userAgent: "Google-Extended", disallow: "/" },
      { userAgent: "anthropic-ai", disallow: "/" },
      { userAgent: "ClaudeBot", disallow: "/" },
      // Все остальные — стандартное правило
      { userAgent: "*", allow: "/", disallow: ["/api/", "/_next/", "/*?*"] },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
