from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimestampedModel, UUIDModel


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _token_expires() -> object:
    return timezone.now() + timedelta(minutes=30)


class TgLink(UUIDModel, TimestampedModel):
    """
    Привязка Telegram chat_id к пользователю ERP или контрагенту.
    XOR: либо user заполнен, либо counterparty.
    """
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="tg_links",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tg_links",
    )
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tg_links",
    )
    chat_id = models.BigIntegerField()
    tg_username = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "chat_id")]
        verbose_name = "TG привязка"
        verbose_name_plural = "TG привязки"

    def __str__(self) -> str:
        who = self.user or self.counterparty or "?"
        return f"TgLink({who} → {self.chat_id})"

    @property
    def is_admin(self) -> bool:
        return self.user_id is not None


class TgLinkToken(UUIDModel, TimestampedModel):
    """
    Одноразовый токен выдаётся в ERP, пользователь вводит его боту
    командой /start <token> или /link <token>.
    Живёт 30 минут.
    """
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="tg_link_tokens",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tg_link_tokens",
    )
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tg_link_tokens",
    )
    token = models.CharField(max_length=64, unique=True, default=_generate_token)
    expires_at = models.DateTimeField(default=_token_expires)
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "TG токен привязки"
        verbose_name_plural = "TG токены привязки"

    @property
    def is_valid(self) -> bool:
        return not self.used and timezone.now() < self.expires_at
