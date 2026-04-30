from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.tgbot.notify_admins_task")
def notify_admins_task(text: str, organization_id: str, module_code: str | None = None) -> dict:
    """Рассылает text активным TgLink для org.

    Если передан module_code — получают только пользователи с доступом
    к этому модулю (уровень >= 'r'). Без module_code — все активные.

    Производительность: предварительно одним запросом подгружаем все
    memberships, override'ы и role-permissions нужного модуля, потом
    решаем «кому слать» в памяти. Старая реализация делала ~3 запроса
    на каждого получателя (N+1) — на орге с 50 сотрудниками это 150+
    SQL-запросов и таска тормозила.
    """
    from .bot import send_message
    from .models import TgLink

    links = list(
        TgLink.objects.filter(
            organization_id=organization_id,
            is_active=True,
            user__isnull=False,
        ).select_related("user")
    )
    if not links:
        return {"sent": 0}

    allowed_user_ids: set | None = None
    if module_code is not None:
        allowed_user_ids = _resolve_allowed_users(
            organization_id=organization_id,
            user_ids=[link.user_id for link in links],
            module_code=module_code,
        )

    sent = 0
    for link in links:
        if allowed_user_ids is not None and link.user_id not in allowed_user_ids:
            continue
        if send_message(link.chat_id, text):
            sent += 1
    logger.info("notify_admins_task: sent=%d org=%s module=%s", sent, organization_id, module_code)
    return {"sent": sent}


def _resolve_allowed_users(*, organization_id: str, user_ids: list, module_code: str) -> set:
    """Возвращает множество user_id, у которых доступ >= 'r' к module_code.

    Делает ровно 3 SQL-запроса независимо от количества пользователей:
      1. memberships по парам (org, user)
      2. UserModuleAccessOverride для этих memberships + module
      3. RolePermission через user_roles → role для этих memberships + module
    """
    from collections import defaultdict

    from apps.common.permissions import _LEVEL_ORDER, level_satisfies
    from apps.organizations.models import OrganizationMembership
    from apps.rbac.models import AccessLevel, RolePermission, UserModuleAccessOverride

    memberships = list(
        OrganizationMembership.objects.filter(
            organization_id=organization_id, user_id__in=user_ids,
        ).values_list("id", "user_id")
    )
    if not memberships:
        return set()

    membership_ids = [m_id for m_id, _ in memberships]
    membership_to_user = dict(memberships)

    # 1. Override-уровни (запись на membership «бьёт» role-уровни)
    override_level: dict = dict(
        UserModuleAccessOverride.objects.filter(
            membership_id__in=membership_ids, module__code=module_code,
        ).values_list("membership_id", "level")
    )

    # 2. Role-уровни — для каждого membership собираем все level'ы
    role_levels: dict = defaultdict(list)
    rp_qs = RolePermission.objects.filter(
        role__user_roles__membership_id__in=membership_ids,
        module__code=module_code,
    ).values_list("role__user_roles__membership_id", "level")
    for m_id, level in rp_qs:
        role_levels[m_id].append(level)

    allowed: set = set()
    for m_id, user_id in memberships:
        if m_id in override_level:
            actual = override_level[m_id]
        else:
            levels = role_levels.get(m_id) or []
            actual = max(levels, key=lambda lv: _LEVEL_ORDER.get(lv, 0)) if levels else AccessLevel.NONE
        if level_satisfies(actual, "r"):
            allowed.add(user_id)
    return allowed


@shared_task(name="apps.tgbot.send_debt_reminder_task")
def send_debt_reminder_task(sale_order_id: str) -> dict:
    """Отправляет напоминание о долге по конкретному SaleOrder."""
    from apps.sales.models import SaleOrder

    from .bot import send_message
    from .models import TgLink
    from .notifications import fmt_debt_reminder_uz

    try:
        order = SaleOrder.objects.select_related("counterparty", "organization").get(
            id=sale_order_id
        )
    except SaleOrder.DoesNotExist:
        return {"error": "sale_order_not_found"}

    link = TgLink.objects.filter(
        organization=order.organization,
        counterparty=order.counterparty,
        is_active=True,
        counterparty__isnull=False,
    ).first()

    if not link:
        return {"error": "no_tg_link", "order": sale_order_id}

    text = fmt_debt_reminder_uz(order, order.counterparty)
    ok = send_message(link.chat_id, text)
    return {"sent": ok, "chat_id": link.chat_id}


@shared_task(name="apps.tgbot.debt_reminder_daily_task")
def debt_reminder_daily_task() -> dict:
    """Celery Beat: каждый день в 09:00 — напоминания всем должникам."""
    from apps.sales.models import SaleOrder

    overdue = SaleOrder.objects.filter(
        status=SaleOrder.Status.CONFIRMED,
    ).exclude(payment_status=SaleOrder.PaymentStatus.PAID)

    count = 0
    for order in overdue:
        send_debt_reminder_task.delay(str(order.id))
        count += 1

    logger.info("debt_reminder_daily_task: queued=%d", count)
    return {"queued": count}


@shared_task(name="apps.tgbot.handle_tg_update_task")
def handle_tg_update_task(update: dict) -> None:
    """Обрабатывает входящий Telegram update."""
    from .commands import dispatch
    try:
        dispatch(update)
    except Exception as exc:
        logger.error("handle_tg_update_task error: %s", exc, exc_info=True)
