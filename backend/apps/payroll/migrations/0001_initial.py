import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounting", "0013_seed_70_01_subaccount"),
        ("currency", "0005_rename_cbu_task_path"),
        ("organizations", "0004_rename_default_org_name"),
        ("payments", "0005_materialize_opening_balance_prepayments"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── CompensationPlan ──────────────────────────────────────────────
        migrations.CreateModel(
            name="CompensationPlan",
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
                    db_index=True, default="monthly_salary", max_length=24,
                )),
                ("notes", models.TextField(blank=True)),
                ("currency", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="currency.currency",
                )),
                ("employee", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="compensation_plan",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="compensation_plans",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "План оплаты",
                "verbose_name_plural": "Планы оплаты",
            },
        ),
        # ── SalaryRate ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="SalaryRate",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("effective_from", models.DateField(db_index=True)),
                ("effective_to", models.DateField(blank=True, db_index=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("currency", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="currency.currency",
                )),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="salary_rates",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="salary_rates",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Ставка ЗП",
                "verbose_name_plural": "Ставки ЗП",
                "ordering": ["-effective_from"],
            },
        ),
        # ── WorkScheduleTemplate ──────────────────────────────────────────
        migrations.CreateModel(
            name="WorkScheduleTemplate",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=128)),
                ("pattern_kind", models.CharField(
                    choices=[
                        ("weekday_mask", "По дням недели"),
                        ("rotation", "Сменный график"),
                    ],
                    db_index=True, max_length=24,
                )),
                ("pattern", models.JSONField()),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="schedule_templates",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Шаблон графика",
                "verbose_name_plural": "Шаблоны графиков",
            },
        ),
        # ── WorkSchedule ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkSchedule",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("effective_from", models.DateField(db_index=True)),
                ("effective_to", models.DateField(blank=True, db_index=True, null=True)),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="work_schedules",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="work_schedules",
                    to="organizations.organization",
                )),
                ("template", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="assignments",
                    to="payroll.workscheduletemplate",
                )),
            ],
            options={
                "verbose_name": "Назначение графика",
                "verbose_name_plural": "Назначения графиков",
                "ordering": ["-effective_from"],
            },
        ),
        # ── WorkShift ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkShift",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("shift_date", models.DateField(db_index=True)),
                ("kind", models.CharField(
                    choices=[
                        ("work", "Рабочая смена"),
                        ("overtime", "Сверхурочная"),
                        ("vacation", "Отпуск"),
                        ("sick_leave", "Больничный"),
                        ("absence", "Прогул"),
                        ("day_off", "Выходной"),
                        ("holiday", "Праздник"),
                    ],
                    db_index=True, default="work", max_length=16,
                )),
                ("source", models.CharField(
                    choices=[
                        ("template", "Из шаблона"),
                        ("manual", "Ручная"),
                        ("import", "Импорт"),
                    ],
                    db_index=True, default="manual", max_length=16,
                )),
                ("start_at", models.DateTimeField(blank=True, null=True)),
                ("end_at", models.DateTimeField(blank=True, null=True)),
                ("hours", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="work_shifts",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="work_shifts",
                    to="organizations.organization",
                )),
                ("source_template", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="generated_shifts",
                    to="payroll.workscheduletemplate",
                )),
            ],
            options={
                "verbose_name": "Смена",
                "verbose_name_plural": "Смены",
                "ordering": ["-shift_date"],
            },
        ),
        # ── PayrollPayout ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="PayrollPayout",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type", models.CharField(
                    choices=[
                        ("advance", "Аванс"),
                        ("salary", "ЗП"),
                        ("bonus", "Премия"),
                        ("correction", "Корректировка/доплата"),
                    ],
                    db_index=True, default="salary", max_length=16,
                )),
                ("period_from", models.DateField()),
                ("period_to", models.DateField()),
                ("amount_uzs", models.DecimalField(decimal_places=2, max_digits=18)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_payouts",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_payouts",
                    to="organizations.organization",
                )),
                ("payment", models.OneToOneField(
                    help_text="Реальный кассовый платёж OUT, kind=salary.",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_payout",
                    to="payments.payment",
                )),
            ],
            options={
                "verbose_name": "Выплата ЗП",
                "verbose_name_plural": "Выплаты ЗП",
                "ordering": ["-period_to", "-created_at"],
            },
        ),
        # ── Indexes ───────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="compensationplan",
            index=models.Index(
                fields=["organization", "compensation_type"],
                name="payroll_cp_org_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="salaryrate",
            index=models.Index(
                fields=["employee", "-effective_from"],
                name="payroll_rate_emp_eff_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="salaryrate",
            index=models.Index(
                fields=["organization", "effective_from", "effective_to"],
                name="payroll_rate_org_eff_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workscheduletemplate",
            index=models.Index(
                fields=["organization", "is_active"],
                name="payroll_tpl_org_act_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workschedule",
            index=models.Index(
                fields=["employee", "-effective_from"],
                name="payroll_ws_emp_eff_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workshift",
            index=models.Index(
                fields=["organization", "-shift_date"],
                name="payroll_shft_org_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workshift",
            index=models.Index(
                fields=["employee", "-shift_date"],
                name="payroll_shft_emp_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workshift",
            index=models.Index(
                fields=["organization", "kind", "shift_date"],
                name="payroll_shft_kind_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrollpayout",
            index=models.Index(
                fields=["organization", "-period_to"],
                name="payroll_pyt_org_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrollpayout",
            index=models.Index(
                fields=["employee", "-period_to"],
                name="payroll_pyt_emp_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrollpayout",
            index=models.Index(
                fields=["employee", "type"],
                name="payroll_pyt_emp_typ_idx",
            ),
        ),
        # ── Constraints ───────────────────────────────────────────────────
        migrations.AlterUniqueTogether(
            name="workscheduletemplate",
            unique_together={("organization", "code")},
        ),
        migrations.AlterUniqueTogether(
            name="workshift",
            unique_together={("employee", "shift_date")},
        ),
        migrations.AddConstraint(
            model_name="salaryrate",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_to__gte", models.F("effective_from")),
                    _connector="OR",
                ),
                name="payroll_rate_valid_interval",
            ),
        ),
        migrations.AddConstraint(
            model_name="salaryrate",
            constraint=models.CheckConstraint(
                check=models.Q(("amount__gt", 0)),
                name="payroll_rate_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="workschedule",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_to__gte", models.F("effective_from")),
                    _connector="OR",
                ),
                name="payroll_workschedule_valid_interval",
            ),
        ),
        migrations.AddConstraint(
            model_name="payrollpayout",
            constraint=models.CheckConstraint(
                check=models.Q(("amount_uzs__gt", 0)),
                name="payroll_payout_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="payrollpayout",
            constraint=models.CheckConstraint(
                check=models.Q(("period_to__gte", models.F("period_from"))),
                name="payroll_payout_valid_period",
            ),
        ),
    ]
