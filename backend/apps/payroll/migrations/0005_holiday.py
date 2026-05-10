import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0004_payrolladjustment"),
        ("organizations", "0004_rename_default_org_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Holiday",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("date", models.DateField(db_index=True)),
                ("name", models.CharField(max_length=128)),
                ("is_paid", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="holidays",
                    to="organizations.organization",
                )),
            ],
            options={
                "verbose_name": "Праздник",
                "verbose_name_plural": "Праздники",
                "ordering": ["date"],
            },
        ),
        migrations.AddIndex(
            model_name="holiday",
            index=models.Index(fields=["date"], name="payroll_hld_date_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="holiday",
            unique_together={("organization", "date")},
        ),
    ]
