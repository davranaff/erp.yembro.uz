import { getTranslations } from "next-intl/server";

import { GlobeIcon, MailIcon, PhoneIcon } from "@/components/ui/Icon";
import { Link } from "@/i18n/routing";
import { ERP_URL } from "@/lib/env";

import { LogoFull } from "./Logo";

export async function Footer() {
  const t = await getTranslations();
  const year = new Date().getFullYear();
  return (
    <footer className="bg-dark" style={{ marginTop: 80, padding: "64px 0 32px", position: "relative", overflow: "hidden" }}>
      <div className="blob" style={{ width: 380, height: 380, top: -100, left: -80, background: "var(--brand-orange)", opacity: 0.18 }} aria-hidden />
      <div className="container" style={{ position: "relative", zIndex: 1 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 48,
          }}
        >
          {/* Brand */}
          <div>
            <div
              style={{
                background: "rgba(255,255,251,0.97)",
                borderRadius: "var(--radius-md)",
                padding: "16px 20px",
                display: "inline-flex",
                alignItems: "center",
                marginBottom: 16,
                boxShadow: "0 4px 16px -2px rgba(0,0,0,0.25)",
              }}
            >
              <LogoFull height={56} />
            </div>
            <p style={{ color: "rgba(255,253,247,0.7)", fontSize: "var(--text-sm)", margin: 0, maxWidth: 300, lineHeight: 1.6 }}>
              {t("brand.tagline")}
            </p>
          </div>

          {/* Catalog */}
          <div>
            <h4 style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,253,247,0.5)", marginBottom: 16, fontWeight: 700 }}>
              {t("nav.catalog")}
            </h4>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
              <li><Link href="/catalog" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("nav.catalog")}</Link></li>
              <li><Link href="/catalog/broiler" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("directions.broiler")}</Link></li>
              <li><Link href="/catalog/layer" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("directions.layer")}</Link></li>
              <li><Link href="/catalog/parent" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("directions.parent")}</Link></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,253,247,0.5)", marginBottom: 16, fontWeight: 700 }}>
              {t("nav.about")}
            </h4>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
              <li><Link href="/about" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("nav.about")}</Link></li>
              <li><Link href="/erp" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("nav.erp")}</Link></li>
              <li><Link href="/contacts" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>{t("nav.contacts")}</Link></li>
              <li><a href={ERP_URL} target="_blank" rel="noopener" style={{ color: "rgba(255,253,247,0.85)", fontSize: "var(--text-sm)" }}>erp.yembro.uz ↗</a></li>
            </ul>
          </div>

          {/* Contacts */}
          <div>
            <h4 style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,253,247,0.5)", marginBottom: 16, fontWeight: 700 }}>
              {t("nav.contacts")}
            </h4>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10, fontSize: "var(--text-sm)", color: "rgba(255,253,247,0.85)" }}>
              <li style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <PhoneIcon width={14} height={14} style={{ color: "var(--brand-yellow)", flex: "0 0 14px" }} />
                <a href="tel:+998900000000">+998 (90) 000-00-00</a>
              </li>
              <li style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <MailIcon width={14} height={14} style={{ color: "var(--brand-yellow)", flex: "0 0 14px" }} />
                <a href="mailto:hello@yembro.uz">hello@yembro.uz</a>
              </li>
              <li style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <GlobeIcon width={14} height={14} style={{ color: "var(--brand-yellow)", flex: "0 0 14px" }} />
                yembro.uz
              </li>
            </ul>
          </div>
        </div>

        <div
          style={{
            borderTop: "1px solid rgba(255,253,247,0.1)",
            marginTop: 48,
            paddingTop: 24,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
            flexWrap: "wrap",
            fontSize: "var(--text-xs)",
            color: "rgba(255,253,247,0.5)",
          }}
        >
          <div>{t("footer.rights", { year })}</div>
          <div style={{ display: "flex", gap: 16 }}>
            <Link href="/about">Privacy</Link>
            <Link href="/about">Terms</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
