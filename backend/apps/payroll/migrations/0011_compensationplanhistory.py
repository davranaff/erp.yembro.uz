import uuid
from datetime import date

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_history(apps, schema_editor):
    """Каждому существующему CompensationPlan создать запись в History."""
    CompensationPlan = apps.get_model("payroll", "CompensationPlan")
    History = apps.get_model("payroll", "CompensationPlanHistory")
    today = date.today()
    for plan in CompensationPlan.objects.all():
        # joined_at у membership — best-guess effective_from
        m = plan.employee
        eff_from = m.joined_at.date() if m.joined_at else today
        if eff_from > today:
            eff_from = today
        if not History.objects.filter(employee=m).exists():
            History.objects.create(
                organization=plan.organization,
                employee=m,
                compensation_type=plan.compensation_type,
                effective_from=eff_from,
                reason="initial backfill",
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0010_seed_snapshot_beat"),
        ("organizations", "0004_rename_default_org_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompensationPlanHistory",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("compensation_type", models.CharField(
                    choices=[
                        ("monthly_salary", "Оклад в месяц"),
                        ("per_shift", "Ставка за смену"),
                        ("per_hour", "Ставка за час"),
                    ],
                    max_length=24,
                )),
                ("effective_from", models.DateField(db_index=True)),
                ("effective_to", models.DateField(blank=True, db_index=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="compensation_history",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="compensation_history",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "История типа оплаты",
                "verbose_name_plural": "История типа оплаты",
                "ordering": ["-effective_from"],
            },
        ),
        migrations.AddIndex(
            model_name="compensationplanhistory",
            index=models.Index(
                fields=["employee", "-effective_from"],
                name="payroll_compH_emp_eff_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="compensationplanhistory",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_to__gte", models.F("effective_from")),
                    _connector="OR",
                ),
                name="payroll_comphistory_valid_interval",
            ),
        ),
        migrations.RunPython(backfill_history, noop),
    ]
