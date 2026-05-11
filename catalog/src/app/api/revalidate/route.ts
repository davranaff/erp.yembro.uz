/**
 * POST /api/revalidate
 *
 * Бэкенд (apps/catalog/signals.py → revalidate_next_task) дёргает этот endpoint
 * при изменении контента, чтобы инвалидировать ISR-кэш Next.js.
 *
 * Body: { "secret": string, "tags": string[] }
 */
import { NextResponse } from "next/server";
import { revalidateTag } from "next/cache";

import { REVALIDATE_SECRET } from "@/lib/env";

export const runtime = "nodejs";

export async function POST(request: Request) {
  if (!REVALIDATE_SECRET) {
    return NextResponse.json({ ok: false, error: "secret_not_configured" }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  const { secret, tags } = (body ?? {}) as { secret?: string; tags?: unknown };
  if (secret !== REVALIDATE_SECRET) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  if (!Array.isArray(tags) || tags.length === 0) {
    return NextResponse.json({ ok: false, error: "tags_required" }, { status: 400 });
  }

  const revalidated: string[] = [];
  for (const tag of tags) {
    if (typeof tag === "string" && tag.length > 0 && tag.length <= 200) {
      revalidateTag(tag);
      revalidated.push(tag);
    }
  }

  return NextResponse.json({ ok: true, revalidated });
}
