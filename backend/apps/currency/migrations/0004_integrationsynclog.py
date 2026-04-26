import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("currency", "0003_seed_base_currencies"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationSyncLog",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.CharField(db_index=True, default="cbu.uz", max_length=32),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "Успех"), ("failed", "Ошибка")],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                (
                    "occurred_at",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now
                    ),
                ),
                (
                    "triggered_by",
                    models.CharField(
                        blank=True,
                        help_text="email юзера для ручного запуска или 'beat' для Celery.",
                        max_length=128,
                    ),
                ),
                (
                    "stats",
                    models.JSONField(
                        blank=True,
                        help_text="Счётчики успешного sync (fetched/created/updated/...).",
                        null=True,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Журнал интеграции",
                "verbose_name_plural": "Журнал интеграций",
                "ordering": ["-occurred_at"],
                "indexes": [
                    models.Index(
                        fields=["provider", "-occurred_at"],
                        name="currency_in_provide_91004b_idx",
                    ),
                    models.Index(
                        fields=["status", "-occurred_at"],
                        name="currency_in_status_d432a5_idx",
                    ),
                ],
            },
        ),
    ]
