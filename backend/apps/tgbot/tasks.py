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
    """Celery Beat: каждый день в 09:00 — таргетированные напоминания.

    Старая логика спамила всем должникам каждый день, что приучало
    клиентов игнорировать. Новая логика — точечная по `due_date`:
      - T-3: первое предупреждение «через 3 дня срок»
      - T-1: «завтра срок»
      - T-0: «сегодня срок»
      - T+N: каждые 7 дней просрочки (T+1, T+8, T+15, …)
      - без due_date: раз в неделю по понедельникам (мягкое напоминание)

    Это даёт клиенту 3 чётких касания до срока + еженедельный пинок
    при просрочке, без раздражения.
    """
    from datetime import date as _date

    from apps.sales.models import SaleOrder

    today = _date.today()
    qs = SaleOrder.objects.filter(
        status=SaleOrder.Status.CONFIRMED,
    ).exclude(payment_status=SaleOrder.PaymentStatus.PAID)

    queued = 0
    skipped = 0
    for order in qs:
        if not _should_remind_today(order, today):
            skipped += 1
            continue
        send_debt_reminder_task.delay(str(order.id))
        queued += 1

    logger.info(
        "debt_reminder_daily_task: queued=%d skipped=%d", queued, skipped
    )
    return {"queued": queued, "skipped": skipped}


def _should_remind_today(order, today) -> bool:
    """Решает, надо ли сегодня дёргать напоминание по этому заказу.

    См. docstring `debt_reminder_daily_task` для расписания.
    """
    if order.due_date is None:
        # Без срока — только по понедельникам (weekday 0), не каждый день
        return today.weekday() == 0

    delta_days = (today - order.due_date).days
    if delta_days < 0:
        # Ещё до срока: T-3 и T-1
        days_until = -delta_days
        return days_until in (3, 1)
    if delta_days == 0:
        # День X
        return True
    # После срока: T+1, потом каждые 7 дней (T+8, T+15, ...)
    return delta_days == 1 or delta_days % 7 == 1


@shared_task(name="apps.tgbot.daily_collection_alerts_task")
def daily_collection_alerts_task() -> dict:
    """Celery Beat: каждый день в 09:00 (после debt-reminders) — алерт
    владельцу/админам по задачам сборщика дебиторки.

    Если есть эскалации (long overdue без касаний) или сорванные обещания —
    шлём в TG сводку: «Сегодня 3 эскалации (12.5М сум) и 7 нарушенных
    обещаний». Это позволяет владельцу не открывать /tasks вручную каждый
    день — пинок придёт сам когда есть что разбирать.
    """
    from apps.organizations.models import Organization
    from apps.sales.services.collection_tasks import compute_collection_tasks

    queued = 0
    skipped = 0
    for org in Organization.objects.all():
        report = compute_collection_tasks(org)
        # Шлём только если есть «горячие» категории. Низкоприоритетные
        # callback-планы — это рутина, не повод отвлекать владельца.
        if not (
            report.escalation
            or report.promise_broken
            or report.forecast_due
        ):
            skipped += 1
            continue

        text = _fmt_collection_alert(report)
        try:
            notify_admins_task.delay(
                text=text,
                organization_id=str(org.id),
                module_code="sales",
            )
            queued += 1
        except Exception:
            logger.exception(
                "daily_collection_alerts_task: failed for org %s", org.code
            )

    logger.info(
        "daily_collection_alerts_task: queued=%d skipped=%d", queued, skipped
    )
    return {"queued": queued, "skipped": skipped}


def _fmt_collection_alert(report) -> str:
    """Текст для TG-алерта по задачам дебиторки."""
    from decimal import Decimal

    def _sum(tasks) -> Decimal:
        return sum((Decimal(t.outstanding_uzs) for t in tasks), Decimal("0"))

    lines = ["📋 <b>Задачи по долгам на сегодня</b>\n"]

    if report.escalation:
        total = _sum(report.escalation)
        lines.append(
            f"🚨 <b>Эскалация:</b> {len(report.escalation)} клиент(ов) · "
            f"{float(total):,.0f} сум"
        )
        for t in report.escalation[:3]:
            lines.append(
                f"  • {t.customer_name} — {float(t.outstanding_uzs):,.0f} сум, "
                f"{t.days_overdue} дн просрочки"
            )

    if report.promise_broken:
        total = _sum(report.promise_broken)
        lines.append(
            f"\n⚠️ <b>Не сдержали обещание:</b> {len(report.promise_broken)} · "
            f"{float(total):,.0f} сум"
        )
        for t in report.promise_broken[:3]:
            lines.append(
                f"  • {t.customer_name} — обещал {t.promised_date}, не заплатил"
            )

    if report.forecast_due:
        total = _sum(report.forecast_due)
        lines.append(
            f"\n🎯 <b>Не сбылся прогноз:</b> {len(report.forecast_due)} · "
            f"{float(total):,.0f} сум"
        )

    if report.callback_due:
        lines.append(
            f"\n📞 Запланированных обзвонов: {len(report.callback_due)}"
        )

    lines.append("\nОткрыть: /tasks")
    return "\n".join(lines)


@shared_task(name="apps.tgbot.handle_tg_update_task")
def handle_tg_update_task(update: dict) -> None:
    """Обрабатывает входящий Telegram update.

    Сам dispatcher (`apps.tgbot.dispatcher.dispatch`) уже оборачивает все
    handler'ы в try/except + logger.exception, так что эта обёртка только
    логирует совсем фатальные исключения уровня импорта/registry.
    """
    from .dispatcher import dispatch
    try:
        dispatch(update)
    except Exception as exc:
        logger.error("handle_tg_update_task error: %s", exc, exc_info=True)


@shared_task(name="apps.tgbot.owner_digest_task")
def owner_digest_task() -> dict:
    """Утренняя сводка для владельцев — 08:00 Asia/Tashkent ежедневно.

    Для каждой активной организации (учитывая `module_enabled_for_org` для
    её модулей) собираем `DigestData` за вчерашний день и отправляем во все
    admin-линки с `digest_enabled=True`. Counterparty-линки игнорим — для
    них существует только debt-reminder flow.

    Beat schedule сидится в миграции `0005_seed_owner_digest_beat.py`.
    """
    from apps.organizations.models import Organization

    from .bot import send_message
    from .models import TgLink
    from .services.digest import build_digest, format_digest

    total_orgs = 0
    total_sent = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        # Линки этой организации с активной подпиской на digest.
        # active_organization имеет приоритет (если юзер переключал /org),
        # иначе — `organization`.
        link_ids = list(
            TgLink.objects.filter(
                is_active=True, user__isnull=False, digest_enabled=True,
            ).filter(
                # либо явный active_organization == org,
                # либо нет active + organization == org
                models_q_active_or_default(org),
            ).values_list("id", flat=True)
        )
        if not link_ids:
            continue
        total_orgs += 1
        try:
            data = build_digest(org)
            text = format_digest(data, organization_name=org.name)
        except Exception:  # noqa: BLE001
            logger.exception("owner_digest: build failed for org=%s", org.id)
            continue

        for link_id in link_ids:
            link = TgLink.objects.select_related("user").get(id=link_id)
            ok = send_message(link.chat_id, text)
            if ok:
                total_sent += 1

    payload = {"orgs_with_subs": total_orgs, "sent": total_sent}
    logger.info("owner_digest_task: %s", payload)
    return payload


def models_q_active_or_default(org):
    """Q-выражение «active_organization=org ИЛИ (active_organization IS NULL
    AND organization=org)». Вынесено отдельно ради читаемости задачи выше."""
    from django.db.models import Q
    return Q(active_organization=org) | Q(
        active_organization__isnull=True, organization=org,
    )
