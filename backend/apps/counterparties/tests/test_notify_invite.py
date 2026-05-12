"""
Тесты эндпоинтов уведомления контрагентов:
  POST /api/counterparties/<id>/notify-debt/
  POST /api/counterparties/<id>/invite-tg/
+ объединённый /api/notifications/.

SMS-отправку и TG send_message мокаем — провайдеров не дёргаем.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounting.models import GLAccount, GLSubaccount
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.otp.models import SmsMessage
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.tgbot.models import TgLink, TgLinkToken, TgMessage
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def admin_user(org):
    u = User.objects.create(email="cp-admin@y.local", full_name="A", is_staff=True)
    u.set_password("x")
    u.save()
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    core = Module.objects.get(code="core")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=core, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


@pytest.fixture
def counterparty(org):
    from apps.sales.services.opening_balance import (
        sync_opening_balance_for_counterparty,
    )
    cp = Counterparty.objects.create(
        organization=org, code="BUYER-1",
        kind=Counterparty.Kind.BUYER,
        name="Иванов Иван",
        phone="+998901234567",
        opening_debt_uzs=Decimal("1000000"),
    )
    # ViewSet делает это в perform_create. В тесте имитируем.
    sync_opening_balance_for_counterparty(cp)
    return cp


@pytest.fixture
def stub_send_sms(monkeypatch):
    """Глушим реальную отправку, но фиксируем что было послано."""
    captured = []

    def fake(*, phone, message, source=None, purpose="", created_by=None):
        sms = SmsMessage.objects.create(
            phone=phone, message=message,
            source=source or SmsMessage.Source.NOTIFY,
            purpose=purpose,
            status=SmsMessage.Status.SENT,
            provider_message_id="stub-%d" % (len(captured) + 1),
            created_by=created_by,
        )
        captured.append({"phone": phone, "message": message, "purpose": purpose})
        return sms

    import apps.counterparties.services.notify as notify_mod
    monkeypatch.setattr(notify_mod, "send_sms", fake)
    return captured


@pytest.fixture
def stub_tg_send(monkeypatch):
    """tg_send_message всегда успешный."""
    captured = []

    def fake(chat_id, text, parse_mode="HTML", reply_markup=None):
        captured.append({"chat_id": chat_id, "text": text})
        return True

    import apps.counterparties.services.notify as notify_mod
    monkeypatch.setattr(notify_mod, "tg_send_message", fake)
    return captured


# ── notify-debt: SMS ─────────────────────────────────────────────────────────

def test_notify_debt_sms_ok(client, counterparty, stub_send_sms):
    r = client.post(
        f"/api/counterparties/{counterparty.id}/notify-debt/",
        {"channels": ["sms"]}, format="json",
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["any_ok"] is True, body
    assert body["results"][0]["channel"] == "sms"
    assert body["results"][0]["ok"] is True
    assert len(stub_send_sms) == 1
    # Текст содержит имя и сумму
    assert "Иванов" in stub_send_sms[0]["message"]
    assert "1 000 000" in stub_send_sms[0]["message"]


def test_notify_debt_sms_no_phone(client, org, stub_send_sms):
    from apps.sales.services.opening_balance import (
        sync_opening_balance_for_counterparty,
    )
    cp = Counterparty.objects.create(
        organization=org, code="BUYER-2",
        kind=Counterparty.Kind.BUYER, name="Без телефона",
        phone="", opening_debt_uzs=Decimal("500000"),
    )
    sync_opening_balance_for_counterparty(cp)
    r = client.post(
        f"/api/counterparties/{cp.id}/notify-debt/",
        {"channels": ["sms"]}, format="json",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["any_ok"] is False
    assert "телефон" in body["results"][0]["detail"].lower()
    assert len(stub_send_sms) == 0


def test_notify_debt_zero_skipped(client, org, stub_send_sms):
    cp = Counterparty.objects.create(
        organization=org, code="BUYER-3",
        kind=Counterparty.Kind.BUYER, name="Без долга",
        phone="+998901234567",
        opening_debt_uzs=Decimal("0"),
    )
    r = client.post(
        f"/api/counterparties/{cp.id}/notify-debt/",
        {"channels": ["sms"]}, format="json",
    )
    assert r.status_code == 200
    assert r.json()["any_ok"] is False
    assert "задолженности" in r.json()["results"][0]["detail"].lower()


def test_notify_debt_bad_channels(client, counterparty):
    r = client.post(
        f"/api/counterparties/{counterparty.id}/notify-debt/",
        {"channels": ["email"]}, format="json",
    )
    assert r.status_code == 400


# ── notify-debt: TG ──────────────────────────────────────────────────────────

def test_notify_debt_tg_no_link(client, counterparty, stub_tg_send):
    r = client.post(
        f"/api/counterparties/{counterparty.id}/notify-debt/",
        {"channels": ["tg"]}, format="json",
    )
    body = r.json()
    assert body["any_ok"] is False
    assert "Пригласите" in body["results"][0]["detail"] or \
           "приглашение" in body["results"][0]["detail"].lower()


def test_notify_debt_tg_ok(client, org, counterparty, stub_tg_send):
    TgLink.objects.create(
        organization=org, counterparty=counterparty,
        chat_id=12345, is_active=True,
    )
    r = client.post(
        f"/api/counterparties/{counterparty.id}/notify-debt/",
        {"channels": ["tg"]}, format="json",
    )
    body = r.json()
    assert body["any_ok"] is True
    assert len(stub_tg_send) == 1
    assert stub_tg_send[0]["chat_id"] == 12345
    assert TgMessage.objects.count() == 1
    assert TgMessage.objects.first().status == TgMessage.Status.SENT


# ── invite-tg ────────────────────────────────────────────────────────────────

def test_invite_tg_ok(client, counterparty, stub_send_sms, settings):
    settings.TELEGRAM_BOT_USERNAME = "yembro_bot"
    r = client.post(
        f"/api/counterparties/{counterparty.id}/invite-tg/", {}, format="json",
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["ok"] is True
    assert TgLinkToken.objects.filter(counterparty=counterparty).count() == 1
    assert len(stub_send_sms) == 1
    msg = stub_send_sms[0]["message"]
    assert "t.me/yembro_bot?start=" in msg
    assert "30 daqiqa" in msg


def test_invite_tg_no_phone(client, org, stub_send_sms, settings):
    settings.TELEGRAM_BOT_USERNAME = "yembro_bot"
    cp = Counterparty.objects.create(
        organization=org, code="BUYER-NP",
        kind=Counterparty.Kind.BUYER, name="NoPhone",
        phone="",
    )
    r = client.post(
        f"/api/counterparties/{cp.id}/invite-tg/", {}, format="json",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "телефон" in body["detail"].lower()


# ── notifications listing ────────────────────────────────────────────────────

def test_notifications_list_merges_sms_and_tg(client, org, counterparty):
    SmsMessage.objects.create(
        phone="998901234567", message="msg1",
        source=SmsMessage.Source.NOTIFY, status=SmsMessage.Status.SENT,
    )
    TgMessage.objects.create(
        organization=org, chat_id=12345, counterparty=counterparty,
        text="tg1", source=TgMessage.Source.DEBT_REMINDER,
        status=TgMessage.Status.SENT,
    )
    r = client.get("/api/notifications/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["count"] == 2
    channels = {x["channel"] for x in body["results"]}
    assert channels == {"sms", "tg"}


def test_notifications_filter_by_channel(client, org, counterparty):
    SmsMessage.objects.create(
        phone="998901234567", message="sms",
        source=SmsMessage.Source.NOTIFY, status=SmsMessage.Status.SENT,
    )
    TgMessage.objects.create(
        organization=org, chat_id=12345,
        text="tg", source=TgMessage.Source.SYSTEM,
        status=TgMessage.Status.SENT,
    )
    r = client.get("/api/notifications/?channel=tg")
    assert r.json()["count"] == 1
    assert r.json()["results"][0]["channel"] == "tg"


def test_notifications_filter_by_counterparty(client, org, counterparty):
    # Сообщения по этому контрагенту через phone-match для SMS, через FK для TG.
    SmsMessage.objects.create(
        phone="998901234567", message="match",
        source=SmsMessage.Source.NOTIFY, status=SmsMessage.Status.SENT,
    )
    SmsMessage.objects.create(
        phone="998990000000", message="other",
        source=SmsMessage.Source.NOTIFY, status=SmsMessage.Status.SENT,
    )
    TgMessage.objects.create(
        organization=org, chat_id=11, counterparty=counterparty,
        text="tg-match", source=TgMessage.Source.DEBT_REMINDER,
        status=TgMessage.Status.SENT,
    )
    r = client.get(f"/api/notifications/?counterparty={counterparty.id}")
    body = r.json()
    assert body["count"] == 2
    texts = [x.get("text") for x in body["results"]]
    assert "match" in texts and "tg-match" in texts
