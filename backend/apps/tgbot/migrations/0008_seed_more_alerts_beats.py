"""
Beat-расписание для расширенной системы оповещений:

- 07:00 ежедневно — head_morning_brief: каждый head своего модуля.
- 07:30 ежедневно — cashflow_alert: alert если касса в минусе.
- 07:45 ежедневно — stale_payment_reminder: sales-админу.
- 08:30 ежедневно — low_stock_feed: head feed-модуля.
- 07:00 каждый понедельник — weekly_monday_summary: admin/reports.

Распределили утренние пуши с 07:00 до 09:00 чтобы не валить юзеру
8 уведомлений в одну минуту. Owner-digest 08:00 уже стоит — это якорь.
"""
import json

from django.db import migrations


SCHEDULES = [
    {
        "name": "tgbot-head-morning-brief",
        "task": "apps.tgbot.head_morning_brief_task",
        "minute": "0", "hour": "7",
        "day_of_week": "*",
        "description": (
            "Каждое утро head'ам модулей: вчерашняя картина по их модулю "
            "(sotuv/xarid с разрезом оплачено/долг). Тихо если за вчера "
            "ничего не было."
        ),
    },
    {
        "name": "tgbot-cashflow-alert-daily",
        "task": "apps.tgbot.cashflow_alert_task",
        "minute": "30", "hour": "7",
        "day_of_week": "*",
        "description": (
            "Alert если хотя бы один cash-канал в минусе. Шлём admin/ledger. "
            "Тихо если все балансы >=0."
        ),
    },
    {
        "name": "tgbot-stale-payment-reminder",
        "task": "apps.tgbot.stale_payment_reminder_task",
        "minute": "45", "hour": "7",
        "day_of_week": "*",
        "description": (
            "Sales-админу: продажи с долгом без касания > 7 дней. "
            "Список + пинок «займись клиентом». Не клиенту, а внутри."
        ),
    },
    {
        "name": "tgbot-low-stock-feed",
        "task": "apps.tgbot.low_stock_feed_task",
        "minute": "30", "hour": "8",
        "day_of_week": "*",
        "description": (
            "Head feed-модуля: партии корма закончатся через <3 дней по "
            "среднему расходу за 14 дней. Дает время заказать сырьё."
        ),
    },
    {
        "name": "tgbot-weekly-monday-summary",
        "task": "apps.tgbot.weekly_monday_summary_task",
        "minute": "0", "hour": "7",
        "day_of_week": "1",  # понедельник
        "description": (
            "Понедельник 07:00: недельный обзор для admin/reports. "
            "Sales/purchases с paid/debt-разрезом за прошлую неделю."
        ),
    },
]

COMMON_CRON = {
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    for s in SCHEDULES:
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=s["minute"], hour=s["hour"],
            day_of_week=s["day_of_week"], **COMMON_CRON,
        )
        PeriodicTask.objects.update_or_create(
            name=s["name"],
            defaults={
                "crontab": schedule,
                "task": s["task"],
                "args": json.dumps([]),
                "kwargs": json.dumps({}),
                "enabled": True,
                "description": s["description"],
            },
        )


def unseed(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=[s["name"] for s in SCHEDULES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tgbot", "0007_seed_client_focused_beats"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
