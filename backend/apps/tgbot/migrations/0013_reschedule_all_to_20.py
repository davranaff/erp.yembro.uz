"""
Переносим все вечерние авто-оповещения на 20:00 Asia/Tashkent.

Было:
    18:00 — owner_digest, cashflow_alert, head_morning_brief, stale_payment_reminder
    22:00 — daily_stock_excel, daily_debtors_excel

Стало:
    20:00 — все шесть
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

ALL_TASKS = [
    "tgbot-owner-digest-daily",
    "tgbot-cashflow-alert-daily",
    "tgbot-head-morning-brief",
    "tgbot-stale-payment-reminder",
    "tgbot-daily-stock-excel",
    "tgbot-daily-debtors-excel",
]


def apply_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule_20, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="20", **COMMON_CRON,
    )
    PeriodicTask.objects.filter(name__in=ALL_TASKS).update(crontab=schedule_20)


def revert_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule_18, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="18", **COMMON_CRON,
    )
    schedule_22, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="22", **COMMON_CRON,
    )

    tasks_18 = [
        "tgbot-owner-digest-daily",
        "tgbot-cashflow-alert-daily",
        "tgbot-head-morning-brief",
        "tgbot-stale-payment-reminder",
    ]
    tasks_22 = [
        "tgbot-daily-stock-excel",
        "tgbot-daily-debtors-excel",
    ]
    PeriodicTask.objects.filter(name__in=tasks_18).update(crontab=schedule_18)
    PeriodicTask.objects.filter(name__in=tasks_22).update(crontab=schedule_22)


class Migration(migrations.Migration):

    dependencies = [
        ("tgbot", "0012_tglink_notify_enabled"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_schedule, revert_schedule),
    ]
