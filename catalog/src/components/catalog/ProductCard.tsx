import Image from "next/image";

import { LogoMark } from "@/components/layout/Logo";
import { Link } from "@/i18n/routing";
import type { ProductCard as ProductCardType } from "@/lib/types";
import { ArrowRightIcon, DirectionIcon, StarIcon } from "@/components/ui/Icon";

export function ProductCard({
  product,
  delay = 0,
}: {
  product: ProductCardType;
  delay?: number;
}) {
  const dirLabel = product.direction;
  return (
    <Link
      href={`/product/${product.code}`}
      className="card card-hover anim-fade-in-up"
      style={{
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        height: "100%",
        animationDelay: `${delay}ms`,
        position: "relative",
      }}
    >
      <div
        style={{
          position: "relative",
          aspectRatio: "4 / 3",
          background: "var(--brand-grad-soft)",
          overflow: "hidden",
          // Padding вокруг — чтобы картинка не была впритык к краям.
          padding: 18,
        }}
      >
        {product.primary_image ? (
          <Image
            src={product.primary_image}
            alt={product.name}
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1280px) 33vw, 320px"
            style={{
              // contain — картинка вписывается целиком, без обрезки.
              objectFit: "contain",
              // padding на родителе обрезается у `fill`, поэтому имитируем
              // его через inset/scale.
              padding: 18,
              transition: "transform 400ms var(--ease)",
            }}
          />
        ) : (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              color: "rgba(224,9,31,0.18)",
              opacity: 0.5,
              gap: 8,
              gridAutoFlow: "column",
            }}
            aria-hidden
          >
            <LogoMark size={64} alt="" />
            <DirectionIcon direction={product.direction} width={56} height={56} strokeWidth={1.5} />
          </div>
        )}

        {/* Top-left badges */}
        <div style={{
          position: "absolute", top: 12, left: 12, display: "flex", gap: 6, flexWrap: "wrap",
        }}>
          {product.is_featured && (
            <span className="badge badge-grad" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <StarIcon width={12} height={12} />
              TOP
            </span>
          )}
          <span className="badge badge-orange" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <DirectionIcon direction={product.direction} width={12} height={12} />
            {dirLabel}
          </span>
        </div>

        {/* Brand badge bottom-right */}
        <span
          style={{
            position: "absolute",
            bottom: 12,
            right: 12,
            background: "rgba(255,253,247,0.9)",
            backdropFilter: "blur(6px)",
            padding: "4px 10px",
            borderRadius: "var(--radius-pill)",
            fontSize: "var(--text-xs)",
            fontWeight: 700,
            color: "var(--fg-1)",
          }}
        >
          {product.brand.name}
        </span>
      </div>

      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        <div style={{
          fontSize: "var(--text-xs)",
          color: "var(--fg-3)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontWeight: 600,
        }}>
          {product.category.name}
        </div>
        <h3 style={{
          fontSize: "var(--text-lg)",
          fontWeight: 700,
          margin: 0,
          lineHeight: 1.3,
          letterSpacing: "-0.01em",
        }}>
          {product.name}
        </h3>
        {product.short_description && (
          <p style={{
            fontSize: "var(--text-sm)",
            color: "var(--fg-2)",
            margin: 0,
            lineHeight: 1.5,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>
            {product.short_description}
          </p>
        )}

        <div style={{
          marginTop: "auto",
          paddingTop: 12,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          borderTop: "1px solid var(--border-subtle)",
          fontSize: "var(--text-xs)",
        }}>
          <div style={{ display: "flex", gap: 12, color: "var(--fg-3)", fontFamily: "var(--font-mono)" }}>
            {product.package_kg && <span>{product.package_kg} kg</span>}
            {(product.age_from_days != null || product.age_to_days != null) && (
              <span>{product.age_from_days ?? "?"}–{product.age_to_days ?? "?"} d</span>
            )}
          </div>
          <span style={{
            color: "var(--brand-orange)",
            fontWeight: 700,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}>
            <ArrowRightIcon width={14} height={14} />
          </span>
        </div>
      </div>
    </Link>
  );
}
