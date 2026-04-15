from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.repositories.system import TelegramRecipientRepository
from app.services.client_notifications import TelegramSendResult
from app.services.telegram_alerts import (
    build_operational_alert_event,
    deliver_operational_admin_alert,
)
from app.services.telegram_bot import TELEGRAM_LINK_TOKEN_TYPE, TelegramBotService
from app.utils.auth_tokens import TokenError, create_signed_token


TEST_EMPLOYEE_ID = "70111111-1111-1111-1111-111111111111"
ADMIN_EMPLOYEE_ID = "70444444-4444-4444-4444-444444444444"
OTHER_ORG_ADMIN_EMPLOYEE_ID = "70333333-3333-3333-3333-333333333333"
NON_ADMIN_EMPLOYEE_ID = "70555555-5555-5555-5555-555555555555"
ORG_ID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_telegram_link_token_roundtrip_and_expiry(sqlite_db) -> None:
    service = TelegramBotService(sqlite_db)

    token, expires_at = service.create_link_token(employee_id=TEST_EMPLOYEE_ID)
    assert expires_at > datetime.now(timezone.utc)
    assert service.decode_link_token(token) == TEST_EMPLOYEE_ID

    expired_token, _ = create_signed_token(
        subject=TEST_EMPLOYEE_ID,
        token_type=TELEGRAM_LINK_TOKEN_TYPE,
        secret_key=service.settings.auth_secret_key,
        expires_in=timedelta(minutes=-1),
    )
    with pytest.raises(TokenError):
        service.decode_link_token(expired_token)


def test_operational_alert_event_filters_non_operational_actions_and_tables() -> None:
    event = build_operational_alert_event(
        action="create",
        entity_table="egg_production",
        entity_id="record-1",
        actor_username="EMP-ADM-00",
        before_data=None,
        after_data={
            "id": "record-1",
            "organization_id": ORG_ID,
            "department_id": "44444444-4444-4444-4444-444444444444",
            "batch_code": "EGG-LOT-01",
        },
    )
    assert event is not None
    assert event["entity_table"] == "egg_production"

    assert (
        build_operational_alert_event(
            action="update",
            entity_table="egg_production",
            entity_id="record-1",
            actor_username="EMP-ADM-00",
            before_data={"organization_id": ORG_ID},
            after_data={"organization_id": ORG_ID},
        )
        is None
    )
    assert (
        build_operational_alert_event(
            action="create",
            entity_table="expenses",
            entity_id="record-2",
            actor_username="EMP-ADM-00",
            before_data=None,
            after_data={"organization_id": ORG_ID},
        )
        is None
    )
    assert (
        build_operational_alert_event(
            action="create",
            entity_table="egg_monthly_analytics",
            entity_id="record-3",
            actor_username="EMP-ADM-00",
            before_data=None,
            after_data={"organization_id": ORG_ID},
        )
        is None
    )


@pytest.mark.asyncio
async def test_deliver_operational_admin_alert_filters_same_org_active_admins(
    sqlite_db,
    monkeypatch,
) -> None:
    repository = TelegramRecipientRepository(sqlite_db)
    now = datetime.now(timezone.utc)

    await repository.create(
        {
            "id": str(uuid4()),
            "organization_id": ORG_ID,
            "user_id": ADMIN_EMPLOYEE_ID,
            "telegram_user_id": "9001",
            "telegram_chat_id": "5001",
            "telegram_username": "org_admin",
            "telegram_first_name": "Bosh",
            "telegram_last_name": "Admin",
            "telegram_language_code": "ru",
            "chat_type": "private",
            "is_active": True,
            "last_started_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    await repository.create(
        {
            "id": str(uuid4()),
            "organization_id": ORG_ID,
            "user_id": NON_ADMIN_EMPLOYEE_ID,
            "telegram_user_id": "9002",
            "telegram_chat_id": "5002",
            "telegram_username": "warehouse_lead",
            "telegram_first_name": "Farhod",
            "telegram_last_name": "Rahimov",
            "telegram_language_code": "ru",
            "chat_type": "private",
            "is_active": True,
            "last_started_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    await repository.create(
        {
            "id": str(uuid4()),
            "organization_id": "22222222-2222-2222-2222-222222222222",
            "user_id": OTHER_ORG_ADMIN_EMPLOYEE_ID,
            "telegram_user_id": "9003",
            "telegram_chat_id": "5003",
            "telegram_username": "demo_admin",
            "telegram_first_name": "Demo",
            "telegram_last_name": "Admin",
            "telegram_language_code": "ru",
            "chat_type": "private",
            "is_active": True,
            "last_started_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )

    sent_messages: list[tuple[str, str]] = []

    async def fake_send_message(self, *, chat_id: str, text: str) -> TelegramSendResult:
        sent_messages.append((chat_id, text))
        return TelegramSendResult(ok=True, provider_message_id="42")

    monkeypatch.setenv("APP_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setattr(
        "app.services.client_notifications.TelegramNotificationGateway.send_message",
        fake_send_message,
    )

    result = await deliver_operational_admin_alert(
        sqlite_db,
        {
            "action": "create",
            "entity_table": "egg_production",
            "entity_id": "record-1",
            "organization_id": ORG_ID,
            "actor_username": "EMP-ADM-00",
            "changed_at": now.isoformat(),
            "after_data": {
                "id": "record-1",
                "organization_id": ORG_ID,
                "department_id": "44444444-4444-4444-4444-444444444444",
                "batch_code": "EGG-LOT-01",
            },
            "before_data": None,
        },
    )

    assert result["sent"] == 1
    assert [chat_id for chat_id, _ in sent_messages] == ["5001"]
    message = sent_messages[0][1]
    assert "🟢 Добавлена запись" in message
    assert "Организация: Zarafshon Parranda" in message
    assert "Ресурс: Производство" in message
    assert "Запись: EGG-LOT-01" in message
    assert "Пользователь: EMP-ADM-00" in message
