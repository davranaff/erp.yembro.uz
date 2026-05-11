import { JetBrains_Mono, Manrope } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Analytics } from "@/components/analytics/Analytics";
import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { ScrollProgress } from "@/components/layout/ScrollProgress";
import { SplashScreen } from "@/components/layout/SplashScreen";
import { OrganizationJsonLd, WebSiteJsonLd } from "@/components/seo/JsonLd";
import { isLocale, locales } from "@/i18n/config";

const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-manrope",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export default async function LangLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  setRequestLocale(lang);
  const messages = await getMessages();

  return (
    <html lang={lang} className={`${manrope.variable} ${jetbrains.variable}`}>
      <body>
        <NextIntlClientProvider locale={lang} messages={messages}>
          <ScrollProgress />
          <SplashScreen />
          <Header />
          <main>{children}</main>
          <Footer />
          <OrganizationJsonLd locale={lang} />
          <WebSiteJsonLd locale={lang} />
          <Analytics />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
