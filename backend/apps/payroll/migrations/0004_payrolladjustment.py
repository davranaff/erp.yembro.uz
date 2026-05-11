import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0003_backfill_compensation_plans"),
        ("organizations", "0004_rename_default_org_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PayrollAdjustment",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(
                    choices=[
                        ("bonus", "Премия"),
                        ("deduction", "Удержание"),
                        ("correction_plus", "Доначисление"),
                        ("correction_minus", "Сторно начисления"),
                    ],
                    db_index=True, max_length=24,
                )),
                ("effective_date", models.DateField(db_index=True)),
                ("amount_uzs", models.DecimalField(decimal_places=2, max_digits=14)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_adjustments",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_adjustments",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Корректировка ЗП",
                "verbose_name_plural": "Корректировки ЗП",
                "ordering": ["-effective_date"],
            },
        ),
        migrations.AddIndex(
            model_name="payrolladjustment",
            index=models.Index(
                fields=["organization", "-effective_date"],
                name="payroll_adj_org_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrolladjustment",
            index=models.Index(
                fields=["employee", "-effective_date"],
                name="payroll_adj_emp_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrolladjustment",
            index=models.Index(
                fields=["employee", "kind"],
                name="payroll_adj_emp_kind_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="payrolladjustment",
            constraint=models.CheckConstraint(
                check=models.Q(("amount_uzs__gt", 0)),
                name="payroll_adj_amount_positive",
            ),
        ),
    ]
