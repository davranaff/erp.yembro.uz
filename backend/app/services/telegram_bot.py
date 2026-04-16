from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from aiogram import Bot
from aiogram.types import Update

from app.api.deps import CurrentActor
from app.core.config import get_settings
from app.repositories.system import TelegramRecipientRepository
from app.services.client_notifications import TelegramNotificationGateway
from app.utils.auth_tokens import TokenError, create_signed_token, decode_signed_token


logger = logging.getLogger(__name__)

TELEGRAM_LINK_TOKEN_TYPE = "telegram_link"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TelegramBotService:
    def __init__(self, db) -> None:
        self.db = db
        self.settings = get_settings()
        self.repository = TelegramRecipientRepository(db)
        self.gateway = TelegramNotificationGateway()
        self._bot_token = str(self.settings.telegram_bot_token or "").strip()
        self._webhook_secret = str(self.settings.telegram_webhook_secret or "").strip()

    @property
    def is_bot_configured(self) -> bool:
        return bool(self._bot_token)

    @property
    def is_webhook_configured(self) -> bool:
        return bool(self._bot_token and self._webhook_secret)

    def _ensure_bot_configured(self) -> None:
        if self.is_bot_configured:
            return
        raise RuntimeError("Telegram bot token is not configured")

    def _ensure_webhook_configured(self) -> None:
        if self.is_webhook_configured:
            return
        raise RuntimeError("Telegram webhook secret is not configured")

    async def _get_active_employee(self, employee_id: str) -> dict[str, Any] | None:
        try:
            normalized_employee_id = str(UUID(str(employee_id)))
        except ValueError:
            return None

        row = await self.db.fetchrow(
            """
            SELECT
                e.id,
                e.organization_id,
                e.organization_key,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.is_active
            FROM employees AS e
            WHERE e.id = $1
              AND e.is_active = true
            LIMIT 1
            """,
            normalized_employee_id,
        )
        return dict(row) if row is not None else None

    def _build_start_url(self, *, bot_username: str, token: str) -> str:
        return f"https://t.me/{bot_username}?start={token}"

    async def get_bot_username(self) -> str:
        self._ensure_bot_configured()
        bot = Bot(token=self._bot_token)
        try:
            me = await bot.get_me()
        finally:
            await bot.session.close()

        username = str(getattr(me, "username", "") or "").strip()
        if not username:
            raise RuntimeError("Telegram bot username is unavailable")
        return username

    def create_link_token(self, *, employee_id: str) -> tuple[str, datetime]:
        ttl_minutes = max(int(self.settings.telegram_link_token_ttl_minutes or 30), 1)
        return create_signed_token(
            subject=employee_id,
            token_type=TELEGRAM_LINK_TOKEN_TYPE,
            secret_key=self.settings.auth_secret_key,
            expires_in=timedelta(minutes=ttl_minutes),
        )

    def decode_link_token(self, token: str) -> str:
        payload = decode_signed_token(
            token,
            secret_key=self.settings.auth_secret_key,
            expected_type=TELEGRAM_LINK_TOKEN_TYPE,
        )
        return str(payload["sub"])

    async def generate_self_service_link(
        self,
        *,
        actor: CurrentActor,
    ) -> dict[str, Any]:
        self._ensure_bot_configured()

        employee = await self._get_active_employee(actor.employee_id)
        if employee is None:
            raise RuntimeError("Authenticated employee is not active")

        token, expires_at = self.create_link_token(employee_id=str(employee["id"]))
        bot_username = await self.get_bot_username()
        return {
            "url": self._build_start_url(bot_username=bot_username, token=token),
            "expires_at": expires_at,
        }

    @staticmethod
    def extract_start_token(message_text: str | None) -> str | None:
        normalized = str(message_text or "").strip()
        if not normalized:
            return None

        command, separator, remainder = normalized.partition(" ")
        if not separator:
            return None

        command_name = command.split("@", 1)[0].strip().lower()
        if command_name != "/start":
            return None

        token = remainder.strip()
        return token or None

    async def _resolve_employee_from_start_token(self, token: str) -> dict[str, Any] | None:
        try:
            employee_id = self.decode_link_token(token)
        except TokenError:
            return None
        return await self._get_active_employee(employee_id)

    async def _send_confirmation(self, *, chat_id: str) -> None:
        await self.gateway.send_message(chat_id=chat_id, text="✅")

    async def _upsert_recipient_binding(
        self,
        *,
        employee: dict[str, Any],
        telegram_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
        telegram_first_name: str | None,
        telegram_last_name: str | None,
        telegram_language_code: str | None,
        chat_type: str,
    ) -> dict[str, Any]:
        now = _now_utc()
        existing = await self.repository.get_by_telegram_account(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
        )
        payload = {
            "organization_id": str(employee["organization_id"]),
            "user_id": str(employee["id"]),
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "telegram_username": telegram_username,
            "telegram_first_name": telegram_first_name,
            "telegram_last_name": telegram_last_name,
            "telegram_language_code": telegram_language_code,
            "chat_type": chat_type,
            "is_active": True,
            "last_started_at": now,
            "updated_at": now,
        }

        if existing is None:
            payload["id"] = str(uuid4())
            payload["created_at"] = now
            recipient = await self.repository.create(payload)
        else:
            recipient = await self.repository.update_by_id(str(existing["id"]), payload)

        await self.repository.deactivate_other_bindings_for_user(
            user_id=str(employee["id"]),
            keep_id=str(recipient["id"]),
            updated_at=now,
        )
        return recipient

    def _build_webhook_url(self) -> str:
        base = str(self.settings.public_api_base_url or "").strip().rstrip("/")
        if not base:
            raise RuntimeError(
                "APP_PUBLIC_API_BASE_URL is not configured — "
                "cannot build Telegram webhook URL"
            )
        return f"{base}/api/v1/system/telegram/webhook"

    async def register_webhook(self) -> dict[str, Any]:
        self._ensure_webhook_configured()
        webhook_url = self._build_webhook_url()
        api_base = str(self.settings.telegram_api_base_url or "https://api.telegram.org").strip().rstrip("/")
        endpoint = f"{api_base}/bot{self._bot_token}/setWebhook"
        payload = {
            "url": webhook_url,
            "secret_token": self._webhook_secret,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, json=payload)
        body = response.json()
        ok = bool(body.get("ok"))
        description = str(body.get("description") or "")
        if ok:
            logger.info("Telegram webhook registered: %s", webhook_url)
        else:
            logger.error("Telegram setWebhook failed: %s", description)
        return {"ok": ok, "description": description, "webhook_url": webhook_url}

    async def delete_webhook(self) -> dict[str, Any]:
        self._ensure_bot_configured()
        api_base = str(self.settings.telegram_api_base_url or "https://api.telegram.org").strip().rstrip("/")
        endpoint = f"{api_base}/bot{self._bot_token}/deleteWebhook"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, json={"drop_pending_updates": False})
        body = response.json()
        ok = bool(body.get("ok"))
        description = str(body.get("description") or "")
        if ok:
            logger.info("Telegram webhook deleted")
        else:
            logger.error("Telegram deleteWebhook failed: %s", description)
        return {"ok": ok, "description": description}

    async def get_webhook_info(self) -> dict[str, Any]:
        self._ensure_bot_configured()
        api_base = str(self.settings.telegram_api_base_url or "https://api.telegram.org").strip().rstrip("/")
        endpoint = f"{api_base}/bot{self._bot_token}/getWebhookInfo"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(endpoint)
        body = response.json()
        result = body.get("result", {})
        return {
            "ok": bool(body.get("ok")),
            "url": result.get("url", ""),
            "has_custom_certificate": result.get("has_custom_certificate", False),
            "pending_update_count": result.get("pending_update_count", 0),
            "last_error_date": result.get("last_error_date"),
            "last_error_message": result.get("last_error_message"),
        }

    async def process_webhook_update(
        self,
        *,
        payload: dict[str, Any],
        secret_token: str | None,
    ) -> None:
        self._ensure_webhook_configured()
        if str(secret_token or "").strip() != self._webhook_secret:
            raise PermissionError("Invalid Telegram webhook secret")

        update = Update.model_validate(payload)
        message = getattr(update, "message", None)
        if message is None or getattr(message, "chat", None) is None:
            return

        token = self.extract_start_token(getattr(message, "text", None))
        if not token:
            return

        employee = await self._resolve_employee_from_start_token(token)
        if employee is None:
            return

        from_user = getattr(message, "from_user", None)
        chat = message.chat
        await self._upsert_recipient_binding(
            employee=employee,
            telegram_user_id=str(getattr(from_user, "id", "") or getattr(chat, "id")),
            telegram_chat_id=str(getattr(chat, "id")),
            telegram_username=str(getattr(from_user, "username", "") or "").strip() or None,
            telegram_first_name=str(getattr(from_user, "first_name", "") or "").strip() or None,
            telegram_last_name=str(getattr(from_user, "last_name", "") or "").strip() or None,
            telegram_language_code=str(getattr(from_user, "language_code", "") or "").strip() or None,
            chat_type=str(getattr(chat, "type", "private") or "private").strip() or "private",
        )
        await self._send_confirmation(chat_id=str(getattr(chat, "id")))


__all__ = ["TELEGRAM_LINK_TOKEN_TYPE", "TelegramBotService"]
