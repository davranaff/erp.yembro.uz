import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Section } from "@/components/layout/Container";
import { Link } from "@/i18n/routing";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchPage } from "@/lib/api";
import { ERP_URL } from "@/lib/env";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) return {};
  const t = await getTranslations({ locale: lang, namespace: "erp" });
  const page = await fetchPage("erp", lang as Locale);
  return buildMetadata({
    locale: lang,
    path: "/erp",
    title: page?.meta_title || t("title"),
    description: page?.meta_description || t("subtitle"),
    ogImage: page?.og_image ?? null,
  });
}

type FeatureKey =
  | "raw" | "incub" | "feedlot" | "matochnik"
  | "slaughter" | "sales" | "finance" | "dashboard";

const FEATURES: { key: FeatureKey; copy: Record<string, { title: string; text: string }> }[] = [
  { key: "raw", copy: {
    ru: { title: "Сырьё и комбикорма", text: "Закупки, усушка, лабораторный QC, рецепты и партии — без Excel под рукой." },
    uz: { title: "Xom ashyo va yemlar", text: "Xaridlar, usushka, laboratoriya QC, retseptlar va partiyalar — Excelsiz." },
    en: { title: "Raw materials & feed mill", text: "Procurement, shrinkage, lab QC, recipes and batches — without Excel duct tape." },
  }},
  { key: "incub", copy: {
    ru: { title: "Инкубация", text: "Партии яйца, hatch rate с разбивкой по поставщикам, биоконтроль." },
    uz: { title: "Inkubatsiya", text: "Tuxum partiyalari, yetkazib beruvchilar boʻyicha hatch rate, bionazorat." },
    en: { title: "Incubation", text: "Egg batches, hatch rate by supplier, biocontrol — all in one place." },
  }},
  { key: "feedlot", copy: {
    ru: { title: "Откорм бройлеров", text: "Посадка, кормление, падёж, FCR и ADG по дням, прогноз убоя." },
    uz: { title: "Broyler boqish", text: "Joylashtirish, oziqlanish, tushgan, kunlik FCR va ADG, soʻyish prognozi." },
    en: { title: "Broiler growing", text: "Placement, feeding, mortality, daily FCR and ADG, slaughter forecast." },
  }},
  { key: "matochnik", copy: {
    ru: { title: "Маточник и несушка", text: "Кривые продуктивности, качество яйца, графики кальция, фотодневник." },
    uz: { title: "Onaxona va tovuqxona", text: "Unumdorlik egri chiziqlari, tuxum sifati, kaltsiy jadvallari." },
    en: { title: "Layer & breeder", text: "Production curves, egg quality, calcium schedules, photo diary." },
  }},
  { key: "slaughter", copy: {
    ru: { title: "Забой и фасовка", text: "Выход тушки, прослеживаемость от партии до пакета на полке." },
    uz: { title: "Soʻyish va qadoqlash", text: "Goʻsht chiqishi, partiyadan javondagi qopgacha kuzatuv." },
    en: { title: "Slaughter & packaging", text: "Carcass yield, batch-to-shelf traceability." },
  }},
  { key: "sales", copy: {
    ru: { title: "Продажи и склад", text: "Несколько юрлиц, отгрузки, документы, дебиторка, остатки в реальном времени." },
    uz: { title: "Sotuv va ombor", text: "Bir nechta yuridik shaxslar, ortishlar, hujjatlar, debitorlik, real vaqt qoldigʻi." },
    en: { title: "Sales & warehouse", text: "Multi-entity, shipments, docs, AR, real-time inventory." },
  }},
  { key: "finance", copy: {
    ru: { title: "Финансы", text: "Платежи, валютные курсы ЦБ РУЗ, P&L по подразделениям, ничего не теряется в табличках." },
    uz: { title: "Moliya", text: "Toʻlovlar, OʻzR MB valyuta kurslari, boʻlinmalar boʻyicha P&L." },
    en: { title: "Finance", text: "Payments, CBU FX rates, P&L by unit — nothing slips through a spreadsheet." },
  }},
  { key: "dashboard", copy: {
    ru: { title: "Дашборд и Telegram-алёрты", text: "Оператор узнаёт о проблеме за минуту, а не за неделю — и сразу её чинит." },
    uz: { title: "Dashboard va Telegram-ogohlantirishlar", text: "Operator muammoni bir hafta emas, bir daqiqada bilib oladi va darhol tuzatadi." },
    en: { title: "Dashboard & Telegram alerts", text: "Operators learn about a problem in a minute, not a week — and fix it on the spot." },
  }},
];

export default async function ErpPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) return null;
  setRequestLocale(lang);
  const locale = lang as Locale;
  const t = await getTranslations({ locale, namespace: "erp" });
  const page = await fetchPage("erp", locale);

  return (
    <>
      <Section style={{ background: "var(--bg-inverse)", color: "var(--fg-inverse)" }}>
        <div style={{ maxWidth: 800 }}>
          <div style={{ color: "var(--brand-yellow)", fontSize: "var(--text-sm)", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 700, marginBottom: 12 }}>
            Yembro ERP
          </div>
          <h1 className="h1" style={{ marginBottom: 16, color: "var(--fg-inverse)" }}>
            {page?.title || t("title")}
          </h1>
          <p className="lead" style={{ marginBottom: 32, color: "rgba(255,253,247,0.85)" }}>
            {t("subtitle")}
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <a href={ERP_URL} className="btn btn-primary btn-lg" target="_blank" rel="noopener">
              {t("ctaPrimary")} →
            </a>
            <Link href="/contacts" className="btn btn-secondary btn-lg">
              {t("ctaSecondary")}
            </Link>
          </div>
        </div>
      </Section>

      <Section>
        <h2 className="h2 anim-fade-in-up" style={{ marginBottom: 12 }}>{t("featuresTitle")}</h2>
        <p className="lead anim-fade-in-up delay-100" style={{ marginBottom: 40, maxWidth: 720 }}>
          {locale === "ru"
            ? "Восемь модулей, каждый из которых решает одну боль птицефабрики. Можно подключить все сразу — или начать с одного, который болит сильнее всего."
            : locale === "uz"
            ? "Sakkizta modul — har biri parrandachilik fabrikasining bitta ogʻrigʻini hal qiladi. Barchasini bir vaqtda ulashingiz mumkin — yoki eng kuchli ogʻriydiganidan boshlashingiz mumkin."
            : "Eight modules — each one solving a single farm-floor pain. Plug them all in at once, or start with the one that hurts the most."}
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
          }}
        >
          {FEATURES.map(({ key, copy }, i) => {
            const c = copy[locale] ?? copy.ru;
            return (
              <div key={key} className="card anim-fade-in-up" style={{ padding: 24, animationDelay: `${i * 60}ms` }}>
                <div style={{ width: 40, height: 40, borderRadius: "var(--radius-md)", background: "var(--brand-grad)", display: "grid", placeItems: "center", color: "#fff", fontWeight: 800, marginBottom: 12, boxShadow: "var(--shadow-orange)" }}>
                  ✓
                </div>
                <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: "0 0 8px" }}>{c.title}</h3>
                <p style={{ fontSize: "var(--text-sm)", color: "var(--fg-2)", margin: 0, lineHeight: 1.6 }}>{c.text}</p>
              </div>
            );
          })}
        </div>
      </Section>

      {page?.body && (
        <Section style={{ background: "var(--bg-card)" }}>
          <div
            style={{
              fontSize: "var(--text-base)",
              color: "var(--fg-2)",
              lineHeight: 1.7,
              maxWidth: 800,
              whiteSpace: "pre-wrap",
            }}
          >
            {page.body}
          </div>
        </Section>
      )}
    </>
  );
}
