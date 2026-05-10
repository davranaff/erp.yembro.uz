import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/routing";

import { LangSwitcher } from "./LangSwitcher";
import { LogoFull } from "./Logo";

export async function Header() {
  const t = await getTranslations("nav");
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        background: "rgba(251,247,238,0.85)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      <div
        className="container"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "var(--header-h)",
          gap: 24,
        }}
      >
        <Link
          href="/"
          aria-label="Yembro — на главную"
          style={{ display: "inline-flex", alignItems: "center" }}
        >
          <LogoFull height={40} />
        </Link>
        <nav
          aria-label="Primary"
          className="primary-nav"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 28,
            fontSize: "var(--text-sm)",
            fontWeight: 600,
          }}
        >
          <Link href="/catalog" className="nav-link">{t("catalog")}</Link>
          <Link href="/about" className="nav-link">{t("about")}</Link>
          <Link href="/erp" className="nav-link">{t("erp")}</Link>
          <Link href="/contacts" className="nav-link">{t("contacts")}</Link>
          <LangSwitcher />
        </nav>
      </div>
      <style>{`
        .nav-link {
          position: relative;
          color: var(--fg-2);
          transition: color 160ms;
        }
        .nav-link:hover { color: var(--brand-orange); }
        .nav-link::after {
          content: "";
          position: absolute;
          left: 0; right: 0; bottom: -6px;
          height: 2px;
          background: var(--brand-grad);
          transform: scaleX(0);
          transform-origin: center;
          transition: transform 200ms var(--ease);
        }
        .nav-link:hover::after { transform: scaleX(1); }
        @media (max-width: 720px) {
          .primary-nav { gap: 16px; font-size: 13px; }
          .primary-nav a:not(:last-child) { display: none; }
        }
      `}</style>
    </header>
  );
}
