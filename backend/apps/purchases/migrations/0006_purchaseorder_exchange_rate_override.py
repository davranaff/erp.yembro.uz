from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0005_purchaseorder_paid_amount_uzs_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="exchange_rate_override",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text=(
                    "Ручной курс, переопределяющий CBU. Заполняется в DRAFT, "
                    "применяется при confirm. Если NULL — берётся курс ЦБ Узбекистана."
                ),
                max_digits=18,
                null=True,
            ),
        ),
    ]
