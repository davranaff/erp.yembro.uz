"""
Юнит-тесты Eskiz-клиента. Реальные HTTP-запросы перехватываются
через responses, чтобы не ходить наружу.
"""
import pytest
import responses
from django.core.cache import cache

from apps.otp.services.eskiz import (
    EskizAuthError,
    EskizClient,
    EskizSendError,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return EskizClient(
        email="bot@example.com",
        password="pw",
        sender="YEMBRO",
        base_url="https://notify.eskiz.uz",
        timeout=1.0,
    )


@responses.activate
def test_login_then_send_ok(client):
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/auth/login",
        json={"data": {"token": "tok-1"}, "message": "token_generated"},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/message/sms/send",
        json={"id": "msg-42", "status": "waiting"},
        status=200,
    )

    message_id = client.send_sms("998901234567", "Bu Eskiz dan test")
    assert message_id == "msg-42"
    # Токен закеширован — повторный вызов не дёргает /login.
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/message/sms/send",
        json={"id": "msg-43", "status": "waiting"},
        status=200,
    )
    assert client.send_sms("998901234567", "Bu Eskiz dan test") == "msg-43"
    login_calls = [
        c for c in responses.calls if c.request.url.endswith("/api/auth/login")
    ]
    assert len(login_calls) == 1


@responses.activate
def test_login_failure_raises(client):
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/auth/login",
        json={"message": "Invalid credentials"},
        status=401,
    )
    with pytest.raises(EskizAuthError):
        client.send_sms("998901234567", "Bu Eskiz dan test")


@responses.activate
def test_401_on_send_triggers_relogin(client):
    # Прогрев кеша устаревшим токеном.
    cache.set("otp:eskiz:token", "stale", 60)

    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/message/sms/send",
        json={"message": "Unauthenticated"},
        status=401,
    )
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/auth/login",
        json={"data": {"token": "fresh"}},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/message/sms/send",
        json={"id": "msg-99", "status": "waiting"},
        status=200,
    )

    assert client.send_sms("998901234567", "Bu Eskiz dan test") == "msg-99"


@responses.activate
def test_send_failure_raises(client):
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/auth/login",
        json={"data": {"token": "tok-1"}},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://notify.eskiz.uz/api/message/sms/send",
        json={"message": "balance"},
        status=400,
    )
    with pytest.raises(EskizSendError):
        client.send_sms("998901234567", "Bu Eskiz dan test")
