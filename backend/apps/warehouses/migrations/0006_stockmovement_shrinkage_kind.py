from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("warehouses", "0005_seed_default_blocks"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockmovement",
            name="kind",
            field=models.CharField(
                choices=[
                    ("incoming", "Приход"),
                    ("outgoing", "Расход"),
                    ("transfer", "Перемещение"),
                    ("write_off", "Списание"),
                    ("shrinkage", "Усушка"),
                ],
                max_length=16,
            ),
        ),
    ]
