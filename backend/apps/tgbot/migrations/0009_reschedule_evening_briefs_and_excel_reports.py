"""
Расписание admin-уведомлений переносится на 18:00 (после рабочего дня),
плюс добавляются два новых beat'а в 22:00 для Excel-рассылки:
    - daily_stock_excel_task   — отчёт по складам
    - daily_debtors_excel_task — список должников

Что меняется:
    18:00 head_morning_brief        (был 07:00, считает СЕГОДНЯШНИЕ движения)
    18:00 cashflow_alert_daily      (был 07:30)
    18:00 owner_digest_daily        (был 08:00)
    18:00 stale_payment_reminder    (был 07:45)

Что НЕ трогаем (clientside, должны бить утром):
    09:00 debt_reminder_daily       — клиентам напоминания по сроку
    09:15 daily_collection_alerts   — sales-админу по обзвону
    09:30 promise_broken_daily      — клиентам по обещаниям
    10:00 pre_block_warning_daily   — клиентам предблок
    08:30 low_stock_feed            — head feed по сырью

Идемпотентно: ищем CrontabSchedule по новому времени, переподвязываем
PeriodicTask. Старые осиротевшие CrontabSchedule оставляем — django_celery_beat
сам их подчистит.
"""
from __future__ import annotations

import json

from django.db import migrations


COMMON_CRON = {
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}


# Перенос существующих beat'ов на 18:00 (вечер).
RESCHEDULE = [
    {
        "name": "tgbot-head-morning-brief",
        "task": "apps.tgbot.head_morning_brief_task",
        "minute": "0", "hour": "18",
        "description": (
            "18:00 head'ам модулей: сегодняшняя картина по их модулю "
            "(sotuv/xarid с разрезом оплачено/долг). Тихо если за день "
            "ничего не было."
        ),
    },
    {
        "name": "tgbot-cashflow-alert-daily",
        "task": "apps.tgbot.cashflow_alert_task",
        "minute": "0", "hour": "18",
        "description": (
            "18:00 alert если хотя бы один cash-канал в минусе. Шлём "
            "admin/ledger. Тихо если все балансы >=0."
        ),
    },
    {
        "name": "tgbot-stale-payment-reminder",
        "task": "apps.tgbot.stale_payment_reminder_task",
        "minute": "0", "hour": "18",
        "description": (
            "18:00 sales-админу: продажи с долгом без касания > 7 дней. "
            "Список + пинок «займись клиентом». Не клиенту, а внутри."
        ),
    },
    {
        "name": "tgbot-owner-digest-daily",
        "task": "apps.tgbot.owner_digest_task",
        "minute": "0", "hour": "18",
        "description": (
            "18:00 владельцу/CFO: сводный digest по орге за день."
        ),
    },
]


# Новые beat'а на 22:00 для Excel-рассылки.
NEW_BEATS = [
    {
        "name": "tgbot-daily-stock-excel",
        "task": "apps.tgbot.daily_stock_excel_task",
        "minute": "0", "hour": "22",
        "description": (
            "22:00 admin/ledger: Excel с остатками по всем складам. "
            "Имя файла <YYYY-MM-DD>_otchet_o_sklade.xlsx."
        ),
    },
    {
        "name": "tgbot-daily-debtors-excel",
        "task": "apps.tgbot.daily_debtors_excel_task",
        "minute": "0", "hour": "22",
        "description": (
            "22:00 admin/ledger/sales: Excel со списком должников + aging. "
            "Имя файла <YYYY-MM-DD>_spisok_doljnikov.xlsx."
        ),
    },
]


def _ensure_schedule(CrontabSchedule, *, minute, hour):
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=minute, hour=hour, **COMMON_CRON,
    )
    return schedule


def _upsert_periodic(PeriodicTask, schedule, spec):
    PeriodicTask.objects.update_or_create(
        name=spec["name"],
        defaults={
            "crontab": schedule,
            "task": spec["task"],
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "enabled": True,
            "description": spec["description"],
        },
    )


def apply_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # Перенос на 18:00
    schedule_18 = _ensure_schedule(CrontabSchedule, minute="0", hour="18")
    for spec in RESCHEDULE:
        _upsert_periodic(PeriodicTask, schedule_18, spec)

    # Новые beat'а 22:00
    schedule_22 = _ensure_schedule(CrontabSchedule, minute="0", hour="22")
    for spec in NEW_BEATS:
        _upsert_periodic(PeriodicTask, schedule_22, spec)


def revert_schedule(apps, schema_editor):
    """Откат: новые beat'а удаляем, перенесённые возвращаем на старое время.

    Используется только в редких rollback'ах, не в проде. Если что-то идёт
    не так — лучше мигрировать вперёд новой миграцией.
    """
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # Снести новые
    for spec in NEW_BEATS:
        PeriodicTask.objects.filter(name=spec["name"]).delete()

    # Вернуть старые часы
    OLD_TIMES = {
        "tgbot-head-morning-brief": ("0", "7"),
        "tgbot-cashflow-alert-daily": ("30", "7"),
        "tgbot-stale-payment-reminder": ("45", "7"),
        "tgbot-owner-digest-daily": ("0", "8"),
    }
    for name, (m, h) in OLD_TIMES.items():
        sched = _ensure_schedule(CrontabSchedule, minute=m, hour=h)
        PeriodicTask.objects.filter(name=name).update(crontab=sched)


class Migration(migrations.Migration):

    dependencies = [
        ("tgbot", "0008_seed_more_alerts_beats"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_schedule, revert_schedule),
    ]
