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
    # Если у юзера есть membership в нескольких организациях, он может через
    # /org переключить активную. NULL → fallback на `organization` (ту, под
    # которой он привязал бота). См. handlers/org.py.
    active_organization = models.ForeignKey(
        "organizations.Organization",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Подписка на ежедневный owner-digest (08:00 Asia/Tashkent). True для
    # admin-link по умолчанию (юзер привязал бота → значит хочет видеть
    # сводку). Counterparty-линки никогда не получают digest, для них
    # есть только debt-reminders. См. tasks.owner_digest_task.
    digest_enabled = models.BooleanField(default=True)

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


def _wizard_expires() -> object:
    return timezone.now() + timedelta(minutes=30)


class TgWizardSession(UUIDModel, TimestampedModel):
    """
    Состояние многошагового диалога (wizard) для конкретного chat_id.

    Юзер запускает команду (например `/qabul`), сервер создаёт сессию
    с начальным state'ом. Каждый callback / текстовый ответ обновляет
    state и накапливает payload (выбранный склад, поставщик, qty и т.п.).
    На последнем шаге payload отдаётся в существующий ERP-сервис
    (`confirm_purchase` / `WriteOff` / `execute_production_task`),
    сессия удаляется.

    Один chat_id → одна активная сессия. При запуске нового wizard'а
    старая сессия (если есть) перезаписывается — это сознательно: если
    юзер бросил wizard на середине и начал новый, старый просто умирает.

    expires_at = 30 минут — для вечерней очистки. Сессии без активности
    дольше TTL не возвращаются `get_active()` и считаются истёкшими.
    """
    chat_id = models.BigIntegerField(unique=True, db_index=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="+",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    wizard = models.CharField(max_length=64)
    """Код wizard'а: `feed_purchase`, `feed_writeoff`, `feed_mix`."""
    state = models.CharField(max_length=64)
    """Текущий step. Формат `<scope>:<step>` — например `purchase:qty`."""
    payload = models.JSONField(default=dict, blank=True)
    """Накопленные данные (warehouse_id, supplier_id, items[], etc)."""
    expires_at = models.DateTimeField(default=_wizard_expires)

    class Meta:
        verbose_name = "TG wizard сессия"
        verbose_name_plural = "TG wizard сессии"

    def __str__(self) -> str:
        return f"WizardSession({self.chat_id} · {self.wizard}@{self.state})"

    @property
    def is_active(self) -> bool:
        return timezone.now() < self.expires_at

    def touch(self) -> None:
        """Продлить сессию (новые 30 минут от now)."""
        self.expires_at = _wizard_expires()
        self.save(update_fields=["expires_at", "updated_at"])

    def advance(self, *, state: str, payload_update: dict | None = None) -> None:
        """Переход на следующий step + опциональный merge в payload."""
        if payload_update:
            current = dict(self.payload or {})
            current.update(payload_update)
            self.payload = current
        self.state = state
        self.expires_at = _wizard_expires()
        self.save(update_fields=["state", "payload", "expires_at", "updated_at"])

    @classmethod
    def get_active(cls, chat_id: int) -> "TgWizardSession | None":
        """Активная (не истёкшая) сессия или None. Истёкшие удаляет в фоне."""
        s = cls.objects.filter(chat_id=chat_id).first()
        if s is None:
            return None
        if not s.is_active:
            s.delete()
            return None
        return s
