"""
Data-migration: backfill `barcode` для FeedBagLot, созданных до того,
как `package_feed_batch` начал авто-генерировать штрих-коды.

Без этого старые мешки не отображаются на /scan/<barcode> и в drawer'е
у них нет блока со штрих-кодом — продавать их можно только из админки,
не сканированием.
"""
from __future__ import annotations

import secrets
from django.db import migrations


def _make_barcode(FeedBagLot, organization_id, recipe_code: str) -> str:
    """Генерим уникальный FEED-{recipe}-{rand4}, как в package_feed_batch."""
    code = (recipe_code or "X").upper().replace(" ", "")[:24]
    for _ in range(10):
        candidate = f"FEED-{code}-{secrets.token_hex(2).upper()}"
        if not FeedBagLot.objects.filter(
            organization_id=organization_id, barcode=candidate,
        ).exists():
            return candidate
    # extreme fallback — добавляем больше энтропии
    return f"FEED-{code}-{secrets.token_hex(4).upper()}"


def backfill_barcodes(apps, schema_editor):
    FeedBagLot = apps.get_model("feed", "FeedBagLot")
    qs = FeedBagLot.objects.filter(barcode__isnull=True).select_related(
        "recipe_version__recipe",
    )
    for lot in qs.iterator():
        recipe_code = ""
        try:
            recipe_code = lot.recipe_version.recipe.code or ""
        except Exception:
            pass
        lot.barcode = _make_barcode(FeedBagLot, lot.organization_id, recipe_code)
        lot.save(update_fields=["barcode"])


def clear_barcodes(apps, schema_editor):
    FeedBagLot = apps.get_model("feed", "FeedBagLot")
    FeedBagLot.objects.filter(barcode__startswith="FEED-").update(barcode=None)


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0007_alter_feedbaglot_unique_together_feedbaglot_barcode_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_barcodes, clear_barcodes),
    ]
