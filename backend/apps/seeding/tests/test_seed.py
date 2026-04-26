"""
Тесты OrganizationSeeder.

Сценарии:
    1. Прогон на пустой организации создаёт всё (counts > 0).
    2. Повторный прогон — ничего не создаёт (всё updated, ноль created).
    3. dry_run не пишет в БД.
    4. Ссылка на несуществующий subaccount/category — SeedError.
    5. Custom inline-config работает (без YAML-файла).
    6. expense_articles parent проставляется во втором проходе.
"""
from __future__ import annotations

import pytest

from apps.accounting.models import ExpenseArticle, GLAccount, GLSubaccount
from apps.currency.models import Currency
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.seeding.services.loader import OrganizationSeeder, SeedError
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def fresh_org():
    """Чистая организация без seed-данных."""
    uzs = Currency.objects.get(code="UZS")
    return Organization.objects.create(
        code="TEST-SEED-FARM",
        name="Test Seed Farm",
        direction="broiler",
        accounting_currency=uzs,
        timezone="Asia/Tashkent",
    )


@pytest.fixture
def minimal_config():
    """Минимальный конфиг для unit-тестов (без полного default_org.yaml)."""
    return {
        "version": 1,
        "units": [
            {"code": "kg", "name": "Килограмм"},
            {"code": "pcs", "name": "Штука"},
        ],
        "accounts": [
            {"code": "10", "name": "Материалы", "type": "asset"},
            {"code": "50", "name": "Касса", "type": "asset"},
        ],
        "subaccounts": [
            {"code": "10.05", "account": "10", "name": "Корма", "module": "feed"},
            {"code": "50.01", "account": "50", "name": "Касса UZS"},
        ],
        "expense_articles": [
            {"code": "UTILS", "name": "Коммуналка", "kind": "expense"},
            {"code": "GAS", "name": "Газ", "kind": "expense", "parent": "UTILS",
             "default_subaccount": "10.05"},
        ],
        "categories": [
            {"name": "Корма", "module": "feed", "default_gl_subaccount": "10.05"},
        ],
        "nomenclature": [
            {"sku": "FEED-START", "name": "Старт", "category": "Корма", "unit": "kg",
             "default_gl_subaccount": "10.05"},
        ],
        "blocks": [
            {"code": "БНК-1", "name": "Бункер №1", "kind": "storage_bin", "module": "feed"},
        ],
        "warehouses": [
            {"code": "СК-К", "name": "Склад кормов", "module": "feed",
             "default_gl_subaccount": "10.05", "production_block": "БНК-1"},
            {"code": "КАССА-НАЛ", "name": "Касса наличные", "module": "stock",
             "default_gl_subaccount": "50.01"},
        ],
    }


def test_seed_on_empty_org_creates_everything(fresh_org, minimal_config):
    seeder = OrganizationSeeder(fresh_org, config_data=minimal_config)
    report = seeder.run()

    assert report.units_created == 2
    assert report.accounts_created == 2
    assert report.subaccounts_created == 2
    assert report.expense_articles_created == 2
    assert report.categories_created == 1
    assert report.nomenclature_created == 1
    assert report.blocks_created == 1
    assert report.warehouses_created == 2

    # Проверка ссылочной целостности
    nom = NomenclatureItem.objects.get(organization=fresh_org, sku="FEED-START")
    assert nom.category.name == "Корма"
    assert nom.unit.code == "kg"
    assert nom.default_gl_subaccount.code == "10.05"

    wh = Warehouse.objects.get(organization=fresh_org, code="СК-К")
    assert wh.module.code == "feed"
    assert wh.default_gl_subaccount.code == "10.05"
    assert wh.production_block.code == "БНК-1"

    # parent у expense_articles проставлен во втором проходе
    gas = ExpenseArticle.objects.get(organization=fresh_org, code="GAS")
    assert gas.parent and gas.parent.code == "UTILS"
    assert gas.default_subaccount.code == "10.05"


def test_idempotent_second_run(fresh_org, minimal_config):
    """Повторный прогон не создаёт дубликатов."""
    OrganizationSeeder(fresh_org, config_data=minimal_config).run()

    counts_before = {
        "units": Unit.objects.filter(organization=fresh_org).count(),
        "accounts": GLAccount.objects.filter(organization=fresh_org).count(),
        "subaccounts": GLSubaccount.objects.filter(account__organization=fresh_org).count(),
        "categories": Category.objects.filter(organization=fresh_org).count(),
        "nomenclature": NomenclatureItem.objects.filter(organization=fresh_org).count(),
        "blocks": ProductionBlock.objects.filter(organization=fresh_org).count(),
        "warehouses": Warehouse.objects.filter(organization=fresh_org).count(),
    }

    second_report = OrganizationSeeder(fresh_org, config_data=minimal_config).run()

    counts_after = {
        "units": Unit.objects.filter(organization=fresh_org).count(),
        "accounts": GLAccount.objects.filter(organization=fresh_org).count(),
        "subaccounts": GLSubaccount.objects.filter(account__organization=fresh_org).count(),
        "categories": Category.objects.filter(organization=fresh_org).count(),
        "nomenclature": NomenclatureItem.objects.filter(organization=fresh_org).count(),
        "blocks": ProductionBlock.objects.filter(organization=fresh_org).count(),
        "warehouses": Warehouse.objects.filter(organization=fresh_org).count(),
    }

    assert counts_before == counts_after
    assert second_report.total_created() == 0
    # Все объекты были обновлены (no-op update_or_create)
    assert second_report.total_updated() > 0


def test_dry_run_writes_nothing(fresh_org, minimal_config):
    seeder = OrganizationSeeder(fresh_org, config_data=minimal_config, dry_run=True)
    report = seeder.run()

    # report содержит планируемые counts
    assert report.units_created == 2
    # но в БД пусто
    assert Unit.objects.filter(organization=fresh_org).count() == 0
    assert GLAccount.objects.filter(organization=fresh_org).count() == 0


def test_unknown_module_raises(fresh_org):
    config = {
        "subaccounts": [
            {"code": "X.01", "account": "X", "name": "...", "module": "no-such-module"},
        ],
        "accounts": [{"code": "X", "name": "X", "type": "asset"}],
    }
    with pytest.raises(SeedError, match="no-such-module"):
        OrganizationSeeder(fresh_org, config_data=config).run()


def test_unknown_subaccount_reference_raises(fresh_org):
    config = {
        "units": [{"code": "kg", "name": "kg"}],
        "categories": [
            {"name": "X", "default_gl_subaccount": "99.99"},  # нет такого
        ],
    }
    with pytest.raises(SeedError, match="99.99"):
        OrganizationSeeder(fresh_org, config_data=config).run()


def test_default_yaml_loads_on_default_org():
    """Проверка что реальный default_org.yaml применяется на DEFAULT-org без ошибок."""
    org = Organization.objects.get(code="DEFAULT")
    seeder = OrganizationSeeder(org)  # config_path=None → DEFAULT_CONFIG
    report = seeder.run()
    # На уже инициализированной DEFAULT-org часть данных уже есть из миграций —
    # ожидаем смесь created/updated, но без ошибок и без skipped.
    assert report.total_created() + report.total_updated() > 50
    assert report.errors == []
