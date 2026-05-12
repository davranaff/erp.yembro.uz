"""
Сквозные тесты OTP-флоу через HTTP. SMS-отправку мокаем, чтобы не
ходить в Eskiz из тестов.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.otp.models import OtpCode
from apps.otp.services import otp as otp_service


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _reset_throttles():
    # DRF AnonRateThrottle хранит счётчики в default cache — чистим между
    # тестами, иначе предыдущие запросы повлияют на следующие кейсы.
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def stub_send(monkeypatch):
    """Перехват SMS — фиксируем последний код, не дёргая внешнего провайдера."""
    captured = {"code": None, "phone": None, "message": None}

    real_generate = otp_service._generate_code

    def fake_generate(length: int) -> str:
        code = real_generate(length)
        captured["code"] = code
        return code

    class _StubSms:
        provider_message_id = "test-stub-id"

    def fake_send(*, phone, message, source=None, purpose="", created_by=None):
        captured["phone"] = phone
        captured["message"] = message
        return _StubSms()

    monkeypatch.setattr(otp_service, "_generate_code", fake_generate)
    monkeypatch.setattr(otp_service, "send_sms", fake_send)
    return captured


def test_request_then_verify_ok(stub_send):
    api = APIClient()
    r = api.post(
        "/api/otp/request/",
        {"phone": "+998901234567", "purpose": "login"},
        format="json",
    )
    assert r.status_code == 200, r.content
    assert r.json()["phone"] == "998901234567"
    assert OtpCode.objects.filter(phone="998901234567", purpose="login").count() == 1
    assert stub_send["code"] is not None and len(stub_send["code"]) == 6

    r = api.post(
        "/api/otp/verify/",
        {"phone": "998901234567", "purpose": "login", "code": stub_send["code"]},
        format="json",
    )
    assert r.status_code == 200, r.content
    otp = OtpCode.objects.get(phone="998901234567", purpose="login")
    assert otp.used_at is not None


def test_verify_wrong_code_increments_attempts(stub_send, settings):
    settings.OTP_MAX_ATTEMPTS = 3
    api = APIClient()
    api.post(
        "/api/otp/request/",
        {"phone": "998901234567", "purpose": "login"},
        format="json",
    )
    for _ in range(3):
        r = api.post(
            "/api/otp/verify/",
            {"phone": "998901234567", "purpose": "login", "code": "000000"},
            format="json",
        )
        assert r.status_code in (400, 429)

    # После исчерпания попыток код помечается как использованный.
    otp = OtpCode.objects.get(phone="998901234567", purpose="login")
    assert otp.used_at is not None

    # Повтор того же кода теперь невозможен — кода нет.
    r = api.post(
        "/api/otp/verify/",
        {"phone": "998901234567", "purpose": "login", "code": stub_send["code"]},
        format="json",
    )
    assert r.status_code == 400
    assert r.json()["code"] == "otp_not_found"


def test_resend_blocked_within_cooldown(stub_send, settings):
    settings.OTP_RESEND_INTERVAL_SECONDS = 60
    api = APIClient()
    r1 = api.post(
        "/api/otp/request/",
        {"phone": "998901234567", "purpose": "login"},
        format="json",
    )
    assert r1.status_code == 200
    r2 = api.post(
        "/api/otp/request/",
        {"phone": "998901234567", "purpose": "login"},
        format="json",
    )
    assert r2.status_code == 429
    assert r2.json()["code"] == "resend_too_soon"
    assert "retry_after" in r2.json()


def test_resend_allowed_after_cooldown(stub_send, settings):
    settings.OTP_RESEND_INTERVAL_SECONDS = 60
    api = APIClient()
    api.post(
        "/api/otp/request/",
        {"phone": "998901234567", "purpose": "login"},
        format="json",
    )
    # Отодвигаем созданный код во времени, чтобы перестал блокировать.
    OtpCode.objects.filter(phone="998901234567").update(
        created_at=timezone.now() - timedelta(seconds=120),
    )
    r = api.post(
        "/api/otp/request/",
        {"phone": "998901234567", "purpose": "login"},
        format="json",
    )
    assert r.status_code == 200, r.content
    # Старый код должен быть погашен, а новый — единственный валидный.
    fresh = OtpCode.objects.filter(
        phone="998901234567", purpose="login", used_at__isnull=True,
    )
    assert fresh.count() == 1


def test_expired_code_rejected(stub_send):
    api = APIClient()
    api.post(
        "/api/otp/request/",
        {"phone": "998901234567", "purpose": "login"},
        format="json",
    )
    OtpCode.objects.filter(phone="998901234567").update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    r = api.post(
        "/api/otp/verify/",
        {"phone": "998901234567", "purpose": "login", "code": stub_send["code"]},
        format="json",
    )
    assert r.status_code == 400
    assert r.json()["code"] == "otp_expired"


def test_invalid_phone_returns_400(stub_send):
    api = APIClient()
    r = api.post(
        "/api/otp/request/",
        {"phone": "12345", "purpose": "login"},
        format="json",
    )
    assert r.status_code == 400
    assert "phone" in r.json()
