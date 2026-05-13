from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0009_hr_manager_only_hr"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userscopeassignment",
            name="scope_type",
            field=models.CharField(
                choices=[
                    ("warehouse", "Склад"),
                    ("production_block", "Производственный блок"),
                    ("module", "Модуль"),
                ],
                db_index=True,
                max_length=24,
            ),
        ),
    ]
