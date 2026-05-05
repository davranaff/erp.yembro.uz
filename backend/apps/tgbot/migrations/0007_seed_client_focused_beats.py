"""
Beat-расписание для клиент-focused напоминаний:

- 09:30 ежедневно — promise_broken_daily_task: клиенту push если он не
  сдержал promised_pay_date (вчера обещал — сегодня тыкаем).
- 10:00 ежедневно — pre_block_warning_daily_task: клиенту push если он
  в «жёлтой зоне» (>=70% лимита) до фактической блокировки.

Время выбрано чтобы не пересекаться:
- 09:00 debt_reminder_daily       (T-3/T-1/T-0/T+N reminder)
- 09:15 daily_collection_alerts   (admin-сводка по сборщику)
- 09:30 promise_broken_daily      (новое — клиенту по обещанию)
- 10:00 pre_block_warning_daily   (новое — клиенту pre-blokirovka)
"""
import json

from django.db import migrations


SCHEDULES = [
    {
        "name": "tgbot-promise-broken-daily",
        "task": "apps.tgbot.promise_broken_daily_task",
        "minute": "30",
        "hour": "9",
        "description": (
            "Клиенту push если он не сдержал promised_pay_date "
            "(SaleCommunication.outcome=PROMISED, дата вчера, оплата не пришла)."
        ),
    },
    {
        "name": "tgbot-pre-block-warning-daily",
        "task": "apps.tgbot.pre_block_warning_daily_task",
        "minute": "0",
        "hour": "10",
        "description": (
            "Клиенту push если он в жёлтой зоне (>=70% credit limit) — "
            "ДО фактической блокировки. Психологически эффективнее чем "
            "пост-фактум."
        ),
    },
]

COMMON_CRON = {
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    for s in SCHEDULES:
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=s["minute"], hour=s["hour"], **COMMON_CRON,
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
        ("tgbot", "0006_seed_collection_alerts_beat"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
