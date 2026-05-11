import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ContactForm } from "@/components/forms/ContactForm";
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
  const contactPage = await fetchPage("contacts", locale);

  return (
    <>
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
                { Icon: PhoneIcon, label: locale === "ru" ? "Телефон" : locale === "uz" ? "Telefon" : "Phone", value: "+998 (94) 542 77 77", href: "tel:+998945427777" },
                { Icon: MailIcon, label: "Email", value: "info@yembro.uz", href: "mailto:info@yembro.uz" },
                { Icon: GlobeIcon, label: "Telegram", value: "@ulugbek_jalolov", href: "https://t.me/ulugbek_jalolov" },
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


      <style>{`
        @media (max-width: 900px) {
          .contacts-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  );
}
