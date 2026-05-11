import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  experimental: {
    optimizePackageImports: ["next-intl", "schema-dts"],
  },
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      // CDN-домен на случай если когда-нибудь введём
      { protocol: "https", hostname: "media.yembro.uz", pathname: "/**" },
      // Прод-API: тут реально живут MediaFiles
      { protocol: "https", hostname: "api.erp.yembro.uz", pathname: "/media/**" },
      // Староe имя на случай если оно ещё где-то осталось
      { protocol: "https", hostname: "api.yembro.uz", pathname: "/media/**" },
      // Staging
      { protocol: "https", hostname: "staging.api.erp.yembro.uz", pathname: "/media/**" },
      // Локалка через docker-compose host port
      { protocol: "http", hostname: "localhost", pathname: "/media/**" },
    ],
  },
  async headers() {
    return [
      {
        source: "/_next/static/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
};

export default withNextIntl(config);
