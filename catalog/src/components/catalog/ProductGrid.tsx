import type { ProductCard as ProductCardType } from "@/lib/types";

import { ProductCard } from "./ProductCard";

export function ProductGrid({
  products,
  staggerStart = 0,
}: {
  products: ProductCardType[];
  staggerStart?: number;
}) {
  if (products.length === 0) return null;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 24,
      }}
    >
      {products.map((p, i) => (
        <ProductCard key={p.id} product={p} delay={staggerStart + i * 60} />
      ))}
    </div>
  );
}
