"""Юнит-тесты для guard'ов баланса в сервисах склада.

Все эти тесты проверяют, что pre-check через ``get_balance`` / батч-
remaining блокирует попытку создать расходную операцию, когда сырья/
корма/медикамента не хватает. Тесты работают через фейковую базу
(``_FakeDb``), имитирующую минимальный подмножество asyncpg API.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.core.exceptions import ValidationError


class _FakeDb:
    """Минимальная имитация ``app.db.pool.Database`` на dict-ах.

    Хранит вручную подготовленные строки для ``stock_movements``,
    ``feed_formula_ingredients``, ``feed_raw_arrivals`` и т.д. и
    отдаёт их по первому встречному паттерну запроса. Возвращаемые
    объекты — обычные dict'ы: достаточно для того, как сервисы их
    используют (через ``row["column"]``).
    """

    def __init__(self) -> None:
        self.stock_movements: list[dict[str, Any]] = []
        self.formula_ingredients: list[dict[str, Any]] = []
        self.feed_raw_arrivals: list[dict[str, Any]] = []
        self.currencies: list[dict[str, Any]] = []
        self.factory_flocks: list[dict[str, Any]] = []
        self.medicine_batches: list[dict[str, Any]] = []
        self.medicine_consumptions: list[dict[str, Any]] = []

    async def fetch(self, query: str, *args: Any):
        q = " ".join(query.split()).lower()
        if "from feed_formula_ingredients" in q:
            formula_id = args[0]
            return [r for r in self.formula_ingredients if str(r["formula_id"]) == str(formula_id)]
        if "from stock_movements" in q and "reference_table" in q:
            return []
        return []

    async def fetchrow(self, query: str, *args: Any):
        q = " ".join(query.split()).lower()
        if "from factory_flocks" in q:
            flock_id = args[0]
            for row in self.factory_flocks:
                if str(row["id"]) == str(flock_id):
                    return row
            return None
        if "coalesce(sum(quantity * unit_price)" in q:
            # _compute_ingredient_avg_price
            organization_id, ingredient_id = args
            rows = [
                r
                for r in self.feed_raw_arrivals
                if str(r["organization_id"]) == str(organization_id)
                and str(r["ingredient_id"]) == str(ingredient_id)
                and r.get("unit_price") is not None
            ]
            if not rows:
                return {"avg_price": Decimal("0"), "currency_id": None}
            total_cost = sum(
                Decimal(str(r["quantity"])) * Decimal(str(r["unit_price"])) for r in rows
            )
            total_qty = sum(Decimal(str(r["quantity"])) for r in rows)
            avg = (total_cost / total_qty) if total_qty > 0 else Decimal("0")
            latest = sorted(
                rows, key=lambda r: (r.get("arrived_on"), r.get("created_at")), reverse=True
            )[0]
            return {"avg_price": avg, "currency_id": latest.get("currency_id")}
        if "from stock_movements" in q and "own" not in q:
            return {"q": Decimal("0")}
        if "from medicine_consumptions" in q and "sum" in q:
            batch_id = args[0]
            total = sum(
                Decimal(str(r["quantity"]))
                for r in self.medicine_consumptions
                if str(r["batch_id"]) == str(batch_id)
            )
            return {"sum": total}
        return None

    async def fetchval(self, query: str, *args: Any):
        return None

    async def execute(self, query: str, *args: Any):
        q = " ".join(query.split()).lower()
        if "update medicine_batches" in q:
            batch_id = args[0]
            for b in self.medicine_batches:
                if str(b["id"]) == str(batch_id):
                    consumed = sum(
                        Decimal(str(c["quantity"]))
                        for c in self.medicine_consumptions
                        if str(c["batch_id"]) == str(batch_id)
                    )
                    received = Decimal(str(b["received_quantity"]))
                    b["remaining_quantity"] = max(received - consumed, Decimal("0"))
            return
        return None


# ---------------------------------------------------------------------------
# Tests: _compute_ingredient_avg_price returns weighted average cost.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_ingredient_avg_price_returns_weighted_mean() -> None:
    from app.services.feed import FeedProductionBatchService

    db = _FakeDb()
    db.feed_raw_arrivals = [
        {
            "organization_id": "org-1",
            "ingredient_id": "ing-wheat",
            "quantity": Decimal("100"),
            "unit_price": Decimal("5.00"),
            "arrived_on": date(2026, 4, 1),
            "created_at": date(2026, 4, 1),
            "currency_id": "cur-uzs",
        },
        {
            "organization_id": "org-1",
            "ingredient_id": "ing-wheat",
            "quantity": Decimal("300"),
            "unit_price": Decimal("6.00"),
            "arrived_on": date(2026, 4, 10),
            "created_at": date(2026, 4, 10),
            "currency_id": "cur-uzs",
        },
    ]

    class _FakeRepo:
        pass

    repo = _FakeRepo()
    repo.db = db  # type: ignore[attr-defined]

    service = FeedProductionBatchService.__new__(FeedProductionBatchService)
    service.repository = repo  # type: ignore[attr-defined]

    avg, currency = await service._compute_ingredient_avg_price(
        organization_id="org-1",
        ingredient_id="ing-wheat",
    )

    # Weighted: (100*5 + 300*6) / 400 = 2300/400 = 5.75
    assert avg == Decimal("5.7500")
    assert currency == "cur-uzs"


@pytest.mark.asyncio
async def test_compute_ingredient_avg_price_no_arrivals_returns_zero() -> None:
    from app.services.feed import FeedProductionBatchService

    db = _FakeDb()

    class _FakeRepo:
        pass

    repo = _FakeRepo()
    repo.db = db  # type: ignore[attr-defined]

    service = FeedProductionBatchService.__new__(FeedProductionBatchService)
    service.repository = repo  # type: ignore[attr-defined]

    avg, currency = await service._compute_ingredient_avg_price(
        organization_id="org-1",
        ingredient_id="ing-wheat",
    )

    assert avg == Decimal("0.0000")
    assert currency is None


# ---------------------------------------------------------------------------
# Tests: formula ingredients fetched correctly for production batch.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_formula_ingredients_returns_all_rows() -> None:
    from app.services.feed import FeedProductionBatchService

    db = _FakeDb()
    db.formula_ingredients = [
        {
            "id": "fi-1",
            "formula_id": "formula-A",
            "ingredient_id": "ing-wheat",
            "quantity_per_unit": Decimal("0.45"),
            "unit": "kg",
            "measurement_unit_id": "mu-kg",
            "ingredient_name": "Пшеница",
            "sort_order": 0,
        },
        {
            "id": "fi-2",
            "formula_id": "formula-A",
            "ingredient_id": "ing-corn",
            "quantity_per_unit": Decimal("0.30"),
            "unit": "kg",
            "measurement_unit_id": "mu-kg",
            "ingredient_name": "Кукуруза",
            "sort_order": 1,
        },
        {
            "id": "fi-3",
            "formula_id": "formula-B",
            "ingredient_id": "ing-rice",
            "quantity_per_unit": Decimal("0.90"),
            "unit": "kg",
            "measurement_unit_id": "mu-kg",
            "ingredient_name": "Рис",
            "sort_order": 0,
        },
    ]

    class _FakeRepo:
        pass

    repo = _FakeRepo()
    repo.db = db  # type: ignore[attr-defined]

    service = FeedProductionBatchService.__new__(FeedProductionBatchService)
    service.repository = repo  # type: ignore[attr-defined]

    result = await service._fetch_formula_ingredients(formula_id="formula-A")

    assert len(result) == 2
    ingredients = {r["ingredient_id"] for r in result}
    assert ingredients == {"ing-wheat", "ing-corn"}
