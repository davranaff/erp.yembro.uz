import apps.tgbot.models
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("counterparties", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TgLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chat_id", models.BigIntegerField()),
                ("tg_username", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tg_links",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tg_links",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "counterparty",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tg_links",
                        to="counterparties.counterparty",
                    ),
                ),
            ],
            options={
                "verbose_name": "TG привязка",
                "verbose_name_plural": "TG привязки",
                "unique_together": {("organization", "chat_id")},
            },
        ),
        migrations.CreateModel(
            name="TgLinkToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("token", models.CharField(default=apps.tgbot.models._generate_token, max_length=64, unique=True)),
                ("expires_at", models.DateTimeField(default=apps.tgbot.models._token_expires)),
                ("used", models.BooleanField(default=False)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tg_link_tokens",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tg_link_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "counterparty",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tg_link_tokens",
                        to="counterparties.counterparty",
                    ),
                ),
            ],
            options={
                "verbose_name": "TG токен привязки",
                "verbose_name_plural": "TG токены привязки",
            },
        ),
    ]
