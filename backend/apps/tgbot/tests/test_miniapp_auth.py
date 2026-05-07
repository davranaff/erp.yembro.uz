"""
Тесты POST /api/tg/miniapp/auth/.

Покрываем критичные ветки:
  - валидный initData + user-линка → 200, linked=true, JWT-пара, MeSerializer
  - counterparty-only chat_id → linked=false (клиенты в Mini App не пускаются)
  - chat_id без линки вообще → linked=false
  - битый hash → 401
  - просроченный auth_date → 401
  - отсутствует/пустой init_data → 400
  - TELEGRAM_BOT_TOKEN не задан → 503
  - preferred_org берёт active_organization если задан
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.organizations.models import Organization, OrganizationMembership
from apps.tgbot.models import TgLink
from apps.users.models import User


pytestmark = pytest.mark.django_db


BOT_TOKEN = "TEST:test-bot-token"


def _build_init_data(
    *,
    user_id: int,
    auth_date: int | None = None,
    bot_token: str = BOT_TOKEN,
    extra: dict | None = None,
    bad_hash: bool = False,
) -> str:
    """
    Собирает корректный initData по схеме Telegram (HMAC_SHA256).

    Если bad_hash=True — подмешивает мусор в hash, чтобы протестировать
    отрицательный кейс без необходимости вручную ломать байты.
    """
    if auth_date is None:
        auth_date = int(time.time())
    payload = {
        "auth_date": str(auth_date),
        "query_id": "AAH-test-query-id",
        "user": json.dumps(
            {"id": user_id, "first_name": "Test", "username": "tester"},
            separators=(",", ":"),
        ),
    }
    if extra:
        payload.update(extra)

    data_check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256,
    ).digest()
    sig = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256,
    ).hexdigest()
    if bad_hash:
        sig = "0" * 64

    payload["hash"] = sig
    return urlencode(payload)


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def linked_user(org):
    """User с активной membership и TgLink."""
    u = User.objects.create(email="tg@y.local", full_name="TG User")
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    TgLink.objects.create(
        organization=org, user=u, chat_id=42424242, is_active=True,
    )
    return u


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_valid_init_data_with_user_link_returns_jwt(api, linked_user, org):
    init_data = _build_init_data(user_id=42424242)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["linked"] is True
    assert body["access"] and body["refresh"]
    assert body["user"]["email"] == linked_user.email
    assert body["user"]["memberships"][0]["organization"]["code"] == org.code
    assert body["preferred_org"]["code"] == org.code


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_counterparty_only_chat_id_returns_unlinked(api, org):
    """
    Если chat_id привязан только к Counterparty (нет user-линки) — Mini App
    должен ответить linked=false. Это ключевая защита: клиенты в админ-вебвью
    не попадают.
    """
    cp = Counterparty.objects.create(
        organization=org, code="CP1", kind="buyer", name="Test Buyer",
    )
    TgLink.objects.create(
        organization=org, counterparty=cp, chat_id=99001, is_active=True,
    )

    init_data = _build_init_data(user_id=99001)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"linked": False}


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_inactive_user_link_treated_as_unlinked(api, org, linked_user):
    """is_active=False → не пускаем."""
    TgLink.objects.filter(user=linked_user).update(is_active=False)

    init_data = _build_init_data(user_id=42424242)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"linked": False}


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_no_link_at_all_returns_unlinked(api):
    """chat_id не известен системе → linked=false."""
    init_data = _build_init_data(user_id=77777777)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"linked": False}


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_bad_signature_returns_401(api, linked_user):
    init_data = _build_init_data(user_id=42424242, bad_hash=True)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 401, resp.content


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_signature_with_wrong_token_returns_401(api, linked_user):
    """initData подписан другим токеном — наш бэк должен отвергнуть."""
    init_data = _build_init_data(user_id=42424242, bot_token="OTHER:wrong-token")
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 401, resp.content


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_expired_auth_date_returns_401(api, linked_user):
    """auth_date старше 1 часа → replay-protection срабатывает."""
    stale = int(time.time()) - 3600 - 60  # на минуту просрочен
    init_data = _build_init_data(user_id=42424242, auth_date=stale)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 401, resp.content


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_missing_init_data_returns_400(api):
    resp = api.post("/api/tg/miniapp/auth/", {}, format="json")
    assert resp.status_code == 400, resp.content


@override_settings(TELEGRAM_BOT_TOKEN="")
def test_no_bot_token_returns_503(api, linked_user):
    init_data = _build_init_data(user_id=42424242)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 503, resp.content


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
def test_preferred_org_uses_active_organization_when_set(api, linked_user, org):
    """
    Юзер раньше переключал /org в боте → active_organization задан.
    preferred_org должен браться из него, а не из org привязки.
    """
    other = Organization.objects.create(
        code="OTHER",
        name="Other Org",
        accounting_currency=org.accounting_currency,
    )
    OrganizationMembership.objects.create(
        user=linked_user, organization=other, is_active=True,
    )
    TgLink.objects.filter(user=linked_user).update(active_organization=other)

    init_data = _build_init_data(user_id=42424242)
    resp = api.post(
        "/api/tg/miniapp/auth/", {"init_data": init_data}, format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["preferred_org"]["code"] == "OTHER"
