"""
Удаляем авторассылку «📞 Mijozlar bilan ishlash kerak»
(tgbot-stale-payment-reminder).
"""
from __future__ import annotations

from django.db import migrations


def remove_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="tgbot-stale-payment-reminder").delete()


def restore_task(apps, schema_editor):
    pass  # не восстанавливаем — forward-only


class Migration(migrations.Migration):

    dependencies = [
        ("tgbot", "0013_reschedule_all_to_20"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_task, restore_task),
    ]
