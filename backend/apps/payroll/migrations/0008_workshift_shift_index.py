from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0007_payrollrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="workshift",
            name="shift_index",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="0 — основная смена дня; 1 — ночная или дополнительная.",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="workshift",
            unique_together={("employee", "shift_date", "shift_index")},
        ),
        migrations.AlterModelOptions(
            name="workshift",
            options={
                "ordering": ["-shift_date", "shift_index"],
                "verbose_name": "Смена",
                "verbose_name_plural": "Смены",
            },
        ),
    ]
