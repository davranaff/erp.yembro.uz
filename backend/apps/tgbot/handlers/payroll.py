"""
Payroll / HR handlers для Telegram-бота.

Read-only (любой с hr:r):
    /zp [search]      — балансы ЗП всех сотрудников
    /myzp             — мой баланс (привязанные сотрудники)
    /people [search]  — список сотрудников с балансом и должностью
    /person <ФИО>     — карточка одного сотрудника
    /today            — кто сегодня на работе

Write (требуют hr:rw):
    /markday <ФИО> <дата|сегодня|вчера> <work|absence|sick|vacation|day_off|overtime>
    /bonus   <ФИО> <сумма> [причина]
    /deduct  <ФИО> <сумма> [причина]
"""
from __future__ import annotations

import html
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from ..bot import answer_callback_query, edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb


logger = logging.getLogger(__name__)


def _fmt_uzs(value) -> str:
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


# ──────────────────────── HR helpers ────────────────────────────────────


def _hr_membership(ctx: HandlerCtx):
    """Membership самого юзера в активной org — нужен для RBAC проверки на write."""
    from apps.organizations.models import OrganizationMembership

    org = ctx.org()
    user_id = getattr(ctx.link, "user_id", None) if ctx.link else None
    if not org or not user_id:
        return None
    return (
        OrganizationMembership.objects.filter(
            organization=org, user_id=user_id, is_active=True,
        ).first()
    )


def _require_hr_rw(ctx: HandlerCtx) -> bool:
    """Проверка: текущий юзер может писать в HR. Шлёт ошибку и возвращает False
    если нет."""
    from apps.common.permissions import _effective_level, level_satisfies

    m = _hr_membership(ctx)
    if m is None:
        send_message(ctx.chat_id, "Нужна активная организация.")
        return False
    if not level_satisfies(_effective_level(m, "hr"), "rw"):
        send_message(ctx.chat_id, "Нужны права hr:rw (Кадровик или выше).")
        return False
    return True


def _find_employee(ctx: HandlerCtx, query: str):
    """Найти сотрудника по части ФИО. Возвращает membership или None.

    Если найдено >1 — шлёт список и возвращает None.
    """
    from apps.organizations.models import OrganizationMembership

    org = ctx.org()
    if not org:
        return None

    q = query.strip().lower()
    if not q:
        send_message(ctx.chat_id, "Укажите ФИО или часть имени.")
        return None

    qs = list(
        OrganizationMembership.objects.filter(
            organization=org, is_active=True,
            user__full_name__icontains=q,
        ).select_related("user", "compensation_plan")[:10]
    )
    if not qs:
        send_message(ctx.chat_id, f"Сотрудник с «{html.escape(query)}» не найден.")
        return None
    if len(qs) > 1:
        lines = [f"Найдено {len(qs)} сотрудников. Уточните:"]
        for m in qs:
            lines.append(f"  • {html.escape(m.user.full_name or '—')}"
                         f" — {html.escape(m.position_title or 'без должности')}")
        send_message(ctx.chat_id, "\n".join(lines))
        return None
    return qs[0]


def _parse_money(s: str) -> Decimal | None:
    """1000000, 1_000_000, 1 000 000, 1.5 — всё валидно."""
    cleaned = s.replace(" ", "").replace("_", "").replace(",", ".")
    try:
        v = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return v if v > 0 else None


_DATE_ALIASES = {
    "сегодня": 0, "today": 0, "bugun": 0,
    "вчера": -1, "yesterday": -1, "kecha": -1,
    "завтра": 1, "tomorrow": 1, "ertaga": 1,
}


def _parse_date(s: str) -> date | None:
    s = s.strip().lower()
    if s in _DATE_ALIASES:
        return date.today() + timedelta(days=_DATE_ALIASES[s])
    # YYYY-MM-DD или DD.MM.YYYY
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m"):
        try:
            d = datetime.strptime(s, fmt).date()
            if fmt == "%d.%m":
                d = d.replace(year=date.today().year)
            return d
        except ValueError:
            continue
    return None


_KIND_ALIASES = {
    "work": "work", "работа": "work", "рабочий": "work", "р": "work",
    "overtime": "overtime", "сверхурочно": "overtime", "переработка": "overtime",
    "vacation": "vacation", "отпуск": "vacation", "о": "vacation",
    "sick": "sick_leave", "sick_leave": "sick_leave", "больничный": "sick_leave", "б": "sick_leave",
    "absence": "absence", "прогул": "absence", "пропуск": "absence", "пр": "absence",
    "day_off": "day_off", "выходной": "day_off", "выход": "day_off",
    "holiday": "holiday", "праздник": "holiday",
}


def _fmt_balance_line(name: str, accrued: Decimal, paid: Decimal, balance: Decimal) -> str:
    sign = "+" if balance > 0 else ("−" if balance < 0 else "·")
    return (
        f"<b>{html.escape(name)}</b>\n"
        f"  Начислено: <code>{_fmt_uzs(accrued)}</code>\n"
        f"  Выплачено: <code>{_fmt_uzs(paid)}</code>\n"
        f"  Баланс:    <code>{sign} {_fmt_uzs(abs(balance))}</code>"
    )


@command(
    "/zp",
    help="Балансы ЗП всех сотрудников (фильтр по ФИО)",
    module="hr", category="hr",
)
def handle_zp_cmd(ctx: HandlerCtx) -> None:
    """Список балансов всех активных сотрудников. /zp иван — фильтр по подстроке."""
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.services.balance import compute_balance

    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Активная организация не выбрана.")
        return

    search = " ".join(ctx.args).strip().lower() if ctx.args else ""
    qs = OrganizationMembership.objects.filter(
        organization=org, is_active=True,
    ).select_related("user")
    if search:
        qs = qs.filter(user__full_name__icontains=search)
    qs = qs[:20]

    if not qs.exists():
        send_message(ctx.chat_id, "Нет активных сотрудников.")
        return

    today = date.today()
    lines = ["💵 <b>Балансы ЗП</b>\n"]
    total_debt = Decimal("0")
    rows = []
    for m in qs:
        bal = compute_balance(m, today)
        rows.append((m, bal))
        if bal.balance_uzs > 0:
            total_debt += bal.balance_uzs
    rows.sort(key=lambda x: x[1].balance_uzs, reverse=True)

    for m, bal in rows:
        lines.append(_fmt_balance_line(
            m.user.full_name if m.user_id else "—",
            bal.accrued_total, bal.paid_total, bal.balance_uzs,
        ))
    lines.append(f"\n─\nДолг компании: <b>{_fmt_uzs(total_debt)}</b> сум")
    send_message(ctx.chat_id, "\n\n".join(lines))


@command(
    "/myzp",
    help="Мой баланс зарплаты",
    audience="any", category="reports",
)
def handle_myzp_cmd(ctx: HandlerCtx) -> None:
    """
    Если link принадлежит TgLink с user_id — показываем балансы юзера во всех
    его активных организациях. Counterparty-link не имеет смысла.
    """
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.services.balance import compute_balance

    user_id = getattr(ctx.link, "user_id", None) if ctx.link else None
    if user_id is None:
        send_message(ctx.chat_id, "Команда доступна только привязанным сотрудникам.")
        return

    memberships = (
        OrganizationMembership.objects.filter(user_id=user_id, is_active=True)
        .select_related("organization", "user")
    )
    if not memberships.exists():
        send_message(ctx.chat_id, "У вас нет активных мест работы.")
        return

    today = date.today()
    blocks = []
    for m in memberships:
        bal = compute_balance(m, today)
        blocks.append(
            f"🏢 <b>{html.escape(m.organization.code)}</b>\n"
            f"  Должность: {html.escape(m.position_title or '—')}\n"
            f"  Начислено: <code>{_fmt_uzs(bal.accrued_total)}</code>\n"
            f"  Выплачено: <code>{_fmt_uzs(bal.paid_total)}</code>\n"
            f"  <b>К выплате: {_fmt_uzs(bal.balance_uzs)} сум</b>"
        )
    send_message(ctx.chat_id, "💵 <b>Ваша зарплата</b>\n\n" + "\n\n".join(blocks))


# ════════════════════════════════════════════════════════════════════════════
#   HR-команды — управление кадрами через бот
# ════════════════════════════════════════════════════════════════════════════


@command(
    "/people",
    help="Список сотрудников: ФИО, должность, баланс (фильтр по ФИО)",
    module="hr", category="hr",
)
def handle_people_cmd(ctx: HandlerCtx) -> None:
    """`/people` или `/people иван` — компактный список."""
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.services.balance import compute_balance

    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Активная организация не выбрана.")
        return

    search = " ".join(ctx.args).strip().lower() if ctx.args else ""
    qs = OrganizationMembership.objects.filter(
        organization=org, is_active=True,
    ).select_related("user")
    if search:
        qs = qs.filter(user__full_name__icontains=search)
    qs = list(qs[:30])

    if not qs:
        send_message(ctx.chat_id, "Нет активных сотрудников по фильтру.")
        return

    today = date.today()
    rows = []
    for m in qs:
        bal = compute_balance(m, today)
        rows.append((m, bal))
    # Сортировка: сначала те, кому больше всего должны.
    rows.sort(key=lambda x: x[1].balance_uzs, reverse=True)

    lines = [f"👥 <b>Сотрудники</b> ({len(rows)})\n"]
    for m, bal in rows:
        name = html.escape(m.user.full_name or "—") if m.user_id else "—"
        pos = html.escape(m.position_title or "")
        bal_v = bal.balance_uzs
        sign = "🟡" if bal_v > 0 else ("🔵" if bal_v < 0 else "·")
        bal_str = _fmt_uzs(abs(bal_v))
        lines.append(
            f"{sign} <b>{name}</b>"
            + (f" · {pos}" if pos else "")
            + f"\n   <code>{bal_str}</code> сум"
        )
    if not search:
        lines.append("\n<i>Фильтр: <code>/people иван</code></i>")
    send_message(ctx.chat_id, "\n".join(lines))


@command(
    "/person",
    help="Карточка сотрудника: ставка, баланс, явка месяца",
    module="hr", category="hr",
)
def handle_person_cmd(ctx: HandlerCtx) -> None:
    """`/person ФИО` — детальная карточка одного."""
    from apps.payroll.models import WorkShift
    from apps.payroll.services.balance import compute_balance

    if not ctx.args:
        send_message(ctx.chat_id, "Использование: <code>/person ФИО</code>")
        return

    m = _find_employee(ctx, " ".join(ctx.args))
    if m is None:
        return

    today = date.today()
    bal = compute_balance(m, today)

    # Явка за текущий месяц
    month_start = today.replace(day=1)
    counts: dict[str, int] = {}
    for k in WorkShift.objects.filter(
        employee=m, shift_date__range=(month_start, today), shift_index=0,
    ).values_list("kind", flat=True):
        counts[k] = counts.get(k, 0) + 1

    plan = getattr(m, "compensation_plan", None)
    comp_label = "—"
    if plan:
        comp_label = {
            "monthly_salary": "Оклад",
            "per_shift": "За смену",
            "per_hour": "За час",
        }.get(plan.compensation_type, plan.compensation_type)

    name = html.escape(m.user.full_name or "—") if m.user_id else "—"
    pos = html.escape(m.position_title or "—")
    email = html.escape(m.user.email or "—") if m.user_id else "—"

    msg = (
        f"👤 <b>{name}</b>\n"
        f"  💼 {pos}\n"
        f"  📧 <code>{email}</code>\n"
        f"  💰 Оплата: {comp_label}\n"
        f"\n"
        f"  📊 <b>Баланс на сегодня</b>\n"
        f"     Начислено: <code>{_fmt_uzs(bal.accrued_total)}</code>\n"
        f"     Выплачено: <code>{_fmt_uzs(bal.paid_total)}</code>\n"
        f"     К выплате: <code>{_fmt_uzs(bal.balance_uzs)}</code> сум\n"
        f"\n"
        f"  📅 <b>Этот месяц</b>\n"
        f"     Работа:     {counts.get('work', 0)}\n"
        f"     Сверхурочно: {counts.get('overtime', 0)}\n"
        f"     Отпуск:     {counts.get('vacation', 0)}\n"
        f"     Больничный: {counts.get('sick_leave', 0)}\n"
        f"     Прогул:     {counts.get('absence', 0)}"
    )
    send_message(ctx.chat_id, msg)


@command(
    "/today",
    help="Кто сегодня на работе / в отпуске / прогуливает",
    module="hr", category="hr",
)
def handle_today_cmd(ctx: HandlerCtx) -> None:
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.models import WorkShift

    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Активная организация не выбрана.")
        return

    today = date.today()
    shifts = (
        WorkShift.objects.filter(
            organization=org, shift_date=today, shift_index=0,
        ).select_related("employee__user")
    )
    by_kind: dict[str, list[str]] = {}
    seen_emp_ids: set = set()
    for s in shifts:
        seen_emp_ids.add(s.employee_id)
        if s.employee.user_id and s.employee.user.full_name:
            name = s.employee.user.full_name
        else:
            name = "—"
        by_kind.setdefault(s.kind, []).append(name)

    # Сотрудники без записи смены на сегодня
    untracked = (
        OrganizationMembership.objects.filter(
            organization=org, is_active=True,
        )
        .exclude(id__in=seen_emp_ids)
        .select_related("user")
    )
    untracked_names = [
        m.user.full_name or "—"
        for m in untracked if m.user_id and m.user.full_name
    ]

    LABEL = {
        "work":       ("✅", "Работают"),
        "overtime":   ("💪", "Сверхурочно"),
        "vacation":   ("🏖", "В отпуске"),
        "sick_leave": ("🏥", "На больничном"),
        "absence":    ("❌", "Прогул"),
        "day_off":    ("🛏", "Выходной"),
        "holiday":    ("🎉", "Праздник"),
    }
    parts = [f"📅 <b>Сегодня · {today.strftime('%d.%m.%Y')}</b>"]
    for kind, (icon, label) in LABEL.items():
        names = by_kind.get(kind, [])
        if names:
            parts.append(f"\n{icon} <b>{label}</b> ({len(names)})")
            for n in sorted(names):
                parts.append(f"  · {html.escape(n)}")
    if untracked_names:
        parts.append(f"\n⚪️ <b>Без записи на сегодня</b> ({len(untracked_names)})")
        for n in sorted(untracked_names)[:20]:
            parts.append(f"  · {html.escape(n)}")

    send_message(ctx.chat_id, "\n".join(parts))


@command(
    "/markday",
    help="Отметить день: /markday ФИО ДАТА КОД (work/absence/sick/vacation/...)",
    module="hr", category="hr",
)
def handle_markday_cmd(ctx: HandlerCtx) -> None:
    """
    `/markday Иванов 2026-05-12 absence`
    `/markday Иван сегодня работа`
    """
    if not _require_hr_rw(ctx):
        return
    if len(ctx.args) < 3:
        send_message(
            ctx.chat_id,
            "Использование:\n"
            "<code>/markday ФИО ДАТА КОД</code>\n\n"
            "Дата: <code>сегодня</code>, <code>вчера</code>, <code>2026-05-12</code>, <code>12.05</code>\n"
            "Код: <code>работа</code>, <code>прогул</code>, <code>отпуск</code>, "
            "<code>больничный</code>, <code>сверхурочно</code>, <code>выходной</code>",
        )
        return

    # Последние 2 аргумента — дата и kind, всё что до — ФИО.
    *name_parts, raw_date, raw_kind = ctx.args
    fio = " ".join(name_parts)

    d = _parse_date(raw_date)
    if d is None:
        send_message(ctx.chat_id, f"Не понял дату: «{html.escape(raw_date)}». Пример: <code>2026-05-12</code>.")
        return
    kind = _KIND_ALIASES.get(raw_kind.lower())
    if kind is None:
        send_message(ctx.chat_id, f"Не понял код: «{html.escape(raw_kind)}». См. <code>/markday</code> без аргументов.")
        return

    m = _find_employee(ctx, fio)
    if m is None:
        return

    from apps.payroll.models import WorkShift

    _, created = WorkShift.objects.update_or_create(
        employee=m, shift_date=d, shift_index=0,
        defaults={
            "organization": ctx.org(),
            "kind": kind,
            "source": "manual",
        },
    )
    action = "✨ Создано" if created else "♻️ Обновлено"
    name = html.escape(m.user.full_name or "—") if m.user_id else "—"
    kind_label = dict(WorkShift.Kind.choices).get(kind, kind)
    send_message(
        ctx.chat_id,
        f"{action}:\n👤 {name}\n📅 {d.strftime('%d.%m.%Y')} → {kind_label}",
    )


def _adjustment_cmd(ctx: HandlerCtx, kind: str, label_icon: str) -> None:
    """Общая логика для /bonus и /deduct."""
    if not _require_hr_rw(ctx):
        return
    if len(ctx.args) < 2:
        verb = "Премия" if kind == "bonus" else "Удержание"
        send_message(
            ctx.chat_id,
            f"{verb}.\n"
            f"Использование: <code>/{'bonus' if kind == 'bonus' else 'deduct'} ФИО СУММА [причина]</code>\n\n"
            f"Пример: <code>/{'bonus' if kind == 'bonus' else 'deduct'} Иванов 500000 за переработку</code>",
        )
        return

    # Найти позицию суммы — первый аргумент который парсится как Decimal.
    sum_idx = -1
    for i, a in enumerate(ctx.args):
        if _parse_money(a) is not None:
            sum_idx = i
            break
    if sum_idx <= 0:
        send_message(ctx.chat_id, "Не нашёл сумму в команде. Пример: <code>/bonus Иванов 500000 повышение</code>")
        return

    fio = " ".join(ctx.args[:sum_idx])
    amount = _parse_money(ctx.args[sum_idx])
    reason = " ".join(ctx.args[sum_idx + 1:]).strip()

    if amount is None or amount <= 0:
        send_message(ctx.chat_id, "Сумма должна быть положительным числом.")
        return

    m = _find_employee(ctx, fio)
    if m is None:
        return

    from apps.payroll.models import PayrollAdjustment

    adj = PayrollAdjustment.objects.create(
        organization=ctx.org(),
        employee=m,
        kind=kind,
        amount_uzs=amount,
        effective_date=date.today(),
        reason=reason or ("Премия через бот" if kind == "bonus" else "Удержание через бот"),
    )
    name = html.escape(m.user.full_name or "—") if m.user_id else "—"
    kind_label = "Премия" if kind == "bonus" else "Удержание"
    msg = (
        f"{label_icon} <b>{kind_label}</b>\n"
        f"  👤 {name}\n"
        f"  💰 <code>{_fmt_uzs(amount)}</code> сум\n"
    )
    if reason:
        msg += f"  📝 {html.escape(reason)}\n"
    msg += f"  📅 {adj.effective_date.strftime('%d.%m.%Y')}"
    send_message(ctx.chat_id, msg)


@command(
    "/bonus",
    help="Премия сотруднику: /bonus ФИО СУММА [причина]",
    module="hr", category="hr",
)
def handle_bonus_cmd(ctx: HandlerCtx) -> None:
    _adjustment_cmd(ctx, "bonus", "🎁")


@command(
    "/deduct",
    help="Удержание из ЗП: /deduct ФИО СУММА [причина]",
    module="hr", category="hr",
)
def handle_deduct_cmd(ctx: HandlerCtx) -> None:
    _adjustment_cmd(ctx, "deduction", "✂️")


# ════════════════════════════════════════════════════════════════════════════
#   Daily check — массовая отметка сотрудников за сегодня кнопками
# ════════════════════════════════════════════════════════════════════════════
#
# UX: одна карточка — один сотрудник. Кадровик нажимает «работал/прогул/
# больничный/отпуск/пропустить», бот пишет в БД и шлёт следующего.
# В конце — сводка.
#
# Telegram-callback'и ограничены 64 байтами, поэтому в data передаём
# первые 8 hex-символов uuid сотрудника. Конфликтов в маленькой ферме (до
# 50 человек) практически нет; на коллизии подстрахуемся проверкой в org.

_CHECK_KIND_BTNS = [
    ("✅ Работал",     "work"),
    ("💪 Сверхурочно", "overtime"),
    ("🏥 Больничный",  "sick_leave"),
    ("🏖 Отпуск",      "vacation"),
    ("❌ Прогул",      "absence"),
    ("🛏 Выходной",    "day_off"),
]


def _resolve_emp_short(org, short_id: str):
    """Найти Membership по первым 8 chars uuid в текущей org."""
    from apps.organizations.models import OrganizationMembership

    short_id = short_id.lower()
    # uuid_id::text не работает в filter; вытягиваем кандидатов и фильтруем в py.
    for m in OrganizationMembership.objects.filter(
        organization=org, is_active=True,
    ).select_related("user")[:500]:
        if str(m.id).replace("-", "").startswith(short_id):
            return m
    return None


def _next_unchecked(org, after_short: str | None = None):
    """Найти следующего активного сотрудника без записи WorkShift на сегодня.

    after_short — короткий id, после которого продолжаем (по сортировке ФИО).
    Если None — берём первого.
    """
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.models import WorkShift

    today = date.today()
    marked_ids = set(
        WorkShift.objects.filter(
            organization=org, shift_date=today, shift_index=0,
        ).values_list("employee_id", flat=True)
    )

    qs = (
        OrganizationMembership.objects.filter(organization=org, is_active=True)
        .exclude(id__in=marked_ids)
        .select_related("user")
        .order_by("user__full_name")
    )

    after_seen = after_short is None
    for m in qs:
        if not after_seen:
            if str(m.id).replace("-", "").startswith(after_short.lower()):
                after_seen = True
            continue
        return m
    return None


def _build_check_card(m, total: int, remaining: int) -> tuple[str, dict]:
    """Возвращает (text, reply_markup) для карточки одного сотрудника."""
    name = html.escape(m.user.full_name or "—") if m.user_id else "—"
    pos = html.escape(m.position_title or "")
    today_str = date.today().strftime("%d.%m.%Y")
    short_id = str(m.id).replace("-", "")[:8]

    text = (
        f"📋 <b>Daily check · {today_str}</b>\n"
        f"<i>Осталось: {remaining} из {total}</i>\n"
        f"\n"
        f"👤 <b>{name}</b>"
        + (f"\n   {pos}" if pos else "")
        + "\n\n"
        f"<i>Что отметить за сегодня?</i>"
    )
    buttons = [(label, f"hrc:m:{short_id}:{kind}") for label, kind in _CHECK_KIND_BTNS]
    buttons.append(("▶️ Пропустить", f"hrc:s:{short_id}"))
    buttons.append(("🏁 Завершить", "hrc:done"))
    return text, kb(buttons, cols=2)


@command(
    "/check",
    help="Daily check: пройтись по неотмеченным и нажимать кнопки",
    module="hr", category="hr",
)
def handle_check_cmd(ctx: HandlerCtx) -> None:
    """Запуск daily-check. Шлёт первую неотмеченную карточку."""
    if not _require_hr_rw(ctx):
        return

    from apps.organizations.models import OrganizationMembership
    from apps.payroll.models import WorkShift

    org = ctx.org()
    today = date.today()
    total = OrganizationMembership.objects.filter(
        organization=org, is_active=True,
    ).count()
    marked = WorkShift.objects.filter(
        organization=org, shift_date=today, shift_index=0,
    ).count()
    remaining = max(0, total - marked)

    if remaining == 0:
        send_message(
            ctx.chat_id,
            f"📋 <b>Daily check · {today.strftime('%d.%m.%Y')}</b>\n\n"
            f"Все {total} сотрудников уже отмечены за сегодня. ✅\n\n"
            f"<i>Чтобы переотметить — <code>/markday ФИО сегодня ...</code></i>",
        )
        return

    first = _next_unchecked(org)
    if first is None:
        send_message(ctx.chat_id, "Все уже отмечены на сегодня.")
        return

    text, markup = _build_check_card(first, total, remaining)
    send_message(ctx.chat_id, text, reply_markup=markup)


@on_callback("hrc:")
def handle_check_callback(ctx: HandlerCtx) -> None:
    """
    Callback'и daily-check:
        hrc:m:<short>:<kind>  — отметить и перейти к следующему
        hrc:s:<short>         — пропустить (не пишем WorkShift, идём дальше)
        hrc:done              — закрыть (показать сводку)
    """
    if not _require_hr_rw(ctx):
        if ctx.callback_id:
            answer_callback_query(ctx.callback_id, "Нет прав", show_alert=True)
        return

    if not ctx.args:
        return
    action = ctx.args[0]

    from apps.organizations.models import OrganizationMembership
    from apps.payroll.models import WorkShift

    org = ctx.org()
    today = date.today()

    if action == "done":
        if ctx.callback_id:
            answer_callback_query(ctx.callback_id, "Готово")
        total = OrganizationMembership.objects.filter(
            organization=org, is_active=True,
        ).count()
        marked = WorkShift.objects.filter(
            organization=org, shift_date=today, shift_index=0,
        ).count()
        edit_message_text(
            ctx.chat_id, ctx.message_id,
            f"📋 <b>Daily check · {today.strftime('%d.%m.%Y')}</b>\n\n"
            f"Отмечено: <b>{marked}</b> из <b>{total}</b>\n"
            f"Не отмечено: <b>{max(0, total - marked)}</b>",
        )
        return

    if action == "m" and len(ctx.args) >= 3:
        short_id, kind = ctx.args[1], ctx.args[2]
        m = _resolve_emp_short(org, short_id)
        if m is None:
            if ctx.callback_id:
                answer_callback_query(ctx.callback_id, "Сотрудник не найден", show_alert=True)
            return
        WorkShift.objects.update_or_create(
            employee=m, shift_date=today, shift_index=0,
            defaults={"organization": org, "kind": kind, "source": "manual"},
        )
        kind_label = dict(WorkShift.Kind.choices).get(kind, kind)
        if ctx.callback_id:
            answer_callback_query(ctx.callback_id, f"✓ {kind_label}")
        _advance_check(ctx, after_short=short_id, last_name=m.user.full_name or "—", last_kind=kind_label)
        return

    if action == "s" and len(ctx.args) >= 2:
        short_id = ctx.args[1]
        if ctx.callback_id:
            answer_callback_query(ctx.callback_id, "Пропущено")
        _advance_check(ctx, after_short=short_id, last_name=None, last_kind="пропущен")
        return


def _advance_check(ctx: HandlerCtx, after_short: str, last_name: str | None, last_kind: str) -> None:
    """После отметки/пропуска — показать следующую карточку или финал."""
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.models import WorkShift

    org = ctx.org()
    today = date.today()
    total = OrganizationMembership.objects.filter(
        organization=org, is_active=True,
    ).count()

    nxt = _next_unchecked(org, after_short=after_short)
    if nxt is None:
        marked = WorkShift.objects.filter(
            organization=org, shift_date=today, shift_index=0,
        ).count()
        edit_message_text(
            ctx.chat_id, ctx.message_id,
            f"📋 <b>Daily check завершён · {today.strftime('%d.%m.%Y')}</b>\n\n"
            f"Отмечено: <b>{marked}</b> из <b>{total}</b>",
        )
        return

    marked = WorkShift.objects.filter(
        organization=org, shift_date=today, shift_index=0,
    ).count()
    remaining = max(0, total - marked)
    text, markup = _build_check_card(nxt, total, remaining)
    if last_name:
        text = f"<i>✓ {html.escape(last_name)} — {last_kind}</i>\n\n" + text
    edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)


# ──────────────────────────────────────────────────────────────────────────
#   Quick-shortcuts: одной командой отметить сотрудника на сегодня
# ──────────────────────────────────────────────────────────────────────────


def _quick_mark(ctx: HandlerCtx, kind: str, label: str, icon: str) -> None:
    """Общая логика для /work, /absent, /sick, /vacay."""
    if not _require_hr_rw(ctx):
        return
    if not ctx.args:
        send_message(
            ctx.chat_id,
            f"Использование: <code>/{kind.replace('_', '')} ФИО</code>\n"
            f"Например: <code>/{kind.replace('_', '')} Иванов</code>",
        )
        return

    m = _find_employee(ctx, " ".join(ctx.args))
    if m is None:
        return

    from apps.payroll.models import WorkShift

    today = date.today()
    _, created = WorkShift.objects.update_or_create(
        employee=m, shift_date=today, shift_index=0,
        defaults={"organization": ctx.org(), "kind": kind, "source": "manual"},
    )
    action = "✨" if created else "♻️"
    name = html.escape(m.user.full_name or "—") if m.user_id else "—"
    send_message(
        ctx.chat_id,
        f"{action} {icon} <b>{name}</b> — {label} на {today.strftime('%d.%m.%Y')}",
    )


@command(
    "/work",
    help="Отметить сотрудника как «работал» сегодня: /work ФИО",
    module="hr", category="hr",
)
def handle_work_cmd(ctx: HandlerCtx) -> None:
    _quick_mark(ctx, "work", "работал", "✅")


@command(
    "/absent",
    help="Отметить прогул сегодня: /absent ФИО",
    module="hr", category="hr",
)
def handle_absent_cmd(ctx: HandlerCtx) -> None:
    _quick_mark(ctx, "absence", "прогул", "❌")


@command(
    "/sick",
    help="Отметить больничный сегодня: /sick ФИО",
    module="hr", category="hr",
)
def handle_sick_cmd(ctx: HandlerCtx) -> None:
    _quick_mark(ctx, "sick_leave", "больничный", "🏥")


@command(
    "/vacay",
    help="Отметить отпуск сегодня: /vacay ФИО",
    module="hr", category="hr",
)
def handle_vacay_cmd(ctx: HandlerCtx) -> None:
    _quick_mark(ctx, "vacation", "отпуск", "🏖")
