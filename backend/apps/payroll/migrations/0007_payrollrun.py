import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0006_seed_uz_holidays"),
        ("accounting", "0013_seed_70_01_subaccount"),
        ("organizations", "0004_rename_default_org_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PayrollRun",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("period_from", models.DateField()),
                ("period_to", models.DateField()),
                ("payout_type", models.CharField(
                    choices=[
                        ("advance", "Аванс"),
                        ("salary", "ЗП"),
                        ("bonus", "Премия"),
                        ("correction", "Корректировка/доплата"),
                    ],
                    default="salary", max_length=16,
                )),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Черновик"),
                        ("executed", "Выполнено"),
                        ("cancelled", "Отменено"),
                    ],
                    db_index=True, default="draft", max_length=16,
                )),
                ("employees_count", models.PositiveIntegerField(default=0)),
                ("total_amount_uzs", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("notes", models.TextField(blank=True)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("cash_subaccount", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="accounting.glsubaccount",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_runs",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Ведомость на выплату",
                "verbose_name_plural": "Ведомости на выплату",
                "ordering": ["-period_to", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="payrollrun",
            index=models.Index(
                fields=["organization", "-period_to"],
                name="payroll_run_org_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrollrun",
            index=models.Index(fields=["status"], name="payroll_run_status_idx"),
        ),
        migrations.AddField(
            model_name="payrollpayout",
            name="run",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payouts",
                to="payroll.payrollrun",
                help_text="Запуск ведомости, в рамках которого создан этот payout.",
            ),
        ),
    ]
