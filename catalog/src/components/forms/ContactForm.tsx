"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { API_URL } from "@/lib/env";

type Status = "idle" | "submitting" | "success" | "error";

export function ContactForm() {
  const t = useTranslations("contacts");
  const params = useParams<{ lang: string }>();
  const lang = params.lang ?? "ru";
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // Сохраняем ссылку на форму ДО await — иначе после async-операции
    // React зануляет e.currentTarget и .reset() падает с TypeError.
    const form = e.currentTarget;
    const fd = new FormData(form);
    setStatus("submitting");
    setErrorMsg("");
    try {
      const res = await fetch(`${API_URL}/contact/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept-Language": lang },
        body: JSON.stringify({
          name: fd.get("name"),
          contact: fd.get("contact"),
          company: fd.get("company") || "",
          message: fd.get("message") || "",
          source_lang: lang,
          source_url: typeof window !== "undefined" ? window.location.href : "",
          // honeypot
          website: fd.get("website") || "",
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatus("success");
      try { form.reset(); } catch { /* форма могла размонтироваться */ }
      if (typeof window !== "undefined" && (window as unknown as { gtag?: (...args: unknown[]) => void }).gtag) {
        (window as unknown as { gtag: (...args: unknown[]) => void }).gtag("event", "generate_lead");
      }
    } catch (err) {
      setErrorMsg(String(err));
      setStatus("error");
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 16, maxWidth: 560 }}>
      <input type="text" name="website" tabIndex={-1} autoComplete="off" className="honeypot" aria-hidden />
      <div style={{ display: "grid", gap: 6 }}>
        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>{t("name")}</label>
        <input className="input" name="name" required minLength={2} maxLength={100} />
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>{t("contact")}</label>
        <input className="input" name="contact" required minLength={5} maxLength={100} />
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>{t("company")}</label>
        <input className="input" name="company" maxLength={100} />
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>{t("message")}</label>
        <textarea className="textarea" name="message" rows={4} maxLength={2000} />
      </div>
      <button
        type="submit"
        className="btn btn-primary btn-lg"
        disabled={status === "submitting"}
      >
        {status === "submitting" ? t("submitting") : t("submit")}
      </button>
      {status === "success" && (
        <div style={{ color: "var(--success)", fontSize: "var(--text-sm)" }}>
          {t("success")}
        </div>
      )}
      {status === "error" && (
        <div style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {t("error")}{errorMsg ? ` (${errorMsg})` : ""}
        </div>
      )}
    </form>
  );
}
