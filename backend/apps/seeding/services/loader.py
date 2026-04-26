"""
OrganizationSeeder — идемпотентный загрузчик core-fixture'ов из YAML.

Дизайн:
    - На вход: путь к YAML + Organization.
    - Резолверы по natural keys: module:code, account:code, subaccount:code,
      unit:code, category:name, block:code.
    - Топологический порядок зашит — порядок секций в YAML свободный.
    - Идемпотентен: update_or_create по (organization, natural_key).
    - dry_run — собирает план, не пишет в БД.

Поведение при конфликтах:
    - Существующие записи с тем же natural key — поля обновляются из YAML.
    - Лишние записи в БД (не упомянутые в YAML) — НЕ удаляются.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import yaml
from django.db import transaction


class SeedError(Exception):
    """Ошибка при загрузке/применении seed-конфига."""


@dataclass
class SeedReport:
    units_created: int = 0
    units_updated: int = 0
    accounts_created: int = 0
    accounts_updated: int = 0
    subaccounts_created: int = 0
    subaccounts_updated: int = 0
    expense_articles_created: int = 0
    expense_articles_updated: int = 0
    categories_created: int = 0
    categories_updated: int = 0
    nomenclature_created: int = 0
    nomenclature_updated: int = 0
    blocks_created: int = 0
    blocks_updated: int = 0
    warehouses_created: int = 0
    warehouses_updated: int = 0
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def total_created(self) -> int:
        return sum(
            v for k, v in self.__dict__.items()
            if k.endswith("_created") and isinstance(v, int)
        )

    def total_updated(self) -> int:
        return sum(
            v for k, v in self.__dict__.items()
            if k.endswith("_updated") and isinstance(v, int)
        )


class OrganizationSeeder:
    """
    Загружает YAML-конфиг и применяет его к указанной организации.

    Использование:
        from apps.organizations.models import Organization
        from apps.seeding.services.loader import OrganizationSeeder

        org = Organization.objects.get(code="DEMO-FARM")
        seeder = OrganizationSeeder(org, config_path="apps/seeding/seeds/default_org.yaml")
        report = seeder.run()
        print(report.as_dict())
    """

    DEFAULT_CONFIG = (
        Path(__file__).resolve().parent.parent / "seeds" / "default_org.yaml"
    )

    def __init__(
        self,
        organization,
        *,
        config_path: Optional[str | Path] = None,
        config_data: Optional[dict] = None,
        dry_run: bool = False,
    ):
        self.org = organization
        self.dry_run = dry_run
        self.report = SeedReport()

        if config_data is not None:
            self.config = config_data
        else:
            path = Path(config_path) if config_path else self.DEFAULT_CONFIG
            if not path.exists():
                raise SeedError(f"Config not found: {path}")
            with path.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            if not isinstance(loaded, dict):
                raise SeedError(f"Config root must be a dict, got {type(loaded).__name__}")
            self.config = loaded
            self._config_path = path

        # Каши резолверов — заполняются по мере создания.
        self._modules: dict[str, Any] = {}
        self._accounts: dict[str, Any] = {}
        self._subaccounts: dict[str, Any] = {}
        self._units: dict[str, Any] = {}
        self._categories: dict[str, Any] = {}
        self._blocks: dict[str, Any] = {}
        self._expense_articles: dict[str, Any] = {}

    # ── Публичный API ──────────────────────────────────────────────────

    def run(self) -> SeedReport:
        """
        Применить конфиг. В dry_run — собирает counts, но всё откатывает.
        """
        try:
            with transaction.atomic():
                self._load_existing_caches()
                self._seed_units()
                self._seed_accounts()
                self._seed_subaccounts()
                self._seed_expense_articles()
                self._seed_categories()
                self._seed_nomenclature()
                self._seed_blocks()
                self._seed_warehouses()

                if self.dry_run:
                    transaction.set_rollback(True)
        except Exception as exc:
            self.report.errors.append(f"{type(exc).__name__}: {exc}")
            raise

        return self.report

    # ── Резолверы ─────────────────────────────────────────────────────

    def _resolve_module(self, code: Optional[str]):
        if not code:
            return None
        from apps.modules.models import Module

        if code not in self._modules:
            try:
                self._modules[code] = Module.objects.get(code=code)
            except Module.DoesNotExist as exc:
                raise SeedError(
                    f"Module '{code}' не найден. Сначала накатите миграцию modules.0003_seed_modules."
                ) from exc
        return self._modules[code]

    def _resolve_subaccount(self, code: Optional[str]):
        if not code:
            return None
        if code not in self._subaccounts:
            from apps.accounting.models import GLSubaccount
            try:
                self._subaccounts[code] = GLSubaccount.objects.get(
                    account__organization=self.org, code=code
                )
            except GLSubaccount.DoesNotExist as exc:
                raise SeedError(
                    f"Субсчёт '{code}' не найден для org={self.org.code}. "
                    f"Проверьте что секция `subaccounts` идёт ПЕРЕД ссылками на неё в YAML."
                ) from exc
        return self._subaccounts[code]

    def _resolve_unit(self, code: Optional[str]):
        if not code:
            return None
        if code not in self._units:
            from apps.nomenclature.models import Unit
            try:
                self._units[code] = Unit.objects.get(organization=self.org, code=code)
            except Unit.DoesNotExist as exc:
                raise SeedError(
                    f"Unit '{code}' не найден для org={self.org.code}. "
                    f"Проверьте секцию `units` в YAML."
                ) from exc
        return self._units[code]

    def _resolve_category(self, name: Optional[str]):
        if not name:
            return None
        if name not in self._categories:
            from apps.nomenclature.models import Category
            try:
                self._categories[name] = Category.objects.get(
                    organization=self.org, name=name
                )
            except Category.DoesNotExist as exc:
                raise SeedError(
                    f"Category '{name}' не найдена для org={self.org.code}."
                ) from exc
        return self._categories[name]

    def _resolve_block(self, code: Optional[str]):
        if not code:
            return None
        if code not in self._blocks:
            from apps.warehouses.models import ProductionBlock
            try:
                self._blocks[code] = ProductionBlock.objects.get(
                    organization=self.org, code=code
                )
            except ProductionBlock.DoesNotExist as exc:
                raise SeedError(
                    f"ProductionBlock '{code}' не найден для org={self.org.code}."
                ) from exc
        return self._blocks[code]

    # ── Прогрев кэшей: подтянуть уже существующие объекты ────────────

    def _load_existing_caches(self) -> None:
        from apps.accounting.models import ExpenseArticle, GLAccount, GLSubaccount
        from apps.nomenclature.models import Category, Unit
        from apps.warehouses.models import ProductionBlock

        for u in Unit.objects.filter(organization=self.org):
            self._units[u.code] = u
        for a in GLAccount.objects.filter(organization=self.org):
            self._accounts[a.code] = a
        for s in GLSubaccount.objects.filter(account__organization=self.org).select_related("account"):
            self._subaccounts[s.code] = s
        for c in Category.objects.filter(organization=self.org):
            self._categories[c.name] = c
        for b in ProductionBlock.objects.filter(organization=self.org):
            self._blocks[b.code] = b
        for ea in ExpenseArticle.objects.filter(organization=self.org):
            self._expense_articles[ea.code] = ea

    # ── 1. Единицы измерения ──────────────────────────────────────────

    def _seed_units(self) -> None:
        from apps.nomenclature.models import Unit

        rows = self.config.get("units") or []
        for row in rows:
            code = row.get("code")
            name = row.get("name") or code
            if not code:
                self.report.skipped.append("unit без code")
                continue
            obj, created = Unit.objects.update_or_create(
                organization=self.org,
                code=code,
                defaults={"name": name},
            )
            self._units[code] = obj
            if created:
                self.report.units_created += 1
            else:
                self.report.units_updated += 1

    # ── 2. Счета ───────────────────────────────────────────────────────

    def _seed_accounts(self) -> None:
        from apps.accounting.models import GLAccount

        rows = self.config.get("accounts") or []
        for row in rows:
            code = row.get("code")
            name = row.get("name")
            type_ = row.get("type")
            if not (code and name and type_):
                self.report.skipped.append(f"account {code or '?'} — пропуск (нет code/name/type)")
                continue
            obj, created = GLAccount.objects.update_or_create(
                organization=self.org,
                code=code,
                defaults={"name": name, "type": type_},
            )
            self._accounts[code] = obj
            if created:
                self.report.accounts_created += 1
            else:
                self.report.accounts_updated += 1

    # ── 3. Субсчета ───────────────────────────────────────────────────

    def _seed_subaccounts(self) -> None:
        from apps.accounting.models import GLSubaccount

        rows = self.config.get("subaccounts") or []
        for row in rows:
            code = row.get("code")
            account_code = row.get("account")
            name = row.get("name")
            if not (code and account_code and name):
                self.report.skipped.append(f"subaccount {code or '?'} — пропуск")
                continue

            account = self._accounts.get(account_code)
            if not account:
                raise SeedError(
                    f"subaccount {code}: account '{account_code}' не найден. "
                    f"Убедитесь что он есть в секции accounts."
                )

            obj, created = GLSubaccount.objects.update_or_create(
                account=account,
                code=code,
                defaults={
                    "name": name,
                    "module": self._resolve_module(row.get("module")),
                },
            )
            self._subaccounts[code] = obj
            if created:
                self.report.subaccounts_created += 1
            else:
                self.report.subaccounts_updated += 1

    # ── 4. Статьи расходов (двухпроходный seed для parent) ───────────

    def _seed_expense_articles(self) -> None:
        from apps.accounting.models import ExpenseArticle

        rows = self.config.get("expense_articles") or []

        # Pass 1: создаём всё без parent.
        for row in rows:
            code = row.get("code")
            name = row.get("name")
            kind = row.get("kind", "expense")
            if not (code and name):
                self.report.skipped.append(f"expense_article {code or '?'} — пропуск")
                continue
            obj, created = ExpenseArticle.objects.update_or_create(
                organization=self.org,
                code=code,
                defaults={
                    "name": name,
                    "kind": kind,
                    "default_subaccount": self._resolve_subaccount(row.get("default_subaccount")),
                    "default_module": self._resolve_module(row.get("default_module")),
                    "is_active": row.get("is_active", True),
                    "notes": row.get("notes", ""),
                },
            )
            self._expense_articles[code] = obj
            if created:
                self.report.expense_articles_created += 1
            else:
                self.report.expense_articles_updated += 1

        # Pass 2: проставляем parent (теперь все записи существуют).
        for row in rows:
            code = row.get("code")
            parent_code = row.get("parent")
            if not parent_code:
                continue
            obj = self._expense_articles.get(code)
            parent = self._expense_articles.get(parent_code)
            if not (obj and parent):
                self.report.skipped.append(
                    f"expense_article {code}: parent '{parent_code}' не найден"
                )
                continue
            if obj.parent_id != parent.id:
                obj.parent = parent
                obj.save(update_fields=["parent", "updated_at"])

    # ── 5. Категории номенклатуры ─────────────────────────────────────

    def _seed_categories(self) -> None:
        from apps.nomenclature.models import Category

        rows = self.config.get("categories") or []
        for row in rows:
            name = row.get("name")
            if not name:
                self.report.skipped.append("category без name")
                continue
            obj, created = Category.objects.update_or_create(
                organization=self.org,
                name=name,
                defaults={
                    "module": self._resolve_module(row.get("module")),
                    "default_gl_subaccount": self._resolve_subaccount(
                        row.get("default_gl_subaccount")
                    ),
                },
            )
            self._categories[name] = obj
            if created:
                self.report.categories_created += 1
            else:
                self.report.categories_updated += 1

    # ── 6. Номенклатура (SKU) ─────────────────────────────────────────

    def _seed_nomenclature(self) -> None:
        from apps.nomenclature.models import NomenclatureItem

        rows = self.config.get("nomenclature") or []
        for row in rows:
            sku = row.get("sku")
            name = row.get("name")
            category_name = row.get("category")
            unit_code = row.get("unit")
            if not (sku and name and category_name and unit_code):
                self.report.skipped.append(f"nomenclature {sku or '?'} — пропуск")
                continue

            moisture = row.get("base_moisture_pct")
            obj, created = NomenclatureItem.objects.update_or_create(
                organization=self.org,
                sku=sku,
                defaults={
                    "name": name,
                    "category": self._resolve_category(category_name),
                    "unit": self._resolve_unit(unit_code),
                    "default_gl_subaccount": self._resolve_subaccount(
                        row.get("default_gl_subaccount")
                    ),
                    "barcode": row.get("barcode", ""),
                    "is_active": row.get("is_active", True),
                    "notes": row.get("notes", ""),
                    "base_moisture_pct": Decimal(str(moisture)) if moisture is not None else None,
                },
            )
            if created:
                self.report.nomenclature_created += 1
            else:
                self.report.nomenclature_updated += 1

    # ── 7. Производственные блоки ─────────────────────────────────────

    def _seed_blocks(self) -> None:
        from apps.warehouses.models import ProductionBlock

        rows = self.config.get("blocks") or []
        for row in rows:
            code = row.get("code")
            name = row.get("name")
            kind = row.get("kind")
            module_code = row.get("module")
            if not (code and name and kind and module_code):
                self.report.skipped.append(f"block {code or '?'} — пропуск")
                continue
            module = self._resolve_module(module_code)

            area = row.get("area_m2")
            capacity = row.get("capacity")
            obj, created = ProductionBlock.objects.update_or_create(
                organization=self.org,
                code=code,
                defaults={
                    "name": name,
                    "kind": kind,
                    "module": module,
                    "area_m2": Decimal(str(area)) if area is not None else None,
                    "capacity": Decimal(str(capacity)) if capacity is not None else None,
                    "capacity_unit": self._resolve_unit(row.get("capacity_unit")),
                    "is_active": row.get("is_active", True),
                },
            )
            self._blocks[code] = obj
            if created:
                self.report.blocks_created += 1
            else:
                self.report.blocks_updated += 1

    # ── 8. Склады ─────────────────────────────────────────────────────

    def _seed_warehouses(self) -> None:
        from apps.warehouses.models import Warehouse

        rows = self.config.get("warehouses") or []
        for row in rows:
            code = row.get("code")
            name = row.get("name")
            module_code = row.get("module")
            if not (code and name and module_code):
                self.report.skipped.append(f"warehouse {code or '?'} — пропуск")
                continue

            _, created = Warehouse.objects.update_or_create(
                organization=self.org,
                code=code,
                defaults={
                    "name": name,
                    "module": self._resolve_module(module_code),
                    "production_block": self._resolve_block(row.get("production_block")),
                    "default_gl_subaccount": self._resolve_subaccount(
                        row.get("default_gl_subaccount")
                    ),
                    "is_active": row.get("is_active", True),
                },
            )
            if created:
                self.report.warehouses_created += 1
            else:
                self.report.warehouses_updated += 1
