"""
Тесты SMS-API: send / list / balance / callback.
"""
from decimal import Decimal

import pytest
import responses
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.otp.models import SmsMessage
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_user():
    u = User.objects.create(email="admin@y.local", full_name="A", is_staff=True)
    u.set_password("x")
    u.save()
    return u


@pytest.fixture
def regular_user():
    u = User.objects.create(email="user@y.local", full_name="U")
    u.set_password("x")
    u.save()
    return u


# ── send ─────────────────────────────────────────────────────────────────


@responses.activate
def test_sms_send_admin_ok(admin_user, settings):
    settings.OTP_DEV_PRINT = False
    settings.ESKIZ_EMAIL = "bot@x"
    settings.ESKIZ_PASSWORD = "pw"
    responses.add(
        responses.POST, "https://notify.eskiz.uz/api/auth/login",
        json={"data": {"token": "t"}}, status=200,
    )
    responses.add(
        responses.POST, "https://notify.eskiz.uz/api/message/sms/send",
        json={"id": "msg-1", "status": "waiting"}, status=200,
    )
    api = APIClient()
    api.force_authenticate(user=admin_user)
    r = api.post("/api/sms/send/", {
        "phone": "+998901234567",
        "message": "Привет",
        "purpose": "test",
    }, format="json")
    assert r.status_code == 201, r.content
    assert r.json()["phone"] == "998901234567"
    assert r.json()["status"] == "sent"
    assert r.json()["provider_message_id"] == "msg-1"
    sms = SmsMessage.objects.get()
    assert sms.source == "manual"
    assert sms.created_by == admin_user


def test_sms_send_regular_user_forbidden(regular_user):
    api = APIClient()
    api.force_authenticate(user=regular_user)
    r = api.post("/api/sms/send/", {
        "phone": "+998901234567",
        "message": "X",
    }, format="json")
    assert r.status_code == 403


def test_sms_send_invalid_phone(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    r = api.post("/api/sms/send/", {
        "phone": "abc",
        "message": "X",
    }, format="json")
    assert r.status_code == 400


# ── list ─────────────────────────────────────────────────────────────────


def test_sms_list_admin_filters(admin_user):
    SmsMessage.objects.create(
        phone="998901234567", message="A",
        source=SmsMessage.Source.OTP, status=SmsMessage.Status.DELIVERED,
    )
    SmsMessage.objects.create(
        phone="998905555555", message="B",
        source=SmsMessage.Source.MANUAL, status=SmsMessage.Status.SENT,
    )
    api = APIClient()
    api.force_authenticate(user=admin_user)
    # все
    r = api.get("/api/sms/messages/")
    assert r.status_code == 200
    assert r.json()["count"] == 2
    # phone
    r = api.get("/api/sms/messages/?phone=901")
    assert r.json()["count"] == 1
    # status
    r = api.get("/api/sms/messages/?status=sent")
    assert r.json()["count"] == 1
    # source
    r = api.get("/api/sms/messages/?source=otp")
    assert r.json()["count"] == 1


# ── balance ───────────────────────────────────────────────────────────────


@responses.activate
def test_sms_balance_ok(admin_user, settings):
    settings.OTP_DEV_PRINT = False
    settings.ESKIZ_EMAIL = "bot@x"
    settings.ESKIZ_PASSWORD = "pw"
    responses.add(
        responses.POST, "https://notify.eskiz.uz/api/auth/login",
        json={"data": {"token": "t"}}, status=200,
    )
    responses.add(
        responses.GET, "https://notify.eskiz.uz/api/user/get-limit",
        json={"data": {"balance": 4700}, "status": "success"}, status=200,
    )
    api = APIClient()
    api.force_authenticate(user=admin_user)
    r = api.get("/api/sms/balance/")
    assert r.status_code == 200, r.content
    assert r.json()["balance"] == 4700
    assert r.json()["cached"] is False
    # повтор должен быть из кеша
    r2 = api.get("/api/sms/balance/")
    assert r2.json()["cached"] is True


def test_sms_balance_not_configured(admin_user, settings):
    settings.OTP_DEV_PRINT = False
    settings.ESKIZ_EMAIL = ""
    settings.ESKIZ_PASSWORD = ""
    api = APIClient()
    api.force_authenticate(user=admin_user)
    r = api.get("/api/sms/balance/")
    assert r.status_code == 503
    assert r.json()["code"] == "sms_not_configured"


# ── callback ──────────────────────────────────────────────────────────────


def test_sms_callback_delivers(settings):
    settings.ESKIZ_CALLBACK_SECRET = "sec123"
    sms = SmsMessage.objects.create(
        phone="998901234567", message="X",
        provider_message_id="abc-1",
        status=SmsMessage.Status.SENT,
    )
    api = APIClient()
    r = api.post("/api/sms/callback/sec123/", {
        "message_id": "abc-1",
        "status": "DELIVRD",
        "phone_number": "998901234567",
    }, format="json")
    assert r.status_code == 200, r.content
    sms.refresh_from_db()
    assert sms.status == SmsMessage.Status.DELIVERED
    assert sms.delivered_at is not None


def test_sms_callback_bad_secret(settings):
    settings.ESKIZ_CALLBACK_SECRET = "sec123"
    api = APIClient()
    r = api.post("/api/sms/callback/wrong/", {
        "message_id": "abc-1", "status": "DELIVRD",
    }, format="json")
    assert r.status_code == 403


def test_sms_callback_unknown_message_id_returns_200(settings):
    """Чтобы Eskiz не ретраил бесконечно — на unknown id возвращаем 200."""
    settings.ESKIZ_CALLBACK_SECRET = "sec"
    api = APIClient()
    r = api.post("/api/sms/callback/sec/", {
        "message_id": "ghost", "status": "DELIVRD",
    }, format="json")
    assert r.status_code == 200
    assert r.json()["matched"] is False


def test_sms_callback_failure_status(settings):
    settings.ESKIZ_CALLBACK_SECRET = "sec"
    sms = SmsMessage.objects.create(
        phone="998901234567", message="X",
        provider_message_id="abc-2",
        status=SmsMessage.Status.SENT,
    )
    api = APIClient()
    r = api.post("/api/sms/callback/sec/", {
        "message_id": "abc-2", "status": "EXPIRED",
    }, format="json")
    assert r.status_code == 200
    sms.refresh_from_db()
    assert sms.status == SmsMessage.Status.FAILED
    assert "EXPIRED" in sms.error_msg
