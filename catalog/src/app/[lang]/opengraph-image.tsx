import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { isLocale } from "@/i18n/config";

export const runtime = "nodejs";
export const alt = "Yembro — корм, рождённый на ферме";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const HEADLINES: Record<string, { title: string; subtitle: string }> = {
  ru: {
    title: "Стадо растёт ровно,\nкогда корм не врёт",
    subtitle: "Yembro · Pro · Bio — три линейки на одну ферму",
  },
  uz: {
    title: "Yem aldamasa,\npod tekis oʻsadi",
    subtitle: "Yembro · Pro · Bio — bir fermaga uchta liniya",
  },
  en: {
    title: "The flock grows even\nwhen the feed is honest",
    subtitle: "Yembro · Pro · Bio — three lines, one farm",
  },
};

async function loadLogoDataUri(): Promise<string | null> {
  // Лого читаем из public/ и эмбеддим как data-URI — `next/og` рендерит в
  // изолированном Edge-runtime и не может скачивать произвольные URL.
  try {
    const file = await readFile(join(process.cwd(), "public", "mark.png"));
    return `data:image/png;base64,${file.toString("base64")}`;
  } catch {
    return null;
  }
}

export default async function OpenGraphImage({
  params,
}: {
  params: { lang: string };
}) {
  const lang = isLocale(params.lang) ? params.lang : "ru";
  const { title, subtitle } = HEADLINES[lang];
  const logoUri = await loadLogoDataUri();

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          background:
            "linear-gradient(135deg, #FBF7F0 0%, #FFE3E6 60%, #FFF1C2 100%)",
          padding: 80,
          position: "relative",
        }}
      >
        {/* Decorative blobs */}
        <div
          style={{
            position: "absolute",
            top: -200,
            right: -200,
            width: 600,
            height: 600,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(224,9,31,0.32) 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: -180,
            left: -120,
            width: 500,
            height: 500,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(245,183,0,0.30) 0%, transparent 70%)",
          }}
        />

        {/* Logo + brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 20, position: "relative" }}>
          {logoUri ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUri} alt="Yembro" width={64} height={109} style={{ objectFit: "contain" }} />
          ) : (
            <div
              style={{
                width: 72,
                height: 72,
                borderRadius: 16,
                background: "#E0091F",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontSize: 40,
                fontWeight: 800,
              }}
            >
              Y
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 44, fontWeight: 800, color: "#1A0E10", lineHeight: 1 }}>
              Yembro
            </div>
            <div style={{ fontSize: 18, color: "#816A6E", marginTop: 4, fontWeight: 500 }}>
              Yuqori sifat — yuqori samaradorlik
            </div>
          </div>
        </div>

        {/* Headline */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            margin: "auto 0",
            position: "relative",
          }}
        >
          <div
            style={{
              fontSize: 92,
              fontWeight: 800,
              color: "#1A0E10",
              letterSpacing: "-0.03em",
              lineHeight: 1.05,
              whiteSpace: "pre-line",
              marginBottom: 24,
            }}
          >
            {title}
          </div>
          <div style={{ fontSize: 32, color: "#4D3A3D", fontWeight: 600 }}>
            {subtitle}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            position: "relative",
          }}
        >
          <div style={{ fontSize: 24, color: "#816A6E", fontWeight: 600 }}>
            yembro.uz
          </div>
          <div
            style={{
              fontSize: 22,
              color: "#fff",
              padding: "12px 24px",
              borderRadius: 999,
              background: "#E0091F",
              fontWeight: 700,
            }}
          >
            Made in Uzbekistan
          </div>
        </div>
      </div>
    ),
    size,
  );
}
