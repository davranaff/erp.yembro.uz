"""
Check and add premix raw material nomenclature items.

Rost 308 premixes are raw material INPUTS to feed production — they must
exist in the "Сырьё для кормов" category so they can be tracked as
RawMaterialBatch entries in the raw materials warehouse.

Idempotent: prints status for each SKU, creates only missing ones.

Usage:
    python manage.py check_premix_nomenclature [--dry-run]
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

PREMIXES = [
    ("RAW-PREMIX-ROST308-START",  "Премикс Старт Rost 308",  "10.00"),
    ("RAW-PREMIX-ROST308-GROW",   "Премикс Рост Rost 308",   "10.00"),
    ("RAW-PREMIX-ROST308-FINISH", "Премикс Финиш Rost 308",  "10.00"),
]


class Command(BaseCommand):
    help = "Check (and optionally create) Rost 308 premix nomenclature items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Roll back the transaction after reporting.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        try:
            with transaction.atomic():
                self._run()
                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN — rolled back."))
        except Exception as exc:
            raise CommandError(f"Failed: {exc}") from exc

    def _run(self):
        from apps.nomenclature.models import Category, NomenclatureItem, Unit
        from apps.organizations.models import Organization

        org = Organization.objects.get(code="DEFAULT")
        kg_unit = Unit.objects.get(organization=org, code="KG")
        raw_cat = Category.objects.get(organization=org, name="Сырьё для кормов")

        self.stdout.write(f"\nOrg: {org.name}  |  Category: {raw_cat.name}\n")
        self.stdout.write(f"{'SKU':<30} {'Name':<30} {'Status'}")
        self.stdout.write("-" * 75)

        for sku, name, moisture in PREMIXES:
            existing = NomenclatureItem.objects.filter(organization=org, sku=sku).first()
            if existing:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{sku:<30} {existing.name:<30} EXISTS  "
                        f"(cat={existing.category.name}, "
                        f"moisture={existing.base_moisture_pct}%, "
                        f"unit={existing.unit.code}, "
                        f"active={existing.is_active})"
                    )
                )
            else:
                item = NomenclatureItem.objects.create(
                    organization=org,
                    sku=sku,
                    name=name,
                    category=raw_cat,
                    unit=kg_unit,
                    base_moisture_pct=Decimal(moisture),
                    is_active=True,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"{sku:<30} {item.name:<30} CREATED"
                    )
                )
