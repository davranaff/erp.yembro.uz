"""
Data-migration: для каждого Counterparty с opening_debt_uzs > 0 создаём
синтетический SaleOrder (kind=opening_balance), чтобы он жил по
стандартному пайплайну (касса/aging/tasks).

После этой миграции в коде убираются «+ opening» костыли в aging.py и
credit_check.py — источник истины один: SaleOrder.

Идемпотентность: если SO уже есть (повторный прогон, ручной seed) —
пропускаем. Reverse: удаляет только OPN- документы без оплат, чтобы не
ломать платёжную историю.
"""
from __future__ import annotations

import re
from datetime import date as date_cls
from decimal import Decimal


def _next_opn_number(SaleOrder, organization_id, on_date):
    year = on_date.year
    regex = rf"^OPN-{year}-\d+$"
    existing = SaleOrder.objects.filter(
        organization_id=organization_id,
        doc_number__regex=regex,
    ).values_list("doc_number", flat=True)
    max_n = 0
    pattern = re.compile(rf"^OPN-{year}-(\d+)$")
    for doc in existing:
        m = pattern.match(doc or "")
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"OPN-{year}-{(max_n + 1):05d}"


def materialize_opening_balances(apps, schema_editor):
    Counterparty = apps.get_model("counterparties", "Counterparty")
    SaleOrder = apps.get_model("sales", "SaleOrder")

    # kind=buyer + положительный opening_debt — те, для кого имеет смысл SO.
    # Поставщиков и предоплаты не трогаем (отдельная ветка реализации).
    qs = Counterparty.objects.filter(
        kind="buyer",
        opening_debt_uzs__gt=0,
    )

    for cp in qs.iterator():
        already = SaleOrder.objects.filter(
            organization_id=cp.organization_id,
            customer_id=cp.id,
            kind="opening_balance",
        ).exists()
        if already:
            continue

        on_date = cp.opening_balance_date or date_cls.today()
        doc = _next_opn_number(SaleOrder, cp.organization_id, on_date)
        SaleOrder.objects.create(
            organization_id=cp.organization_id,
            customer_id=cp.id,
            kind="opening_balance",
            status="confirmed",
            payment_status="unpaid",
            doc_number=doc,
            date=on_date,
            due_date=on_date,
            amount_uzs=cp.opening_debt_uzs,
            cost_uzs=Decimal("0"),
            paid_amount_uzs=Decimal("0"),
            module=None,
            warehouse=None,
            notes="Перенесённый долг из предыдущей системы (data-migration).",
        )


def remove_unpaid_opening_balances(apps, schema_editor):
    SaleOrder = apps.get_model("sales", "SaleOrder")
    SaleOrder.objects.filter(
        kind="opening_balance",
        paid_amount_uzs=0,
    ).delete()


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0009_add_kind_opening_balance"),
        ("counterparties", "0004_counterparty_opening_balance_date_and_more"),
    ]

    operations = [
        migrations.RunPython(
            materialize_opening_balances,
            remove_unpaid_opening_balances,
        ),
    ]
