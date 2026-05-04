from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="saleorder",
            name="exchange_rate_override",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text=(
                    "Ручной курс, переопределяющий CBU. Заполняется в DRAFT, "
                    "применяется при confirm. Если NULL — берётся курс ЦБ."
                ),
                max_digits=18,
                null=True,
            ),
        ),
    ]
