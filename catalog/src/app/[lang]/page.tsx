import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Section } from "@/components/layout/Container";
import {
  ArrowRightIcon,
  ChartIcon,
  CheckIcon,
  DirectionIcon,
  FlaskIcon,
  LeafIcon,
  ShieldIcon,
  StarIcon,
  TruckIcon,
} from "@/components/ui/Icon";
import { Link } from "@/i18n/routing";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchBrands, fetchCategories, fetchProducts } from "@/lib/api";
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
  const t = await getTranslations({ locale: lang, namespace: "home" });
  const brand = await getTranslations({ locale: lang, namespace: "brand" });
  return buildMetadata({
    locale: lang,
    path: "/",
    title: `${brand("name")} — ${t("heroTitle")}`,
    description: t("heroSubtitle"),
  });
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) return null;
  setRequestLocale(lang);
  const locale = lang as Locale;

  const t = await getTranslations({ locale, namespace: "home" });
  const tCommon = await getTranslations({ locale, namespace: "common" });
  const tDir = await getTranslations({ locale, namespace: "directions" });
  const tNav = await getTranslations({ locale, namespace: "nav" });

  const [featuredResp, categories, brandsResp] = await Promise.all([
    fetchProducts(locale, { is_featured: true, page_size: 8 }),
    fetchCategories(locale),
    fetchBrands(locale),
  ]);
  const featured = featuredResp?.results ?? [];
  const rootCategories = (categories ?? []).filter((c) => c.level === 0);
  const brands = brandsResp?.results ?? [];

  const benefits = [
    { icon: FlaskIcon, key: "qc" },
    { icon: ChartIcon, key: "fcr" },
    { icon: ShieldIcon, key: "stable" },
    { icon: TruckIcon, key: "delivery" },
    { icon: LeafIcon, key: "natural" },
    { icon: StarIcon, key: "support" },
  ] as const;

  const benefitText: Record<string, { title: string; text: string }> = {
    ru: {} as never,
    uz: {} as never,
    en: {} as never,
  };
  // Embedded copy by locale (избегаем расширения messages json'ов).
  const COPY: Record<string, Record<string, { title: string; text: string }>> = {
    ru: {
      qc: {
        title: "Лаборатория в цеху",
        text: "Не «у партнёра». В пятидесяти метрах от линии. 12 параметров на каждую партию, проба в архиве шесть месяцев.",
      },
      fcr: {
        title: "FCR, который не стыдно показать",
        text: "Рецепты собираются под целевой FCR 1.55–1.65 у бройлера. Не «в среднем по году», а в каждой партии.",
      },
      stable: {
        title: "Партии, которые повторяются",
        text: "Отклонение протеина не больше 0.5% между поставками. Стадо не «качает» от мешка к мешку.",
      },
      delivery: {
        title: "Машина выезжает в течение суток",
        text: "По всему Узбекистану — окно доставки 24–72 часа. Свой парк, своя диспетчерская, ноль перекупов.",
      },
      natural: {
        title: "Линейка Bio — без АБ всерьёз",
        text: "Эфирные масла, защищённые кислоты, пробиотики Bacillus. Этикетка «без антибиотиков», которую не стыдно показать лаборатории.",
      },
      support: {
        title: "Зоотехник, который не пропадает",
        text: "После поставки мы остаёмся на связи. Скорректируем программу по возрасту, по сезону, по тому, что показывает дашборд.",
      },
    },
    uz: {
      qc: {
        title: "Sexdagi laboratoriya",
        text: "«Hamkorda» emas. Liniyadan ellik metr narida. Har bir partiyada 12 parametr, namuna olti oy arxivda.",
      },
      fcr: {
        title: "Koʻrsatishga uyalmaydigan FCR",
        text: "Retseptlar broyler uchun maqsadli FCR 1.55–1.65 ga moslab yigʻiladi. «Yiliga oʻrtacha» emas, har bir partiyada.",
      },
      stable: {
        title: "Takrorlanadigan partiyalar",
        text: "Yetkazib berishlar orasida protein chetga chiqishi 0.5% dan oshmaydi. Pod qopdan-qopga «ogʻib ketmaydi».",
      },
      delivery: {
        title: "Mashina bir kun ichida yoʻlga chiqadi",
        text: "Butun Oʻzbekiston boʻylab — 24–72 soat yetkazib berish oynasi. Oʻz transporti, oʻz dispetcheri, vositachilarsiz.",
      },
      natural: {
        title: "Bio liniya — jiddiy ravishda AB-siz",
        text: "Efir moylari, himoyalangan kislotalar, Bacillus probiotiklari. Laboratoriyaga koʻrsatishga uyalmaydigan «antibiotiksiz» yorlik.",
      },
      support: {
        title: "Yoʻqolib qolmaydigan zootexnik",
        text: "Yetkazib berishdan keyin ham aloqada qolamiz. Yosh, fasl va dashbord koʻrsatkichlariga qarab dasturni tuzatamiz.",
      },
    },
    en: {
      qc: {
        title: "Lab inside the mill",
        text: "Not «at a partner's». Fifty meters from the line. Twelve parameters on every batch, sample retained for six months.",
      },
      fcr: {
        title: "FCR worth showing",
        text: "Recipes built around a target broiler FCR of 1.55–1.65. Not «yearly average» — every batch.",
      },
      stable: {
        title: "Batches that repeat",
        text: "Protein deviation between shipments stays under 0.5%. The flock doesn't swing bag-to-bag.",
      },
      delivery: {
        title: "Truck rolling within a day",
        text: "Nationwide — a 24–72 hour delivery window. Our fleet, our dispatch, zero middlemen.",
      },
      natural: {
        title: "Bio line — antibiotic-free for real",
        text: "Essential oils, protected acids, Bacillus probiotics. The kind of «no-AB» label you can hand straight to a lab.",
      },
      support: {
        title: "A nutritionist who stays around",
        text: "We don't disappear after delivery. We retune the program by age, by season, by what the dashboard says.",
      },
    },
  };
  const copy = COPY[locale] ?? COPY.ru;
  void benefitText;

  return (
    <>
      {/* ── HERO ─────────────────────────────────────────── */}
      <section
        className="bg-grad-soft bg-noise"
        style={{
          position: "relative",
          padding: "80px 0 96px",
          overflow: "hidden",
        }}
      >
        {/* decorative blobs */}
        <div className="blob" style={{ width: 440, height: 440, top: -100, right: -120, background: "var(--brand-orange)" }} aria-hidden />
        <div className="blob" style={{ width: 360, height: 360, bottom: -120, left: -80, background: "var(--brand-yellow)", animationDelay: "-6s" }} aria-hidden />

        <div className="container" style={{ position: "relative", zIndex: 1 }}>
          <div style={{ maxWidth: 880 }}>
            <div className="anim-fade-in-up" style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 16px",
              borderRadius: "var(--radius-pill)",
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-card)",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              color: "var(--fg-2)",
              marginBottom: 24,
            }}>
              <span className="anim-pulse-glow" style={{
                width: 8, height: 8, borderRadius: "50%",
                background: "var(--brand-orange)",
              }} aria-hidden />
              {locale === "ru" ? "Узбекское зерно. Узбекская лаборатория. Узбекская ферма."
                : locale === "uz" ? "Oʻzbek doni. Oʻzbek laboratoriyasi. Oʻzbek fermasi."
                : "Uzbek grain. Uzbek lab. Uzbek farm."}
            </div>

            <h1 className="h1 anim-fade-in-up delay-100" style={{ marginBottom: 24 }}>
              {locale === "ru" ? <>Стадо растёт ровно,<br />когда корм <span className="text-grad">не врёт</span></>
                : locale === "uz" ? <>Yem <span className="text-grad">aldamasa</span>,<br />pod tekis oʻsadi</>
                : <>The flock grows even<br />when the feed <span className="text-grad">tells the truth</span></>}
            </h1>
            <p className="lead anim-fade-in-up delay-200" style={{ marginBottom: 40, maxWidth: 640 }}>
              {t("heroSubtitle")}
            </p>
            <div className="anim-fade-in-up delay-300" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Link href="/catalog" className="btn btn-primary btn-xl">
                {t("ctaCatalog")} <ArrowRightIcon width={18} height={18} />
              </Link>
              <Link href="/contacts" className="btn btn-secondary btn-xl">
                {t("ctaContact")}
              </Link>
            </div>

            {/* Stats */}
            <div className="anim-fade-in-up delay-500" style={{
              marginTop: 64,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 24,
              maxWidth: 720,
            }}>
              {[
                ["19+", locale === "ru" ? "позиций под каждый этап" : locale === "uz" ? "har bir bosqich uchun pozitsiya" : "SKUs across every stage"],
                ["3", locale === "ru" ? "линейки — стандарт, премиум, без АБ" : locale === "uz" ? "liniya — standart, premium, AB-siz" : "lines — standard, premium, AB-free"],
                ["48ч", locale === "ru" ? "от заявки до выгрузки в бункер" : locale === "uz" ? "buyurtmadan bunkerga yuklashgacha" : "from order to silo unload"],
                ["<0.5%", locale === "ru" ? "разброс протеина между партиями" : locale === "uz" ? "partiyalar orasida protein farqi" : "protein spread between batches"],
              ].map(([num, label]) => (
                <div key={label}>
                  <div className="text-grad" style={{
                    fontSize: "var(--text-3xl)",
                    fontWeight: 800,
                    fontFamily: "var(--font-mono)",
                    letterSpacing: "-0.02em",
                    lineHeight: 1,
                  }}>{num}</div>
                  <div style={{
                    fontSize: "var(--text-sm)",
                    color: "var(--fg-3)",
                    marginTop: 6,
                    fontWeight: 500,
                  }}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── BENEFITS ─────────────────────────────────────── */}
      <Section>
        <div style={{ maxWidth: 760, marginBottom: 56 }}>
          <div className="eyebrow anim-fade-in-up" style={{ marginBottom: 12 }}>
            {locale === "ru" ? "Почему фермеры остаются с нами" : locale === "uz" ? "Fermerlar nega biz bilan qoladi" : "Why farms stick with us"}
          </div>
          <h2 className="h2 anim-fade-in-up delay-100">
            {locale === "ru" ? "Шесть вещей, ради которых обычно меняют поставщика" : locale === "uz" ? "Yetkazib beruvchini odatda almashtiradigan oltita narsa" : "Six things farms usually change suppliers for"}
          </h2>
        </div>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 20,
        }}>
          {benefits.map(({ icon: Icon, key }, i) => (
            <div key={key} className="card anim-fade-in-up" style={{
              padding: 28,
              animationDelay: `${100 + i * 80}ms`,
            }}>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: "var(--radius-md)",
                background: "var(--brand-grad-soft)",
                display: "grid",
                placeItems: "center",
                color: "var(--brand-orange)",
                marginBottom: 16,
              }}>
                <Icon width={24} height={24} />
              </div>
              <h3 style={{
                fontSize: "var(--text-lg)",
                fontWeight: 700,
                margin: "0 0 8px",
              }}>{copy[key].title}</h3>
              <p style={{
                fontSize: "var(--text-sm)",
                color: "var(--fg-2)",
                margin: 0,
                lineHeight: 1.6,
              }}>{copy[key].text}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── DIRECTIONS ───────────────────────────────────── */}
      {rootCategories.length > 0 && (
        <Section style={{ background: "var(--bg-card)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", marginBottom: 40, gap: 24, flexWrap: "wrap" }}>
            <div>
              <div className="eyebrow" style={{ marginBottom: 12 }}>
                {locale === "ru" ? "Корм под задачу" : locale === "uz" ? "Vazifaga moslangan yem" : "Feed by purpose"}
              </div>
              <h2 className="h2">{t("directionsTitle")}</h2>
              <p className="lead" style={{ marginTop: 12, maxWidth: 600 }}>
                {locale === "ru"
                  ? "Не «универсальный комбикорм для всего». Каждая программа собрана под конкретную задачу: вырастить мясо, отдать яйцо, получить инкубационное яйцо."
                  : locale === "uz"
                  ? "«Hamma narsa uchun universal yem» emas. Har bir dastur aniq vazifaga moslangan: goʻsht oʻstirish, tuxum berish, inkubatsiya tuxumi olish."
                  : "Not «one feed for everything». Every program is built for a specific job: grow meat, lay eggs, produce hatching eggs."}
              </p>
            </div>
            <Link href="/catalog" className="btn btn-ghost">
              {tCommon("viewAll")} <ArrowRightIcon width={16} height={16} />
            </Link>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 20,
            }}
          >
            {rootCategories.map((c, i) => (
              <Link
                key={c.id}
                href={`/catalog/${c.code}`}
                className="card card-hover anim-fade-in-up glow-hover"
                style={{
                  padding: 32,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  minHeight: 220,
                  animationDelay: `${i * 80}ms`,
                  position: "relative",
                  isolation: "isolate",
                }}
              >
                <div style={{
                  width: 56,
                  height: 56,
                  borderRadius: "var(--radius-md)",
                  background: "var(--brand-grad)",
                  display: "grid",
                  placeItems: "center",
                  color: "#fff",
                  boxShadow: "var(--shadow-orange)",
                }}>
                  <DirectionIcon direction={c.direction} width={28} height={28} />
                </div>
                <div style={{ marginTop: "auto" }}>
                  <div className="eyebrow" style={{ marginBottom: 6 }}>
                    {tDir(c.direction as never)}
                  </div>
                  <h3 className="h3" style={{ margin: "0 0 8px" }}>{c.name}</h3>
                  {c.description && (
                    <p style={{
                      fontSize: "var(--text-sm)",
                      color: "var(--fg-2)",
                      margin: 0,
                      lineHeight: 1.5,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}>{c.description}</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* ── BRANDS ───────────────────────────────────────── */}
      {brands.length > 0 && (
        <Section>
          <div style={{ marginBottom: 40 }}>
            <div className="eyebrow anim-fade-in-up" style={{ marginBottom: 12 }}>
              {locale === "ru" ? "Три бренда — три уровня требовательности"
                : locale === "uz" ? "Uch brend — uch darajadagi talabchanlik"
                : "Three brands — three levels of demand"}
            </div>
            <h2 className="h2 anim-fade-in-up delay-100">
              {locale === "ru" ? "Yembro, Yembro Pro и Yembro Bio"
                : locale === "uz" ? "Yembro, Yembro Pro va Yembro Bio"
                : "Yembro, Yembro Pro and Yembro Bio"}
            </h2>
            <p className="lead anim-fade-in-up delay-200" style={{ marginTop: 16, maxWidth: 720 }}>
              {locale === "ru"
                ? "Стандартная линейка для рутинных циклов. Pro — для интенсивного откорма с прицелом на сотые доли FCR. Bio — для производителей яйца и мяса категории «без антибиотиков»."
                : locale === "uz"
                ? "Rutin sikllar uchun standart liniya. Pro — FCRning yuzdan bir ulushlariga moslashgan intensiv boqish uchun. Bio — «antibiotiksiz» kategoriyadagi tuxum va goʻsht ishlab chiqaruvchilar uchun."
                : "The standard line for routine cycles. Pro — for intensive operations chasing the last hundredths of FCR. Bio — for producers in the «no-AB» tier."}
            </p>
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: 20,
          }}>
            {brands.map((b, i) => (
              <Link
                key={b.id}
                href={`/brand/${b.code}`}
                className="card card-hover anim-fade-in-up"
                style={{
                  padding: 32,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  animationDelay: `${i * 100}ms`,
                  borderTop: "4px solid var(--brand-orange)",
                }}
              >
                <h3 className="h3 text-grad" style={{ margin: 0 }}>{b.name}</h3>
                <p style={{
                  fontSize: "var(--text-base)",
                  color: "var(--fg-2)",
                  margin: 0,
                  lineHeight: 1.6,
                  display: "-webkit-box",
                  WebkitLineClamp: 4,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}>{b.description}</p>
                <div style={{
                  marginTop: "auto",
                  paddingTop: 16,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  color: "var(--brand-orange)",
                  fontWeight: 600,
                  fontSize: "var(--text-sm)",
                }}>
                  {tCommon("readMore")} <ArrowRightIcon width={14} height={14} />
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* ── FEATURED ─────────────────────────────────────── */}
      {featured.length > 0 && (
        <Section style={{ background: "var(--bg-card)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", marginBottom: 40, gap: 24, flexWrap: "wrap" }}>
            <div>
              <div className="eyebrow" style={{ marginBottom: 12 }}>
                <StarIcon width={12} height={12} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
                {locale === "ru" ? "К ним возвращаются" : locale === "uz" ? "Qaytib keladigan tovarlar" : "Customers come back for"}
              </div>
              <h2 className="h2">{t("featuredTitle")}</h2>
            </div>
            <Link href="/catalog" className="btn btn-secondary">
              {tCommon("viewAll")} <ArrowRightIcon width={16} height={16} />
            </Link>
          </div>
          <ProductGrid products={featured} />
        </Section>
      )}

      {/* ── ERP CTA ──────────────────────────────────────── */}
      <Section className="bg-dark" style={{ position: "relative", overflow: "hidden" }}>
        <div className="blob" style={{ width: 500, height: 500, top: -120, right: -100, background: "var(--brand-orange)", opacity: 0.25 }} aria-hidden />
        <div className="container" style={{ position: "relative", zIndex: 1 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 32, maxWidth: 880 }}>
            <div className="badge badge-grad" style={{
              alignSelf: "flex-start",
              padding: "8px 16px",
              fontSize: "var(--text-sm)",
            }}>
              Yembro ERP
            </div>
            <h2 className="h2" style={{ color: "var(--fg-inverse)", margin: 0 }}>
              {t("erpBlockTitle")}
            </h2>
            <p style={{ fontSize: "var(--text-lg)", color: "rgba(255,253,247,0.85)", margin: 0, lineHeight: 1.6 }}>
              {t("erpBlockText")}
            </p>
            <ul style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 12,
              listStyle: "none",
              padding: 0,
              margin: 0,
            }}>
              {[
                locale === "ru" ? "Сырьё, рецепты и QC в одном модуле"
                  : locale === "uz" ? "Xom ashyo, retseptlar va QC bitta modulda"
                  : "Raw materials, recipes and QC in one module",
                locale === "ru" ? "Инкубация и откорм с FCR по дням"
                  : locale === "uz" ? "Inkubatsiya va kunlik FCR bilan boqish"
                  : "Incubation and growing with daily FCR",
                locale === "ru" ? "Несушка, забой, прослеживаемость"
                  : locale === "uz" ? "Tovuqxona, soʻyish, kuzatuv"
                  : "Layer, slaughter, traceability",
                locale === "ru" ? "Финансы, валюта ЦБ, П&L по подразделениям"
                  : locale === "uz" ? "Moliya, MB valyutasi, boʻlinmalar boʻyicha P&L"
                  : "Finance, central-bank FX, P&L by unit",
              ].map((it) => (
                <li key={it} style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: "var(--text-sm)",
                  color: "rgba(255,253,247,0.92)",
                }}>
                  <CheckIcon width={18} height={18} style={{ color: "var(--brand-yellow)" }} />
                  {it}
                </li>
              ))}
            </ul>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
              <Link href="/erp" className="btn btn-primary btn-lg">
                {t("erpBlockCta")} <ArrowRightIcon width={18} height={18} />
              </Link>
              <a href={ERP_URL} target="_blank" rel="noopener" className="btn btn-secondary btn-lg" style={{
                background: "rgba(255,253,247,0.1)",
                color: "var(--fg-inverse)",
                borderColor: "rgba(255,253,247,0.2)",
              }}>
                {tNav("erp")} →
              </a>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
