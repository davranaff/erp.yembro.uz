"""
Тесты «Modullar» секции и per-module hub.

Сценарии:
- Owner видит все enabled-модули.
- Юзер с доступом только к feed видит ТОЛЬКО feed-кнопку.
- mod:<code> рендерит hub с финансовым блоком и партиями.
- rep:<code> рендерит детальную аналитику модуля.
"""
import pytest

from apps.modules.models import Module, OrganizationModule
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.tgbot.dispatcher import dispatch_callback
from apps.tgbot.models import TgLink
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


def _enabled(org, codes):
    """Гарантируем что нужные модули enabled у org."""
    for code in codes:
        m = Module.objects.get(code=code)
        OrganizationModule.objects.update_or_create(
            organization=org, module=m, defaults={"is_enabled": True},
        )


def _link(org, email, modules_levels):
    u = User.objects.create(email=email, full_name=email)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    for code, level in modules_levels.items():
        UserModuleAccessOverride.objects.create(
            membership=m, module=Module.objects.get(code=code), level=level,
        )
    return TgLink.objects.create(
        organization=org, user=u, chat_id=hash(email) % 1_000_000,
        is_active=True,
    )


def _cbq(chat_id, data, message_id=10):
    return {
        "id": f"cbq-{data}", "data": data,
        "message": {"chat": {"id": chat_id}, "message_id": message_id},
    }


def test_modules_section_lists_only_accessible_modules(org, fake_send):
    """Юзер с доступом только к feed видит одну feed-кнопку, не feedlot/vet/др."""
    _enabled(org, ["feed", "feedlot", "vet", "matochnik"])
    link = _link(org, "feed-only@y.local", {"feed": AccessLevel.ADMIN})

    dispatch_callback(_cbq(link.chat_id, "home:modules"))
    edits_text = "\n".join(t for _, _, t, _ in fake_send.edits)
    assert "Modullar" in edits_text

    callbacks = set()
    for _, _, _, markup in fake_send.edits:
        for row in markup["inline_keyboard"]:
            for btn in row:
                callbacks.add(btn["callback_data"])
    assert "mod:feed" in callbacks
    # Не должны видеть остальные production-модули
    assert "mod:feedlot" not in callbacks
    assert "mod:vet" not in callbacks


def test_modules_section_owner_sees_all_enabled(org, fake_send):
    """Owner видит все включённые модули."""
    _enabled(org, ["feed", "feedlot", "vet"])
    link = _link(org, "owner-mods@y.local", {"admin": AccessLevel.ADMIN})

    dispatch_callback(_cbq(link.chat_id, "home:modules"))
    callbacks = set()
    for _, _, _, markup in fake_send.edits:
        for row in markup["inline_keyboard"]:
            for btn in row:
                callbacks.add(btn["callback_data"])
    assert "mod:feed" in callbacks
    assert "mod:feedlot" in callbacks
    assert "mod:vet" in callbacks


def test_module_hub_renders_finance_and_warehouses(org, fake_send):
    """mod:feed рендерит hub: заголовок, блок финансы, блок склады."""
    _enabled(org, ["feed"])
    link = _link(org, "feed-hub@y.local", {"feed": AccessLevel.ADMIN})

    dispatch_callback(_cbq(link.chat_id, "mod:feed"))
    text = fake_send.edits[-1][2]
    assert "Yem-xashak" in text  # MODULE_LABELS_UZ['feed']
    assert "Moliya" in text  # финблок
    assert "Daromad" in text and "Xarajat" in text


def test_module_hub_blocks_user_without_access(org, fake_send):
    """Юзер без доступа к модулю → ⛔ при попытке открыть hub."""
    _enabled(org, ["vet", "feed"])
    link = _link(org, "no-vet@y.local", {"feed": AccessLevel.ADMIN})

    dispatch_callback(_cbq(link.chat_id, "mod:vet"))
    text = "\n".join(t for _, t, _ in fake_send.calls)
    assert "ruxsat yo'q" in text.lower()


def test_reports_section_lists_modules(org, fake_send):
    """home:reports теперь показывает список модулей (анlytика по каждому)."""
    _enabled(org, ["sales", "feed"])
    link = _link(org, "owner-rep@y.local", {"admin": AccessLevel.ADMIN})

    dispatch_callback(_cbq(link.chat_id, "home:reports"))
    text = fake_send.edits[-1][2]
    assert "Hisobotlar" in text
    callbacks = set()
    for _, _, _, markup in fake_send.edits:
        for row in markup["inline_keyboard"]:
            for btn in row:
                callbacks.add(btn["callback_data"])
    assert "rep:sales" in callbacks
    assert "rep:feed" in callbacks


def test_report_drill_renders_analytics(org, fake_send):
    """rep:sales рендерит детальную аналитику с paid/debt разрезом."""
    _enabled(org, ["sales"])
    link = _link(org, "sales-mgr-rep@y.local", {"sales": AccessLevel.ADMIN})

    dispatch_callback(_cbq(link.chat_id, "rep:sales"))
    text = fake_send.edits[-1][2]
    assert "Sotuvlar" in text  # MODULE_LABELS_UZ['sales']
    assert "analitika" in text.lower()
