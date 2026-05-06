"""
Data-migration: для каждого Counterparty kind=supplier с
opening_debt_uzs > 0 создаём синтетический PurchaseOrder
(kind=opening_balance), чтобы AP-долг жил по стандартному пайплайну
(касса/balances/уведомления).

Симметрично 0010_materialize_opening_balance_sales.py для покупателей.
"""
from __future__ import annotations

import re
from datetime import date as date_cls
from decimal import Decimal


def _next_opn_ap_number(PurchaseOrder, organization_id, on_date):
    year = on_date.year
    regex = rf"^OPN-AP-{year}-\d+$"
    existing = PurchaseOrder.objects.filter(
        organization_id=organization_id,
        doc_number__regex=regex,
    ).values_list("doc_number", flat=True)
    max_n = 0
    pattern = re.compile(rf"^OPN-AP-{year}-(\d+)$")
    for doc in existing:
        m = pattern.match(doc or "")
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"OPN-AP-{year}-{(max_n + 1):05d}"


def materialize_supplier_opening_balances(apps, schema_editor):
    Counterparty = apps.get_model("counterparties", "Counterparty")
    PurchaseOrder = apps.get_model("purchases", "PurchaseOrder")

    qs = Counterparty.objects.filter(
        kind="supplier",
        opening_debt_uzs__gt=0,
    )

    for cp in qs.iterator():
        already = PurchaseOrder.objects.filter(
            organization_id=cp.organization_id,
            counterparty_id=cp.id,
            kind="opening_balance",
        ).exists()
        if already:
            continue

        on_date = cp.opening_balance_date or date_cls.today()
        doc = _next_opn_ap_number(PurchaseOrder, cp.organization_id, on_date)
        PurchaseOrder.objects.create(
            organization_id=cp.organization_id,
            counterparty_id=cp.id,
            kind="opening_balance",
            status="confirmed",
            payment_status="unpaid",
            doc_number=doc,
            date=on_date,
            amount_uzs=cp.opening_debt_uzs,
            paid_amount_uzs=Decimal("0"),
            module=None,
            warehouse=None,
            notes="Перенесённый долг поставщику из предыдущей системы (data-migration).",
        )


def remove_unpaid_supplier_opening_balances(apps, schema_editor):
    PurchaseOrder = apps.get_model("purchases", "PurchaseOrder")
    PurchaseOrder.objects.filter(
        kind="opening_balance",
        paid_amount_uzs=0,
    ).delete()


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0009_add_kind_opening_balance"),
        ("counterparties", "0004_counterparty_opening_balance_date_and_more"),
    ]

    operations = [
        migrations.RunPython(
            materialize_supplier_opening_balances,
            remove_unpaid_supplier_opening_balances,
        ),
    ]
