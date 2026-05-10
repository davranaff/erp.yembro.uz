import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0011_compensationplanhistory"),
        ("organizations", "0004_rename_default_org_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PayrollPeriod",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("period_from", models.DateField()),
                ("period_to", models.DateField()),
                ("status", models.CharField(
                    choices=[("open", "Открыт"), ("closed", "Закрыт")],
                    db_index=True, default="open", max_length=8,
                )),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("closed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payroll_periods",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Закрытый период ЗП",
                "verbose_name_plural": "Закрытые периоды ЗП",
                "ordering": ["-period_to"],
            },
        ),
        migrations.AddIndex(
            model_name="payrollperiod",
            index=models.Index(
                fields=["organization", "-period_to"],
                name="payroll_per_org_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrollperiod",
            index=models.Index(fields=["status"], name="payroll_per_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="payrollperiod",
            constraint=models.CheckConstraint(
                check=models.Q(("period_to__gte", models.F("period_from"))),
                name="payroll_period_valid_range",
            ),
        ),
    ]
