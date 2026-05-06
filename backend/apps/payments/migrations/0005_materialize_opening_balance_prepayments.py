"""
Data-migration: для каждого Counterparty с opening_debt_uzs < 0
создаём синтетический Payment(kind=opening_balance_prepayment),
status=POSTED, без allocations и без JE.

Симметрично:
    sales/migrations/0010     — для opening_debt > 0, kind=buyer
    purchases/migrations/0010 — для opening_debt > 0, kind=supplier
    тут                       — для opening_debt < 0, оба kind

Идемпотентна: если синтетический Payment уже есть — пропускаем.
"""
from __future__ import annotations

import re
from datetime import date as date_cls
from decimal import Decimal


def _next_obp_number(Payment, organization_id, on_date):
    year = on_date.year
    regex = rf"^ОБП-{year}-\d+$"
    existing = Payment.objects.filter(
        organization_id=organization_id,
        doc_number__regex=regex,
    ).values_list("doc_number", flat=True)
    max_n = 0
    pattern = re.compile(rf"^ОБП-{year}-(\d+)$")
    for doc in existing:
        m = pattern.match(doc or "")
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"ОБП-{year}-{(max_n + 1):05d}"


def materialize_prepayments(apps, schema_editor):
    Counterparty = apps.get_model("counterparties", "Counterparty")
    Payment = apps.get_model("payments", "Payment")

    qs = Counterparty.objects.filter(
        opening_debt_uzs__lt=0,
        kind__in=("buyer", "supplier"),
    )

    for cp in qs.iterator():
        already = Payment.objects.filter(
            organization_id=cp.organization_id,
            counterparty_id=cp.id,
            kind="opening_balance_prepayment",
        ).exists()
        if already:
            continue

        amount = abs(Decimal(cp.opening_debt_uzs))
        on_date = cp.opening_balance_date or date_cls.today()
        direction = "in" if cp.kind == "buyer" else "out"
        doc = _next_obp_number(Payment, cp.organization_id, on_date)

        # posted_at — обязательно для status=posted (audit-консистентность),
        # но в самой модели поле nullable. Используем opening_balance_date
        # как «момент проведения» — это снимок миграции.
        from datetime import datetime, time

        posted_at = datetime.combine(on_date, time(12, 0))

        Payment.objects.create(
            organization_id=cp.organization_id,
            counterparty_id=cp.id,
            module=None,
            doc_number=doc,
            date=on_date,
            direction=direction,
            channel="other",
            kind="opening_balance_prepayment",
            status="posted",
            amount_uzs=amount,
            posted_at=posted_at,
            notes=(
                "Перенесённая предоплата из предыдущей системы (data-migration). "
                "Применяется к будущим документам через allocations."
            ),
        )


def remove_prepayments(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    # Удаляем только те, у которых нет allocations — иначе разрушим
    # уже применённые «деньги» к SO/PO.
    PaymentAllocation = apps.get_model("payments", "PaymentAllocation")
    has_alloc_ids = set(PaymentAllocation.objects.values_list(
        "payment_id", flat=True,
    ))
    Payment.objects.filter(
        kind="opening_balance_prepayment",
    ).exclude(id__in=has_alloc_ids).delete()


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_add_opening_balance_prepayment_kind"),
        ("counterparties", "0004_counterparty_opening_balance_date_and_more"),
    ]

    operations = [
        migrations.RunPython(materialize_prepayments, remove_prepayments),
    ]
