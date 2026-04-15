from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.telegram_bot import TelegramBotService
from tests.helpers import build_create_payload, build_update_payload, extract_data, make_auth_headers


TEST_EMPLOYEE_ID = "70111111-1111-1111-1111-111111111111"
ORG_ID = "11111111-1111-1111-1111-111111111111"


def _telegram_message_payload(*, chat_id: int, user_id: int, text: str) -> dict[str, object]:
    return {
        "update_id": user_id,
        "message": {
            "message_id": 10,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": f"user{user_id}",
                "language_code": "ru",
            },
            "text": text,
        },
    }


@pytest.mark.asyncio
async def test_create_telegram_deep_link_endpoint_returns_bot_link(api_client, sqlite_db, monkeypatch) -> None:
    async def fake_get_bot_username(self) -> str:
        return "yembro_test_bot"

    monkeypatch.setenv("APP_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setattr(TelegramBotService, "get_bot_username", fake_get_bot_username)

    response = await api_client.post(
        "/api/v1/system/telegram/deep-link",
        headers={"X-Employee-Id": TEST_EMPLOYEE_ID},
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    assert str(payload["url"]).startswith("https://t.me/yembro_test_bot?start=")
    token = str(payload["url"]).split("start=", 1)[1]
    service = TelegramBotService(sqlite_db)
    assert service.decode_link_token(token) == TEST_EMPLOYEE_ID
    assert token
    assert payload["expires_at"]


@pytest.mark.asyncio
async def test_telegram_webhook_requires_secret_header(api_client, monkeypatch) -> None:
    monkeypatch.setenv("APP_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("APP_TELEGRAM_WEBHOOK_SECRET", "webhook-secret")

    response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5001, user_id=9001, text="/start bad-token"),
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_telegram_webhook_valid_start_upserts_recipient_and_sends_confirmation(
    api_client,
    sqlite_db,
    monkeypatch,
) -> None:
    confirmations: list[str] = []

    async def fake_send_confirmation(self, *, chat_id: str) -> None:
        confirmations.append(chat_id)

    monkeypatch.setenv("APP_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("APP_TELEGRAM_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(TelegramBotService, "_send_confirmation", fake_send_confirmation)

    service = TelegramBotService(sqlite_db)
    token, _ = service.create_link_token(employee_id=TEST_EMPLOYEE_ID)

    response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5001, user_id=9001, text=f"/start {token}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert response.status_code == 200, response.text

    rows = await sqlite_db.fetch(
        """
        SELECT *
        FROM telegram_recipients
        ORDER BY created_at, id
        """
    )
    assert len(rows) == 1
    assert str(rows[0]["organization_id"]) == ORG_ID
    assert str(rows[0]["user_id"]) == TEST_EMPLOYEE_ID
    assert str(rows[0]["telegram_user_id"]) == "9001"
    assert str(rows[0]["telegram_chat_id"]) == "5001"
    assert confirmations == ["5001"]


@pytest.mark.asyncio
async def test_telegram_webhook_ignores_invalid_or_non_start_messages(
    api_client,
    sqlite_db,
    monkeypatch,
) -> None:
    confirmations: list[str] = []

    async def fake_send_confirmation(self, *, chat_id: str) -> None:
        confirmations.append(chat_id)

    monkeypatch.setenv("APP_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("APP_TELEGRAM_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(TelegramBotService, "_send_confirmation", fake_send_confirmation)

    response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5001, user_id=9001, text="/start invalid-token"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert response.status_code == 200, response.text

    service = TelegramBotService(sqlite_db)
    unknown_token, _ = service.create_link_token(employee_id=str(uuid4()))
    response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5002, user_id=9002, text=f"/start {unknown_token}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert response.status_code == 200, response.text

    response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5003, user_id=9003, text="hello"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert response.status_code == 200, response.text

    rows = await sqlite_db.fetch("SELECT * FROM telegram_recipients")
    assert rows == []
    assert confirmations == []


@pytest.mark.asyncio
async def test_telegram_webhook_re_registration_keeps_single_active_binding_for_user(
    api_client,
    sqlite_db,
    monkeypatch,
) -> None:
    confirmations: list[str] = []

    async def fake_send_confirmation(self, *, chat_id: str) -> None:
        confirmations.append(chat_id)

    monkeypatch.setenv("APP_TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("APP_TELEGRAM_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(TelegramBotService, "_send_confirmation", fake_send_confirmation)

    service = TelegramBotService(sqlite_db)
    token, _ = service.create_link_token(employee_id=TEST_EMPLOYEE_ID)

    first_response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5001, user_id=9001, text=f"/start {token}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert first_response.status_code == 200, first_response.text

    second_response = await api_client.post(
        "/api/v1/system/telegram/webhook",
        json=_telegram_message_payload(chat_id=5002, user_id=9002, text=f"/start {token}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert second_response.status_code == 200, second_response.text

    rows = await sqlite_db.fetch(
        """
        SELECT user_id, telegram_user_id, telegram_chat_id, is_active
        FROM telegram_recipients
        WHERE user_id = $1
        ORDER BY created_at, id
        """,
        TEST_EMPLOYEE_ID,
    )
    assert len(rows) == 2
    assert [bool(row["is_active"]) for row in rows] == [False, True]
    assert str(rows[-1]["telegram_user_id"]) == "9002"
    assert str(rows[-1]["telegram_chat_id"]) == "5002"
    assert confirmations == ["5001", "5002"]


@pytest.mark.asyncio
async def test_operational_create_delete_enqueue_and_update_does_not(
    api_client,
    monkeypatch,
) -> None:
    queued_calls: list[dict[str, object]] = []

    async def fake_enqueue_operational_admin_alert(**kwargs):
        queued_calls.append(kwargs)
        return True

    monkeypatch.setattr("app.services.base.enqueue_operational_admin_alert", fake_enqueue_operational_admin_alert)

    create_payload = await build_create_payload(api_client, "/api/v1/egg/production")
    create_response = await api_client.post(
        "/api/v1/egg/production",
        json=create_payload,
        headers=make_auth_headers("egg_production"),
    )
    assert create_response.status_code == 201, create_response.text
    created_record = extract_data(create_response)

    assert len(queued_calls) == 1
    assert queued_calls[0]["action"] == "create"
    assert queued_calls[0]["entity_table"] == "egg_production"

    queued_calls.clear()
    update_response = await api_client.put(
        f"/api/v1/egg/production/{created_record['id']}",
        json=build_update_payload(created_record),
        headers=make_auth_headers("egg_production"),
    )
    assert update_response.status_code == 200, update_response.text
    assert queued_calls == []

    delete_response = await api_client.delete(
        f"/api/v1/egg/production/{created_record['id']}",
        headers=make_auth_headers("egg_production"),
    )
    assert delete_response.status_code == 200, delete_response.text
    assert len(queued_calls) == 1
    assert queued_calls[0]["action"] == "delete"
    assert queued_calls[0]["entity_table"] == "egg_production"
