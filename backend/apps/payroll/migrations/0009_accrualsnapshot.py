import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0008_workshift_shift_index"),
        ("organizations", "0004_rename_default_org_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="PayrollAccrualSnapshot",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("as_of", models.DateField(db_index=True)),
                ("accrued_total", models.DecimalField(decimal_places=2, max_digits=18)),
                ("paid_total", models.DecimalField(decimal_places=2, max_digits=18)),
                ("adjustments_plus", models.DecimalField(decimal_places=2, max_digits=18)),
                ("adjustments_minus", models.DecimalField(decimal_places=2, max_digits=18)),
                ("balance_uzs", models.DecimalField(decimal_places=2, max_digits=18)),
                ("computed_at", models.DateTimeField(db_index=True)),
                ("employee", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="accrual_snapshot",
                    to="organizations.organizationmembership",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="accrual_snapshots",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Снимок баланса ЗП",
                "verbose_name_plural": "Снимки балансов ЗП",
            },
        ),
        migrations.AddIndex(
            model_name="payrollaccrualsnapshot",
            index=models.Index(
                fields=["organization", "computed_at"],
                name="payroll_snap_org_at_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payrollaccrualsnapshot",
            index=models.Index(
                fields=["organization", "balance_uzs"],
                name="payroll_snap_org_bal_idx",
            ),
        ),
    ]
