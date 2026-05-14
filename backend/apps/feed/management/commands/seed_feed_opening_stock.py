"""
One-time opening-balance seeder for the feed module.

Creates:
  • NomenclatureItem – 10 finished-feed SKUs + raw-material SKUs
  • Recipe + RecipeVersion (v1, active, empty) per finished product
  • RawMaterialBatch – one per raw material with non-zero stock
  • ProductionTask → FeedBatch → FeedBagLot(s) – per finished product / warehouse

Idempotent: skips anything that already exists (identified by doc_number or SKU).

Usage:
    python manage.py seed_feed_opening_stock [--dry-run]
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


# ─── Opening-balance data ──────────────────────────────────────────────────

BALANCE_DATE = datetime.date(2026, 5, 1)
BALANCE_DT = datetime.datetime(2026, 5, 1, 6, 0, tzinfo=datetime.timezone.utc)

# (sku, name, unit_code, base_moisture_pct_or_None)
RAW_MATERIALS = [
    ("RAW-MAKKA",       "Кукуруза",                    "kg",  "14.00"),
    ("RAW-SOYA",        "Шрот соевый",                 "kg",  "12.00"),
    ("RAW-BUGDOY",      "Пшеница",                     "kg",  "14.00"),
    ("RAW-YOG",         "Жир кормовой",                "kg",  None),
    ("RAW-EGG-IRAN",    "Яйцо инкубационное иранское", "pcs", None),
    ("RAW-EGG-ROOSTER", "Яйцо петуха",                 "pcs", None),
    ("RAW-IZVES",       "Известняк кормовой",          "kg",  None),
    ("RAW-BIODOB",      "Биодобавка",                  "kg",  "10.00"),
    ("RAW-GIPCH",       "Гипс кормовой",               "kg",  None),
    ("RAW-TUZ",         "Соль кормовая",               "kg",  None),
    ("RAW-KOP",         "Копра",                       "kg",  "10.00"),
]

# (sku, quantity, unit_code)  — non-zero only; 0-stock skus created via FINISHED_FEED
RAW_STOCK = [
    ("RAW-MAKKA",       Decimal("31909.000"), "kg"),
    ("RAW-SOYA",        Decimal("89483.000"), "kg"),
    ("RAW-BUGDOY",      Decimal("326843.000"), "kg"),
    ("RAW-YOG",         Decimal("18546.000"), "kg"),
    ("RAW-EGG-IRAN",    Decimal("100.000"),   "pcs"),
    ("RAW-EGG-ROOSTER", Decimal("540.000"),   "pcs"),
    ("RAW-IZVES",       Decimal("3366.000"),  "kg"),
    ("RAW-BIODOB",      Decimal("17044.000"), "kg"),
    ("RAW-GIPCH",       Decimal("1700.000"),  "kg"),
    ("RAW-TUZ",         Decimal("296.000"),   "kg"),
    ("RAW-KOP",         Decimal("19965.000"), "kg"),
]

# (sku, recipe_code, name, direction)
FINISHED_FEED = [
    ("FEED-START-ROST308",  "ROST308-START",  "Старт Rost 308",  "broiler"),
    ("FEED-GROW-ROST308",   "ROST308-GROW",   "Рост Rost 308",   "broiler"),
    ("FEED-FINISH-ROST308", "ROST308-FINISH", "Финиш Rost 308",  "broiler"),
    ("FEED-START-KOP500",   "KOP500-START",   "Старт Kop 500",   "broiler"),
    ("FEED-GROW-KOP500",    "KOP500-GROW",    "Рост Kop 500",    "broiler"),
    ("FEED-FINISH-KOP500",  "KOP500-FINISH",  "Финиш Kop 500",   "broiler"),
    ("FEED-START-CARGEL",   "CARGEL-START",   "Старт Cargel",    "broiler"),
    ("FEED-GROW-CARGEL",    "CARGEL-GROW",    "Рост Cargel",     "broiler"),
    ("FEED-FINISH-CARGEL",  "CARGEL-FINISH",  "Финиш Cargel",    "broiler"),
    ("FEED-CARGEL-500600",  "CARGEL-500600",  "Cargel 500600",   "broiler"),
]

BAG_KG = Decimal("50.000")

# (sku, warehouse_key, bags)
#   warehouse_key: "main" = КОРМ-ОСНОВНОЙ (raw+bulk), "bags" = КОРМ-МЕШКИ
BAG_STOCK = [
    ("FEED-START-ROST308",  "main", 1_300),
    ("FEED-GROW-ROST308",   "main", 6_800),
    ("FEED-FINISH-ROST308", "main", 10_160),
    ("FEED-START-ROST308",  "bags", 52_600),
    ("FEED-GROW-ROST308",   "bags", 163_250),
    ("FEED-FINISH-ROST308", "bags", 93_400),
    ("FEED-GROW-KOP500",    "bags", 9_400),
    ("FEED-FINISH-KOP500",  "bags", 2_000),
]


class Command(BaseCommand):
    help = "Seed feed opening stock (nomenclature, recipes, raw batches, bag lots)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Roll back the transaction after reporting counts.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        try:
            with transaction.atomic():
                counts = self._run()
                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN — rolled back."))
        except Exception as exc:
            raise CommandError(f"Seeding failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Done. Counts:"))
        for key, val in counts.items():
            self.stdout.write(f"  {key}: {val}")

    # ──────────────────────────────────────────────────────────────────────

    def _run(self):
        from apps.modules.models import Module
        from apps.nomenclature.models import NomenclatureItem, Category, Unit
        from apps.organizations.models import Organization
        from apps.warehouses.models import ProductionBlock, Warehouse
        from apps.feed.models import (
            FeedBatch, FeedBagLot, ProductionTask, RawMaterialBatch,
            Recipe, RecipeVersion,
        )

        counts = {
            "nomenclature_created": 0,
            "recipes_created": 0,
            "recipe_versions_created": 0,
            "raw_batches_created": 0,
            "production_tasks_created": 0,
            "feed_batches_created": 0,
            "bag_lots_created": 0,
        }

        org = Organization.objects.get(code="DEFAULT")
        feed_module = Module.objects.get(code="feed")

        # ── Units ─────────────────────────────────────────────────────────
        kg_unit = Unit.objects.get(organization=org, code="KG")
        pcs_unit = Unit.objects.get(organization=org, code="PCS")

        unit_map = {"kg": kg_unit, "pcs": pcs_unit}

        # ── Categories ────────────────────────────────────────────────────
        raw_cat = Category.objects.get(organization=org, name="Сырьё для кормов")
        feed_cat = Category.objects.get(organization=org, name="Корма")

        # ── Production blocks ──────────────────────────────────────────────
        mixer_line, _ = ProductionBlock.objects.get_or_create(
            organization=org, code="МКС-1",
            defaults={
                "name": "Линия замеса №1",
                "kind": ProductionBlock.Kind.MIXER_LINE,
                "module": feed_module,
            },
        )
        storage_bin, _ = ProductionBlock.objects.get_or_create(
            organization=org, code="БНК-1",
            defaults={
                "name": "Бункер готового комбикорма №1",
                "kind": ProductionBlock.Kind.STORAGE_BIN,
                "module": feed_module,
            },
        )

        # ── Warehouses ─────────────────────────────────────────────────────
        # Raw materials warehouse (for raw batches)
        raw_wh, _ = Warehouse.objects.get_or_create(
            organization=org, code="СК-СР",
            defaults={
                "name": "Склад сырья для кормов",
                "module": feed_module,
            },
        )
        # Main finished-feed warehouse (bulk / bags stored together with raw)
        main_wh, _ = Warehouse.objects.get_or_create(
            organization=org, code="КОРМ-ОСНОВНОЙ",
            defaults={
                "name": "Склад кормов основной",
                "module": feed_module,
            },
        )
        # Bag warehouse
        bag_wh, _ = Warehouse.objects.get_or_create(
            organization=org, code="КОРМ-МЕШКИ",
            defaults={
                "name": "Склад кормов мешки",
                "module": feed_module,
            },
        )
        wh_map = {"main": main_wh, "bags": bag_wh}

        # ── CEO / technologist ─────────────────────────────────────────────
        from django.contrib.auth import get_user_model
        User = get_user_model()
        technologist = (
            User.objects.filter(is_superuser=True).order_by("date_joined").first()
            or User.objects.order_by("date_joined").first()
        )
        if technologist is None:
            raise CommandError("No user found to assign as technologist.")

        # ── Raw material nomenclature ──────────────────────────────────────
        for sku, name, unit_code, moisture in RAW_MATERIALS:
            _, created = NomenclatureItem.objects.get_or_create(
                organization=org, sku=sku,
                defaults={
                    "name": name,
                    "category": raw_cat,
                    "unit": unit_map[unit_code],
                    "base_moisture_pct": Decimal(moisture) if moisture else None,
                },
            )
            if created:
                counts["nomenclature_created"] += 1
                self.stdout.write(f"  [NOM] created {sku}")

        # ── Finished feed nomenclature + recipes ───────────────────────────
        recipe_version_map: dict[str, RecipeVersion] = {}

        for sku, recipe_code, name, direction in FINISHED_FEED:
            nom, created = NomenclatureItem.objects.get_or_create(
                organization=org, sku=sku,
                defaults={
                    "name": name,
                    "category": feed_cat,
                    "unit": kg_unit,
                },
            )
            if created:
                counts["nomenclature_created"] += 1
                self.stdout.write(f"  [NOM] created {sku}")

            recipe, r_created = Recipe.objects.get_or_create(
                organization=org, code=recipe_code,
                defaults={
                    "name": name,
                    "direction": direction,
                    "is_active": True,
                },
            )
            if r_created:
                counts["recipes_created"] += 1
                self.stdout.write(f"  [RCP] created recipe {recipe_code}")

            rv, rv_created = RecipeVersion.objects.get_or_create(
                recipe=recipe, version_number=1,
                defaults={
                    "status": RecipeVersion.Status.ACTIVE,
                    "effective_from": BALANCE_DATE,
                },
            )
            if rv_created:
                counts["recipe_versions_created"] += 1
                self.stdout.write(f"  [RV]  created version {recipe_code} v1")

            recipe_version_map[sku] = rv

        # ── Raw material batches ───────────────────────────────────────────
        for sku, qty, unit_code in RAW_STOCK:
            nom = NomenclatureItem.objects.get(organization=org, sku=sku)
            doc = f"OPENING-RAW-{sku}"
            if RawMaterialBatch.objects.filter(organization=org, doc_number=doc).exists():
                self.stdout.write(f"  [RAW] skip {doc} (exists)")
                continue
            batch = RawMaterialBatch(
                organization=org,
                module=feed_module,
                doc_number=doc,
                nomenclature=nom,
                warehouse=raw_wh,
                received_date=BALANCE_DATE,
                quantity=qty,
                current_quantity=qty,
                unit=unit_map[unit_code],
                price_per_unit_uzs=Decimal("0.00"),
                status=RawMaterialBatch.Status.AVAILABLE,
                notes="Входящий остаток 01.05.2026",
            )
            batch.save()
            counts["raw_batches_created"] += 1
            self.stdout.write(f"  [RAW] created {doc} qty={qty}")

        # ── Finished feed bag lots ─────────────────────────────────────────
        # Group by SKU so we create one ProductionTask + FeedBatch per SKU
        from collections import defaultdict
        bags_by_sku: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for sku, wh_key, bags in BAG_STOCK:
            bags_by_sku[sku].append((wh_key, bags))

        for sku, wh_bags in bags_by_sku.items():
            rv = recipe_version_map[sku]
            total_bags = sum(b for _, b in wh_bags)
            total_kg = BAG_KG * total_bags

            task_doc = f"OPENING-TASK-{sku}"
            if not ProductionTask.objects.filter(organization=org, doc_number=task_doc).exists():
                task = ProductionTask(
                    organization=org,
                    module=feed_module,
                    doc_number=task_doc,
                    recipe_version=rv,
                    production_line=mixer_line,
                    scheduled_at=BALANCE_DT,
                    planned_quantity_kg=total_kg,
                    actual_quantity_kg=total_kg,
                    status=ProductionTask.Status.DONE,
                    technologist=technologist,
                    notes="Входящий остаток 01.05.2026",
                )
                task.save()
                counts["production_tasks_created"] += 1
                self.stdout.write(f"  [TSK] created {task_doc}")
            else:
                task = ProductionTask.objects.get(organization=org, doc_number=task_doc)
                self.stdout.write(f"  [TSK] skip {task_doc} (exists)")

            batch_doc = f"OPENING-BATCH-{sku}"
            if not FeedBatch.objects.filter(organization=org, doc_number=batch_doc).exists():
                fb = FeedBatch(
                    organization=org,
                    module=feed_module,
                    doc_number=batch_doc,
                    produced_by_task=task,
                    recipe_version=rv,
                    produced_at=BALANCE_DT,
                    quantity_kg=total_kg,
                    current_quantity_kg=total_kg,
                    unit_cost_uzs=Decimal("0.000000"),
                    total_cost_uzs=Decimal("0.00"),
                    storage_bin=storage_bin,
                    storage_warehouse=main_wh,
                    status=FeedBatch.Status.APPROVED,
                    quality_passport_status=FeedBatch.PassportStatus.PASSED,
                    notes="Входящий остаток 01.05.2026",
                )
                fb.save()
                counts["feed_batches_created"] += 1
                self.stdout.write(f"  [FB]  created {batch_doc}")
            else:
                fb = FeedBatch.objects.get(organization=org, doc_number=batch_doc)
                self.stdout.write(f"  [FB]  skip {batch_doc} (exists)")

            for wh_key, bags in wh_bags:
                lot_doc = f"OPENING-LOT-{sku}-{wh_key.upper()}"
                if FeedBagLot.objects.filter(organization=org, doc_number=lot_doc).exists():
                    self.stdout.write(f"  [LOT] skip {lot_doc} (exists)")
                    continue
                lot = FeedBagLot(
                    organization=org,
                    module=feed_module,
                    doc_number=lot_doc,
                    source_feed_batch=fb,
                    recipe_version=rv,
                    bag_weight_kg=BAG_KG,
                    bags_initial=bags,
                    bags_remaining=bags,
                    unit_cost_uzs=Decimal("0.00"),
                    total_cost_uzs=Decimal("0.00"),
                    storage_warehouse=wh_map[wh_key],
                    packaged_at=BALANCE_DT,
                    status=FeedBagLot.Status.ACTIVE,
                    notes="Входящий остаток 01.05.2026",
                )
                lot.save()
                counts["bag_lots_created"] += 1
                self.stdout.write(f"  [LOT] created {lot_doc} bags={bags}")

        return counts
