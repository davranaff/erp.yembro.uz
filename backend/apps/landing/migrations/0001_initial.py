import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DemoLead",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "name",
                    models.CharField(max_length=200, verbose_name="Имя"),
                ),
                (
                    "contact",
                    models.CharField(max_length=200, verbose_name="Телефон / Email"),
                ),
                (
                    "company",
                    models.CharField(blank=True, max_length=200, verbose_name="Компания"),
                ),
                (
                    "notified",
                    models.BooleanField(default=False, verbose_name="Уведомление отправлено"),
                ),
            ],
            options={
                "verbose_name": "Заявка на демо",
                "verbose_name_plural": "Заявки на демо",
                "ordering": ["-created_at"],
            },
        ),
    ]
