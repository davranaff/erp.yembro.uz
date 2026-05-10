import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ContactForm } from "@/components/forms/ContactForm";
import { Section } from "@/components/layout/Container";
import { FAQPageJsonLd } from "@/components/seo/JsonLd";
import { GlobeIcon, MailIcon, PhoneIcon } from "@/components/ui/Icon";
import { isLocale, type Locale } from "@/i18n/config";
import { fetchPage } from "@/lib/api";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) return {};
  const t = await getTranslations({ locale: lang, namespace: "contacts" });
  const page = await fetchPage("contacts", lang as Locale);
  return buildMetadata({
    locale: lang,
    path: "/contacts",
    title: page?.meta_title || t("title"),
    description: page?.meta_description || t("subtitle"),
    ogImage: page?.og_image ?? null,
  });
}

function parseFaqBody(body: string): { question: string; answer: string }[] {
  // Простой парсер «В: ... О: ...» / «S: ... J: ...» / «Q: ... A: ...»
  const pattern = /(?:В|S|Q):\s*([\s\S]+?)\n\s*(?:О|J|A):\s*([\s\S]+?)(?=\n\s*(?:В|S|Q):|$)/g;
  const out: { question: string; answer: string }[] = [];
  let m;
  while ((m = pattern.exec(body)) !== null) {
    out.push({ question: m[1].trim(), answer: m[2].trim() });
  }
  return out;
}

export default async function ContactsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) return null;
  setRequestLocale(lang);
  const locale = lang as Locale;
  const t = await getTranslations({ locale, namespace: "contacts" });
  const [contactPage, faqPage] = await Promise.all([
    fetchPage("contacts", locale),
    fetchPage("faq", locale),
  ]);

  const faqs = faqPage?.body ? parseFaqBody(faqPage.body) : [];

  return (
    <>
      {faqs.length > 0 && <FAQPageJsonLd faqs={faqs} />}

      {/* Hero with form */}
      <section className="bg-grad-soft" style={{ position: "relative", overflow: "hidden" }}>
        <div className="blob" style={{ width: 420, height: 420, top: -120, right: -100, background: "var(--brand-orange)", opacity: 0.25 }} aria-hidden />
        <div className="container" style={{ position: "relative", zIndex: 1, paddingTop: 64, paddingBottom: 64 }}>
          <div className="anim-fade-in-up" style={{ marginBottom: 48 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>
              {locale === "ru" ? "На связи" : locale === "uz" ? "Aloqada" : "Get in touch"}
            </div>
            <h1 className="h1" style={{ marginBottom: 16, maxWidth: 800 }}>
              {contactPage?.title || t("title")}
            </h1>
            <p className="lead" style={{ maxWidth: 640 }}>{t("subtitle")}</p>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.2fr)",
            gap: 56,
            alignItems: "start",
          }} className="contacts-grid">
            {/* CONTACTS info */}
            <div className="anim-fade-in-up delay-200">
              {[
                { Icon: PhoneIcon, label: locale === "ru" ? "Телефон" : locale === "uz" ? "Telefon" : "Phone", value: "+998 (90) 000-00-00", href: "tel:+998900000000" },
                { Icon: MailIcon, label: "Email", value: "hello@yembro.uz", href: "mailto:hello@yembro.uz" },
                { Icon: GlobeIcon, label: "Telegram", value: "@yembro", href: "https://t.me/yembro" },
              ].map(({ Icon, label, value, href }) => (
                <a key={label} href={href} className="card card-hover" style={{
                  display: "flex",
                  gap: 16,
                  alignItems: "center",
                  padding: 20,
                  marginBottom: 12,
                  textDecoration: "none",
                  color: "inherit",
                }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: "var(--radius-md)",
                    background: "var(--brand-grad)", color: "#fff",
                    display: "grid", placeItems: "center",
                    boxShadow: "var(--shadow-orange)",
                    flexShrink: 0,
                  }}>
                    <Icon width={20} height={20} />
                  </div>
                  <div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--fg-3)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>{label}</div>
                    <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, marginTop: 2 }}>{value}</div>
                  </div>
                </a>
              ))}
              {contactPage?.body && (
                <div style={{
                  marginTop: 24,
                  padding: 20,
                  fontSize: "var(--text-sm)",
                  color: "var(--fg-2)",
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.7,
                }}>
                  {contactPage.body}
                </div>
              )}
            </div>

            {/* FORM */}
            <div className="card anim-fade-in-up delay-300" style={{ padding: 32 }}>
              <h2 className="h3" style={{ marginBottom: 24 }}>{t("formTitle")}</h2>
              <ContactForm />
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      {faqs.length > 0 && (
        <Section>
          <div className="eyebrow anim-fade-in-up" style={{ marginBottom: 12 }}>FAQ</div>
          <h2 className="h2 anim-fade-in-up delay-100" style={{ marginBottom: 40 }}>
            {locale === "ru" ? "Частые вопросы" : locale === "uz" ? "Tez-tez beriladigan savollar" : "Frequently asked questions"}
          </h2>
          <div style={{ maxWidth: 820, display: "grid", gap: 12 }}>
            {faqs.map((f, i) => (
              <details key={i} className="card anim-fade-in-up" style={{
                padding: "20px 24px",
                animationDelay: `${i * 60}ms`,
              }}>
                <summary style={{
                  cursor: "pointer",
                  fontWeight: 700,
                  fontSize: "var(--text-lg)",
                  listStyle: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                }}>
                  {f.question}
                  <span style={{
                    width: 28, height: 28, flexShrink: 0,
                    borderRadius: "50%",
                    background: "var(--brand-orange-soft)",
                    color: "var(--brand-orange)",
                    display: "grid", placeItems: "center",
                    fontSize: 18, fontWeight: 700,
                  }}>+</span>
                </summary>
                <div style={{
                  marginTop: 16,
                  fontSize: "var(--text-base)",
                  color: "var(--fg-2)",
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                }}>
                  {f.answer}
                </div>
              </details>
            ))}
          </div>
        </Section>
      )}

      <style>{`
        @media (max-width: 900px) {
          .contacts-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  );
}
