from __future__ import annotations

import logging

from celery import shared_task
from django.db.models import Q

logger = logging.getLogger(__name__)


@shared_task(name="apps.tgbot.notify_admins_task")
def notify_admins_task(
    text: str,
    organization_id: str,
    module_code: str | None = None,
    min_level: str = "r",
    modules: list[str] | None = None,
) -> dict:
    """Рассылает text активным TgLink для org.

    ``module_code`` (одиночный) или ``modules`` (список с OR-логикой) —
    получают только пользователи с доступом ≥ ``min_level`` ХОТЯ БЫ К
    ОДНОМУ из указанных модулей. Если ни тот, ни другой не передан —
    все активные admin-линки.

    Дедупликация: каждый chat получает СООБЩЕНИЕ ОДИН РАЗ, даже если
    юзер проходит по нескольким модулям (раньше отправляли отдельные
    задачи на admin + sales — owner получал дубликаты).

    `min_level='admin'` — только «head» модуля (для эскалаций/решений).
    """
    from .bot import send_message
    from .models import TgLink

    # Нормализуем: modules имеет приоритет, иначе [module_code], иначе [].
    if modules:
        check_modules = list(modules)
    elif module_code:
        check_modules = [module_code]
    else:
        check_modules = []

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
    if check_modules:
        # OR по модулям: юзер допущен если у него >=min_level хотя бы к
        # одному. Союз allow-set'ов по модулям.
        allowed_user_ids = set()
        user_ids = [link.user_id for link in links]
        for mc in check_modules:
            allowed_user_ids |= _resolve_allowed_users(
                organization_id=organization_id,
                user_ids=user_ids,
                module_code=mc,
                min_level=min_level,
            )

    sent_chats: set = set()
    for link in links:
        if allowed_user_ids is not None and link.user_id not in allowed_user_ids:
            continue
        # Дедуп: один chat — одно сообщение (на случай если у юзера
        # несколько активных линков на тот же chat_id, маловероятно но
        # защитно).
        if link.chat_id in sent_chats:
            continue
        if send_message(link.chat_id, text):
            sent_chats.add(link.chat_id)
    logger.info(
        "notify_admins_task: sent=%d org=%s modules=%s min_level=%s",
        len(sent_chats), organization_id, check_modules, min_level,
    )
    return {"sent": len(sent_chats)}


@shared_task(name="apps.tgbot.notify_counterparty_task")
def notify_counterparty_task(
    text: str,
    organization_id: str,
    counterparty_id: str,
) -> dict:
    """Шлёт text в TG-чат привязанного контрагента.

    Используется для клиентских уведомлений: «оплата зачислена», «у вас
    задолженность», «продажа ХХХ оформлена». Если у контрагента нет
    активного TgLink — тихо возвращает sent=0 (ошибка не нужна — клиент
    может быть не привязан, это нормально).
    """
    from .bot import send_message
    from .models import TgLink

    link = TgLink.objects.filter(
        organization_id=organization_id,
        counterparty_id=counterparty_id,
        is_active=True,
    ).first()
    if not link:
        logger.info(
            "notify_counterparty_task: no_tg_link org=%s counterparty=%s",
            organization_id, counterparty_id,
        )
        return {"sent": 0, "reason": "no_tg_link"}

    sent = 1 if send_message(link.chat_id, text) else 0
    logger.info(
        "notify_counterparty_task: sent=%d org=%s counterparty=%s chat=%s",
        sent, organization_id, counterparty_id, link.chat_id,
    )
    return {"sent": sent, "chat_id": link.chat_id}


def _resolve_allowed_users(
    *,
    organization_id: str,
    user_ids: list,
    module_code: str,
    min_level: str = "r",
) -> set:
    """Возвращает множество user_id, у которых доступ ≥ ``min_level`` к module_code.

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

    # 2. Role-уровни — для каждого membership собираем все level'ы.
    # Reverse от UserRole.role это `Role.assignments` (related_name на FK).
    # Раньше было `role__user_roles` → FieldError, и notify_admins_task
    # падал с unhandled exception → ни одно TG-уведомление не уходило.
    role_levels: dict = defaultdict(list)
    rp_qs = RolePermission.objects.filter(
        role__assignments__membership_id__in=membership_ids,
        module__code=module_code,
    ).values_list("role__assignments__membership_id", "level")
    for m_id, level in rp_qs:
        role_levels[m_id].append(level)

    allowed: set = set()
    for m_id, user_id in memberships:
        if m_id in override_level:
            actual = override_level[m_id]
        else:
            levels = role_levels.get(m_id) or []
            actual = max(levels, key=lambda lv: _LEVEL_ORDER.get(lv, 0)) if levels else AccessLevel.NONE
        if level_satisfies(actual, min_level):
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
        # SaleOrder.customer (а не counterparty) — поле так и называется,
        # см. apps/sales/models.py. Раньше select_related("counterparty")
        # падал с FieldError, и debt-reminder daily молча всем не доходил.
        order = SaleOrder.objects.select_related("customer", "organization").get(
            id=sale_order_id
        )
    except SaleOrder.DoesNotExist:
        return {"error": "sale_order_not_found"}

    link = TgLink.objects.filter(
        organization=order.organization,
        counterparty=order.customer,
        is_active=True,
        counterparty__isnull=False,
    ).first()

    if not link:
        return {"error": "no_tg_link", "order": sale_order_id}

    text = fmt_debt_reminder_uz(order, order.customer)
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


# ─── Promise-broken (клиент не сдержал обещание) ──────────────────────────


@shared_task(name="apps.tgbot.promise_broken_daily_task")
def promise_broken_daily_task() -> dict:
    """Каждое утро (09:30) находим SaleCommunication с outcome=PROMISED
    где promised_pay_date == ВЧЕРА, но соответствующая SaleOrder ещё не
    оплачена. Шлём клиенту мягкий push «вы обещали вчера, мы ждём».

    Дедуп: фильтр по точной дате (только yesterday). Если клиент дал
    несколько обещаний на одну дату — отправим один раз на каждое
    активное communication, но обычно их не больше одного. Спам-фактор
    низкий (триггер раз в день, точечно).
    """
    from datetime import date as _date, timedelta

    from apps.sales.models import SaleCommunication, SaleOrder

    from .notifications import fmt_promise_broken_uz

    yesterday = _date.today() - timedelta(days=1)
    qs = (
        SaleCommunication.objects
        .filter(
            outcome=SaleCommunication.Outcome.PROMISED,
            promised_pay_date=yesterday,
            order__status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(order__payment_status=SaleOrder.PaymentStatus.PAID)
        .select_related("order", "order__customer", "order__organization")
    )

    queued = 0
    for comm in qs:
        order = comm.order
        try:
            text = fmt_promise_broken_uz(order, comm)
            notify_counterparty_task.delay(
                text, str(order.organization_id), str(order.customer_id),
            )
            queued += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "promise_broken: failed for comm=%s", comm.id,
            )

    logger.info("promise_broken_daily_task: queued=%d", queued)
    return {"queued": queued}


# ─── Pre-block warning (близко к лимиту/просрочке) ────────────────────────


@shared_task(name="apps.tgbot.pre_block_warning_daily_task")
def pre_block_warning_daily_task() -> dict:
    """Каждое утро (10:00) ищем клиентов в «жёлтой зоне» — ещё не
    заблокированы, но близко (debt > 70% лимита ИЛИ просрочка ≥
    max_overdue - 3 дня). Шлём предупреждающий push.

    Цель: дать клиенту понять что он близок к стопу до того как стоп
    случится (а не после). Психологически эффективно — большинство
    предпочитают не доводить до блока.

    Дедуп: каждый день, но клиент в зоне риска ≠ каждый раз. Если он
    погасил часть и вышел из 70%-зоны — push прекратится.
    """
    from decimal import Decimal

    from apps.counterparties.models import Counterparty
    from apps.organizations.models import Organization
    from apps.sales.services.credit_check import check_customer_credit

    from .notifications import fmt_pre_block_warning_uz

    queued = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        # Только клиенты у которых есть credit_limit ИЛИ max_overdue —
        # без них проверять нечего.
        cps = (
            Counterparty.objects
            .filter(
                organization=org, kind=Counterparty.Kind.BUYER,
                is_active=True,
            )
            .filter(
                # хотя бы один лимит установлен
                credit_limit_uzs__isnull=False,
            )
        )
        for cp in cps.iterator():
            try:
                result = check_customer_credit(
                    organization=org, customer=cp, new_sale_uzs=Decimal("0"),
                )
                if not result.ok:
                    continue  # уже заблокирован — debt-reminder его подхватит
                # «Жёлтая зона»: 70%+ от лимита
                if result.limit_uzs is None:
                    continue
                ratio = (
                    Decimal(result.current_debt_uzs) / Decimal(result.limit_uzs)
                    if result.limit_uzs > 0 else Decimal("0")
                )
                if ratio < Decimal("0.7"):
                    continue
                text = fmt_pre_block_warning_uz(cp, result, ratio)
                notify_counterparty_task.delay(
                    text, str(org.id), str(cp.id),
                )
                queued += 1
            except Exception:  # noqa: BLE001
                logger.exception(
                    "pre_block_warning: cp=%s failed", cp.id,
                )

    logger.info("pre_block_warning_daily_task: queued=%d", queued)
    return {"queued": queued}


# ─── Head morning brief (07:00) ──────────────────────────────────────────


@shared_task(name="apps.tgbot.head_morning_brief_task")
def head_morning_brief_task() -> dict:
    """Утренний brief каждому head'у модуля (level=admin на свой модуль).

    Логика: для каждой org — ищем head'ов production-модулей (admin
    доступ). Каждому шлём mini-сводку его модуля (sotuvlar/xaridlar/
    qoldiq за вчера) — чтобы день начинался с свежей картинки без
    необходимости открывать бот.
    """
    from apps.organizations.models import Organization

    from .notifications import fmt_head_brief_uz

    PRODUCTION_MODULES = [
        "matochnik", "incubation", "feedlot", "slaughter",
        "feed", "vet",
    ]
    queued = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        for module_code in PRODUCTION_MODULES:
            try:
                text = fmt_head_brief_uz(org, module_code)
                if text is None:
                    continue  # модуль выключен или нет данных
                # Шлём только head'ам этого модуля (level=admin), не всему staff.
                notify_admins_task.delay(
                    text, str(org.id), module_code, min_level="admin",
                )
                queued += 1
            except Exception:  # noqa: BLE001
                logger.exception(
                    "head_morning_brief: org=%s module=%s failed",
                    org.code, module_code,
                )

    logger.info("head_morning_brief_task: queued=%d", queued)
    return {"queued": queued}


# ─── Cash-flow alert (касса в минусе) ────────────────────────────────────


@shared_task(name="apps.tgbot.cashflow_alert_task")
def cashflow_alert_task() -> dict:
    """Каждый день (07:30) проверяем не ушла ли касса/банк в МИНУС.

    Если хотя бы один cash-канал отрицательный → admin модуля 'admin'
    + 'ledger' получают alert. Это сигнал «что-то не так с движением
    денег» — либо начальный остаток не настроен, либо реальный овердрафт.
    """
    from apps.dashboard.services import cash_balances
    from apps.organizations.models import Organization

    from .notifications import fmt_cashflow_alert_uz

    queued = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        try:
            cash = cash_balances(org)
            negatives = []
            for ch_key, ch_data in cash.items():
                if ch_key.startswith("_"):
                    continue
                bal = float(ch_data.get("balance_uzs", 0) or 0)
                if bal < 0:
                    negatives.append((ch_data.get("label", ch_key), bal))
            if not negatives:
                continue
            text = fmt_cashflow_alert_uz(negatives, cash.get("_total_uzs", 0))
            notify_admins_task.delay(
                text, str(org.id),
                modules=["admin", "ledger"],
            )
            queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("cashflow_alert: org=%s failed", org.code)

    logger.info("cashflow_alert_task: queued=%d", queued)
    return {"queued": queued}


# ─── Stale-payment reminder (продажа с долгом без касания > 7 дней) ───────


@shared_task(name="apps.tgbot.stale_payment_reminder_task")
def stale_payment_reminder_task() -> dict:
    """Каждый день (07:45) ищет confirmed-продажи с долгом, у которых
    последняя SaleCommunication > 7 дней назад (или вообще нет касаний).
    Пинок sales-админу: «займись клиентом X».

    Не путать с debt-reminder (тот шлёт КЛИЕНТУ). Этот шлёт ВНУТРИ —
    менеджеру который должен вести коммуникацию.
    """
    from datetime import date as _date, datetime, timedelta, timezone as _tz
    from django.db.models import Max
    from apps.organizations.models import Organization
    from apps.sales.models import SaleCommunication, SaleOrder

    from .notifications import fmt_stale_payment_alert_uz

    threshold = datetime.now(_tz.utc) - timedelta(days=7)
    queued = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        try:
            stale = list(
                SaleOrder.objects
                .filter(
                    organization=org, status=SaleOrder.Status.CONFIRMED,
                )
                .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
                .annotate(last_touch=Max("communications__contacted_at"))
                .filter(
                    # Либо вообще нет касаний, либо последнее > 7 дней назад
                    Q(last_touch__isnull=True) | Q(last_touch__lt=threshold),
                )
                .select_related("customer")
                .order_by("date")[:50]
            )
            if not stale:
                continue
            text = fmt_stale_payment_alert_uz(stale, threshold_days=7)
            notify_admins_task.delay(text, str(org.id), "sales")
            queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("stale_payment: org=%s failed", org.code)

    logger.info("stale_payment_reminder_task: queued=%d", queued)
    return {"queued": queued}


# ─── Low-stock warning (комбикорм закончится через N дней) ───────────────


@shared_task(name="apps.tgbot.low_stock_feed_task")
def low_stock_feed_task() -> dict:
    """Каждое утро (08:30) проверяем партии готового корма (FeedBatch +
    FeedBagLot ACTIVE/APPROVED). Считаем средний дневной расход за
    последние 14 дней (через StockMovement OUTGOING). Если по этому
    темпу запас закончится за <3 дня → alert head'у feed-модуля.

    Идея: дать оператору возможность заказать сырьё / запустить замес
    ДО того как корм закончился, а не пост-фактум.
    """
    from datetime import date as _date, datetime, timedelta, timezone as _tz
    from decimal import Decimal
    from django.db.models import Sum
    from apps.organizations.models import Organization

    from .notifications import fmt_low_stock_alert_uz

    queued = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        try:
            alerts = _compute_low_stock_alerts(org)
            if not alerts:
                continue
            text = fmt_low_stock_alert_uz(alerts)
            notify_admins_task.delay(text, str(org.id), "feed")
            queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("low_stock_feed: org=%s failed", org.code)

    logger.info("low_stock_feed_task: queued=%d", queued)
    return {"queued": queued}


def _compute_low_stock_alerts(org) -> list:
    """Returns list of (label, remaining_qty, avg_daily_consumption, days_left)."""
    from datetime import date as _date, timedelta
    from decimal import Decimal
    from django.db.models import Sum
    from apps.feed.models import FeedBagLot, FeedBatch
    from apps.warehouses.models import StockMovement

    today = _date.today()
    df = today - timedelta(days=14)

    alerts = []
    for fb in FeedBatch.objects.filter(
        organization=org, status=FeedBatch.Status.APPROVED,
        current_quantity_kg__gt=0,
    ).select_related("recipe_version__recipe"):
        # Средний расход за 14 дней по этой nomenclature (через recipe.code)
        recipe_code = (
            fb.recipe_version.recipe.code if fb.recipe_version_id else None
        )
        if not recipe_code:
            continue
        # Берём все OUTGOING по этой партии (через source_object_id)
        consumed = (
            StockMovement.objects.filter(
                organization=org, kind=StockMovement.Kind.OUTGOING,
                date__date__gte=df, date__date__lte=today,
                source_object_id=fb.id,
            ).aggregate(s=Sum("quantity"))["s"] or Decimal("0")
        )
        avg_daily = Decimal(consumed) / Decimal("14")
        if avg_daily <= 0:
            continue  # не расходуется — нет смысла alert'ить
        remaining = Decimal(fb.current_quantity_kg)
        days_left = float(remaining / avg_daily)
        if days_left < 3:
            alerts.append({
                "label": f"{fb.doc_number} · {recipe_code}",
                "remaining": f"{float(remaining):,.0f} kg".replace(",", " "),
                "avg_daily": f"{float(avg_daily):,.0f} kg/kun".replace(",", " "),
                "days_left": round(days_left, 1),
            })
    return alerts


# ─── Weekly Monday summary (07:00 в понедельник) ──────────────────────────


@shared_task(name="apps.tgbot.weekly_monday_summary_task")
def weekly_monday_summary_task() -> dict:
    """Понедельник 07:00 — недельный обзор для admin-линков с
    digest_enabled. Что было за прошлую неделю: продажи / оплаты /
    закупки / производство / ключевые KPI.

    Дополняет owner-digest (ежедневный) — еженедельный показывает тренд.
    """
    from apps.organizations.models import Organization

    from .notifications import fmt_weekly_summary_uz

    queued = 0
    for org in Organization.objects.filter(is_active=True).iterator():
        try:
            text = fmt_weekly_summary_uz(org)
            if text is None:
                continue
            notify_admins_task.delay(
                text, str(org.id), modules=["admin", "reports"],
            )
            queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("weekly_monday_summary: org=%s failed", org.code)

    logger.info("weekly_monday_summary_task: queued=%d", queued)
    return {"queued": queued}


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
