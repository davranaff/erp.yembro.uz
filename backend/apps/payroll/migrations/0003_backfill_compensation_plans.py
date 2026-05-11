"""
Backfill: для каждого активного OrganizationMembership создать CompensationPlan
с safe-default (monthly_salary, валюта = accounting_currency организации).
HR-админ потом скорректирует.

Идемпотентно: пропускаем если CompensationPlan уже существует.
"""
from django.db import migrations


def backfill_plans(apps, schema_editor):
    OrganizationMembership = apps.get_model("organizations", "OrganizationMembership")
    CompensationPlan = apps.get_model("payroll", "CompensationPlan")

    qs = OrganizationMembership.objects.filter(is_active=True).select_related(
        "organization__accounting_currency",
    )
    for m in qs:
        if CompensationPlan.objects.filter(employee_id=m.id).exists():
            continue
        currency = m.organization.accounting_currency
        if currency is None:
            continue
        CompensationPlan.objects.create(
            organization=m.organization,
            employee=m,
            compensation_type="monthly_salary",
            currency=currency,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0002_seed_default_templates"),
    ]

    operations = [
        migrations.RunPython(backfill_plans, noop),
    ]
